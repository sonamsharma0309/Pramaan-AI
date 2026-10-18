// Appeals list and the appeal workspace: letter | cited policy clauses | chart evidence, autosave, regenerate, citation highlighting.
import { api, download } from "../api.js";
import { $, $$, debounce, emptyBox, errorBox, esc, fmtDate, go, icon, modal, money, pct, pill, skeleton, toast, withBusy } from "../ui.js";
import { criteriaCard, evidenceCards, policyCards, strengthCard } from "./analysis.js";
import { frame } from "./shell.js";

export async function appealsList(root, key) {
  const F = frame(root, key, "/appeals", key === "b" ? "Appeals" : "My appeals", "Drafts, submissions and outcomes.");
  const load = async () => {
    F.view.innerHTML = skeleton(4);
    try {
      const r = await api("/appeals");
      F.view.innerHTML = r.appeals.length ? `<div class="tbl-wrap"><table class="tbl"><thead><tr><th>Claim</th><th>Patient</th><th>Payer</th><th>Amount</th><th>Status</th><th>Strength</th><th>Recovered</th></tr></thead><tbody>${r.appeals.map((a) => `<tr data-id="${a.id}"><td><b>${esc(a.claim_no)}</b><div class="small muted">${fmtDate(a.created_at)}</div></td><td>${esc(a.patient_name)}</td><td>${esc(a.payer)}</td><td>${money(a.denied_amount)}</td><td>${pill(a.status)}</td><td>${pct(a.win_probability)} ${a.model_kind === "synthetic" ? '<span class="badge" title="Estimate based on synthetic data">syn</span>' : ""}</td><td>${a.recovered_amount ? `<b style="color:var(--win)">${money(a.recovered_amount)}</b>` : "–"}</td></tr>`).join("")}</tbody></table></div>`
        : emptyBox("No appeals yet", "Open a denied claim and choose Generate appeal.", `<a class="btn btn-ink" href="#/${key}/claims">Go to ${key === "b" ? "denials" : "my cases"}</a>`);
      $$("tbody tr", F.view).forEach((tr) => tr.addEventListener("click", () => go(`#/${key}/appeal/${tr.dataset.id}`)));
    } catch (e) { F.view.innerHTML = errorBox(e.message, true); $("[data-retry]", F.view)?.addEventListener("click", load); }
  };
  load();
}

const CITE = /\[([PE]\d+)\]/g;
const renderLetter = (text) => esc(text).replace(CITE, (_, r) => `<button class="cite" data-ref="${r}" aria-label="Show source ${r}">[${r}]</button>`);

export async function appealView(root, key, id) {
  const F = frame(root, key, "/appeals", "Appeal", "");
  let a, ai = false;
  try { [a, ai] = await Promise.all([api(`/appeals/${id}`).then((r) => r.appeal), api("/health").then((h) => h.integrations.ai).catch(() => false)]); } catch (e) { F.view.innerHTML = errorBox(e.message); return; }
  const c = a.claim, an = a.analysis;
  $(".top h1", root).textContent = `Appeal for ${c.patient_name}`;
  $(".top .row.wrap", root).insertAdjacentHTML("beforeend", `<a class="btn btn-ghost btn-sm" href="#/${key}/claim/${c.id}">Back to claim</a>`);
  let editing = false, letter = a.letter;
  F.view.innerHTML = `<div class="ws3"><div><div class="row wrap noprint" style="margin-bottom:10px"><button class="btn btn-ink btn-sm" id="pdf">${icon("download")} PDF packet</button><button class="btn btn-ghost btn-sm" id="ed">Edit letter</button><button class="btn btn-ghost btn-sm" id="cp">${icon("copy")} Copy</button><button class="btn btn-ghost btn-sm" id="rg">${icon("refresh")} Regenerate${ai ? " with Claude" : ""}</button><span class="savestate" id="ss" aria-live="polite"></span></div>
      <div id="lv"></div><p class="small muted noprint" style="margin-top:8px">Written by <b>${a.engine.startsWith("claude") ? "Claude" : "the template engine"}</b> (${esc(a.engine)}) in ${a.gen_seconds}s · Packet ${esc(a.packet_id)}. Click a <span class="cite">[P1]</span> or <span class="cite">[E1]</span> citation to see its source.</p></div>
    <div class="noprint"><p class="colhead">Cited policy clauses</p><div class="card scroll" id="pc">${policyCards(an.policy_hits)}</div></div>
    <div class="noprint col3"><p class="colhead">Chart evidence</p><div class="card scroll" id="ec">${evidenceCards(an.evidence)}</div></div></div>
    <div class="grid2e noprint"><div>${strengthCard(an, true)}<div class="card"><h3>Track this appeal</h3><div class="field"><label class="lb" for="st">Status</label><select class="inp" id="st">${[["drafted", "Drafted"], ["submitted", "Submitted to payer"], ["won", "Won (paid in full)"], ["partial", "Partly won"], ["lost", "Lost"]].map(([v, l]) => `<option value="${v}" ${a.status === v ? "selected" : ""}>${l}</option>`).join("")}</select></div>
      <div class="field ${["won", "partial"].includes(a.status) ? "" : "hide"}" id="recw"><label class="lb" for="rec">Amount recovered (USD)</label><input class="inp" id="rec" type="number" min="0" step="0.01" value="${a.recovered_amount || c.denied_amount || ""}"></div>
      <button class="btn btn-ink btn-sm" id="ssb">Update status</button><p class="srcnote">Recorded outcomes train the win-probability model (scripts/train_predictor.py).</p></div></div><div>${criteriaCard(an)}</div></div>`;
  const lv = $("#lv", F.view), ss = $("#ss", F.view);
  const drawLetter = () => {
    if (editing) { lv.innerHTML = `<textarea class="letter" id="letter" spellcheck="true" aria-label="Appeal letter">${esc(letter)}</textarea>`; const t = $("#letter", lv); const fit = () => { t.style.height = "auto"; t.style.height = Math.max(520, t.scrollHeight + 4) + "px"; }; fit(); t.addEventListener("input", () => { letter = t.value; fit(); saveSoon(); }); }
    else { lv.innerHTML = `<div class="paperview" id="pv">${renderLetter(letter)}</div>`; $$(".cite", lv).forEach((b) => b.addEventListener("click", () => showSource(b.dataset.ref))); }
    $("#ed", F.view).textContent = editing ? "Done editing" : "Edit letter";
  };
  const flash = (el) => { el.classList.add("hl"); setTimeout(() => el.classList.remove("hl"), 2400); };
  function showSource(ref) { $$(".cite", lv).forEach((b) => b.classList.toggle("on", b.dataset.ref === ref)); const el = $("#src-" + ref, F.view); if (el) { el.scrollIntoView({ behavior: "smooth", block: "center" }); flash(el); } else toast(`Source ${ref} is not in this analysis`, "err"); }
  $$("[data-cite]", F.view).forEach((b) => { const go2 = () => { $$(".cite", lv).forEach((x) => x.classList.toggle("on", x.dataset.ref === b.dataset.cite)); $(`.cite[data-ref="${b.dataset.cite}"]`, lv)?.scrollIntoView({ block: "center", behavior: "smooth" }); flash(b.closest(".src")); }; b.addEventListener("click", go2); b.addEventListener("keydown", (e) => e.key === "Enter" && go2()); });
  const save = async () => { ss.className = "savestate"; ss.textContent = "Saving…"; try { await api(`/appeals/${id}`, { method: "PATCH", body: { letter } }); ss.className = "savestate ok"; ss.textContent = "Saved"; } catch (e) { ss.className = "savestate err"; ss.textContent = "Not saved: " + e.message; } };
  const saveSoon = debounce(save, 1200);
  $("#ed", F.view).addEventListener("click", () => { editing = !editing; drawLetter(); if (!editing) save(); });
  $("#cp", F.view).addEventListener("click", async () => { try { await navigator.clipboard.writeText(letter); toast("Letter copied", "ok"); } catch { toast("Copy failed. Select the text and copy manually.", "err"); } });
  $("#pdf", F.view).addEventListener("click", (e) => withBusy(e.currentTarget, async () => { try { await save(); await download(`/appeals/${id}/pdf`, `appeal-${c.claim_no}.pdf`); } catch (er) { toast(er.message, "err"); } }));
  $("#rg", F.view).addEventListener("click", () => { const m = modal(`<h3>Regenerate this letter?</h3><p class="muted">The letter is rewritten from the latest claim, policy and chart data. Your manual edits will be replaced.</p><div class="row" style="justify-content:flex-end"><button class="btn btn-ghost" data-close>Keep my version</button><button class="btn btn-primary" id="yes">Regenerate</button></div>`);
    $("#yes", m.el).addEventListener("click", (e) => withBusy(e.currentTarget, async () => { try { await api(`/appeals/${id}/regenerate`, { method: "POST" }); m.close(); toast("Letter regenerated", "ok"); go(location.hash); } catch (er) { toast(er.message, "err"); } })); });
  $("#st", F.view).addEventListener("change", (e) => $("#recw", F.view).classList.toggle("hide", !["won", "partial"].includes(e.target.value)));
  $("#ssb", F.view).addEventListener("click", (e) => withBusy(e.currentTarget, async () => { const s = $("#st", F.view).value; const body = { status: s }; if (["won", "partial"].includes(s)) body.recovered_amount = parseFloat($("#rec", F.view).value) || 0; try { await api(`/appeals/${id}`, { method: "PATCH", body }); toast("Status updated", "ok"); } catch (er) { toast(er.message, "err"); } }));
  drawLetter();
}
