/* Bilim grafi — jonli force-graph (docs/10-obsidian-vault.md, roadmap 3.7).
 * Vanilla JS, tashqi kutubxonalar: force-graph (jsdelivr), marked (cdnjs).
 * WS ishlamasa ham `/v1/vault/graph` JSON snapshot bilan statik holda ishlaydi.
 */
(() => {
  "use strict";

  const TYPE_COLOR = {
    brand: "#6366F1",
    sop: "#22D3EE",
    script: "#10B981",
    report: "#8B95AD",
    staff: "#F59E0B",
    reference: "#A78BFA",
    plan: "#F472B6",
  };
  const DEFAULT_COLOR = "#8B95AD";
  const POP_MS = 600;
  const FADE_MS = 500;
  const RIPPLE_MS = 900;

  const els = {
    graph: document.getElementById("graph"),
    panel: document.getElementById("panel"),
    panelClose: document.getElementById("panel-close"),
    panelType: document.getElementById("panel-type"),
    panelTitle: document.getElementById("panel-title"),
    panelTags: document.getElementById("panel-tags"),
    panelPath: document.getElementById("panel-path"),
    panelMarkdown: document.getElementById("panel-markdown"),
    ticker: document.getElementById("ticker"),
    kpiFiles: document.getElementById("kpi-files"),
    kpiToday: document.getElementById("kpi-today"),
    kpiLinks: document.getElementById("kpi-links"),
    connDot: document.getElementById("conn-dot"),
    demoToggle: document.getElementById("demo-toggle"),
    stage: document.querySelector(".stage"),
  };

  const state = {
    nodesByPath: new Map(),
    links: [],
    ripples: [],
    hoverNode: null,
    selectedPath: null,
    demo: false,
    demoTimer: null,
    wsConnected: false,
  };

  // ---------------------------------------------------------------- utils
  function todayStr() {
    return new Date().toISOString().slice(0, 10);
  }

  function fmtTime(d) {
    return d.toLocaleTimeString("uz-UZ", { hour: "2-digit", minute: "2-digit" });
  }

  function easeOutBack(t) {
    const c1 = 1.70158;
    const c3 = c1 + 1;
    return 1 + c3 * Math.pow(t - 1, 3) + c1 * Math.pow(t - 1, 2);
  }

  function degreeMap() {
    const deg = new Map();
    for (const n of state.nodesByPath.keys()) deg.set(n, 0);
    for (const l of state.links) {
      deg.set(l.source, (deg.get(l.source) || 0) + 1);
      deg.set(l.target, (deg.get(l.target) || 0) + 1);
    }
    return deg;
  }

  function animateCount(el, to) {
    const from = Number(el.dataset.val || "0");
    if (from === to) return;
    const start = performance.now();
    const dur = 650;
    function tick(now) {
      const t = Math.min(1, (now - start) / dur);
      const eased = 1 - Math.pow(1 - t, 3);
      const val = Math.round(from + (to - from) * eased);
      el.textContent = String(val);
      if (t < 1) requestAnimationFrame(tick);
      else el.dataset.val = String(to);
    }
    el.dataset.val = String(from);
    requestAnimationFrame(tick);
  }

  function updateKpis() {
    const nodes = [...state.nodesByPath.values()].filter((n) => !n._removing);
    const today = nodes.filter((n) => (n.updated || "").slice(0, 10) === todayStr()).length;
    const links = state.links.filter(
      (l) => state.nodesByPath.has(l.source) && state.nodesByPath.has(l.target)
    ).length;
    animateCount(els.kpiFiles, nodes.length);
    animateCount(els.kpiToday, today);
    animateCount(els.kpiLinks, links);
  }

  function pushTicker(event, path) {
    const icon = { added: "➕", updated: "✏️", removed: "➖" }[event] || "•";
    const verb = { added: "qo'shildi", updated: "yangilandi", removed: "o'chirildi" }[event] || event;
    const li = document.createElement("li");
    li.innerHTML = `${icon} <b>${escapeHtml(path)}</b> ${verb} · ${fmtTime(new Date())}`;
    els.ticker.appendChild(li);
    while (els.ticker.children.length > 8) {
      els.ticker.removeChild(els.ticker.firstChild);
    }
    els.ticker.scrollLeft = els.ticker.scrollWidth;
  }

  function escapeHtml(s) {
    return String(s).replace(/[&<>"']/g, (c) => (
      { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]
    ));
  }

  // ---------------------------------------------------------------- graph setup
  const Graph = ForceGraph()(els.graph)
    .backgroundColor("rgba(0,0,0,0)")
    .nodeId("path")
    .linkColor(() => "rgba(139, 149, 173, 0.35)")
    .linkWidth(1)
    .linkDirectionalParticles(0)
    .warmupTicks(30)
    .cooldownTicks(200)
    .onNodeHover((node) => {
      state.hoverNode = node || null;
      els.graph.style.cursor = node ? "pointer" : "default";
    })
    .onNodeClick((node) => openPanel(node))
    .onBackgroundClick(() => closePanel())
    .nodeCanvasObject((node, ctx, globalScale) => {
      drawNode(node, ctx, globalScale);
    })
    .nodePointerAreaPaint((node, color, ctx) => {
      const r = nodeRadius(node);
      ctx.fillStyle = color;
      ctx.beginPath();
      ctx.arc(node.x, node.y, r + 2, 0, 2 * Math.PI);
      ctx.fill();
    });

  function nodeRadius(node) {
    const deg = state._degree ? state._degree.get(node.path) || 0 : 0;
    return 5 + Math.min(10, Math.sqrt(deg) * 3.2);
  }

  function drawNode(node, ctx, globalScale) {
    const target = nodeRadius(node);
    if (node._r === undefined) node._r = target;
    if (node._animStart) {
      const t = Math.min(1, (performance.now() - node._animStart) / POP_MS);
      node._r = target * Math.max(0, easeOutBack(t));
      if (t >= 1) node._animStart = null;
    }
    const r = Math.max(0.5, node._r);
    let alpha = 1;
    if (node._removing) {
      const t = Math.min(1, (performance.now() - node._removeStart) / FADE_MS);
      alpha = 1 - t;
    }

    const color = TYPE_COLOR[node.type] || DEFAULT_COLOR;
    const isHover = state.hoverNode && state.hoverNode.path === node.path;
    const isSelected = state.selectedPath === node.path;

    ctx.save();
    ctx.globalAlpha = alpha;

    if (isHover || isSelected) {
      ctx.shadowColor = color;
      ctx.shadowBlur = isHover ? 18 : 10;
    }
    ctx.fillStyle = color;
    ctx.beginPath();
    ctx.arc(node.x, node.y, r, 0, 2 * Math.PI);
    ctx.fill();
    ctx.shadowBlur = 0;

    if (isSelected) {
      ctx.strokeStyle = "#E6EAF2";
      ctx.lineWidth = 1.5 / globalScale;
      ctx.beginPath();
      ctx.arc(node.x, node.y, r + 2.5, 0, 2 * Math.PI);
      ctx.stroke();
    }

    const showLabel = isHover || globalScale > 2.6;
    if (showLabel) {
      const label = node.title || node.path;
      const fontSize = Math.max(10, 12 / globalScale);
      ctx.font = `600 ${fontSize}px Manrope, sans-serif`;
      const padX = 4;
      const w = ctx.measureText(label).width + padX * 2;
      const h = fontSize + 4;
      ctx.fillStyle = "rgba(11, 15, 25, 0.85)";
      ctx.fillRect(node.x - w / 2, node.y + r + 4, w, h);
      ctx.fillStyle = "#E6EAF2";
      ctx.textAlign = "center";
      ctx.textBaseline = "top";
      ctx.fillText(label, node.x, node.y + r + 6);
    }
    ctx.restore();

    if (node._animStart) requestAnimationFrame(() => Graph.refresh());
    if (node._removing) requestAnimationFrame(() => Graph.refresh());
  }

  function refreshGraphData() {
    state._degree = degreeMap();
    const nodes = [...state.nodesByPath.values()];
    const links = state.links
      .filter((l) => state.nodesByPath.has(l.source) && state.nodesByPath.has(l.target))
      .map((l) => ({ source: l.source, target: l.target }));
    Graph.graphData({ nodes, links });
    updateKpis();
  }

  function spawnRipple(node) {
    const coords = Graph.graph2ScreenCoords(node.x || 0, node.y || 0);
    const el = document.createElement("div");
    el.className = "ripple";
    el.style.left = `${coords.x}px`;
    el.style.top = `${coords.y}px`;
    els.stage.appendChild(el);
    setTimeout(() => el.remove(), RIPPLE_MS);
  }

  // ---------------------------------------------------------------- events
  function applyEvent(payload) {
    const { event, node, links } = payload;
    if (!node) return;

    if (event === "added") {
      const existing = state.nodesByPath.get(node.path);
      const merged = Object.assign({}, existing, node, {
        _animStart: performance.now(),
        x: existing ? existing.x : undefined,
        y: existing ? existing.y : undefined,
      });
      state.nodesByPath.set(node.path, merged);
      setLinksFor(node.path, links || []);
      refreshGraphData();
      requestAnimationFrame(() => spawnRipple(merged));
    } else if (event === "updated") {
      const existing = state.nodesByPath.get(node.path) || {};
      state.nodesByPath.set(node.path, Object.assign({}, existing, node));
      setLinksFor(node.path, links || []);
      refreshGraphData();
    } else if (event === "removed") {
      const existing = state.nodesByPath.get(node.path);
      if (existing) {
        existing._removing = true;
        existing._removeStart = performance.now();
        setTimeout(() => {
          state.nodesByPath.delete(node.path);
          state.links = state.links.filter(
            (l) => l.source !== node.path && l.target !== node.path
          );
          refreshGraphData();
        }, FADE_MS + 30);
      }
      refreshGraphData();
    }
    pushTicker(event, node.path);
  }

  function setLinksFor(sourcePath, targetPaths) {
    state.links = state.links.filter((l) => l.source !== sourcePath);
    for (const target of targetPaths) {
      state.links.push({ source: sourcePath, target });
    }
  }

  // ---------------------------------------------------------------- panel
  async function openPanel(node) {
    state.selectedPath = node.path;
    els.panel.classList.add("open");
    els.panel.setAttribute("aria-hidden", "false");
    els.panelType.textContent = node.type || "—";
    els.panelTitle.textContent = node.title || node.path;
    els.panelPath.textContent = node.path;
    els.panelTags.innerHTML = (node.tags || [])
      .map((t) => `<span class="chip">${escapeHtml(t)}</span>`)
      .join("");
    els.panelMarkdown.innerHTML = '<p class="panel-hint">Yuklanmoqda…</p>';
    Graph.refresh();

    try {
      const res = await fetch(`/v1/vault/notes/${node.path}`);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      els.panelTitle.textContent = data.title || node.path;
      els.panelTags.innerHTML = (data.tags || [])
        .map((t) => `<span class="chip">${escapeHtml(t)}</span>`)
        .join("");
      const html = window.marked ? window.marked.parse(data.markdown || "") : escapeHtml(data.markdown || "");
      els.panelMarkdown.innerHTML = html;
    } catch (err) {
      els.panelMarkdown.innerHTML = `<p class="panel-hint">Matnni yuklab bo'lmadi (${escapeHtml(String(err.message || err))}).</p>`;
    }
  }

  function closePanel() {
    state.selectedPath = null;
    els.panel.classList.remove("open");
    els.panel.setAttribute("aria-hidden", "true");
    Graph.refresh();
  }

  els.panelClose.addEventListener("click", closePanel);

  // ---------------------------------------------------------------- REST fallback
  async function loadSnapshotRest() {
    try {
      const res = await fetch("/v1/vault/graph");
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      applySnapshot(data);
    } catch (err) {
      console.warn("vault graph: REST snapshot yuklanmadi", err);
    }
  }

  function applySnapshot(data) {
    const now = performance.now();
    const nextPaths = new Set((data.nodes || []).map((n) => n.path));
    for (const path of state.nodesByPath.keys()) {
      if (!nextPaths.has(path)) state.nodesByPath.delete(path);
    }
    for (const n of data.nodes || []) {
      const existing = state.nodesByPath.get(n.path);
      state.nodesByPath.set(n.path, Object.assign({}, existing, n));
    }
    state.links = (data.links || []).map((l) => ({ source: l.source, target: l.target }));
    refreshGraphData();
  }

  // ---------------------------------------------------------------- WebSocket
  let backoffMs = 1000;
  const MAX_BACKOFF = 15000;
  let snapshotTimeout = null;

  function connectWs() {
    const proto = location.protocol === "https:" ? "wss:" : "ws:";
    const ws = new WebSocket(`${proto}//${location.host}/ws/vault`);

    snapshotTimeout = setTimeout(loadSnapshotRest, 3000);

    ws.addEventListener("open", () => {
      state.wsConnected = true;
      backoffMs = 1000;
      els.connDot.classList.add("live");
      els.connDot.classList.remove("down");
      els.connDot.title = "Ulangan (jonli)";
    });

    ws.addEventListener("message", (ev) => {
      let payload;
      try {
        payload = JSON.parse(ev.data);
      } catch {
        return;
      }
      if (payload.event === "snapshot") {
        clearTimeout(snapshotTimeout);
        applySnapshot(payload);
      } else if (payload.event) {
        applyEvent(payload);
      }
    });

    ws.addEventListener("close", () => {
      state.wsConnected = false;
      els.connDot.classList.remove("live");
      els.connDot.classList.add("down");
      els.connDot.title = "Ulanmagan — qayta urinilmoqda";
      clearTimeout(snapshotTimeout);
      setTimeout(connectWs, backoffMs);
      backoffMs = Math.min(MAX_BACKOFF, backoffMs * 2);
    });

    ws.addEventListener("error", () => ws.close());
  }

  // ---------------------------------------------------------------- demo mode
  const DEMO_TYPES = Object.keys(TYPE_COLOR);
  let demoCounter = 0;

  function demoTick() {
    const roll = Math.random();
    const demoNodes = [...state.nodesByPath.values()].filter((n) => n._demo);

    if (roll < 0.55 || demoNodes.length === 0) {
      demoCounter += 1;
      const type = DEMO_TYPES[demoCounter % DEMO_TYPES.length];
      const path = `demo/${type}-${demoCounter}.md`;
      const targets = demoNodes.length
        ? [demoNodes[Math.floor(Math.random() * demoNodes.length)].path]
        : [];
      applyEvent({
        event: "added",
        node: {
          id: path,
          path,
          title: `Demo ${type} #${demoCounter}`,
          type,
          tags: [`demo/${type}`],
          updated: new Date().toISOString(),
        },
        links: targets,
      });
      const node = state.nodesByPath.get(path);
      if (node) node._demo = true;
    } else if (roll < 0.85) {
      const node = demoNodes[Math.floor(Math.random() * demoNodes.length)];
      applyEvent({ event: "updated", node, links: [] });
    } else {
      const node = demoNodes[Math.floor(Math.random() * demoNodes.length)];
      applyEvent({ event: "removed", node, links: [] });
    }
  }

  function setDemo(on) {
    state.demo = on;
    els.demoToggle.setAttribute("aria-pressed", String(on));
    if (on) {
      state.demoTimer = setInterval(demoTick, 2000);
      demoTick();
    } else {
      clearInterval(state.demoTimer);
      state.demoTimer = null;
      for (const [path, n] of [...state.nodesByPath.entries()]) {
        if (n._demo) {
          state.nodesByPath.delete(path);
          state.links = state.links.filter((l) => l.source !== path && l.target !== path);
        }
      }
      refreshGraphData();
    }
  }

  els.demoToggle.addEventListener("click", () => setDemo(!state.demo));

  // ---------------------------------------------------------------- boot
  function fitCanvas() {
    Graph.width(els.graph.clientWidth).height(els.graph.clientHeight);
  }
  window.addEventListener("resize", fitCanvas);
  fitCanvas();

  loadSnapshotRest();
  connectWs();
})();
