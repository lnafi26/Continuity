/* Project Continuity — Authenticated Night Observatory live timeline (first slice).
 * Displays user-scoped records already loaded by auth.js from Supabase.
 * No network requests, data mutations, sample fixtures, or localStorage.
 * The public synthetic Night Observatory preview is not modified.
 */
(function (root, factory) {
  'use strict';
  const api = factory();
  if (typeof module === 'object' && module.exports) module.exports = api;
  if (root && root.document) {
    root.ContinuityLiveObservatory = api;
    api.mount(root.document, root);
  }
})(typeof window === 'undefined' ? null : window, function () {
  'use strict';
  const TIMELINE_BATCH = 80;

  const validDate = (date) => typeof date === 'string' && /^\d{4}-\d{2}-\d{2}$/.test(date) &&
    !Number.isNaN(Date.parse(date + 'T00:00:00Z')) &&
    new Date(Date.parse(date + 'T00:00:00Z')).toISOString().slice(0, 10) === date;

  function normalizedRecords(project) {
    const history = [];
    const scheduled = [];
    const unscheduled = [];
    for (const event of project?.events || []) {
      const stamp = typeof event.dateMs === 'number' && Number.isFinite(event.dateMs)
        && Number.isFinite(new Date(event.dateMs).getTime()) ? event.dateMs : null;
      const rec = {
        id: String(event.id), kind: 'event', type: event.type || 'Update',
        title: event.title || '(Untitled update)', detail: event.body || '',
        person: event.person || '', timestamp: stamp,
        date: stamp === null ? '' : new Date(stamp).toISOString().slice(0, 10),
        state: ''
      };
      if (stamp === null) unscheduled.push(rec);
      else history.push(rec);
    }
    for (const task of project?.actions || []) {
      const due = validDate(task.dueDate) ? task.dueDate : '';
      const rec = {
        id: String(task.id), kind: 'task', type: 'Task deadline',
        title: task.title || '(Untitled task)', detail: '', person: '',
        timestamp: due ? Date.parse(due + 'T00:00:00Z') : null,
        date: due, state: task.done ? 'Completed' : task.backlog ? 'Backlog' : 'Open'
      };
      if (due) scheduled.push(rec);
      else unscheduled.push(rec);
    }
    history.sort((a, b) => a.timestamp - b.timestamp || a.id.localeCompare(b.id));
    scheduled.sort((a, b) => a.timestamp - b.timestamp || a.id.localeCompare(b.id));
    return { history, scheduled, unscheduled };
  }

  function mount(doc, hostWindow) {
    const shell = doc.getElementById('liveObservatory');
    const selector = doc.getElementById('observatoryProjectSelect');
    const canvas = doc.getElementById('observatoryCanvas');
    const inspector = doc.getElementById('observatoryInspector');
    const heading = doc.getElementById('observatoryProjectTitle');
    const summary = doc.getElementById('observatoryProjectSummary');
    const openButton = doc.getElementById('observatoryOpenProject');
    if (!shell || !selector || !canvas || !inspector || !heading || !summary || !openButton) return;

    let projects = {};
    let selectedId = null;
    let searchTerm = '';

    const el = (tag, cls, text) => {
      const node = doc.createElement(tag);
      if (cls) node.className = cls;
      if (text !== undefined) node.textContent = String(text);
      return node;
    };

    function showInspector(record) {
      inspector.replaceChildren();
      const top = el('div', 'lo-inspector-top', record.kind === 'task' ? 'SCHEDULED WORK' : 'RECORDED EVENT');
      const title = el('h3', '', record.title);
      const meta = el('p', 'lo-inspector-meta', [record.type, record.date || 'Date not recorded', record.state].filter(Boolean).join(' · '));
      inspector.append(top, title, meta);
      if (record.detail) inspector.append(el('p', 'lo-inspector-detail', record.detail));
      if (record.person) inspector.append(el('p', 'lo-inspector-meta', 'Recorded by: ' + record.person));
      if (record.kind === 'task') inspector.append(el('p', 'lo-inspector-foot', 'A task due date is a planned deadline, not evidence that work happened on that date.'));
    }

    function makeLane(title, subtitle, records, laneKind) {
      const lane = el('section', 'lo-lane');
      const headingNode = el('header', 'lo-lane-head');
      headingNode.append(el('h3', '', title), el('small', '', subtitle));
      lane.append(headingNode);
      if (!records.length) {
        lane.append(el('p', 'lo-lane-empty', searchTerm ? 'No matching records in this lane.' : laneKind === 'history' ? 'No dated project history recorded yet.' : laneKind === 'schedule' ? 'No tasks with due dates yet.' : 'No undated records.'));
        return lane;
      }
      const rail = el('div', 'lo-rail lo-rail-' + laneKind);
      rail.setAttribute('role', 'group');
      rail.setAttribute('aria-label', title);
      function recordButton(record) {
        const button = el('button', 'lo-node');
        button.type = 'button';
        button.append(el('span', 'lo-node-marker ' + (record.kind === 'task' ? 'lo-task-marker' : 'lo-event-marker')));
        button.append(el('span', 'lo-node-date', record.date || 'NO DATE'));
        button.append(el('strong', 'lo-node-title', record.title));
        button.append(el('span', 'lo-node-type', record.kind === 'task' ? record.state + ' · Task' : record.type));
        button.addEventListener('click', () => {
          shell.querySelectorAll('.lo-node[aria-pressed="true"]').forEach((item) => item.setAttribute('aria-pressed', 'false'));
          button.setAttribute('aria-pressed', 'true');
          showInspector(record);
        });
        return button;
      }
      // Retain all authorized records; create DOM rows incrementally.
      // Never infer dates or relationships while navigating older entries.
      let firstVisible = Math.max(0, records.length - TIMELINE_BATCH);
      const earlier = el('button', 'lc-navigator-item lo-load-earlier');
      earlier.type = 'button';
      function updateEarlierLabel() {
        const count = Math.min(TIMELINE_BATCH, firstVisible);
        const label = laneKind === 'undated' ? 'more undated' : `earlier ${laneKind}`;
        earlier.textContent = `Show ${count} ${label} record(s) · ${firstVisible} remaining`;
        earlier.hidden = firstVisible === 0;
      }
      earlier.addEventListener('click', () => {
        if (firstVisible === 0) return;
        const next = Math.max(0, firstVisible - TIMELINE_BATCH);
        const batch = records.slice(next, firstVisible).map(recordButton);
        rail.prepend(...batch);
        firstVisible = next;
        updateEarlierLabel();
      });
      for (const record of records.slice(firstVisible)) rail.append(recordButton(record));
      if (firstVisible) {
        updateEarlierLabel();
        lane.append(earlier);
      }
      lane.append(rail);
      return lane;
    }

    function paint() {
      canvas.replaceChildren();
      inspector.replaceChildren();
      const project = selectedId && projects[selectedId];
      if (!project) {
        heading.textContent = 'Your project history, visually';
        summary.textContent = 'Create a project in Projects to begin a real timeline.';
        openButton.disabled = true;
        doc.getElementById('observatoryRecordCount').textContent = '0 records';
        canvas.append(el('p', 'lo-empty', 'No projects available in your signed-in workspace.'));
        inspector.append(el('p', 'lo-inspector-empty', 'Choose a project to inspect its records.'));
        return;
      }
      heading.textContent = project.name || 'Untitled project';
      summary.textContent = project.summary || 'Project records loaded from your Supabase account.';
      openButton.disabled = false;
      const { history, scheduled, unscheduled } = normalizedRecords(project);
      const total = history.length + scheduled.length + unscheduled.length;
      const toolbar = el('div', 'lo-timeline-search');
      const searchLabel = el('label', '', 'Find a record');
      searchLabel.setAttribute('for', 'loTimelineSearch');
      const search = el('input', 'lo-timeline-search-input');
      search.id = 'loTimelineSearch';
      search.type = 'search';
      search.placeholder = 'Search this project’s events and tasks';
      search.value = searchTerm;
      const searchStatus = el('p', 'lo-timeline-search-status');
      searchStatus.setAttribute('aria-live', 'polite');
      toolbar.append(searchLabel, search, searchStatus);
      const lanes = el('div', 'lo-timeline-lanes');

      function paintMatches() {
        const matches = records => searchTerm ? records.filter(record =>
          [record.title, record.detail, record.type, record.state, record.date]
            .some(value => String(value || '').toLowerCase().includes(searchTerm))
        ) : records;
        const visibleHistory = matches(history);
        const visibleScheduled = matches(scheduled);
        const visibleUndated = matches(unscheduled);
        lanes.replaceChildren(
          makeLane('Recorded history', 'Chronological, user-owned project events', visibleHistory, 'history'),
          makeLane('Scheduled work', 'Task deadlines — not historical events', visibleScheduled, 'schedule')
        );
        if (unscheduled.length) lanes.append(
          makeLane('Without a date', 'Events and tasks with no usable date', visibleUndated, 'undated')
        );
        const count = visibleHistory.length + visibleScheduled.length + visibleUndated.length;
        searchStatus.textContent = searchTerm ? `${count} matching record(s) of ${total}` : '';
      }

      search.addEventListener('input', () => {
        searchTerm = String(search.value || '').trim().toLowerCase();
        inspector.replaceChildren(
          el('p', 'lo-inspector-empty', 'Select any timeline node to inspect its details.')
        );
        paintMatches();
      });
      canvas.append(toolbar, lanes);
      paintMatches();
      inspector.append(el('p', 'lo-inspector-empty', 'Select any timeline node to inspect its details.'));
      doc.getElementById('observatoryRecordCount').textContent = total + (total === 1 ? ' record' : ' records');
    }

    function render(nextProjects = {}) {
      searchTerm = '';
      projects = nextProjects && typeof nextProjects === 'object' ? nextProjects : {};
      const entries = Object.values(projects).filter((p) => p && typeof p.id === 'string')
        .sort((a, b) => (a.name || '').localeCompare(b.name || ''));
      if (!entries.some((p) => p.id === selectedId)) selectedId = entries[0]?.id || null;
      selector.replaceChildren();
      if (!entries.length) {
        const opt = el('option', '', 'No projects');
        opt.value = '';
        selector.append(opt);
      }
      for (const project of entries) {
        const opt = el('option', '', project.name || 'Untitled project');
        opt.value = project.id;
        selector.append(opt);
      }
      selector.value = selectedId || '';
      paint();
    }

    selector.addEventListener('change', () => {
      selectedId = selector.value;
      searchTerm = '';
      paint();
    });
    openButton.addEventListener('click', () => {
      if (selectedId && typeof hostWindow.openProjectById === 'function') hostWindow.openProjectById(selectedId);
    });

    // The dashboard's auth-scoped loader calls this after each successful reload.
    // Account switch and sign-out call setTimelineData({}), clearing all records.
    const api = hostWindow.ContinuityLiveObservatory;
    api.render = render;
    api.inspectRecord = showInspector;
    api.clear = () => render({});
    render({});
  }

  return { normalizedRecords, validDate, mount };
});

/* Continuity: opt-in, local-only Project Memory panel.
 * Uses the authenticated backend; never stores tokens or writes records.
 */
;(function (root) {
  'use strict';

  const BACKEND = 'http://127.0.0.1:8765';
  const PREVIEW = 'http://127.0.0.1:8000';
  const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

  function enabled(host) {
    return Boolean(
      host &&
      host.CONTINUITY_MEMORY_API_BASE === BACKEND &&
      host.location?.origin === PREVIEW
    );
  }

  function text(value) {
    return typeof value === 'string'
      ? value.trim().slice(0, 300)
      : '';
  }

  function rows(context, keys) {
    for (const key of keys) {
      if (Array.isArray(context[key])) return context[key];
    }
    return [];
  }

  function describe(record) {
    if (!record || typeof record !== 'object') return '';
    return text(
      record.title ||
      record.name ||
      record.statement ||
      record.summary
    );
  }

  function memoryRecord(record, kind) {
    if (!record || typeof record !== 'object' ||
        Array.isArray(record)) return null;

    const title = describe(record);
    if (!title) return null;

    return {
      kind,
      title,
      id: text(record.id),
      type: kind === 'event' ? text(record.type) : 'Task',
      occurredAt: kind === 'event' ? text(record.occurred_at) : '',
      dueDate: kind === 'action' ? text(record.due_date) : '',
      status: kind === 'action' ? text(record.status) : '',
      sourceItemId: kind === 'event'
        ? text(record.source_item_id) : '',
      sourceLinkStatus: kind === 'event'
        ? text(record.source_link_status) : '',
      evidenceVerification: kind === 'event'
        ? text(record.evidence_verification) : '',
      userEdited: kind === 'event' &&
        typeof record.user_edited === 'boolean'
        ? record.user_edited : null
    };
  }

  function viewModel(context) {
    if (!context || typeof context !== 'object' ||
        Array.isArray(context) ||
        context.schema_version !== 1 ||
        context.kind !== 'derived_read_only' ||
        context.persisted !== false) {
      throw new TypeError('Unsupported project memory snapshot.');
    }

    const project = context.project &&
      typeof context.project === 'object'
      ? context.project : {};

    const historyRecords = rows(context, [
      'recent_events'
    ]).slice(0, 6)
      .map(record => memoryRecord(record, 'event'))
      .filter(Boolean);

    const actionRecords = rows(context, [
      'open_actions'
    ]).slice(0, 6)
      .map(record => memoryRecord(record, 'action'))
      .filter(Boolean);

    return {
      name: text(project.name),
      summary: text(project.summary),
      asOf: text(context.as_of),
      history: historyRecords.map(record => record.title),
      actions: actionRecords.map(record => record.title),
      historyRecords,
      actionRecords
    };
  }

  function mount(host, doc) {
    if (!enabled(host)) return;

    const picker = doc.getElementById('observatoryProjectSelect');
    const summary = doc.getElementById('observatoryProjectSummary');

    if (!picker || !summary) return;

    const section = doc.createElement('section');
    section.className = 'lo-memory-panel';
    section.hidden = true;
    section.setAttribute('aria-label', 'Project Memory');

    const header = doc.createElement('div');
    header.className = 'lo-memory-header';

    const title = doc.createElement('h4');
    title.textContent = 'Project Memory';

    const reload = doc.createElement('button');
    reload.type = 'button';
    reload.textContent = 'Refresh';
    reload.className = 'lo-memory-refresh';

    header.append(title, reload);

    const status = doc.createElement('p');
    status.className = 'lo-memory-status';
    status.setAttribute('role', 'status');

    const body = doc.createElement('div');
    body.className = 'lo-memory-content';

    section.append(header, status, body);
    summary.insertAdjacentElement('afterend', section);

    let generation = 0;
    const details = doc.createElement('section');
    details.id = 'loMemoryRecordDetail';
    details.className = 'lo-memory-evidence';
    details.setAttribute('role', 'region');
    details.setAttribute('aria-label', 'Selected memory record details');
    details.hidden = true;

    function clear() {
      body.replaceChildren();
      details.replaceChildren();
      details.hidden = true;
    }

    function showEvidence(entry, button) {
      body.querySelectorAll('.lo-memory-record').forEach(item => {
        item.setAttribute(
          'aria-pressed',
          item === button ? 'true' : 'false'
        );
      });

      details.replaceChildren();

      const heading = doc.createElement('h5');
      heading.textContent = entry.title;

      const metadata = doc.createElement('dl');

      function field(label, value) {
        const row = doc.createElement('div');
        const name = doc.createElement('dt');
        const content = doc.createElement('dd');

        name.textContent = label;
        content.textContent = value;
        row.append(name, content);
        metadata.appendChild(row);
      }

      field('Record ID', entry.id || 'Not supplied');
      field('Record type', entry.type || 'Not supplied');

      if (entry.kind === 'event') {
        field('Recorded date',
          entry.occurredAt || 'Not supplied');

        field('Source item reference',
          entry.sourceItemId || 'No source ID recorded');

        let linkStatus = entry.sourceLinkStatus || 'Not supplied';

        if (linkStatus === 'no_source') {
          linkStatus = 'No source recorded for this event';
        } else if (linkStatus === 'link_not_in_snapshot') {
          linkStatus = 'Link not included in this bounded snapshot';
        }

        field('Source-link status', linkStatus);

        field('Evidence verification',
          entry.evidenceVerification === 'not_verified'
            ? 'Not verified'
            : 'No verification result available');

        if (entry.userEdited !== null) {
          field('User edit flag',
            entry.userEdited
              ? 'User edit recorded'
              : 'No user edit flagged');
        }
      } else {
        field('Task status',
          entry.status || 'Not supplied');
        field('Due date',
          entry.dueDate || 'No due date recorded');
      }

      const notice = doc.createElement('p');
      notice.className = 'lo-memory-evidence-note';
      notice.textContent = entry.kind === 'event'
        ? 'A source reference or link status does not verify a claim. No source document is available in this snapshot.'
        : 'This task snapshot does not include source-document evidence.';

      details.append(heading, metadata, notice);
      details.hidden = false;
      body.appendChild(details);
    }

    function addGroup(label, entries) {
      if (!entries.length) return;

      const group = doc.createElement('div');
      group.className = 'lo-memory-group';

      const heading = doc.createElement('h5');
      heading.textContent = label;

      const list = doc.createElement('ul');

      for (const entry of entries) {
        const item = doc.createElement('li');
        const button = doc.createElement('button');

        button.type = 'button';
        button.className = 'lo-memory-record';
        button.textContent = entry.title;
        button.setAttribute('aria-pressed', 'false');
        button.setAttribute('aria-controls', details.id);

        button.addEventListener('click', () => {
          showEvidence(entry, button);
        });

        item.appendChild(button);
        list.appendChild(item);
      }

      group.append(heading, list);
      body.appendChild(group);
    }

    async function refresh() {
      const current = ++generation;
      clear();

      const id = picker.value;
      if (!UUID.test(id)) {
        section.hidden = true;
        return;
      }

      section.hidden = false;
      status.textContent = 'Loading project memory…';

      try {
        const db = host.supabaseDb;
        if (!db?.auth?.getSession) {
          throw new Error('Session unavailable');
        }

        const { data, error } = await db.auth.getSession();
        if (current !== generation) return;

        const token = data?.session?.access_token;
        if (error || typeof token !== 'string' || !token) {
          throw new Error('Authentication required');
        }

        const response = await host.fetch(
          BACKEND + '/memory/projects/' +
            encodeURIComponent(id) + '/context',
          {
            method: 'GET',
            headers: {
              Authorization: 'Bearer ' + token,
              Accept: 'application/json'
            },
            cache: 'no-store'
          }
        );

        if (current !== generation) return;
        if (!response.ok) throw new Error('Memory unavailable');

        const result = await response.json();
        if (current !== generation) return;
        if (result?.ok !== true) {
          throw new Error('Invalid memory response');
        }

        const memory = viewModel(result.context);
        status.textContent = 'Derived read-only snapshot · not durable';

        addGroup('Recorded history', memory.historyRecords);
        addGroup('Outstanding actions', memory.actionRecords);

        if (!memory.historyRecords.length &&
            !memory.actionRecords.length) {
          status.textContent =
            'No displayable records in this bounded snapshot.';
        }

        const notice = doc.createElement('p');
        notice.className = 'lo-memory-snapshot-note';
        notice.textContent =
          'Showing up to six records per group. Missing source links do not prove that no association exists.';
        body.appendChild(notice);
      } catch (_) {
        if (current !== generation) return;
        clear();
        status.textContent =
          'Project memory unavailable. Check the local backend and try again.';
      }
    }

    reload.addEventListener('click', refresh);
    picker.addEventListener('change', refresh);

    if (typeof host.MutationObserver === 'function') {
      const observer = new host.MutationObserver(refresh);
      observer.observe(picker, { childList: true });
    }

    host.supabaseDb?.auth?.onAuthStateChange?.((_event, session) => {
      const version = ++generation;
      clear();

      if (session) {
        // Avoid calling Supabase APIs inside its auth-state callback.
        host.setTimeout(() => {
          if (version === generation) refresh();
        }, 0);
      } else {
        section.hidden = true;
      }
    });

    refresh();
  }

  if (typeof module === 'object' && module.exports) {
    module.exports.localMemoryPanel = { enabled, viewModel };
  }

  if (typeof document !== 'undefined' &&
      root?.addEventListener && enabled(root)) {
    if (document.readyState === 'loading') {
      document.addEventListener(
        'DOMContentLoaded', () => mount(root, document),
        { once: true }
      );
    } else {
      mount(root, document);
    }
  }
})(typeof window !== 'undefined' ? window : globalThis);

/* B4.6b: isolated local-only human-review interaction preview.
 * This is NOT a memory revision, user confirmation, or saved project record.
 * It never reads project data, makes requests, or stores a decision.
 */
(function (host) {
  'use strict';
  if (!host || !host.document ||
      host.location?.origin !== 'http://127.0.0.1:8000' ||
      host.CONTINUITY_MEMORY_API_BASE !== 'http://127.0.0.1:8765') return;

  const doc = host.document;

  function node(tag, className, label) {
    const item = doc.createElement(tag);
    if (className) item.className = className;
    if (label !== undefined) item.textContent = label;
    return item;
  }

  function mount() {
    const shell = doc.getElementById('liveObservatory');
    if (!shell || doc.getElementById('continuityRevisionReviewPreview')) return false;

    const panel = node('details', 'crrp-workbench');
    panel.id = 'continuityRevisionReviewPreview';

    const summary = node('summary', 'crrp-summary',
      'Try the memory review controls · Local prototype');
    const content = node('div', 'crrp-content');
    const notice = node('p', 'crrp-notice',
      'FICTIONAL EXAMPLE · No project data loaded. No review decision is saved or sent to a server.');
    const intro = node('p', '',
      'Compare a previously recorded value with a proposed change, then preview the decision you would make.');
    const comparison = node('div', 'crrp-comparison');

    function comparisonCard(label, value) {
      const card = node('section', 'crrp-card');
      card.append(node('h4', '', label), node('p', '', value));
      return card;
    }

    comparison.append(
      comparisonCard('Previous · fictional',
        'Project Cedar kickoff is scheduled for June 12.'),
      comparisonCard('Proposed · fictional',
        'Change the scheduled kickoff to June 20.')
    );

    const evidence = node('p', 'crrp-evidence',
      'Evidence example: fictional meeting note · source not verified');
    const controls = node('div', 'crrp-controls');
    const status = node('p', 'crrp-status',
      'Awaiting your preview choice. No project memory has been changed.');

    status.setAttribute('role', 'status');
    status.setAttribute('aria-live', 'polite');

    const actions = [
      ['confirm', 'Preview confirm'],
      ['dispute', 'Preview dispute'],
      ['reject', 'Preview reject']
    ];

    for (const [action, label] of actions) {
      const button = node('button', 'crrp-action', label);
      button.type = 'button';
      button.addEventListener('click', () => {
        status.textContent = 'Preview choice: ' + action +
          '. No confirmation was recorded, and no revision was saved or sent.';
      });
      controls.append(button);
    }

    const reset = node('button', 'crrp-reset', 'Reset preview');
    reset.type = 'button';
    reset.addEventListener('click', () => {
      status.textContent =
        'Awaiting your preview choice. No project memory has been changed.';
    });
    controls.append(reset);

    content.append(notice, intro, comparison, evidence, controls, status);
    panel.append(summary, content);
    shell.append(panel);
    return true;
  }

  if (doc.readyState === 'loading') {
    doc.addEventListener('DOMContentLoaded', mount, { once: true });
  } else {
    mount();
  }
})(typeof window === 'undefined' ? null : window);
