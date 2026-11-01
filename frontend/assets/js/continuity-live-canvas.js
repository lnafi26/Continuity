/* Continuity — read-only authenticated project Canvas, first real-data slice.
 * Date-aligned historical and planned-work strands. An ordering rail is not
 * evidence of causation: no junctions or cross-strand links are inferred.
 * Uses already-authorized dashboard records; never reads or writes the network.
 */
(function (root, factory) {
  'use strict';
  const api = factory();
  if (typeof module === 'object' && module.exports) module.exports = api;
  if (root && root.document) {
    root.ContinuityLiveCanvas = api;
    api.mount(root.document, root);
  }
})(typeof window === 'undefined' ? null : window, function () {
  'use strict';
  const MAX_PER_LANE = 80;
  const LEFT = 108;
  const MIN_SPACING = 210;
  const TOP = { history: 122, schedule: 348 };

  function buildCanvasModel(project, normalize) {
    const groups = normalize(project);
    const eligible = [
      { kind: 'history', records: groups.history || [] },
      { kind: 'schedule', records: groups.scheduled || [] }
    ];
    const allDated = eligible.flatMap(g => g.records)
      .map(r => r.timestamp).filter(t => typeof t === 'number' && Number.isFinite(t));
    const earliest = allDated.length ? Math.min(...allDated) : null;
    const latest = allDated.length ? Math.max(...allDated) : null;
    const duration = earliest === null ? 1 : Math.max(1, latest - earliest);
    const nodes = [];
    const truncated = {};
    for (const group of eligible) {
      const records = group.records.slice(-MAX_PER_LANE);
      truncated[group.kind] = group.records.length - records.length;
      let previousX = -Infinity;
      for (const record of records) {
        // A date influences position, but collisions receive a minimum gutter.
        const temporal = earliest === null ? 0 : (record.timestamp - earliest) / duration;
        const x = Math.max(LEFT + temporal * 950, previousX + MIN_SPACING);
        previousX = x;
        nodes.push({
          key: group.kind + ':' + String(record.id),
          kind: group.kind,
          x: Math.round(x), y: TOP[group.kind],
          record: { ...record }
        });
      }
    }
    const width = Math.max(1040, ...nodes.map(n => n.x + 220));
    return {
      nodes, width, height: 475, earliest, latest,
      undatedCount: (groups.unscheduled || []).length,
      truncated,
      links: [] // No saved evidence of causal or cross-project relationships.
    };
  }

  function mount(doc, hostWindow) {
    const live = hostWindow.ContinuityLiveObservatory;
    const timeline = doc.getElementById('observatoryCanvas');
    const selector = doc.getElementById('observatoryProjectSelect');
    const canvasRoot = doc.getElementById('loCanvasMode');
    const viewport = doc.getElementById('loCanvasViewport');
    const stage = doc.getElementById('loCanvasStage');
    const navigator = doc.getElementById('loCanvasNavigator');
    const buttons = [...doc.querySelectorAll('[data-lo-mode]')];
    const zoomOut = doc.getElementById('loZoomOut');
    const zoomIn = doc.getElementById('loZoomIn');
    const zoomReset = doc.getElementById('loZoomReset');
    if (!live || !timeline || !selector || !canvasRoot || !viewport ||
        !stage || !navigator || buttons.length !== 2 || !zoomOut || !zoomIn || !zoomReset) return;

    const originalRender = live.render;
    if (typeof originalRender !== 'function') return;
    const create = (tag, cls, text) => {
      const node = doc.createElement(tag);
      node.className = cls || '';
      if (text !== undefined) node.textContent = String(text);
      return node;
    };
    let projectMap = {};
    let model = null;
    let mode = 'timeline';
    let zoom = 1;
    let chosen = null;
    const keyFor = n => n.key;

    function setMode(next) {
      mode = next === 'canvas' ? 'canvas' : 'timeline';
      timeline.hidden = mode === 'canvas';
      canvasRoot.hidden = mode !== 'canvas';
      for (const button of buttons) {
        const active = button.dataset.loMode === mode;
        button.setAttribute('aria-pressed', String(active));
      }
    }

    function scale() {
      if (!model) return;
      const holder = doc.getElementById('loCanvasHolder');
      holder.style.width = Math.ceil(model.width * zoom) + 'px';
      holder.style.height = Math.ceil(model.height * zoom) + 'px';
      stage.style.width = model.width + 'px';
      stage.style.height = model.height + 'px';
      stage.style.transform = `scale(${zoom})`;
      const output = doc.getElementById('loZoomValue');
      if (output) output.textContent = Math.round(zoom * 100) + '%';
      zoomOut.disabled = zoom <= 0.7;
      zoomIn.disabled = zoom >= 1.8;
    }

    function focusNode(node, fromNavigator = false) {
      chosen = keyFor(node);
      stage.querySelectorAll('[data-lo-node]').forEach(el => {
        el.setAttribute('aria-pressed', String(el.dataset.loNode === chosen));
      });
      if (typeof live.inspectRecord === 'function') live.inspectRecord(node.record);
      const target = [...stage.querySelectorAll('[data-lo-node]')]
        .find(el => el.dataset.loNode === chosen);
      if (target && fromNavigator) {
        viewport.scrollLeft = Math.max(0,
          node.x * zoom - viewport.clientWidth / 2 + 85 * zoom);
        viewport.scrollTop = Math.max(0, node.y * zoom - 35 * zoom);
        target.focus({ preventScroll: true });
      }
    }

    function draw() {
      stage.replaceChildren();
      navigator.replaceChildren();
      const project = projectMap[selector.value] || null;
      model = buildCanvasModel(project, live.normalizedRecords);
      const sub = create('p', 'lc-navigator-caption',
        'Navigator · Real records only · Chronology is not a causal link');
      navigator.append(sub);
      const labels = [
        ['history', 'RECORDED HISTORY'],
        ['schedule', 'PLANNED DEADLINES']
      ];
      for (const [lane, label] of labels) {
        const y = TOP[lane];
        const rail = create('div', 'lc-strand lc-strand-' + lane);
        rail.style.top = y + 16 + 'px';
        rail.style.left = LEFT + 14 + 'px';
        const last = model.nodes.filter(n => n.kind === lane).at(-1);
        rail.style.width = last ? Math.max(0, last.x - LEFT) + 'px' : '0px';
        stage.append(rail);
        const laneLabel = create('div', 'lc-lane-label', label);
        laneLabel.style.top = y - 38 + 'px';
        stage.append(laneLabel);
      }
      if (!model.nodes.length) {
        const empty = create('p', 'lc-empty', 'No dated records for this project yet. Add a decision or a dated task in Projects.');
        empty.style.top = '185px';
        stage.append(empty);
      }
      for (const node of model.nodes) {
        const item = create('button', 'lc-node lc-node-' + node.kind);
        item.type = 'button';
        item.dataset.loNode = node.key;
        item.setAttribute('aria-pressed', 'false');
        item.style.left = node.x + 'px';
        item.style.top = node.y + 'px';
        item.append(
          create('span', 'lc-node-date', node.record.date),
          create('strong', 'lc-node-title', node.record.title),
          create('small', 'lc-node-type', node.record.kind === 'task' ?
            'Task · ' + node.record.state : node.record.type)
        );
        item.addEventListener('click', () => focusNode(node));
        stage.append(item);

        const jump = create('button', 'lc-navigator-item',
          node.record.date + ' · ' + node.record.title);
        jump.type = 'button';
        jump.addEventListener('click', () => focusNode(node, true));
        navigator.append(jump);
      }
      if (model.undatedCount) {
        navigator.append(create('p', 'lc-navigator-note',
          `${model.undatedCount} undated record(s) remain in the Timeline view.`));
      }
      const hidden = model.truncated.history + model.truncated.schedule;
      if (hidden) navigator.append(create('p', 'lc-navigator-note',
        `${hidden} earlier dated records omitted from Canvas for performance. Timeline retains them.`));
      scale();
    }

    live.render = (projects = {}) => {
      originalRender(projects);
      projectMap = projects && typeof projects === 'object' ? projects : {};
      chosen = null;
      draw();
    };
    live.clear = () => live.render({});
    selector.addEventListener('change', () => {
      chosen = null;
      draw();
    });
    for (const button of buttons) {
      button.addEventListener('click', () => setMode(button.dataset.loMode));
    }
    zoomOut.addEventListener('click', () => {
      zoom = Math.max(0.7, Math.round((zoom - 0.2) * 10) / 10);
      scale();
    });
    zoomIn.addEventListener('click', () => {
      zoom = Math.min(1.8, Math.round((zoom + 0.2) * 10) / 10);
      scale();
    });
    zoomReset.addEventListener('click', () => {
      zoom = 1;
      viewport.scrollLeft = 0;
      viewport.scrollTop = 0;
      scale();
    });
    setMode('timeline');
    draw();
  }

  return { buildCanvasModel, mount };
});
