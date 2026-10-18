// Shared analysis rendering: win gauge + factors, criteria check, policy clauses, chart evidence, and the "generating" dialog.
import { api } from "../api.js";
import { $, $$, esc, go, icon, modal, pct, toast } from "../ui.js";

export function gauge(p) {
  const c = 2 * Math.PI * 46; const col = p >= 0.6 ? "var(--win)" : p >= 0.4 ? "var(--accent)" : "var(--red)";
  return `<svg viewBox="0 0 112 112" role="img" aria-label="Estimated chance ${Math.round(p * 100)} percent"><circle cx="56" cy="56" r="46" fill="none" stroke="var(--line2)" stroke-width="10"/><circle cx="56" cy="56" r="46" fill="none" stroke="${col}" stroke-width="10" stroke-linecap="round" stroke-dasharray="${(p * c).toFixed(1)} ${c.toFixed(1)}" transform="rotate(-90 56 56)"/></svg>`;
}

export const policyCards = (hits) => hits.map((h) => `<div class="src" id="src-${h.ref}" data-ref="${h.ref}"><span class="ref" tabindex="0" role="button" data-cite="${h.ref}">${h.ref}</span> <b>${esc(h.title)}</b> <span class="small muted">· ${esc(h.payer)} · relevance ${h.score}</span><div class="quote">${esc(h.text).replace(/\n/g, "<br>")}</div></div>`).join("")
  || `<div class="lockbox">No payer policy was found for this service, so the letter states that honestly and relies on chart evidence. Upload this payer's policy in the Policy library to improve it.</div>`;
export const evidenceCards = (ev) => ev.map((e) => `<div class="src" id="src-${e.ref}" data-ref="${e.ref}"><span class="ref" tabindex="0" role="button" data-cite="${e.ref}">${e.ref}</span> ${esc(e.text)}<div class="small muted">${esc(e.labels.join(", "))}</div></div>`).join("")
  || `<div class="lockbox">No chart notes attached yet. Add notes on the claim's Clinical notes tab.</div>`;

export function strengthCard(a, compact = false) {
  const pr = a.prediction;
  return `<div class="card" style="margin-bottom:16px"><h3>Appeal strength</h3><div class="gauge">${gauge(pr.probability)}<div><b>${pct(pr.probability)}</b><div class="small muted">${esc(a.denial.category_label)} · CARC ${esc(a.denial.code)}<br>${pr.days_since_denial} days since denial</div></div></div>
    <div style="margin-top:12px">${pr.factors.slice(0, compact ? 4 : 6).map((f) => `<div class="factor"><span>${esc(f.name)}</span><span class="${f.impact >= 0 ? "pos" : "neg"}">${f.impact >= 0 ? "+" : ""}${f.impact}</span></div>`).join("")}</div>
    <p class="srcnote">${pr.model_kind === "trained" ? `<span class="badge ok">learned from recorded outcomes</span>` : `<span class="badge">estimate based on synthetic data</span>`} Use it to sort work, not as a promise.</p></div>`;
}

export function criteriaCard(a) {
  const rows = a.criteria.map((c) => `<div class="crit"><span class="st ${c.status}">${icon(c.status === "met" ? "check" : c.status === "partial" ? "alert" : "x")}</span><div><div>${esc(c.text)}</div><div class="small muted"><span class="ref">${c.policy_ref}</span>${c.evidence_ref ? ` supported by <span class="ref">${c.evidence_ref}</span>` : " no matching chart evidence found"}</div></div></div>`).join("");
  return `<div class="card" style="margin-bottom:16px"><h3>Policy criteria check</h3>${rows || '<p class="muted">No criteria available for this claim.</p>'}<p class="small muted" style="margin:10px 0 0">Coverage ${pct(a.coverage)} · policy match ${pct(a.policy_match)}${a.embeddings ? " · semantic retrieval on" : ""}</p></div>`
    + (a.missing_docs.length ? `<div class="card" style="margin-bottom:16px"><h3>To strengthen this appeal</h3><ul style="margin:0;padding-left:18px">${a.missing_docs.map((m) => `<li style="margin-bottom:6px">${esc(m)}</li>`).join("")}</ul></div>` : "");
}

export function analysisHtml(a) {
  return strengthCard(a) + criteriaCard(a) + `<div class="card" style="margin-bottom:16px"><h3>Policy clauses used</h3>${policyCards(a.policy_hits)}</div><div class="card"><h3>Chart evidence used</h3>${evidenceCards(a.evidence)}</div>`;
}

export async function generate(c, key) {
  const steps = ["Reading the denial", "Searching the payer policy", "Pulling evidence from the chart", "Drafting the letter"];
  const m = modal(`<h3>Building your appeal</h3><div class="gen" id="gen" role="status" aria-live="polite">${steps.map((s, i) => `<div data-i="${i}"><span class="dot">${icon("check")}</span>${s}</div>`).join("")}</div>`);
  let i = 0; const mark = () => $$("#gen div", m.el).forEach((d, j) => { d.className = j < i ? "done" : j === i ? "on" : ""; });
  mark(); const t = setInterval(() => { if (i < steps.length - 1) { i++; mark(); } }, 450);
  try { const r = await api(`/claims/${c.id}/appeal`, { method: "POST" }); clearInterval(t); i = steps.length; mark(); setTimeout(() => { m.close(); toast(`Appeal drafted in ${r.seconds}s (${r.engine.split(":")[0]})`, "ok"); go(`#/${key}/appeal/${r.appeal_id}`); }, 350); }
  catch (e) { clearInterval(t); m.close(); toast(e.message, "err"); }
}
