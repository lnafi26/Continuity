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
        lane.append(el('p', 'lo-lane-empty', laneKind === 'history' ? 'No dated project history recorded yet.' : laneKind === 'schedule' ? 'No tasks with due dates yet.' : 'No undated records.'));
        return lane;
      }
      const rail = el('div', 'lo-rail lo-rail-' + laneKind);
      rail.setAttribute('role', 'group');
      rail.setAttribute('aria-label', title);
      for (const record of records) {
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
        rail.append(button);
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
      canvas.append(
        makeLane('Recorded history', 'Chronological, user-owned project events', history, 'history'),
        makeLane('Scheduled work', 'Task deadlines — not historical events', scheduled, 'schedule')
      );
      if (unscheduled.length) canvas.append(makeLane('Without a date', 'Events and tasks with no usable date', unscheduled, 'undated'));
      inspector.append(el('p', 'lo-inspector-empty', 'Select any timeline node to inspect its details.'));
      const total = history.length + scheduled.length + unscheduled.length;
      doc.getElementById('observatoryRecordCount').textContent = total + (total === 1 ? ' record' : ' records');
    }

    function render(nextProjects = {}) {
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
      paint();
    });
    openButton.addEventListener('click', () => {
      if (selectedId && typeof hostWindow.openProjectById === 'function') hostWindow.openProjectById(selectedId);
    });

    // The dashboard's auth-scoped loader calls this after each successful reload.
    // Account switch and sign-out call setTimelineData({}), clearing all records.
    const api = hostWindow.ContinuityLiveObservatory;
    api.render = render;
    api.clear = () => render({});
    render({});
  }

  return { normalizedRecords, validDate, mount };
});
