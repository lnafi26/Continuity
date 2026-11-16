/* Synthetic-only revision projection view. Not wired to live Observatory. */
(function (root, factory) {
  'use strict';
  const api = factory();
  if (typeof module === 'object' && module.exports) module.exports = api;
  else if (root) root.ContinuityRevisionHistory = api;
})(typeof window === 'undefined' ? null : window, function () {
  'use strict';

  const REVIEW = new Set(['proposed', 'confirmed', 'disputed', 'rejected']);
  const ACTORS = new Set(['user', 'agent', 'system']);
  const EVIDENCE = new Set(['supports', 'contradicts', 'context']);

  function requireValid(condition, message) {
    if (!condition) throw new TypeError('Invalid revision projection: ' + message);
  }

  function identifier(value) {
    return typeof value === 'string' && value.length > 0 && value.length <= 256;
  }

  function instant(value) {
    return typeof value === 'string' &&
      /(?:Z|[+-]\d{2}:\d{2})$/.test(value) &&
      Number.isFinite(Date.parse(value));
  }

  function normalizeProjection(input) {
    requireValid(input && typeof input === 'object' && !Array.isArray(input), 'object required');
    requireValid(input.schema_version === 1 &&
      input.kind === 'synthetic_revision_projection' && input.persisted === false,
    'only synthetic, non-durable projections are supported');
    for (const key of ['assertion_id', 'user_id', 'project_id']) {
      requireValid(identifier(input[key]), key + ' required');
    }
    requireValid(instant(input.as_of), 'snapshot time required');
    requireValid(Array.isArray(input.visible_revisions) && input.visible_revisions.length <= 200,
      'bounded revision array required');
    requireValid(Array.isArray(input.evidence) && input.evidence.length <= 500,
      'bounded evidence array required');
    requireValid(Array.isArray(input.open_review_revision_ids), 'review IDs required');
    requireValid(Array.isArray(input.warnings), 'warnings required');

    const revisions = input.visible_revisions.map((raw, index) => {
      requireValid(raw && typeof raw === 'object' && !Array.isArray(raw), 'revision record required');
      requireValid(identifier(raw.id), 'revision ID required');
      requireValid(Number.isInteger(raw.version_number) && raw.version_number === index + 1,
        'revision versions must be sequential');
      requireValid(raw.supersedes_revision_id === (index ? input.visible_revisions[index - 1].id : null),
        'explicit predecessor chain required');
      requireValid(REVIEW.has(raw.review_state) && ACTORS.has(raw.actor_type),
        'invalid review state or actor');
      requireValid(raw.review_state !== 'confirmed' || raw.actor_type === 'user',
        'only user-confirmed revisions are authoritative');
      requireValid(instant(raw.recorded_at) && instant(raw.effective_at) &&
        Date.parse(raw.recorded_at) <= Date.parse(input.as_of),
      'invalid or future-recorded revision time');
      const expectedStates = raw.review_state === 'confirmed'
        ? ['current', 'superseded', 'not_yet_effective']
        : [raw.review_state];
      requireValid(expectedStates.includes(raw.derived_state), 'invalid derived state');
      requireValid(raw.structured_value && typeof raw.structured_value === 'object' &&
        !Array.isArray(raw.structured_value), 'structured value required');
      const valueJSON = JSON.stringify(raw.structured_value);
      requireValid(typeof valueJSON === 'string' && valueJSON.length <= 16000,
        'structured value must be bounded JSON');
      return {
        id: raw.id, version_number: raw.version_number,
        supersedes_revision_id: raw.supersedes_revision_id,
        review_state: raw.review_state, actor_type: raw.actor_type,
        derived_state: raw.derived_state,
        recorded_at: raw.recorded_at, effective_at: raw.effective_at,
        value_json: valueJSON
      };
    });

    const byId = new Map(revisions.map(row => [row.id, row]));
    requireValid(byId.size === revisions.length, 'duplicate revision IDs');
    const currentId = input.current_confirmed === null
      ? null : input.current_confirmed?.id;
    requireValid(currentId === null || identifier(currentId), 'invalid current revision');
    const markedCurrent = revisions.filter(row => row.derived_state === 'current');
    requireValid(markedCurrent.length === (currentId === null ? 0 : 1),
      'current revision marker mismatch');
    if (currentId !== null) {
      requireValid(markedCurrent[0].id === currentId &&
        markedCurrent[0].review_state === 'confirmed' &&
        Date.parse(markedCurrent[0].effective_at) <= Date.parse(input.as_of),
      'current revision must be effective and user-confirmed');
    }
    const currentVersion = currentId === null ? 0 : byId.get(currentId)?.version_number;
    requireValid(Number.isInteger(currentVersion), 'unknown current revision');

    const open = new Set();
    for (const id of input.open_review_revision_ids) {
      const row = byId.get(id);
      requireValid(identifier(id) && !open.has(id) && row &&
        row.version_number > currentVersion &&
        ['proposed', 'disputed'].includes(row.review_state),
      'invalid open-review reference');
      open.add(id);
    }
    const expectedOpen = revisions.filter(row =>
      row.version_number > currentVersion &&
      ['proposed', 'disputed'].includes(row.review_state));
    requireValid(open.size === expectedOpen.length && expectedOpen.every(row => open.has(row.id)),
      'open-review set mismatch');

    const evidence = input.evidence.map(raw => {
      requireValid(raw && typeof raw === 'object' && !Array.isArray(raw) &&
        byId.has(raw.revision_id) && identifier(raw.source_item_id) &&
        EVIDENCE.has(raw.role) && raw.evidence_verification === 'not_verified' &&
        instant(raw.linked_at) && Date.parse(raw.linked_at) <= Date.parse(input.as_of),
      'invalid or incorrectly verified evidence reference');
      return {
        revision_id: raw.revision_id, source_item_id: raw.source_item_id,
        role: raw.role, evidence_verification: 'not_verified', linked_at: raw.linked_at
      };
    });
    const anyConflict = evidence.some(row => row.role === 'contradicts');
    const currentConflict = evidence.some(row =>
      row.role === 'contradicts' && row.revision_id === currentId);
    requireValid(input.has_contradictory_evidence === anyConflict &&
      input.has_current_contradictory_evidence === currentConflict,
    'contradiction flags inconsistent with evidence references');
    requireValid(input.warnings.every(w => typeof w === 'string' && w.length <= 1000),
      'invalid warnings');

    return {
      kind: input.kind, persisted: false, as_of: input.as_of,
      assertion_id: input.assertion_id,
      current_id: currentId, visible_revisions: revisions,
      open_review_revision_ids: [...open], evidence,
      warnings: [...input.warnings],
      has_contradictory_evidence: anyConflict,
      has_current_contradictory_evidence: currentConflict
    };
  }

  function renderRevisionHistory(container, raw, doc) {
    const projection = normalizeProjection(raw);
    requireValid(container && typeof container.replaceChildren === 'function', 'target required');
    doc = doc || container.ownerDocument;
    requireValid(doc && typeof doc.createElement === 'function', 'document required');

    function element(tag, className, label) {
      const node = doc.createElement(tag);
      if (className) node.className = className;
      if (label !== undefined) node.textContent = label;
      return node;
    }

    const root = element('section', 'crh-root');
    root.setAttribute('aria-label', 'Synthetic revision history preview');
    root.append(
      element('h3', '', 'Revision history — synthetic preview'),
      element('p', 'crh-warning',
        'Demo data only. Not saved project memory, not linked to a signed-in user, and not independently verified.')
    );
    const layout = element('div', 'crh-layout');
    const list = element('div', 'crh-list');
    list.setAttribute('role', 'group');
    list.setAttribute('aria-label', 'Revisions');
    const detail = element('section', 'crh-detail');
    detail.setAttribute('aria-label', 'Selected synthetic revision');
    const buttons = new Map();
    let selectedId = null;

    function field(dl, name, value) {
      const pair = element('div');
      pair.append(element('dt', '', name), element('dd', '', String(value)));
      dl.append(pair);
    }

    function select(id) {
      const record = projection.visible_revisions.find(row => row.id === id);
      if (!record) throw new RangeError('Unknown revision.');
      selectedId = id;
      for (const [otherId, button] of buttons) {
        button.setAttribute('aria-pressed', String(otherId === id));
      }
      detail.replaceChildren();
      detail.append(element('h4', '', `Revision ${record.version_number} · ${record.derived_state}`));
      const metadata = element('dl');
      field(metadata, 'Revision ID', record.id);
      field(metadata, 'Review state', record.review_state);
      field(metadata, 'Recorded by', record.actor_type);
      field(metadata, 'Recorded at', record.recorded_at);
      field(metadata, 'Effective at', record.effective_at);
      field(metadata, 'Supersedes', record.supersedes_revision_id || 'None recorded');
      detail.append(metadata);
      detail.append(element('h5', '', 'Recorded structured value'));
      detail.append(element('pre', 'crh-value', JSON.stringify(JSON.parse(record.value_json), null, 2)));
      const related = projection.evidence.filter(row => row.revision_id === record.id);
      detail.append(element('h5', '', 'Evidence references'));
      if (related.length) {
        const links = element('ul');
        for (const ref of related) {
          links.append(element('li', '',
            `${ref.role} · source ${ref.source_item_id} · NOT VERIFIED`));
        }
        detail.append(links);
      } else {
        detail.append(element('p', '',
          'No evidence reference in this bounded projection; absence is not proof none exists.'));
      }
      detail.append(element('p', 'crh-warning',
        'Source links do not verify claims. Human review is required for confirmation.'));
    }

    for (const record of projection.visible_revisions) {
      const button = element('button', 'crh-select',
        `Revision ${record.version_number} · ${record.derived_state} · ${record.actor_type}`);
      button.type = 'button';
      button.setAttribute('aria-pressed', 'false');
      button.addEventListener('click', () => select(record.id));
      buttons.set(record.id, button);
      list.append(button);
    }
    layout.append(list, detail);
    root.append(layout);
    if (projection.open_review_revision_ids.length) {
      root.append(element('p', 'crh-review',
        `${projection.open_review_revision_ids.length} synthetic revision(s) awaiting human review.`));
    }
    container.replaceChildren(root);
    const first = projection.current_id || projection.visible_revisions.at(-1)?.id;
    if (first) select(first);
    else detail.append(element('p', '', 'No revisions known at this snapshot time.'));
    return {
      get selectedId() { return selectedId; },
      select,
      snapshot: projection
    };
  }

  return { normalizeProjection, renderRevisionHistory };
});
