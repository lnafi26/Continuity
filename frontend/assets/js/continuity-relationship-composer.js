/* Project Continuity — deliberate, authenticated project-record connection authoring.
 * Never infer causation or insert on render/open. Inserts happen only after a
 * user explicitly confirms a documented statement in the dialog. RLS remains
 * authoritative for ownership, endpoints, and server-generated proof metadata.
 */
(function (root, factory) {
  'use strict';
  const api = factory();
  if (typeof module === 'object' && module.exports) module.exports = api;
  if (root) {
    root.ContinuityRelationshipComposer = api;
    if (root.document) api.mount(root.document, root);
  }
})(typeof window === 'undefined' ? null : window, function () {
  'use strict';
  const TABLE = 'project_record_relationships';
  const KINDS = new Set(['dependency', 'handoff', 'divergence', 'convergence']);
  const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;

  function visibleRecords(project, canvas, observatory) {
    if (!project || typeof project !== 'object' || !canvas || !observatory ||
        typeof canvas.buildCanvasModel !== 'function' ||
        typeof observatory.normalizedRecords !== 'function') return [];
    const model = canvas.buildCanvasModel(project, observatory.normalizedRecords);
    if (!model || !Array.isArray(model.nodes)) return [];
    const seen = new Set();
    return model.nodes.flatMap(node => {
      const type = node?.kind === 'history' ? 'event' :
        node?.kind === 'schedule' ? 'action' : null;
      const id = Number(node?.record?.id);
      const key = type === 'event' ? 'history:' + String(id) :
        type === 'action' ? 'schedule:' + String(id) : null;
      if (!type || !Number.isSafeInteger(id) || id <= 0 ||
          node.key !== key || seen.has(key) ||
          typeof node.record?.title !== 'string') return [];
      seen.add(key);
      return [{ key, type, id, title: node.record.title }];
    });
  }

  function prepare(project, records, choice) {
    if (!project || typeof project.id !== 'string' || !UUID.test(project.id) ||
        typeof project.user_id !== 'string' || !UUID.test(project.user_id)) {
      return { error: 'Choose an authenticated, owned project.' };
    }
    if (!choice || choice.confirmed !== true) {
      return { error: 'Confirm the documented connection before saving.' };
    }
    if (!KINDS.has(choice.kind)) return { error: 'Choose a supported connection type.' };
    const statement = typeof choice.statement === 'string' ? choice.statement.trim() : '';
    if (!statement || statement.length > 2000) {
      return { error: 'Enter an explanation of 1–2000 characters.' };
    }
    const options = Array.isArray(records) ? records : [];
    const from = options.find(r => r.key === choice.fromKey);
    const to = options.find(r => r.key === choice.toKey);
    if (!from || !to || from.key === to.key ||
        !['event', 'action'].includes(from.type) || !['event', 'action'].includes(to.type) ||
        !Number.isSafeInteger(from.id) || from.id <= 0 ||
        !Number.isSafeInteger(to.id) || to.id <= 0) {
      return { error: 'Choose two distinct records visible in this project Canvas.' };
    }
    const saved = project.canvasRelationshipBundle?.relationships;
    if (Array.isArray(saved) && saved.some(r =>
      r.kind === choice.kind && r.from?.type === from.type &&
      String(r.from?.id) === String(from.id) && r.to?.type === to.type &&
      String(r.to?.id) === String(to.id))) {
      return { error: 'This connection already exists for the selected direction and type.' };
    }
    return { payload: {
      project_id: project.id,
      kind: choice.kind,
      statement,
      from_event_id: from.type === 'event' ? from.id : null,
      from_action_id: from.type === 'action' ? from.id : null,
      to_event_id: to.type === 'event' ? to.id : null,
      to_action_id: to.type === 'action' ? to.id : null
    } };
  }

  async function save(db, project, records, choice, stillCurrent = () => true) {
    const proposal = prepare(project, records, choice);
    if (proposal.error) return { ok: false, message: proposal.error };
    if (!db || !db.auth || typeof db.auth.getUser !== 'function' ||
        typeof db.from !== 'function') return { ok: false, message: 'Sign in to save a connection.' };
    let identity;
    try {
      const result = await db.auth.getUser();
      identity = !result.error && result.data?.user?.id;
    } catch (_) {
      return { ok: false, message: 'Could not verify the signed-in account.' };
    }
    if (!identity || identity !== project.user_id || !stillCurrent()) {
      return { ok: false, message: 'The signed-in account or selected project changed.' };
    }
    try {
      // Explicitly omit all server-owned fields: user_id, state, confirmed_by,
      // confirmed_at, created_at, id. SQL GRANT and RLS enforce this too.
      const response = await db.from(TABLE).insert(proposal.payload)
        .select('id,user_id,project_id,kind,state,confirmed_by,confirmed_at').single();
      if (response.error) {
        const code = response.error.code;
        const message = code === 'PGRST205' || code === '42P01'
          ? 'Relationship storage has not been enabled in this environment.'
          : code === '23505'
            ? 'That connection is already saved.'
            : 'Unable to save the connection. Your account or record permissions may have changed.';
        return { ok: false, message };
      }
      const row = response.data;
      if (!row || row.user_id !== identity || row.project_id !== project.id ||
          row.kind !== proposal.payload.kind || row.state !== 'documented' ||
          row.confirmed_by !== identity || !Number.isFinite(Date.parse(row.confirmed_at))) {
        return { ok: false, message: 'Server confirmation could not be verified. Reload your project before retrying.' };
      }
      return { ok: true, id: row.id, current: stillCurrent() };
    } catch (_) {
      return { ok: false, message: 'The connection could not be saved. Check your connection and try again.' };
    }
  }

  function mount(doc, hostWindow) {
    const live = hostWindow.ContinuityLiveObservatory;
    const canvas = hostWindow.ContinuityLiveCanvas;
    const button = doc.getElementById('loCreateRelationship');
    const selector = doc.getElementById('observatoryProjectSelect');
    const dialog = doc.getElementById('loRelationshipDialog');
    const form = doc.getElementById('loRelationshipForm');
    const from = doc.getElementById('loRelationshipFrom');
    const to = doc.getElementById('loRelationshipTo');
    const kind = doc.getElementById('loRelationshipKind');
    const statement = doc.getElementById('loRelationshipStatement');
    const confirmed = doc.getElementById('loRelationshipConfirmed');
    const submit = doc.getElementById('loRelationshipSubmit');
    const cancel = doc.getElementById('loRelationshipCancel');
    const status = doc.getElementById('loRelationshipStatus');
    if (!live || typeof live.render !== 'function' || !canvas || !button ||
        !selector || !dialog || !form || !from || !to || !kind ||
        !statement || !confirmed || !submit || !cancel || !status) return;

    let projectMap = {};
    let revision = 0;
    let pending = false;
    const selected = () => projectMap[selector.value] || null;
    const recordsFor = project => visibleRecords(project, canvas, live);
    const updateAvailability = () => {
      const project = selected();
      const records = recordsFor(project);
      button.disabled = !project?.user_id || records.length < 2 || pending;
      button.title = records.length < 2 ? 'At least two dated records must be visible in this project Canvas.' : '';
    };
    const originalRender = live.render;
    live.render = (projects = {}) => {
      originalRender(projects);
      projectMap = projects && typeof projects === 'object' && !Array.isArray(projects)
        ? projects : {};
      revision++;
      if (dialog.open) dialog.close();
      updateAvailability();
    };
    live.clear = () => live.render({});

    selector.addEventListener('change', () => {
      revision++;
      if (dialog.open) dialog.close();
      updateAvailability();
    });

    function option(el, record) {
      const node = doc.createElement('option');
      node.value = record.key;
      node.textContent = (record.type === 'event' ? 'Event · ' : 'Task · ') + record.title;
      el.append(node);
    }
    button.addEventListener('click', () => {
      const project = selected();
      const records = recordsFor(project);
      if (!project?.user_id || records.length < 2 || pending) return;
      form.reset();
      status.textContent = '';
      from.replaceChildren();
      to.replaceChildren();
      for (const record of records) {
        option(from, record);
        option(to, record);
      }
      from.selectedIndex = 0;
      to.selectedIndex = records.length > 1 ? 1 : 0;
      submit.disabled = false;
      dialog.showModal();
      from.focus();
    });

    cancel.addEventListener('click', () => { if (!pending) dialog.close(); });
    dialog.addEventListener('cancel', event => { if (pending) event.preventDefault(); });
    form.addEventListener('submit', async event => {
      event.preventDefault();
      if (pending || !dialog.open) return;
      const project = selected();
      const records = recordsFor(project);
      const submittedRevision = revision;
      const submittedProject = project?.id;
      pending = true;
      submit.disabled = true;
      cancel.disabled = true;
      status.textContent = 'Saving confirmed connection…';
      const result = await save(hostWindow.supabaseDb, project, records, {
        fromKey: from.value, toKey: to.value, kind: kind.value,
        statement: statement.value, confirmed: confirmed.checked
      }, () => revision === submittedRevision && selected()?.id === submittedProject);
      pending = false;
      submit.disabled = false;
      cancel.disabled = false;
      if (!result.ok) {
        status.textContent = result.message;
        updateAvailability();
        return;
      }
      dialog.close();
      status.textContent = '';
      // An account switch may have occurred during the write: do not refresh
      // or show any prior-user information in that case.
      if (!result.current) { updateAvailability(); return; }
      try {
        if (typeof hostWindow.refreshProjectData !== 'function') {
          throw new Error('Refresh unavailable');
        }
        await hostWindow.refreshProjectData();
        hostWindow.showToast?.('Connection documented', 'Saved to your project.');
      } catch (_) {
        hostWindow.showToast?.('Connection saved', 'Reload the project to see the new connection.');
      }
      updateAvailability();
    });
    updateAvailability();
  }
  return { visibleRecords, prepare, save, mount };
});
