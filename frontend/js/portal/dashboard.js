// Dashboard with real charts (Chart.js from CDN) fed by /api/dashboard, plus date-range and payer filters.
import { api, auth } from "../api.js";
import { $, $$, emptyBox, errorBox, esc, go, icon, money, pct, skeleton, statusLabel, toast, withBusy } from "../ui.js";
import { frame } from "./shell.js";

let chartLib = null;
const loadChart = () => (chartLib ||= new Promise((res, rej) => {
  if (window.Chart) return res(window.Chart);
  const s = document.createElement("script"); s.src = "https://cdn.jsdelivr.net/npm/chart.js@4.4.4/dist/chart.umd.min.js";
  s.onload = () => res(window.Chart); s.onerror = () => { chartLib = null; rej(new Error("Chart library could not be loaded (offline?)")); }; document.head.appendChild(s);
}));
const css = (v) => getComputedStyle(document.documentElement).getPropertyValue(v).trim();
const deadlineBadge = (d) => d.days_left == null ? `<span class="dl na">n/a</span>` : `<span class="dl ${d.days_left <= 0 ? "gone" : d.days_left < 14 ? "urgent" : d.days_left < 45 ? "soon" : "ok"}">${d.days_left <= 0 ? "window passed" : d.days_left + " days left"}</span>`;
export { deadlineBadge };

export async function dashboard(root, key) {
  const biller = key === "b";
  const F = frame(root, key, "", biller ? "Dashboard" : `Hello, ${auth.user.name.split(" ")[0]}`, biller ? "Revenue at risk, appeals in motion and what you have won back." : "Your denied claims and appeals in one place.",
    `<a class="btn btn-primary" href="#/${key}/${biller ? "claims" : "start"}">${icon("plus")} ${biller ? "Add denial" : "Start an appeal"}</a>`);
  const state = { date_from: "", date_to: "", payer: "" }; const charts = [];
  F.view.innerHTML = `<div class="toolbar" id="flt"><label class="small muted">From <input class="inp" type="date" id="df" aria-label="From date"></label><label class="small muted">To <input class="inp" type="date" id="dt" aria-label="To date"></label>
    <select class="inp" id="dp" aria-label="Payer"><option value="">All payers</option></select><button class="btn btn-ghost btn-sm" id="dr">Reset</button></div><div id="dash">${skeleton(5)}</div>`;
  async function load() {
    const box = $("#dash", F.view); charts.splice(0).forEach((c) => c.destroy());
    try {
      const q = new URLSearchParams(Object.entries(state).filter(([, v]) => v)).toString();
      const d = await api("/dashboard" + (q ? "?" + q : "")); const t = d.totals;
      const sel = $("#dp", F.view); if (sel.options.length === 1) d.payers.forEach((p) => sel.add(new Option(p, p)));
      if (!t.claims) {
        const filtered = state.date_from || state.date_to || state.payer;
        box.innerHTML = emptyBox(filtered ? "No claims match these filters" : biller ? "No denials yet" : "No cases yet", filtered ? "Try a wider date range or another payer." : "Import an 835 remittance file or load fictional sample data to see Pramaan AI work end to end.",
          filtered ? "" : `<div class="row wrap" style="justify-content:center">${biller ? `<a class="btn btn-ink" href="#/b/import">${icon("upload")} Import 835</a>` : `<a class="btn btn-ink" href="#/p/start">Start an appeal</a>`}<button class="btn btn-ghost" id="seed">Load sample data</button></div>`);
        $("#seed", box)?.addEventListener("click", (e) => withBusy(e.currentTarget, async () => { try { const r = await api("/claims/seed-demo", { method: "POST" }); toast(`Loaded ${r.imported} fictional sample denials`, "ok"); load(); } catch (er) { toast(er.message, "err"); } }));
        return;
      }
      box.innerHTML = `<div class="kpis">
        <div class="kpi hl"><span>Recovered</span><b>${money(t.recovered)}</b><small>${t.win_rate == null ? "no decided appeals yet" : pct(t.win_rate) + " win rate (" + t.decided + " decided)"}</small></div>
        <div class="kpi"><span>${biller ? "Revenue at risk" : "In dispute"}</span><b>${money(t.at_risk_value)}</b><small>${t.pending_appeals} still need an appeal</small></div>
        <div class="kpi"><span>Appeals drafted</span><b>${t.appeals}</b><small>of ${t.claims} denied claims</small></div>
        <div class="kpi"><span>Average draft time</span><b>${t.avg_generation_seconds}s</b><small>from denial to letter</small></div></div>
      <div id="chartwrap"><div class="charts"><div class="card"><h3>Denied vs recovered by month</h3><div class="chartbox"><canvas id="c1" aria-label="Denied versus recovered amount by month" role="img"></canvas></div></div>
        <div class="card"><h3>Appeals by status</h3><div class="chartbox"><canvas id="c3" aria-label="Claims by status" role="img"></canvas></div></div></div>
        <div class="charts2"><div class="card"><h3>Win rate by denial category</h3><div class="chartbox sm"><canvas id="c2" aria-label="Win rate by denial category" role="img"></canvas></div><p class="small muted" style="margin:8px 0 0" id="c2n"></p></div>
        <div class="card"><h3>Top denial codes</h3><div class="chartbox sm"><canvas id="c4" aria-label="Top denial codes" role="img"></canvas></div></div></div></div>
      <div class="grid2e"><div class="card"><h3>Appeal deadlines</h3><div class="list">${d.deadlines.length ? d.deadlines.map((x) => `<div class="li"><div><a href="#/${key}/claim/${x.id}">${esc(x.patient_name)}</a><div class="small muted">${esc(x.claim_no)} · ${money(x.amount)}</div></div>${deadlineBadge({ days_left: x.days_left })}</div>`).join("") : `<p class="muted">Nothing waiting.</p>`}</div>
        <p class="srcnote">Deadlines use rules from appeal_rules.csv. Rows not marked verified there are baselines: confirm with the payer.</p></div>
        <div class="card"><h3>${biller ? "Exposure by payer" : "Where claims stand"}</h3><div class="list">${(biller ? d.payer_exposure.map((p) => `<div class="li"><span>${esc(p.payer)}</span><b>${money(p.amount)}</b></div>`) : Object.entries(d.by_status).map(([s, n]) => `<div class="li"><span>${statusLabel(s)}</span><b>${n}</b></div>`)).join("") || `<p class="muted">No open claims.</p>`}</div>
        <p class="srcnote">Win estimates: <span class="badge ${d.model.kind === "trained" ? "ok" : ""}">${d.model.kind === "trained" ? "model learned from " + d.model.n + " outcomes" : "synthetic model (needs " + d.model.min_outcomes + " real outcomes to learn)"}</span></p></div></div>`;
      try {
        const Chart = await loadChart(); const ink = css("--ink"), grid = css("--line2"), accent = css("--accent"), win = css("--win"), red = css("--red");
        Chart.defaults.color = css("--muted"); Chart.defaults.font.family = css("--body"); Chart.defaults.borderColor = grid;
        const mk = (id, cfg) => charts.push(new Chart($("#" + id, box), cfg));
        const opts = { responsive: true, maintainAspectRatio: false };
        mk("c1", { type: "bar", data: { labels: d.monthly.map((m) => m.month), datasets: [{ label: "Denied", data: d.monthly.map((m) => m.denied), backgroundColor: red + "AA", borderRadius: 6 }, { label: "Recovered", data: d.monthly.map((m) => m.recovered), backgroundColor: win, borderRadius: 6 }] }, options: { ...opts, scales: { y: { ticks: { callback: (v) => "$" + Number(v).toLocaleString() } } } } });
        const sc = { denied: red, appeal_ready: accent, appealed: "#D8A024", recovered: win, lost: "#8796A5", written_off: "#C3CDD8" };
        mk("c3", { type: "doughnut", data: { labels: Object.keys(d.by_status).map(statusLabel), datasets: [{ data: Object.values(d.by_status), backgroundColor: Object.keys(d.by_status).map((s) => sc[s] || "#999"), borderWidth: 0 }] }, options: { ...opts, cutout: "62%", plugins: { legend: { position: "bottom" } } } });
        const wc = d.win_by_category; mk("c2", { type: "bar", data: { labels: wc.map((c) => c.category), datasets: [{ label: "Win rate %", data: wc.map((c) => (c.win_rate == null ? 0 : Math.round(c.win_rate * 100))), backgroundColor: accent, borderRadius: 6 }] }, options: { ...opts, indexAxis: "y", plugins: { legend: { display: false } }, scales: { x: { max: 100, ticks: { callback: (v) => v + "%" } } } } });
        $("#c2n", box).textContent = wc.every((c) => c.win_rate == null) ? "No decided appeals yet. Mark appeals as won or lost to see win rates." : "";
        mk("c4", { type: "bar", data: { labels: d.top_codes.map((c) => "CARC " + c.code), datasets: [{ label: "Claims", data: d.top_codes.map((c) => c.count), backgroundColor: ink + "99", borderRadius: 6 }] }, options: { ...opts, plugins: { legend: { display: false } }, scales: { y: { ticks: { precision: 0 } } } } });
      } catch (e) { $("#chartwrap", box).innerHTML = `<div class="card">${errorBox(e.message + ". The numbers below are still live.")}</div>`; }
    } catch (e) { box.innerHTML = errorBox(e.message, true); $("[data-retry]", box)?.addEventListener("click", load); }
  }
  const bind = (id, k) => $(id, F.view).addEventListener("change", (e) => { state[k] = e.target.value; load(); });
  bind("#df", "date_from"); bind("#dt", "date_to"); bind("#dp", "payer");
  $("#dr", F.view).addEventListener("click", () => { Object.keys(state).forEach((k) => (state[k] = "")); $$("#flt input,#flt select", F.view).forEach((i) => (i.value = "")); load(); });
  load();
}
