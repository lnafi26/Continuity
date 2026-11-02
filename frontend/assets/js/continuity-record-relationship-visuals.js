/* Continuity — opt-in, read-only documented-relationship visual bridge.
 * Rendering is not persistence or authorization. Without explicit scoped data,
 * no links appear. Never infer causation from dates or similar wording.
 */
(function (root, factory) {
  'use strict';
  const api = factory();
  if (typeof module === 'object' && module.exports) module.exports = api;
  if (root) root.ContinuityRecordRelationshipVisuals = api;
})(typeof window === 'undefined' ? null : window, function () {
  'use strict';
  const NS = 'http://www.w3.org/2000/svg';
  const EMPTY = () => ({ links: [], withheld: [] });

  function geometry(model, relation, offset = 0) {
    if (!model || !Array.isArray(model.nodes) || !relation) return null;
    const source = model.nodes.find(n => n && n.key === relation.fromKey);
    const target = model.nodes.find(n => n && n.key === relation.toKey);
    if (!source || !target || source === target) return null;
    if (![source.x, source.y, target.x, target.y].every(Number.isFinite)) return null;
    // Visual node centers (the connectors sit behind opaque event/task cards).
    const x1 = source.x + 91, x2 = target.x + 91;
    const y1 = source.y + 40, y2 = target.y + 40;
    let d;
    if (source.kind === target.kind) {
      const lift = source.kind === 'history' ? -92 : 92;
      d = `M ${x1} ${y1} C ${x1} ${y1 + lift + offset}, ${x2} ${y2 + lift + offset}, ${x2} ${y2}`;
    } else {
      const bend = Math.max(48, Math.abs(y2 - y1) * 0.45);
      const direction = y2 > y1 ? 1 : -1;
      d = `M ${x1} ${y1} C ${x1} ${y1 + bend * direction + offset}, ${x2} ${y2 - bend * direction + offset}, ${x2} ${y2}`;
    }
    return { ...relation, path: d };
  }

  function plan(project, model, contract) {
    if (!project || !model || !contract || typeof contract.classify !== 'function') return EMPTY();
    const bundle = project.canvasRelationshipBundle;
    // Strict opt-in. Existing dashboard/project payloads don't contain a bundle.
    if (!bundle || !Array.isArray(bundle.relationships) ||
        typeof project.id !== 'string' || !project.id ||
        typeof project.user_id !== 'string' || !project.user_id ||
        bundle.projectId !== project.id || bundle.userId !== project.user_id) return EMPTY();
    try {
      const context = {
        projectId: project.id, userId: project.user_id,
        acceptedEvidence: Array.isArray(bundle.acceptedEvidence) ? bundle.acceptedEvidence : []
      };
      const result = contract.classify(model, bundle.relationships, context);
      // Separate independently documented links sharing the same endpoints.
      // Pure presentation: never modify endpoints or infer causation.
      const groups = new Map();
      for (const link of result.drawable) {
        const pair = [link.fromKey, link.toKey].sort().join('|');
        if (!groups.has(pair)) groups.set(pair, []);
        groups.get(pair).push(link);
      }
      const offsets = new Map();
      for (const group of groups.values()) {
        group.sort((a, b) => a.id.localeCompare(b.id));
        const step = Math.min(16, 112 / Math.max(1, group.length - 1));
        group.forEach((link, index) => {
          offsets.set(link.id, (index - (group.length - 1) / 2) * step);
        });
      }
      const links = result.drawable.map(link =>
        geometry(model, link, offsets.get(link.id) || 0)
      ).filter(Boolean);
      return { links, withheld: result.withheld };
    } catch (_) {
      return EMPTY(); // Malformed input must never break Observatory.
    }
  }

  function render(doc, stage, model, links) {
    if (!doc || !stage || !model || !Array.isArray(links) || !links.length) return null;
    const svg = doc.createElementNS(NS, 'svg');
    svg.setAttribute('class', 'lc-relationship-overlay');
    svg.setAttribute('viewBox', `0 0 ${model.width} ${model.height}`);
    svg.setAttribute('width', String(model.width));
    svg.setAttribute('height', String(model.height));
    svg.setAttribute('aria-hidden', 'true');
    for (const link of links) {
      if (!link || typeof link.path !== 'string' || !/^M [\d.]+ [\d.]+ C /.test(link.path)) continue;
      const path = doc.createElementNS(NS, 'path');
      path.setAttribute('class', `lc-relationship-path lc-relationship-${link.kind}`);
      path.setAttribute('d', link.path);
      path.setAttribute('fill', 'none');
      svg.append(path);
    }
    if (!svg.childNodes.length) return null;
    stage.append(svg);
    return svg;
  }

  return { geometry, plan, render };
});
