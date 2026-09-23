/* Bilim grafi — jonli force-graph (docs/10-obsidian-vault.md, roadmap 3.7).
 * Vanilla JS, tashqi kutubxonalar: force-graph (vendored, CDN fallback), marked (vendored, CDN fallback).
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
  const TYPE_LABEL_UZ = {
    brand: "Brend",
    sop: "SOP",
    staff: "Xodim",
    reference: "Referens",
    plan: "Reja",
    script: "Ssenariy",
    report: "Hisobot",
  };
  const DEFAULT_COLOR = "#8B95AD";
  const POP_MS = 600;
  const FADE_MS = 500;
  const RIPPLE_MS = 900;
  const DIMMED_ALPHA = 0.15;

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
    legend: document.getElementById("legend"),
  };

  const state = {
    nodesByPath: new Map(),
    links: [],
    hoverNode: null,
    selectedPath: null,
    demo: false,
    demoTimer: null,
    wsConnected: false,
    focusType: null,
    tickerSeeded: false,
    userZoomed: false,
    suppressZoomEvent: false,
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

  function hexToRgba(hex, alpha) {
    const clean = String(hex || "").replace("#", "");
    const full = clean.length === 3 ? clean.split("").map((c) => c + c).join("") : clean;
    const num = parseInt(full || "8B95AD", 16);
    const r = (num >> 16) & 255;
    const g = (num >> 8) & 255;
    const b = num & 255;
    return `rgba(${r}, ${g}, ${b}, ${alpha})`;
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

  function escapeHtml(s) {
    return String(s).replace(/[&<>"']/g, (c) => (
      { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]
    ));
  }

  // ---------------------------------------------------------------- ticker
  function pushTickerRaw(html) {
    const li = document.createElement("li");
    li.innerHTML = html;
    els.ticker.appendChild(li);
    while (els.ticker.children.length > 8) {
      els.ticker.removeChild(els.ticker.firstChild);
    }
    els.ticker.scrollLeft = els.ticker.scrollWidth;
  }

  function pushTicker(event, path) {
    const icon = { added: "➕", updated: "✏️", removed: "➖" }[event] || "•";
    const verb = { added: "qo'shildi", updated: "yangilandi", removed: "o'chirildi" }[event] || event;
    pushTickerRaw(
      `${icon} <b>${escapeHtml(path)}</b> ${verb} · ${fmtTime(new Date())}`
    );
  }

  function seedTickerFromSnapshot(nodes) {
    if (state.tickerSeeded) return;
    state.tickerSeeded = true;
    if (!nodes.length) return;
    const recent = [...nodes]
      .filter((n) => n.updated)
      .sort((a, b) => String(b.updated).localeCompare(String(a.updated)))
      .slice(0, 8)
      .reverse(); // eskisi birinchi qo'shiladi, eng yangisi ro'yxat oxirida (o'ngda) tursin
    for (const n of recent) {
      const when = n.updated ? new Date(n.updated) : new Date();
      pushTickerRaw(`📄 <b>${escapeHtml(n.path)}</b> · ${fmtTime(when)}`);
    }
  }

  // ---------------------------------------------------------------- legend
  function buildLegend() {
    if (!els.legend) return;
    els.legend.innerHTML = "";
    for (const type of Object.keys(TYPE_COLOR)) {
      const chip = document.createElement("button");
      chip.type = "button";
      chip.className = "legend-chip";
      chip.dataset.type = type;
      chip.setAttribute("aria-pressed", "false");
      chip.innerHTML =
        `<span class="legend-dot" style="background:${TYPE_COLOR[type]}"></span>` +
        `<span>${TYPE_LABEL_UZ[type] || type}</span>`;
      chip.addEventListener("click", () => toggleFocusType(type));
      els.legend.appendChild(chip);
    }
  }

  function toggleFocusType(type) {
    state.focusType = state.focusType === type ? null : type;
    for (const chip of els.legend.querySelectorAll(".legend-chip")) {
      const active = chip.dataset.type === state.focusType;
      chip.setAttribute("aria-pressed", String(active));
      chip.classList.toggle("dimmed", Boolean(state.focusType) && !active);
    }
    Graph.refresh();
  }

  function typeAlphaFactor(type) {
    if (!state.focusType) return 1;
    return type === state.focusType ? 1 : DIMMED_ALPHA;
  }

  // ---------------------------------------------------------------- graph setup
  const Graph = ForceGraph()(els.graph)
    .backgroundColor("rgba(0,0,0,0)")
    .nodeId("path")
    .linkColor((link) => linkColorFor(link))
    .linkWidth(1)
    .linkDirectionalParticles(2)
    .linkDirectionalParticleSpeed(0.004)
    .linkDirectionalParticleWidth(2)
    .linkDirectionalParticleColor((link) => linkParticleColorFor(link))
    .warmupTicks(30)
    .cooldownTicks(200)
    .onNodeHover((node) => {
      state.hoverNode = node || null;
      els.graph.style.cursor = node ? "pointer" : "default";
    })
    .onNodeClick((node) => openPanel(node))
    .onBackgroundClick(() => closePanel())
    .onZoom(() => {
      if (!state.suppressZoomEvent) state.userZoomed = true;
    })
    .onEngineStop(() => zoomToFitNow(false))
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

  function linkColorFor(link) {
    const srcType = typeOfEndpoint(link.source);
    const tgtType = typeOfEndpoint(link.target);
    const relevant =
      !state.focusType || srcType === state.focusType || tgtType === state.focusType;
    return relevant ? "rgba(139, 149, 173, 0.35)" : "rgba(139, 149, 173, 0.06)";
  }

  function linkParticleColorFor(link) {
    const srcType = typeOfEndpoint(link.source);
    const relevant = !state.focusType || srcType === state.focusType;
    const color = TYPE_COLOR[srcType] || DEFAULT_COLOR;
    return hexToRgba(color, relevant ? 0.6 : 0.08);
  }

  function typeOfEndpoint(endpoint) {
    const path = typeof endpoint === "object" && endpoint ? endpoint.path : endpoint;
    const node = state.nodesByPath.get(path);
    return node ? node.type : null;
  }

  function nodeRadius(node) {
    const deg = state._degree ? state._degree.get(node.path) || 0 : 0;
    return 5 + Math.min(10, Math.sqrt(deg) * 3.2);
  }

  function drawGlow(ctx, node, r, color, alpha) {
    if (!Number.isFinite(node.x) || !Number.isFinite(node.y) || !(r > 0.01)) return;
    const outerR = r * 4.2;
    const outer = ctx.createRadialGradient(node.x, node.y, r * 0.5, node.x, node.y, outerR);
    outer.addColorStop(0, hexToRgba(color, 0.30 * alpha));
    outer.addColorStop(1, hexToRgba(color, 0));
    ctx.fillStyle = outer;
    ctx.beginPath();
    ctx.arc(node.x, node.y, outerR, 0, 2 * Math.PI);
    ctx.fill();

    const innerR = r * 1.9;
    const inner = ctx.createRadialGradient(node.x, node.y, 0, node.x, node.y, innerR);
    inner.addColorStop(0, hexToRgba(color, 0.55 * alpha));
    inner.addColorStop(1, hexToRgba(color, 0));
    ctx.fillStyle = inner;
    ctx.beginPath();
    ctx.arc(node.x, node.y, innerR, 0, 2 * Math.PI);
    ctx.fill();
  }

  function drawNode(node, ctx, globalScale) {
    if (!Number.isFinite(node.x) || !Number.isFinite(node.y)) return;
    const target = nodeRadius(node);
    if (node._r === undefined) node._r = target;

    let popT = 1;
    if (node._animStart) {
      popT = Math.min(1, (performance.now() - node._animStart) / POP_MS);
      node._r = target * Math.max(0, easeOutBack(popT));
      if (popT >= 1) node._animStart = null;
    }
    const r = Math.max(0.5, node._r);

    let fadeAlpha = 1;
    if (node._removing) {
      const t = Math.min(1, (performance.now() - node._removeStart) / FADE_MS);
      fadeAlpha = 1 - t;
    }

    const color = TYPE_COLOR[node.type] || DEFAULT_COLOR;
    const isHover = state.hoverNode && state.hoverNode.path === node.path;
    const isSelected = state.selectedPath === node.path;
    const dimFactor = typeAlphaFactor(node.type);
    const alpha = fadeAlpha * dimFactor;

    ctx.save();
    ctx.globalAlpha = alpha;

    // 1) yumshoq ikki qatlamli halo (har doim, hover'da kuchayadi)
    drawGlow(ctx, node, r, color, isHover ? 1.6 : 1);

    // 2) asosiy doira
    if (isHover || isSelected) {
      ctx.shadowColor = color;
      ctx.shadowBlur = isHover ? 18 : 10;
    }
    ctx.fillStyle = color;
    ctx.beginPath();
    ctx.arc(node.x, node.y, r, 0, 2 * Math.PI);
    ctx.fill();
    ctx.shadowBlur = 0;

    // 3) yupqa halqa (tur rangida)
    ctx.strokeStyle = hexToRgba(color, 0.9);
    ctx.lineWidth = 1.2 / Math.max(0.6, globalScale ** 0.15);
    ctx.beginPath();
    ctx.arc(node.x, node.y, r + 1.6, 0, 2 * Math.PI);
    ctx.stroke();

    if (isSelected) {
      ctx.strokeStyle = "#E6EAF2";
      ctx.lineWidth = 1.5 / globalScale;
      ctx.beginPath();
      ctx.arc(node.x, node.y, r + 4, 0, 2 * Math.PI);
      ctx.stroke();
    }

    // 4) sarlavha — doim ko'rinadi, "portlash" bilan birga paydo bo'ladi, qorong'i halo bilan
    const label = node.title || node.path;
    if (label) {
      const fontSize = (isHover ? 13 : 12) / Math.max(globalScale, 0.6);
      ctx.font = `600 ${fontSize}px Manrope, sans-serif`;
      ctx.textAlign = "center";
      ctx.textBaseline = "top";
      const ly = node.y + r + 5 / Math.max(globalScale, 0.6);
      ctx.globalAlpha = alpha * popT;
      ctx.lineWidth = 3 / Math.max(globalScale, 0.6);
      ctx.strokeStyle = "rgba(5, 7, 13, 0.85)";
      ctx.strokeText(label, node.x, ly);
      ctx.fillStyle = `rgba(230, 234, 242, ${0.85 * alpha * popT})`;
      ctx.fillText(label, node.x, ly);
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
    // Tugunlar bir-biriga yopishmasin: kuchliroq itarish va uzunroq bog'lanish
    const charge = Graph.d3Force("charge");
    if (charge) charge.strength(-260);
    const linkF = Graph.d3Force("link");
    if (linkF) linkF.distance(90);
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

  // ---------------------------------------------------------------- zoom-to-fit
  function zoomToFitNow(force) {
    if (!force && state.userZoomed) return;
    state.suppressZoomEvent = true;
    Graph.zoomToFit(600, 80);
    setTimeout(() => {
      // Kichik graflarda haddan tashqari yaqinlashmasin
      if (Graph.zoom() > 3.2) Graph.zoom(3.2, 300);
      setTimeout(() => { state.suppressZoomEvent = false; }, 350);
    }, 650);
  }

  let settleTimer = null;
  function scheduleSettleZoom() {
    clearTimeout(settleTimer);
    settleTimer = setTimeout(() => zoomToFitNow(true), 1500);
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
      zoomToFitNow(false);
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
    seedTickerFromSnapshot(data.nodes || []);
    scheduleSettleZoom();
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

  let resizeTimer = null;
  window.addEventListener("resize", () => {
    fitCanvas();
    clearTimeout(resizeTimer);
    resizeTimer = setTimeout(() => zoomToFitNow(false), 250);
  });
  fitCanvas();

  // Telefon eni (390px atrofida): legend ko'p qatorga o'tadi, KPI'lar
  // o'z qatoriga tushib "stack" bo'ladi — body.phone klassi orqali.
  const phoneMq = window.matchMedia("(max-width: 480px)");
  function applyPhoneLayout(mq) {
    document.body.classList.toggle("phone", mq.matches);
  }
  applyPhoneLayout(phoneMq);
  if (phoneMq.addEventListener) {
    phoneMq.addEventListener("change", applyPhoneLayout);
  } else if (phoneMq.addListener) {
    phoneMq.addListener(applyPhoneLayout); // eski Safari
  }

  buildLegend();
  loadSnapshotRest();
  connectWs();
})();
