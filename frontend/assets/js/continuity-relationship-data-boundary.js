/* Continuity — read-only adapter for future authenticated relationship rows.
 * This is a presentation boundary, NOT an authentication or authorization system.
 * Feed only rows fetched under an authenticated server/RLS-controlled context.
 * No network calls, storage, inference, changes to input, or automatic confirmations.
 * Until a real persisted relationship table and server security exist, do not
 * wire this into the live dashboard or supply unverified relationship rows.
 */
(function (root, factory) {
  'use strict';
  const api = factory();
  if (typeof module === 'object' && module.exports) module.exports = api;
  if (root) root.ContinuityRelationshipDataBoundary = api;
})(typeof window === 'undefined' ? null : window, function () {
  'use strict';
  const KINDS = new Set(['dependency', 'handoff', 'divergence', 'convergence']);
  const VALID_ID = /^[1-9][0-9]*$/;
  const ISO_TIME = /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})$/;
  function eventActionId(value) {
    if (typeof value === 'number') return Number.isSafeInteger(value) && value > 0 ? value : null;
    return typeof value === 'string' && VALID_ID.test(value) ? value : null;
  }
  function endpoint(row, side) {
    const event = eventActionId(row[side + '_event_id']);
    const action = eventActionId(row[side + '_action_id']);
    if ((event === null) === (action === null)) return null;
    return event !== null ? { type: 'event', id: event } : { type: 'action', id: action };
  }
  function normalizeRow(row, userId, projectId) {
    if (!row || typeof row !== 'object' || Array.isArray(row) ||
        typeof row.id !== 'string' || !row.id.trim() ||
        row.user_id !== userId || row.project_id !== projectId ||
        !KINDS.has(row.kind) || row.state !== 'documented' ||
        typeof row.statement !== 'string' || !row.statement.trim() ||
        row.confirmed_by !== userId ||
        typeof row.confirmed_at !== 'string' ||
        !ISO_TIME.test(row.confirmed_at) ||
        !Number.isFinite(Date.parse(row.confirmed_at))) return null;
    const from = endpoint(row, 'from');
    const to = endpoint(row, 'to');
    if (!from || !to || (from.type === to.type && String(from.id) === String(to.id))) return null;
    return {
      id: row.id, userId, projectId, kind: row.kind,
      state: 'documented', from, to, statement: row.statement.trim(),
      proof: { mode: 'user-confirmed', confirmedBy: userId, confirmedAt: row.confirmed_at }
    };
  }
  // Never infer that a missing user_id belongs to the current signed-in user.
  // Any stale bundle supplied by callers is stripped from the newly returned map.
  function attach(projectMap, rows, userId) {
    const map = projectMap && typeof projectMap === 'object' && !Array.isArray(projectMap)
      ? projectMap : {};
    const output = Object.create(null);
    const grouped = new Map();
    const authenticated = typeof userId === 'string' && userId.trim().length > 0;
    const seen = new Set();
    if (authenticated && Array.isArray(rows)) {
      for (const row of rows) {
        if (!row || typeof row !== 'object' ||
            typeof row.id !== 'string' || !row.id.trim() || seen.has(row.id)) continue;
        seen.add(row.id);
        const projectId = row.project_id;
        if (typeof projectId !== 'string' || !Object.hasOwn(map, projectId)) continue;
        const project = map[projectId];
        if (!project || project.id !== projectId || project.user_id !== userId) continue;
        const normalized = normalizeRow(row, userId, projectId);
        if (!normalized) continue;
        if (!grouped.has(projectId)) grouped.set(projectId, []);
        grouped.get(projectId).push(normalized);
      }
    }
    for (const [key, project] of Object.entries(map)) {
      if (!project || typeof project !== 'object' || Array.isArray(project)) {
        output[key] = project;
        continue;
      }
      const clone = { ...project };
      delete clone.canvasRelationshipBundle;
      if (authenticated && project.id === key && project.user_id === userId && grouped.has(key)) {
        clone.canvasRelationshipBundle = {
          projectId: key, userId, relationships: grouped.get(key), acceptedEvidence: []
        };
      }
      output[key] = clone;
    }
    return output;
  }
  return { eventActionId, endpoint, normalizeRow, attach };
});
