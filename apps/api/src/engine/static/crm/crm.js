/* CRM dashboard — vanilla JS + vendored Chart.js (docs/06-jarvis-crm.md "CRM web-sahifa").
 * Ishlaydi faqat /v1/crm/dashboard JSON'idan — server-side render yo'q.
 */
(() => {
  "use strict";

  const REFRESH_MS = 30000;

  const TOKENS = {
    primary: "#6366F1",
    accent: "#22D3EE",
    success: "#10B981",
    warning: "#F59E0B",
    danger: "#EF4444",
    muted: "#8B95AD",
    border: "#26304A",
    text: "#E6EAF2",
  };

  const FUNNEL_LABELS = {
    new: "Yangi",
    contacted: "Aloqa qilindi",
    meeting: "Uchrashuv",
    deal: "Sotuv",
    lost: "Yo'qotilgan",
  };

  const ACTION_ICON = {
    send_report: "📊",
    assign_task: "📝",
    message_lead: "✉️",
    call_lead: "📞",
    escalate_owner: "⚠️",
    remind_staff: "⏰",
    change_deal: "💼",
  };
  const ACTION_LABEL = {
    send_report: "Hisobot yuborildi",
    assign_task: "Vazifa biriktirildi",
    message_lead: "Lidga xabar",
    call_lead: "Qo'ng'iroq",
    escalate_owner: "Eskalatsiya",
    remind_staff: "Xodimga eslatma",
    change_deal: "Bitim o'zgartirildi",
  };
  const LEVEL_LABEL = { autonomous: "avtonom", requires_approval: "tasdiq kerak" };
  const STATUS_LABEL = { executed: "bajarildi", pending: "kutilmoqda", cancelled: "bekor" };
  const TEMP_LABEL = { hot: "issiq", warm: "iliq", cold: "sovuq" };

  const els = {
    emptyState: document.getElementById("empty-state"),
    demoSeedBtn: document.getElementById("demo-seed-btn"),
    refreshBtn: document.getElementById("refresh-btn"),
    refreshDot: document.getElementById("refresh-dot"),
    kpiRow: document.getElementById("kpi-row"),
    trendChart: document.getElementById("trend-chart"),
    trendSub: document.getElementById("trend-sub"),
    funnel: document.getElementById("funnel"),
    funnelSub: document.getElementById("funnel-sub"),
    campaignsBody: document.getElementById("campaigns-body"),
    staffGrid: document.getElementById("staff-grid"),
    staffSub: document.getElementById("staff-sub"),
    jarvisList: document.getElementById("jarvis-list"),
    pendingSub: document.getElementById("pending-sub"),
  };

  const sections = [...document.querySelectorAll(".kpi-row, .grid-2col, main.page > .card")];

  const state = {
    workspaceId: new URLSearchParams(location.search).get("workspace_id") || null,
    chart: null,
  };

  // ---------------------------------------------------------------- utils

  function fmtInt(n) {
    return new Intl.NumberFormat("uz-UZ").format(Math.round(n || 0));
  }
  function fmtMoney(n) {
    return new Intl.NumberFormat("uz-UZ").format(Math.round(n || 0));
  }
  function fmtUsd(n) {
    return "$" + (Number(n) || 0).toFixed(2);
  }

  function relativeTime(iso) {
    if (!iso) return "";
    const then = new Date(iso).getTime();
    const diffS = Math.max(0, (Date.now() - then) / 1000);
    if (diffS < 60) return "hozirgina";
    const m = Math.floor(diffS / 60);
    if (m < 60) return `${m} daqiqa oldin`;
    const h = Math.floor(m / 60);
    if (h < 24) return `${h} soat oldin`;
    const d = Math.floor(h / 24);
    return `${d} kun oldin`;
  }

  function animateCount(el, to, formatter) {
    const from = Number(el.dataset.val || "0");
    el.dataset.val = String(to);
    if (from === to) {
      el.textContent = formatter(to);
      return;
    }
    const start = performance.now();
    const dur = 650;
    function tick(now) {
      const t = Math.min(1, (now - start) / dur);
      const eased = 1 - Math.pow(1 - t, 3);
      const val = from + (to - from) * eased;
      el.textContent = formatter(val);
      if (t < 1) requestAnimationFrame(tick);
      else el.textContent = formatter(to);
    }
    requestAnimationFrame(tick);
  }

  // Oldingi ``days``-kunlik oynaga nisbatan foizli o'zgarish (server ``kpis_prev``
  // qaytaradi — birinchi yuklanishda ham ishlaydi, mijoz tomonidagi oldingi poll'ga
  // tayanmaydi).
  function pctDelta(cur, prev) {
    if (!prev) return cur > 0 ? 100 : 0;
    return ((cur - prev) / Math.abs(prev)) * 100;
  }

  function renderDeltaChip(el, cur, prev, opts = {}) {
    const pct = pctDelta(Number(cur) || 0, Number(prev) || 0);
    const rounded = Math.round(pct);
    if (rounded === 0) {
      el.textContent = "0%";
      el.className = "kpi-delta";
      return;
    }
    const up = rounded > 0;
    const good = opts.lowerIsBetter ? !up : up;
    el.textContent = `${up ? "▲" : "▼"} ${up ? "+" : "−"}${Math.abs(rounded)}%`;
    el.className = "kpi-delta " + (good ? "up" : "down");
  }

  // ---------------------------------------------------------------- fetch

  async function fetchDashboard() {
    const params = new URLSearchParams({ days: "30" });
    if (state.workspaceId) params.set("workspace_id", state.workspaceId);
    const res = await fetch(`/v1/crm/dashboard?${params.toString()}`);
    if (!res.ok) throw new Error(`dashboard fetch: ${res.status}`);
    return res.json();
  }

  async function loadAndRender({ animate = true } = {}) {
    els.refreshDot.classList.remove("live");
    let data;
    try {
      data = await fetchDashboard();
    } catch (err) {
      console.error("CRM dashboard fetch xato:", err);
      els.refreshDot.classList.add("down");
      return;
    }
    els.refreshDot.classList.remove("down");
    els.refreshDot.classList.add("live");
    if (data.workspace_id) state.workspaceId = data.workspace_id;
    render(data, animate);
  }

  // ---------------------------------------------------------------- render

  function render(data, animate) {
    const isEmpty = (data.kpis?.leads_total || 0) === 0 && (data.jarvis_actions || []).length === 0;
    els.emptyState.hidden = !isEmpty;
    for (const s of sections) s.style.display = isEmpty ? "none" : "";

    renderKpis(data.kpis || {}, data.kpis_prev || {});
    renderTrend(data.leads_by_day || [], data.kpis || {});
    renderFunnel(data.funnel || []);
    renderCampaigns(data.campaigns || []);
    renderStaff(data.staff || []);
    renderJarvis(data.jarvis_actions || [], data.pending_actions || 0);
  }

  function renderKpis(k, prev) {
    animateCount(document.getElementById("kpi-leads-today"), k.leads_today || 0, fmtInt);
    animateCount(document.getElementById("kpi-hot"), k.hot || 0, fmtInt);
    animateCount(document.getElementById("kpi-deals"), k.deals_count || 0, fmtInt);
    animateCount(document.getElementById("kpi-revenue"), k.revenue_uzs || 0, fmtMoney);
    const cplEl = document.getElementById("kpi-cpl");
    cplEl.dataset.val = String(k.cost_per_lead_usd || 0);
    cplEl.textContent = fmtUsd(k.cost_per_lead_usd || 0);
    animateCount(document.getElementById("kpi-overdue"), k.tasks_overdue || 0, fmtInt);

    renderDeltaChip(document.getElementById("kpi-leads-today-delta"), k.leads_today, prev.leads_today);
    renderDeltaChip(document.getElementById("kpi-hot-delta"), k.hot, prev.hot);
    renderDeltaChip(document.getElementById("kpi-deals-delta"), k.deals_count, prev.deals_count);
    renderDeltaChip(document.getElementById("kpi-revenue-delta"), k.revenue_uzs, prev.revenue_uzs);
    renderDeltaChip(document.getElementById("kpi-cpl-delta"), k.cost_per_lead_usd, prev.cost_per_lead_usd, {
      lowerIsBetter: true,
    });
    renderDeltaChip(document.getElementById("kpi-overdue-delta"), k.tasks_overdue, prev.tasks_overdue, {
      lowerIsBetter: true,
    });
  }

  function gradientFill(ctx, color) {
    const g = ctx.createLinearGradient(0, 0, 0, 220);
    g.addColorStop(0, hexToRgba(color, 0.35));
    g.addColorStop(1, hexToRgba(color, 0.0));
    return g;
  }
  function hexToRgba(hex, alpha) {
    const n = parseInt(hex.replace("#", ""), 16);
    const r = (n >> 16) & 255, g = (n >> 8) & 255, b = n & 255;
    return `rgba(${r}, ${g}, ${b}, ${alpha})`;
  }

  function renderTrend(rows, kpis) {
    const total = rows.reduce((s, r) => s + (r.leads || 0), 0);
    els.trendSub.textContent = `jami ${fmtInt(total)} lid`;

    const labels = rows.map((r) => r.date.slice(5).replace("-", "."));
    const leadsData = rows.map((r) => r.leads || 0);
    const hotData = rows.map((r) => r.hot || 0);

    if (typeof Chart === "undefined" || !els.trendChart) return;
    const ctx = els.trendChart.getContext("2d");

    if (state.chart) {
      state.chart.data.labels = labels;
      state.chart.data.datasets[0].data = leadsData;
      state.chart.data.datasets[1].data = hotData;
      state.chart.update();
      return;
    }

    state.chart = new Chart(ctx, {
      type: "line",
      data: {
        labels,
        datasets: [
          {
            label: "Lidlar",
            data: leadsData,
            borderColor: TOKENS.primary,
            backgroundColor: gradientFill(ctx, TOKENS.primary),
            fill: true,
            tension: 0.35,
            pointRadius: 0,
            pointHoverRadius: 4,
            borderWidth: 2.5,
          },
          {
            label: "Issiq",
            data: hotData,
            borderColor: TOKENS.accent,
            backgroundColor: "transparent",
            fill: false,
            tension: 0.35,
            pointRadius: 0,
            pointHoverRadius: 4,
            borderWidth: 2,
            borderDash: [4, 3],
          },
        ],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        interaction: { mode: "index", intersect: false },
        plugins: {
          legend: {
            display: true,
            position: "top",
            align: "end",
            labels: { color: TOKENS.muted, boxWidth: 10, font: { size: 11, family: "Manrope" } },
          },
          tooltip: {
            backgroundColor: "#131A2A",
            borderColor: TOKENS.border,
            borderWidth: 1,
            titleColor: TOKENS.text,
            bodyColor: TOKENS.muted,
            padding: 10,
            cornerRadius: 8,
          },
        },
        scales: {
          x: {
            grid: { color: "rgba(38,48,74,0.5)", drawTicks: false },
            ticks: { color: TOKENS.muted, font: { size: 10 }, maxRotation: 0, autoSkip: true, maxTicksLimit: 8 },
            border: { color: TOKENS.border },
          },
          y: {
            beginAtZero: true,
            grid: { color: "rgba(38,48,74,0.5)" },
            ticks: { color: TOKENS.muted, font: { size: 10 }, precision: 0 },
            border: { display: false },
          },
        },
      },
    });
  }

  function renderFunnel(rows) {
    const total = rows.reduce((s, r) => s + (r.count || 0), 0);
    els.funnelSub.textContent = `${fmtInt(total)} lid`;
    const max = Math.max(1, ...rows.map((r) => r.count || 0));
    els.funnel.innerHTML = rows
      .map((r) => {
        const pct = Math.round(((r.count || 0) / max) * 100);
        const label = FUNNEL_LABELS[r.stage] || r.stage;
        return `<div class="funnel-row stage-${r.stage}">
          <div class="funnel-label">${label}</div>
          <div class="funnel-track"><div class="funnel-fill" style="width:${pct}%"></div></div>
          <div class="funnel-count">${fmtInt(r.count || 0)}</div>
        </div>`;
      })
      .join("");
  }

  function renderCampaigns(rows) {
    if (!rows.length) {
      els.campaignsBody.innerHTML = '<tr class="empty-row"><td colspan="7">Kampaniyalar yo\'q</td></tr>';
      return;
    }
    els.campaignsBody.innerHTML = rows
      .map((c) => {
        const roiPct = (c.roi || 0) * 100;
        const roiCls = roiPct >= 0 ? "pos" : "neg";
        const roiSign = roiPct >= 0 ? "+" : "";
        return `<tr>
          <td class="campaign-name">${escapeHtml(c.name)}<span class="sub">${fmtInt(c.post_reach || 0)} qamrov</span></td>
          <td>${fmtInt(c.post_reach || 0)}</td>
          <td>$${fmtInt(c.spend_usd || 0)}</td>
          <td>${fmtInt(c.leads || 0)}</td>
          <td>${fmtInt(c.deals || 0)}</td>
          <td>${fmtMoney(c.revenue_uzs || 0)} so'm</td>
          <td><span class="roi-badge ${roiCls}">${roiSign}${roiPct.toFixed(0)}%</span></td>
        </tr>`;
      })
      .join("");
  }

  function renderStaff(rows) {
    els.staffSub.textContent = `${rows.length} xodim`;
    els.staffGrid.innerHTML = rows
      .map((s) => {
        const doneTotal = (s.done_tasks || 0) + (s.open_tasks || 0);
        const pct = doneTotal > 0 ? Math.round(((s.done_tasks || 0) / doneTotal) * 100) : 0;
        const r = 26;
        const c = 2 * Math.PI * r;
        const offset = c - (pct / 100) * c;
        const overdueBadge = s.overdue > 0
          ? `<span class="staff-overdue-badge">⏰ ${s.overdue} muddati o'tgan</span>`
          : "";
        const avgText = s.avg_response_h
          ? `~${s.avg_response_h.toFixed(1)} soat javob`
          : "javob vaqti: —";
        return `<div class="staff-card">
          <div class="ring">
            <svg width="64" height="64" viewBox="0 0 64 64">
              <circle class="ring-track" cx="32" cy="32" r="${r}"></circle>
              <circle class="ring-fill" cx="32" cy="32" r="${r}"
                stroke-dasharray="${c}" stroke-dashoffset="${offset}"></circle>
              <text class="ring-label" x="32" y="36" text-anchor="middle">${pct}%</text>
            </svg>
          </div>
          <div class="staff-info">
            <div class="staff-name">${escapeHtml(s.name)}</div>
            <div class="staff-meta">
              <span>${s.open_tasks || 0} ochiq</span>
              <span>${s.done_tasks || 0} bajarilgan</span>
              <span>${avgText}</span>
            </div>
            ${overdueBadge}
          </div>
        </div>`;
      })
      .join("");
  }

  function renderJarvis(rows, pending) {
    els.pendingSub.textContent = `${fmtInt(pending)} ta tasdiq kutilmoqda`;
    if (!rows.length) {
      els.jarvisList.innerHTML = '<li class="jarvis-row"><div class="jarvis-main">Hali harakatlar yo\'q</div></li>';
      return;
    }
    els.jarvisList.innerHTML = rows.map(jarvisRowHtml).join("");
    els.jarvisList.querySelectorAll("[data-decide]").forEach((btn) => {
      btn.addEventListener("click", onDecisionClick);
    });
  }

  // Uzunlikni kesish RAW matnda bo'lishi kerak, escape qilingan HTML'da emas —
  // aks holda "&qu..." kabi yarim-entity artefaktlar chiqadi.
  function truncate(s, n) {
    const str = String(s || "");
    return str.length > n ? str.slice(0, n) + "…" : str;
  }

  function fmtDueLabel(iso) {
    if (!iso) return "—";
    const d = new Date(iso);
    if (Number.isNaN(d.getTime())) return "—";
    const hh = String(d.getHours()).padStart(2, "0");
    const mm = String(d.getMinutes()).padStart(2, "0");
    const day = String(d.getDate()).padStart(2, "0");
    const month = String(d.getMonth() + 1).padStart(2, "0");
    return `${hh}:${mm}, ${day}.${month}`;
  }

  // Har bir Jarvis harakat turi uchun inson o'qiydigan xulosa — payload'dagi
  // maydonlardan quriladi, hech qachon xom JSON ko'rsatilmaydi.
  function jarvisTitle(a) {
    const p = a.payload || {};
    switch (a.type) {
      case "message_lead": {
        const name = p.lead_name || p.name || "Lid";
        const temp = p.temperature ? ` (${TEMP_LABEL[p.temperature] || p.temperature})` : "";
        const text = truncate(p.reply_text || p.text || "", 70);
        return `Lidga xabar · ${name}${temp} — «${text}»`;
      }
      case "call_lead": {
        const name = p.lead_name || p.name || "Lid";
        const reason = truncate(p.reason || "", 60);
        return `Qo'ng'iroq · ${name}${reason ? " — " + reason : ""}`;
      }
      case "assign_task": {
        const staffName = p.staff_name || "Xodim";
        const title = truncate(p.title || "", 60);
        const due = p.due_at ? ` · muddat ${fmtDueLabel(p.due_at)}` : "";
        return `Vazifa · ${staffName}: ${title}${due}`;
      }
      case "remind_staff": {
        const staffName = p.staff_name || "Xodim";
        const title = truncate(p.title || "", 60);
        return `Eslatma · ${staffName}: ${title}`;
      }
      case "escalate_owner": {
        const staffName = p.staff_name || "Xodim";
        const title = truncate(p.title || "", 60);
        const hours = p.hours_overdue != null ? ` (${p.hours_overdue} soat kechikdi)` : "";
        return `Eskalatsiya · ${staffName}, ${title}${hours}`;
      }
      case "send_report": {
        const leads = p.leads ?? 0;
        const hot = p.hot ?? 0;
        const overdue = p.overdue ?? 0;
        return `Kunlik hisobot yuborildi · ${leads} lid / ${hot} issiq / ${overdue} kechikkan`;
      }
      default:
        return `${ACTION_ICON[a.type] || "🤖"} ${ACTION_LABEL[a.type] || a.type}`;
    }
  }

  function jarvisRowHtml(a) {
    const icon = ACTION_ICON[a.type] || "🤖";
    const isPending = a.status === "pending";
    const actions = isPending
      ? `<div class="decision-actions">
          <button class="decision-btn yes" data-decide="yes" data-id="${a.id}">✅ Ha</button>
          <button class="decision-btn no" data-decide="no" data-id="${a.id}">❌ Yo'q</button>
        </div>`
      : "";
    return `<li class="jarvis-row" id="jarvis-row-${a.id}">
      <div class="jarvis-icon">${icon}</div>
      <div class="jarvis-main">
        <div class="jarvis-title">${escapeHtml(jarvisTitle(a))}</div>
        <div class="jarvis-time">${relativeTime(a.created_at)}</div>
      </div>
      <div class="jarvis-right">
        <span class="chip level-${a.level}">${LEVEL_LABEL[a.level] || a.level}</span>
        <span class="chip status-${a.status}">${isPending ? '<span class="pulse-dot"></span>' : ""}${STATUS_LABEL[a.status] || a.status}</span>
        ${actions}
      </div>
    </li>`;
  }

  async function onDecisionClick(ev) {
    const btn = ev.currentTarget;
    const id = btn.dataset.id;
    const decision = btn.dataset.decide;
    const row = document.getElementById(`jarvis-row-${id}`);
    if (!row) return;
    row.classList.add("updating");
    row.querySelectorAll(".decision-btn").forEach((b) => (b.disabled = true));
    try {
      const res = await fetch(`/v1/crm/actions/${id}/decision`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ decision }),
      });
      if (!res.ok) throw new Error(`decision: ${res.status}`);
      const result = await res.json();
      row.classList.remove("updating");
      const statusChip = row.querySelector(".jarvis-right .chip.status-pending, .jarvis-right .chip[class*='status-']");
      if (statusChip) {
        statusChip.className = `chip status-${result.status}`;
        statusChip.textContent = STATUS_LABEL[result.status] || result.status;
      }
      const actionsWrap = row.querySelector(".decision-actions");
      if (actionsWrap) actionsWrap.remove();
    } catch (err) {
      console.error("CRM decision xato:", err);
      row.classList.remove("updating");
      row.querySelectorAll(".decision-btn").forEach((b) => (b.disabled = false));
    }
  }

  function escapeHtml(s) {
    return String(s)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  // ---------------------------------------------------------------- demo seed + wiring

  async function runDemoSeed() {
    els.demoSeedBtn.disabled = true;
    els.demoSeedBtn.textContent = "Yuklanmoqda…";
    try {
      const params = state.workspaceId ? `?workspace_id=${state.workspaceId}` : "";
      const res = await fetch(`/v1/crm/demo-seed${params}`, { method: "POST" });
      if (!res.ok) throw new Error(`demo-seed: ${res.status}`);
      const result = await res.json();
      if (result.workspace_id) state.workspaceId = result.workspace_id;
      await loadAndRender();
    } catch (err) {
      console.error("CRM demo-seed xato:", err);
    } finally {
      els.demoSeedBtn.disabled = false;
      els.demoSeedBtn.textContent = "Demo ma'lumot yuklash";
    }
  }

  els.demoSeedBtn?.addEventListener("click", runDemoSeed);
  els.refreshBtn?.addEventListener("click", () => loadAndRender());

  loadAndRender();
  setInterval(() => loadAndRender(), REFRESH_MS);
})();
