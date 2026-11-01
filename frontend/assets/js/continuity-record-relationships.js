/* Continuity — explicit relationship preflight for real project records.
 * Presentation validation only, never authorization or proof of historical truth.
 * No inference, storage, network calls, or mutations.
 * A drawable relationship still requires authenticated server-side validation
 * of endpoints, project/user ownership, and the confirmation/evidence.
 */
(function (root, factory) {
  'use strict';
  const api = factory();
  if (typeof module === 'object' && module.exports) module.exports = api;
  if (root) root.ContinuityRecordRelationships = api;
})(typeof window === 'undefined' ? null : window, function () {
  'use strict';

  const KINDS = new Set(['dependency', 'handoff', 'divergence', 'convergence']);
  const LANES = Object.freeze({ event: 'history', action: 'schedule' });

  function idString(value) {
    if (typeof value === 'number') {
      return Number.isSafeInteger(value) && value > 0 ? String(value) : null;
    }
    return typeof value === 'string' && /^[1-9][0-9]*$/.test(value) ? value : null;
  }

  function endpointKey(endpoint) {
    if (!endpoint || typeof endpoint !== 'object' ||
        !Object.hasOwn(LANES, endpoint.type)) return null;
    const id = idString(endpoint.id);
    return id === null ? null : LANES[endpoint.type] + ':' + id;
  }

  function acceptedProof(relation, context) {
    const proof = relation.proof;
    if (!proof || typeof proof !== 'object') return false;

    if (proof.mode === 'user-confirmed') {
      return proof.confirmedBy === context.userId &&
        typeof proof.confirmedAt === 'string' &&
        proof.confirmedAt.trim() !== '' &&
        Number.isFinite(Date.parse(proof.confirmedAt));
    }

    if (proof.mode === 'accepted-source') {
      if (!Array.isArray(proof.sourceItemIds) || !proof.sourceItemIds.length ||
          new Set(proof.sourceItemIds).size !== proof.sourceItemIds.length) {
        return false;
      }
      const available = new Map((context.acceptedEvidence || [])
        .filter(item => item && typeof item.sourceItemId === 'string')
        .map(item => [item.sourceItemId, item]));
      return proof.sourceItemIds.every(id => {
        const item = available.get(id);
        return typeof id === 'string' && id.trim() && item &&
          item.reviewState === 'accepted' &&
          Array.isArray(item.relationshipIds) &&
          item.relationshipIds.includes(relation.id);
      });
    }
    return false;
  }

  function classify(model, relationships, context) {
    if (!Array.isArray(relationships)) {
      throw new TypeError('Explicit relationships must be an array.');
    }
    const drawable = [];
    const withheld = [];
    const scoped = context &&
      typeof context.projectId === 'string' && !!context.projectId &&
      typeof context.userId === 'string' && !!context.userId;
    const nodes = new Set();
    if (model && Array.isArray(model.nodes)) {
      for (const node of model.nodes) {
        if (!node || !node.record) continue;
        const type = node.kind === 'history' ? 'event' :
          node.kind === 'schedule' ? 'action' : null;
        const key = type ? endpointKey({ type, id: node.record.id }) : null;
        if (key && node.key === key &&
            (!Object.hasOwn(node.record, 'project_id') ||
             node.record.project_id === context?.projectId)) nodes.add(key);
      }
    }
    const seen = new Set();
    for (const relation of relationships) {
      const id = relation && relation.id;
      function reject(reason) { withheld.push({ id: typeof id === 'string' ? id : null, reason }); }
      if (!relation || typeof id !== 'string' || !id.trim() || seen.has(id)) {
        reject('invalid-or-duplicate-id');
        continue;
      }
      seen.add(id);
      if (!scoped || relation.projectId !== context.projectId ||
          relation.userId !== context.userId) {
        reject('scope-mismatch');
        continue;
      }
      if (!KINDS.has(relation.kind)) {
        reject('unsupported-kind');
        continue;
      }
      if (relation.state !== 'documented') {
        reject('not-documented');
        continue;
      }
      const fromKey = endpointKey(relation.from);
      const toKey = endpointKey(relation.to);
      if (!fromKey || !toKey || fromKey === toKey ||
          !nodes.has(fromKey) || !nodes.has(toKey)) {
        reject('invalid-or-unavailable-endpoints');
        continue;
      }
      if (typeof relation.statement !== 'string' ||
          !relation.statement.trim()) {
        reject('missing-statement');
        continue;
      }
      if (!acceptedProof(relation, context)) {
        reject('unconfirmed-or-unaccepted-evidence');
        continue;
      }
      drawable.push({
        id, kind: relation.kind, fromKey, toKey,
        statement: relation.statement.trim(),
        proofMode: relation.proof.mode
      });
    }
    return { drawable, withheld };
  }

  return { classify, endpointKey };
});
