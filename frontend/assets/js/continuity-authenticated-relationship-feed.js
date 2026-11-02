/* Project Continuity — read-only authenticated relationship feed.
 * This is an optional presentation integration, not a permissions layer.
 * Hosted environments without the migration must continue showing real records
 * with ZERO links. Never synthesize relationships, infer proof, or write data.
 * The database/RLS owns authorization and confirmation metadata.
 */
(function (root, factory) {
  'use strict';
  const api = factory();
  if (typeof module === 'object' && module.exports) module.exports = api;
  if (root) root.ContinuityAuthenticatedRelationshipFeed = api;
})(typeof window === 'undefined' ? null : window, function () {
  'use strict';
  const TABLE = 'project_record_relationships';
  const FIELDS = [
    'id', 'user_id', 'project_id', 'kind', 'state', 'statement',
    'from_event_id', 'from_action_id', 'to_event_id', 'to_action_id',
    'confirmed_by', 'confirmed_at'
  ].join(', ');
  const ABSENT_TABLE = new Set(['PGRST205', '42P01']);

  function withoutBundles(projectMap) {
    const clean = Object.create(null);
    if (!projectMap || typeof projectMap !== 'object' || Array.isArray(projectMap)) return clean;
    for (const [key, project] of Object.entries(projectMap)) {
      if (!project || typeof project !== 'object' || Array.isArray(project)) {
        clean[key] = project;
      } else {
        const copy = { ...project };
        delete copy.canvasRelationshipBundle;
        clean[key] = copy;
      }
    }
    return clean;
  }

  async function load(db, projectMap, userId, boundary) {
    // Always strip caller-provided/stale bundles, even if the fetch is disabled.
    const clean = withoutBundles(projectMap);
    if (typeof userId !== 'string' || !userId.trim() ||
        !boundary || typeof boundary.attach !== 'function' ||
        !db || typeof db.from !== 'function') return clean;

    try {
      // Only read the authenticated account's persisted, server-confirmed rows.
      const response = await db.from(TABLE).select(FIELDS).eq('user_id', userId);
      if (!response || response.error || !Array.isArray(response.data)) {
        if (response?.error && !ABSENT_TABLE.has(response.error.code)) {
          console.warn('Relationship data unavailable; Canvas connections withheld.',
            typeof response.error.code === 'string' ? response.error.code : 'query-failed');
        }
        return clean;
      }
      // The boundary verifies user + project + confirmation + typed endpoints.
      // Its output is new; neither the project map nor fetched rows are mutated.
      return boundary.attach(clean, response.data, userId);
    } catch (_) {
      // Network failure and malformed client implementations fail closed.
      console.warn('Relationship data unavailable; Canvas connections withheld.');
      return clean;
    }
  }

  return { load, withoutBundles };
});
