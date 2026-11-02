/* Continuity — accessible Inspector for explicitly validated project relationships.
 * This module is PRESENTATION ONLY. It does not verify authentication, infer
 * relationships, create them, read/write data or persist user confirmation.
 * Only pass links returned by the existing validated relationshipPlan.
 */
(function (root, factory) {
  'use strict';
  const api = factory();
  if (typeof module === 'object' && module.exports) module.exports = api;
  if (root) root.ContinuityRelationshipInspector = api;
})(typeof window === 'undefined' ? null : window, function () {
  'use strict';
  const KINDS = new Set(['dependency', 'handoff', 'divergence', 'convergence']);
  const PROOF = new Set(['user-confirmed', 'accepted-source']);

  function view(link, model) {
    if (!link || !model || !Array.isArray(model.nodes) ||
        typeof link.id !== 'string' || !link.id.trim() ||
        !KINDS.has(link.kind) || typeof link.statement !== 'string' ||
        !link.statement.trim() || !PROOF.has(link.proofMode) ||
        typeof link.fromKey !== 'string' ||
        typeof link.toKey !== 'string' || link.fromKey === link.toKey) return null;
    const from = model.nodes.find(n => n && n.key === link.fromKey);
    const to = model.nodes.find(n => n && n.key === link.toKey);
    if (!from?.record || !to?.record ||
        typeof from.record.title !== 'string' ||
        typeof to.record.title !== 'string') return null;
    return {
      id: link.id, kind: link.kind,
      statement: link.statement.trim(),
      proofMode: link.proofMode,
      fromTitle: from.record.title,
      toTitle: to.record.title,
      fromKey: link.fromKey, toKey: link.toKey,
      midpoint: (Number(from.x) + Number(to.x)) / 2
    };
  }

  function inspect(doc, inspector, link, model) {
    const info = view(link, model);
    if (!doc || !inspector || !info) return false;
    const create = (tag, cls, value) => {
      const el = doc.createElement(tag);
      if (cls) el.className = cls;
      if (value !== undefined) el.textContent = String(value);
      return el;
    };
    inspector.replaceChildren();
    inspector.append(
      create('div', 'lo-inspector-top', 'DOCUMENTED RELATIONSHIP'),
      create('h3', '', info.kind.charAt(0).toUpperCase() + info.kind.slice(1)),
      create('p', 'lo-inspector-meta', 'From: ' + info.fromTitle),
      create('p', 'lo-inspector-meta', 'To: ' + info.toTitle),
      create('p', 'lo-inspector-detail', info.statement),
      create('p', 'lo-inspector-meta',
        info.proofMode === 'user-confirmed' ? 'Support: User-confirmed' : 'Support: Accepted source evidence'),
      create('p', 'lo-inspector-foot',
        'This displays a documented connection, not an AI-inferred causal claim. Presentation checks do not replace server-side verification.')
    );
    return true;
  }

  function forRecord(links, model, recordKey) {
    if (!Array.isArray(links) || typeof recordKey !== 'string') return [];
    return links.map(link => ({ link, info: view(link, model) }))
      .filter(entry => entry.info &&
        (entry.info.fromKey === recordKey || entry.info.toKey === recordKey));
  }

  // The selected record's Inspector exposes its explicitly documented links;
  // no relationship is inferred from proximity or chronological order.
  function attachForRecord(doc, inspector, links, model, recordKey, onSelect) {
    if (!doc || !inspector || typeof onSelect !== 'function') return [];
    const related = forRecord(links, model, recordKey);
    if (!related.length) return [];
    const section = doc.createElement('section');
    section.className = 'lc-inspector-connections';
    section.setAttribute('aria-label', 'Documented connections for this record');
    const heading = doc.createElement('h4');
    heading.textContent = 'Documented connections';
    section.append(heading);
    const buttons = [];
    for (const { link, info } of related) {
      const button = doc.createElement('button');
      button.type = 'button';
      button.className = 'lc-inspector-connection';
      const direction = info.fromKey === recordKey
        ? 'To: ' + info.toTitle : 'From: ' + info.fromTitle;
      const label = doc.createElement('strong');
      label.textContent = info.kind + ' · ' + direction;
      const statement = doc.createElement('span');
      statement.textContent = info.statement;
      button.append(label, statement);
      button.addEventListener('click', () => onSelect(link, info));
      section.append(button);
      buttons.push(button);
    }
    inspector.append(section);
    return buttons;
  }

  function attach(doc, navigator, links, model, onSelect) {
    if (!doc || !navigator || !Array.isArray(links) || !links.length ||
        typeof onSelect !== 'function') return [];
    const valid = links.map(link => ({ link, info: view(link, model) }))
      .filter(entry => entry.info && Number.isFinite(entry.info.midpoint));
    if (!valid.length) return [];
    const caption = doc.createElement('p');
    caption.className = 'lc-navigator-caption lc-relation-list-title';
    caption.textContent = 'DOCUMENTED CONNECTIONS';
    navigator.append(caption);
    const buttons = [];
    for (const { link, info } of valid) {
      const button = doc.createElement('button');
      button.type = 'button';
      button.className = 'lc-navigator-item lc-relation-jump';
      button.textContent = info.kind + ' · ' + info.fromTitle + ' → ' + info.toTitle;
      button.setAttribute('aria-pressed', 'false');
      button.addEventListener('click', () => {
        for (const other of buttons) other.setAttribute('aria-pressed', 'false');
        button.setAttribute('aria-pressed', 'true');
        onSelect(link, info);
      });
      navigator.append(button);
      buttons.push(button);
    }
    return buttons;
  }

  return { view, forRecord, attachForRecord, inspect, attach };
});
