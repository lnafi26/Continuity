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
  const NODE_WIDTH = 182;
  const NODE_HEIGHT = 155; // Include room for wrapped record titles.
  const FIT_GUTTER = 32;
  const MIN_ZOOM = 0.25;
  const MAX_ZOOM = 1.8;

  // Pure, deterministic camera calculation; no record or connection is inferred.
  function fitCanvasView(model, viewportWidth, viewportHeight) {
    if (!model || !Array.isArray(model.nodes) || !model.nodes.length ||
        !Number.isFinite(viewportWidth) || viewportWidth <= 0 ||
        !Number.isFinite(viewportHeight) || viewportHeight <= 0) return null;
    let left = Infinity, right = -Infinity, top = Infinity, bottom = -Infinity;
    for (const node of model.nodes) {
      if (!node || !Number.isFinite(node.x) || !Number.isFinite(node.y)) continue;
      left = Math.min(left, node.x);
      right = Math.max(right, node.x + NODE_WIDTH);
      top = Math.min(top, node.y - 42);
      bottom = Math.max(bottom, node.y + NODE_HEIGHT);
    }
    if (!Number.isFinite(left)) return null;
    const availableWidth = Math.max(1, viewportWidth - FIT_GUTTER * 2);
    const availableHeight = Math.max(1, viewportHeight - FIT_GUTTER * 2);
    const requested = Math.min(1, availableWidth / Math.max(1, right - left),
      availableHeight / Math.max(1, bottom - top));
    const zoom = Math.max(MIN_ZOOM, requested);
    return {
      zoom,
      left: Math.max(0, left * zoom - FIT_GUTTER),
      top: Math.max(0, top * zoom - FIT_GUTTER),
      fitsAll: requested >= MIN_ZOOM
    };
  }

  function buildCanvasModel(project, normalize) {
    const groups = normalize(project);
    const eligible = [
      { kind: 'history', records: groups.history || [] },
      { kind: 'schedule', records: groups.scheduled || [] }
    ];
    // Scan date bounds without spreading an unbounded project history
    // into function arguments. Visible records remain lane-capped.
    let earliest = null;
    let latest = null;
    for (const group of eligible) {
      for (const record of group.records) {
        const stamp = record && record.timestamp;
        if (typeof stamp !== 'number' || !Number.isFinite(stamp)) continue;
        earliest = earliest === null ? stamp : Math.min(earliest, stamp);
        latest = latest === null ? stamp : Math.max(latest, stamp);
      }
    }
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

  // Navigator positions are a spatial index, not a claim of causation.
  function navigatorMarkers(model) {
    if (!model || !Array.isArray(model.nodes)) return [];
    const width = Math.max(1, Number(model.width) || 1);
    return model.nodes.map(node => ({
      key: node.key,
      kind: node.kind,
      title: node.record.title,
      position: Math.max(0, Math.min(100, Math.round((node.x + 91) / width * 1000) / 10))
    }));
  }

  function adjacentNode(model, key, step) {
    if (!model || !Array.isArray(model.nodes) || !model.nodes.length) return null;
    const ordered = model.nodes.slice().sort((a, b) =>
      a.x - b.x || a.y - b.y || a.key.localeCompare(b.key));
    const index = ordered.findIndex(n => n.key === key);
    if (index < 0) return step < 0 ? ordered.at(-1) : ordered[0];
    return ordered[(index + (step < 0 ? -1 : 1) + ordered.length) % ordered.length];
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
    const previous = doc.getElementById('loPreviousNode');
    const next = doc.getElementById('loNextNode');
    if (!live || !timeline || !selector || !canvasRoot || !viewport ||
        !stage || !navigator || buttons.length !== 2 || !zoomOut || !zoomIn ||
        !zoomReset || !previous || !next) return;

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
    let relationButtons = [];
    let validatedLinks = [];
    let hasEnteredCanvas = false;
    let mapTrack = null;
    let mapWindow = null;
    const keyFor = n => n.key;

    function syncMapViewport() {
      if (!model || !mapTrack || !mapWindow) return;
      const total = Math.max(1, model.width * zoom);
      const visible = Math.min(total, Math.max(0, viewport.clientWidth));
      const left = Math.max(0, Math.min(total - visible, viewport.scrollLeft));
      mapWindow.style.left = (left / total * 100).toFixed(2) + '%';
      mapWindow.style.width = (visible / total * 100).toFixed(2) + '%';
    }

    function syncSelection() {
      stage.querySelectorAll('[data-lo-node]').forEach(el => {
        el.setAttribute('aria-pressed', String(el.dataset.loNode === chosen));
      });
      navigator.querySelectorAll('[data-lo-jump]').forEach(el => {
        el.setAttribute('aria-current', el.dataset.loJump === chosen ? 'true' : 'false');
      });
      navigator.querySelectorAll('[data-lo-map]').forEach(el => {
        el.setAttribute('aria-pressed', String(el.dataset.loMap === chosen));
      });
      previous.disabled = next.disabled = !model?.nodes?.length;
    }

    function setMode(next) {
      mode = next === 'canvas' ? 'canvas' : 'timeline';
      timeline.hidden = mode === 'canvas';
      canvasRoot.hidden = mode !== 'canvas';
      for (const button of buttons) {
        const active = button.dataset.loMode === mode;
        button.setAttribute('aria-pressed', String(active));
      }
      // The Canvas was hidden at mount time: measure only after it is visible.
      // Switching back from Timeline preserves subsequent manual navigation.
      if (mode === 'canvas' && !hasEnteredCanvas && viewport.clientWidth) {
        hasEnteredCanvas = true;
        fitView();
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
      zoomOut.disabled = zoom <= MIN_ZOOM;
      zoomIn.disabled = zoom >= MAX_ZOOM;
      syncMapViewport();
    }

    function fitView() {
      const fit = fitCanvasView(model, viewport.clientWidth, viewport.clientHeight);
      if (!fit) return;
      zoom = fit.zoom;
      scale();
      viewport.scrollLeft = fit.left;
      viewport.scrollTop = fit.top;
      syncMapViewport();
    }

    function inspectLink(link, info) {
      chosen = null;
      syncSelection();
      const relationInspector = hostWindow.ContinuityRelationshipInspector;
      if (relationInspector) relationInspector.inspect(
        doc, doc.getElementById('observatoryInspector'), link, model);
      viewport.scrollLeft = Math.max(0,
        info.midpoint * zoom - viewport.clientWidth / 2 + 91 * zoom);
      syncMapViewport();
    }

    function focusNode(node, fromNavigator = false) {
      for (const button of relationButtons) button.setAttribute('aria-pressed', 'false');
      chosen = keyFor(node);
      syncSelection();
      if (typeof live.inspectRecord === 'function') live.inspectRecord(node.record);
      const relationInspector = hostWindow.ContinuityRelationshipInspector;
      const inspector = doc.getElementById('observatoryInspector');
      if (relationInspector && inspector &&
          typeof relationInspector.attachForRecord === 'function') {
        relationInspector.attachForRecord(doc, inspector, validatedLinks,
          model, chosen, inspectLink);
      }
      const target = [...stage.querySelectorAll('[data-lo-node]')]
        .find(el => el.dataset.loNode === chosen);
      if (target && fromNavigator) {
        viewport.scrollLeft = Math.max(0,
          node.x * zoom - viewport.clientWidth / 2 + 85 * zoom);
        viewport.scrollTop = Math.max(0, node.y * zoom - 35 * zoom);
        target.focus({ preventScroll: true });
        syncMapViewport();
      }
    }

    function draw() {
      stage.replaceChildren();
      navigator.replaceChildren();
      relationButtons = [];
      mapTrack = null;
      mapWindow = null;
      const project = projectMap[selector.value] || null;
      model = buildCanvasModel(project, live.normalizedRecords);
      // Optional, explicitly scoped relationship data only. No inference.
      const relationshipVisuals = hostWindow.ContinuityRecordRelationshipVisuals;
      const relationshipPlan = relationshipVisuals
        ? relationshipVisuals.plan(project, model, hostWindow.ContinuityRecordRelationships)
        : { links: [], withheld: [] };
      validatedLinks = relationshipPlan.links;
      const sub = create('p', 'lc-navigator-caption',
        'Navigator · Real records only · Chronology is not a causal link');
      navigator.append(sub);
      mapTrack = create('div', 'lc-mini-track');
      mapTrack.setAttribute('role', 'group');
      mapTrack.setAttribute('aria-label', 'Navigator overview. Dots are saved project records.');
      mapWindow = create('div', 'lc-mini-window');
      mapWindow.setAttribute('aria-hidden', 'true');
      const mapHistory = create('span', 'lc-mini-lane lc-mini-history', 'Recorded');
      const mapScheduled = create('span', 'lc-mini-lane lc-mini-schedule', 'Planned');
      mapTrack.append(mapHistory, mapScheduled, mapWindow);
      for (const marker of navigatorMarkers(model)) {
        const target = model.nodes.find(node => node.key === marker.key);
        const dot = create('button', 'lc-mini-dot lc-mini-' + marker.kind);
        dot.type = 'button';
        dot.dataset.loMap = marker.key;
        dot.style.left = marker.position + '%';
        dot.setAttribute('aria-label', marker.kind + ' · ' + marker.title);
        dot.setAttribute('aria-pressed', 'false');
        dot.title = marker.title;
        dot.addEventListener('click', () => focusNode(target, true));
        mapTrack.append(dot);
      }
      mapTrack.addEventListener('click', event => {
        if (!model || !model.nodes.length || event.target.closest('button')) return;
        const rect = mapTrack.getBoundingClientRect();
        if (!rect.width) return;
        const fraction = Math.max(0, Math.min(1, (event.clientX - rect.left) / rect.width));
        viewport.scrollLeft = fraction * model.width * zoom - viewport.clientWidth / 2;
        syncMapViewport();
      });
      navigator.append(mapTrack);
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
      // Draw connectors behind nodes, without changing the Canvas record layout.
      if (relationshipVisuals && relationshipPlan.links.length) {
        relationshipVisuals.render(doc, stage, model, relationshipPlan.links);
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
        jump.dataset.loJump = node.key;
        jump.addEventListener('click', () => focusNode(node, true));
        navigator.append(jump);
      }
      if (relationshipPlan.links.length) {
        navigator.append(create('p', 'lc-navigator-note',
          `${relationshipPlan.links.length} documented relationship(s) displayed. ` +
          'Connections are explicit, not inferred from the timeline.'));
      }
      // Only prevalidated, scoped Canvas relationships get Inspector controls.
      const relationInspector = hostWindow.ContinuityRelationshipInspector;
      if (relationInspector && relationshipPlan.links.length) {
        relationButtons = relationInspector.attach(doc, navigator,
          relationshipPlan.links, model, inspectLink);
      }
      if (model.undatedCount) {
        navigator.append(create('p', 'lc-navigator-note',
          `${model.undatedCount} undated record(s) remain in the Timeline view.`));
      }
      const hidden = model.truncated.history + model.truncated.schedule;
      if (hidden) navigator.append(create('p', 'lc-navigator-note',
        `${hidden} earlier dated records omitted from Canvas for performance. Timeline retains them.`));
      scale();
      if (mode === 'canvas') fitView(); // Reframe on project/data changes.
      syncSelection();
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
      zoom = Math.max(MIN_ZOOM, Math.round((zoom - 0.2) * 100) / 100);
      scale();
    });
    zoomIn.addEventListener('click', () => {
      zoom = Math.min(MAX_ZOOM, Math.round((zoom + 0.2) * 100) / 100);
      scale();
    });
    const zoomFit = doc.getElementById('loZoomFit');
    if (zoomFit) zoomFit.addEventListener('click', fitView);
    zoomReset.addEventListener('click', () => {
      zoom = 1;
      viewport.scrollLeft = 0;
      viewport.scrollTop = 0;
      scale();
    });
    function navigate(step) {
      const target = adjacentNode(model, chosen, step);
      if (target) focusNode(target, true);
    }
    previous.addEventListener('click', () => navigate(-1));
    next.addEventListener('click', () => navigate(1));
    viewport.addEventListener('keydown', event => {
      if (mode !== 'canvas' || event.altKey || event.ctrlKey || event.metaKey) return;
      if (event.key === 'ArrowRight' || event.key === 'ArrowLeft') {
        event.preventDefault();
        navigate(event.key === 'ArrowRight' ? 1 : -1);
      } else if ((event.key === 'Home' || event.key === 'End') && model?.nodes?.length) {
        event.preventDefault();
        const ordered = model.nodes.slice().sort((a,b) => a.x - b.x || a.y - b.y);
        focusNode(event.key === 'Home' ? ordered[0] : ordered.at(-1), true);
      }
    });
    viewport.addEventListener('scroll', syncMapViewport, { passive: true });
    hostWindow.addEventListener('resize', syncMapViewport);
    setMode('timeline');
    draw();
  }

  return { buildCanvasModel, navigatorMarkers, adjacentNode, fitCanvasView, mount };
});
