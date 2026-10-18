// Claims: server-side table (search/filter/sort/pagination/bulk), claim detail with timeline, 835 import, patient wizard.
import { api, auth, download } from "../api.js";
import { $, $$, debounce, emptyBox, errorBox, esc, fieldError, fmtDate, go, icon, modal, money, money2, pct, pill, skeleton, toast, withBusy } from "../ui.js";
import { analysisHtml, generate } from "./analysis.js";
import { deadlineBadge } from "./dashboard.js";
import { autocomplete, frame } from "./shell.js";

const STATUS = [["", "All statuses"], ["denied", "Denied"], ["appeal_ready", "Appeal ready"], ["appealed", "Sent"], ["recovered", "Recovered"], ["lost", "Lost"]];
const EVENT = { imported: "Imported from remittance", created: "Claim created", notes_added: "Clinical notes added", analysed: "Analysis run", appeal_generated: "Appeal generated", appeal_regenerated: "Appeal regenerated",
  appeal_submitted: "Appeal submitted to payer", appeal_won: "Appeal won", appeal_partial: "Appeal partly won", appeal_lost: "Appeal lost", appeal_drafted: "Moved back to draft", status_changed: "Status changed", edited: "Claim edited" };

export async function claimsList(root, key) {
  const biller = key === "b";
  const F = frame(root, key, "/claims", biller ? "Denials" : "My cases", biller ? "Every denied claim. Sort by deadline or value, then act in bulk." : "Each denial you are fighting.",
    `<button class="btn btn-primary" id="add">${icon("plus")} ${biller ? "Add denial" : "Add case"}</button>`);
  const S = { status: "", q: "", payer: "", category: "", sort: "id", order: "desc", page: 1, page_size: 12 }; const picked = new Set();
  let cats = [], payers = [];
  try { [cats, payers] = await Promise.all([api("/codes/categories").then((r) => r.categories), api("/dashboard").then((r) => r.payers)]); } catch { /* filters degrade */ }
  F.view.innerHTML = `<div class="toolbar"><input class="inp grow" id="q" placeholder="Search patient, claim, payer, CPT" aria-label="Search claims">
    <select class="inp" id="st" aria-label="Status">${STATUS.map(([v, l]) => `<option value="${v}">${l}</option>`).join("")}</select>
    <select class="inp" id="py" aria-label="Payer"><option value="">All payers</option>${payers.map((p) => `<option>${esc(p)}</option>`).join("")}</select>
    <select class="inp" id="ct" aria-label="Denial category"><option value="">All categories</option>${cats.map((c) => `<option value="${c.key}">${esc(c.label)}</option>`).join("")}</select></div>
    <div class="toolbar"><button class="btn btn-ghost btn-sm" id="x1">${icon("download")} Claims CSV</button><button class="btn btn-ghost btn-sm" id="x2">${icon("download")} Outcomes CSV</button><button class="btn btn-ghost btn-sm" id="x3">${icon("download")} All PDF packets (ZIP)</button></div>
    <div id="bulk"></div><div id="tbl">${skeleton(5)}</div>`;
  const exp = (id, path, name) => $(id, F.view).addEventListener("click", (e) => withBusy(e.currentTarget, async () => { try { await download(path, name); } catch (er) { toast(er.message, "err"); } }));
  exp("#x1", "/export/claims.csv", "claims.csv"); exp("#x2", "/export/outcomes.csv", "outcomes.csv"); exp("#x3", "/export/packets.zip", "appeal-packets.zip");
  const bulkBar = () => { $("#bulk", F.view).innerHTML = picked.size ? `<div class="bulkbar"><b>${picked.size} selected</b><button class="btn btn-ink btn-sm" id="ba">${icon("search")} Run analysis</button><button class="btn btn-primary btn-sm" id="bg">${icon("ai")} Generate appeals</button><button class="btn btn-ghost btn-sm" id="bc">Clear</button></div>` : "";
    $("#bc", F.view)?.addEventListener("click", () => { picked.clear(); load(); });
    $("#ba", F.view)?.addEventListener("click", (e) => withBusy(e.currentTarget, async () => { try {
      const r = (await api("/claims/bulk/analyze", { method: "POST", body: { ids: [...picked] } })).results;
      modal(`<h3>Analysis results</h3><div class="tbl-wrap"><table class="tbl" style="min-width:420px"><thead><tr><th>Claim</th><th>Win estimate</th><th>Evidence coverage</th><th>Policy</th></tr></thead><tbody>${r.map((x) => x.ok ? `<tr style="cursor:default"><td>${esc(x.claim_no)}</td><td>${pct(x.win)}</td><td>${pct(x.coverage)}</td><td>${x.no_policy ? '<span class="badge">none found</span>' : '<span class="badge ok">matched</span>'}</td></tr>` : `<tr style="cursor:default"><td colspan="4">#${x.id}: ${esc(x.error)}</td></tr>`).join("")}</tbody></table></div><div class="row" style="justify-content:flex-end;margin-top:14px"><button class="btn btn-ink" data-close>Close</button></div>`, { large: true });
    } catch (er) { toast(er.message, "err"); } }));
    $("#bg", F.view)?.addEventListener("click", (e) => withBusy(e.currentTarget, async () => { try {
      const r = (await api("/claims/bulk/appeal", { method: "POST", body: { ids: [...picked] } })).results; const ok = r.filter((x) => x.ok).length;
      toast(`${ok} appeal${ok === 1 ? "" : "s"} generated${ok < r.length ? `, ${r.length - ok} skipped` : ""}`, ok ? "ok" : "err"); picked.clear(); load();
    } catch (er) { toast(er.message, "err"); } })); };
  async function load() {
    const box = $("#tbl", F.view); box.innerHTML = skeleton(5); bulkBar();
    try {
      const r = await api("/claims?" + new URLSearchParams(Object.entries(S).filter(([, v]) => v !== "" && v != null)));
      if (!r.claims.length) { box.innerHTML = emptyBox("Nothing here", S.q || S.status || S.payer || S.category ? "No claims match these filters." : "Add a denial or import a remittance to get started."); return; }
      const th = (k, l) => `<th class="sort" data-s="${k}" aria-sort="${S.sort === k ? (S.order === "asc" ? "ascending" : "descending") : "none"}">${l}${S.sort === k ? (S.order === "asc" ? " ▲" : " ▼") : ""}</th>`;
      box.innerHTML = `<div class="tbl-wrap"><table class="tbl"><thead><tr><th style="width:36px"><input type="checkbox" id="all" aria-label="Select all on page"></th>${th("claim_no", "Claim")}${th("patient_name", "Patient")}${th("payer", "Payer")}<th>Code</th>${th("amount", "Amount")}${th("status", "Status")}${th("deadline", "Deadline")}${th("win", "Win chance")}</tr></thead><tbody>
        ${r.claims.map((c) => `<tr data-id="${c.id}"><td><input type="checkbox" class="pick" data-id="${c.id}" ${picked.has(c.id) ? "checked" : ""} aria-label="Select claim ${esc(c.claim_no)}"></td><td><b>${esc(c.claim_no)}</b><div class="small muted">${esc(c.procedure_desc || c.procedure_code || "")}</div></td><td>${esc(c.patient_name)}</td><td>${esc(c.payer)}</td><td><span class="code">${esc(c.denial_code || "?")}</span></td><td>${money(c.denied_amount || c.billed_amount)}</td><td>${pill(c.status)}</td><td>${["denied", "appeal_ready"].includes(c.status) ? deadlineBadge(c.deadline) : '<span class="muted">–</span>'}</td><td>${c.win_probability != null ? `<span class="meter-b"><i style="width:${c.win_probability * 100}%"></i></span>${pct(c.win_probability)}` : '<span class="muted">–</span>'}</td></tr>`).join("")}</tbody></table></div>
        <div class="pager"><span class="small muted">${r.total} claim${r.total === 1 ? "" : "s"} · page ${r.page} of ${r.pages}</span><div class="row"><button class="btn btn-ghost btn-sm" id="pv" ${r.page <= 1 ? "disabled" : ""}>Previous</button><button class="btn btn-ghost btn-sm" id="nx" ${r.page >= r.pages ? "disabled" : ""}>Next</button></div></div>`;
      $$("tbody tr", box).forEach((tr) => tr.addEventListener("click", (e) => { if (e.target.closest("input")) return; go(`#/${key}/claim/${tr.dataset.id}`); }));
      $$(".pick", box).forEach((cb) => cb.addEventListener("change", () => { cb.checked ? picked.add(+cb.dataset.id) : picked.delete(+cb.dataset.id); bulkBar(); }));
      $("#all", box).addEventListener("change", (e) => { $$(".pick", box).forEach((cb) => { cb.checked = e.target.checked; e.target.checked ? picked.add(+cb.dataset.id) : picked.delete(+cb.dataset.id); }); bulkBar(); });
      $$("th.sort", box).forEach((h) => h.addEventListener("click", () => { const k = h.dataset.s; S.order = S.sort === k && S.order === "desc" ? "asc" : "desc"; S.sort = k; S.page = 1; load(); }));
      $("#pv", box).addEventListener("click", () => { S.page--; load(); }); $("#nx", box).addEventListener("click", () => { S.page++; load(); });
    } catch (e) { box.innerHTML = errorBox(e.message, true); $("[data-retry]", box)?.addEventListener("click", load); }
  }
  const bind = (id, k) => $(id, F.view).addEventListener("change", (e) => { S[k] = e.target.value; S.page = 1; load(); });
  bind("#st", "status"); bind("#py", "payer"); bind("#ct", "category");
  $("#q", F.view).addEventListener("input", debounce((e) => { S.q = e.target.value.trim(); S.page = 1; load(); }));
  $("#add", root).addEventListener("click", () => claimModal(key));
  load();
}

function claimModal(key) {
  const today = new Date().toISOString().slice(0, 10);
  const m = modal(`<h3>Add a denied claim</h3><form id="cf" novalidate><div class="fgrid">
    <div class="field"><label class="lb" for="f_claim_no">Claim number</label><input class="inp" id="f_claim_no" name="claim_no"></div>
    <div class="field"><label class="lb" for="f_patient">Patient name</label><input class="inp" id="f_patient" name="patient_name" value="${key === "p" ? esc(auth.user.name) : ""}"></div>
    <div class="field"><label class="lb" for="f_payer">Insurance payer</label><input class="inp" id="f_payer" name="payer" list="payl" autocomplete="off"><datalist id="payl"></datalist></div>
    <div class="field"><label class="lb" for="f_code">Denial code (CARC)</label><input class="inp" id="f_code" name="denial_code" placeholder="Type 50 or a word like authorization" autocomplete="off"><p class="hint" id="f_codedesc"></p></div>
    <div class="field"><label class="lb" for="f_cpt">Procedure code (CPT)</label><input class="inp" id="f_cpt" name="procedure_code" placeholder="72148" autocomplete="off"></div>
    <div class="field"><label class="lb" for="f_desc">Service description</label><input class="inp" id="f_desc" name="procedure_desc" autocomplete="off"></div>
    <div class="field"><label class="lb" for="f_icd">Diagnosis (ICD-10)</label><input class="inp" id="f_icd" name="diagnosis" placeholder="Type a condition or code" autocomplete="off"></div>
    <div class="field"><label class="lb" for="f_amt">Amount denied (USD)</label><input class="inp" id="f_amt" name="billed_amount" type="number" min="0" step="0.01"></div>
    <div class="field"><label class="lb" for="f_date">Date of denial</label><input class="inp" id="f_date" name="denied_on" type="date" value="${today}"></div></div>
    <div id="ce" class="alert err hide"></div><div class="row" style="justify-content:flex-end"><button type="button" class="btn btn-ghost" data-close>Cancel</button><button class="btn btn-primary" id="cs">Save claim</button></div></form>`, { large: true });
  const el = (id) => $(id, m.el);
  api("/policies/payers").then((r) => { el("#payl").innerHTML = r.payers.map((p) => `<option value="${esc(p)}">`).join(""); }).catch(() => {});
  autocomplete(el("#f_code"), async (q) => (await api("/codes/list?limit=8&q=" + encodeURIComponent(q))).codes.map((c) => ({ value: c.code, label: `${c.code}`, sub: c.description })), (i) => { el("#f_code").value = i.value; el("#f_codedesc").textContent = i.sub; });
  autocomplete(el("#f_cpt"), async (q) => (await api("/procedures?q=" + encodeURIComponent(q))).procedures.map((p) => ({ value: p.code, label: p.code, sub: p.description })), (i) => { el("#f_cpt").value = i.value; el("#f_desc").value = i.sub; });
  autocomplete(el("#f_icd"), async (q) => (await api("/icd/search?q=" + encodeURIComponent(q))).results.map((r) => ({ value: r.code, label: r.code, sub: r.name })), (i) => { el("#f_icd").value = `${i.value} ${i.sub}`; });
  $("#cf", m.el).addEventListener("submit", async (e) => {
    e.preventDefault(); const f = Object.fromEntries(new FormData(e.target)); f.billed_amount = parseFloat(f.billed_amount);
    let bad = false; const chk = (id, ok, msg) => { fieldError(el(id), ok ? "" : msg); if (!ok) bad = true; };
    chk("#f_claim_no", !!f.claim_no.trim(), "Enter the claim number."); chk("#f_patient", !!f.patient_name.trim(), "Enter the patient name."); chk("#f_payer", !!f.payer.trim(), "Enter the payer.");
    chk("#f_code", !!f.denial_code.trim(), "Enter the denial code."); chk("#f_amt", f.billed_amount >= 0, "Enter the amount (0 or more).");
    if (bad) return;
    await withBusy(el("#cs"), async () => {
      try { const r = await api("/claims", { method: "POST", body: f }); m.close(); toast("Claim saved", "ok"); go(`#/${key}/claim/${r.claim.id}`); }
      catch (er) { const a = el("#ce"); a.textContent = er.message; a.classList.remove("hide"); }
    });
  });
}

export async function claimDetail(root, key, id, tabStart = "overview") {
  const F = frame(root, key, "/claims", "Claim", "");
  let c;
  try { c = (await api(`/claims/${id}`)).claim; } catch (e) { F.view.innerHTML = errorBox(e.message); return; }
  $(".top h1", root).textContent = `${c.claim_no} · ${c.patient_name}`;
  $(".top .row.wrap", root).insertAdjacentHTML("beforeend", `${pill(c.status)}<button class="btn btn-danger btn-sm" id="del">${icon("trash")} Delete</button>`);
  let tab = tabStart, analysis = null, fhir = false;
  api("/fhir/status").then((s) => { fhir = s.enabled; }).catch(() => {});
  const keep = (n) => ({ ...n, denial: c.denial, appeals: c.appeals, deadline: c.deadline, group: c.group });
  const draw = async () => {
    F.view.innerHTML = `<div class="tabs" role="tablist">${[["overview", "Overview"], ["notes", "Clinical notes"], ["analysis", "Analysis and appeal"], ["timeline", "Timeline"]].map(([t, l]) => `<button role="tab" aria-selected="${tab === t}" class="${tab === t ? "on" : ""}" data-t="${t}">${l}</button>`).join("")}</div><div id="tab"></div>`;
    $$(".tabs button", F.view).forEach((b) => b.addEventListener("click", () => { tab = b.dataset.t; draw(); }));
    const T = $("#tab", F.view);
    if (tab === "overview") {
      T.innerHTML = `<div class="grid2"><div class="card"><h3>Denial details</h3><dl class="kv"><dt>Payer</dt><dd>${esc(c.payer)}</dd><dt>Service</dt><dd>${esc(c.procedure_desc || "–")} ${c.procedure_code ? `<span class="code">CPT ${esc(c.procedure_code)}</span>` : ""}</dd><dt>Diagnosis</dt><dd>${esc(c.diagnosis || "–")}</dd>
        <dt>Denial code</dt><dd><span class="code">CARC ${esc(c.denial_code)}</span> ${esc(c.denial.category_label)}</dd><dt>Reason</dt><dd>${esc(c.denial_reason)}</dd>
        ${c.group ? `<dt>Group code</dt><dd><span class="code">${esc(c.group.code)}</span> ${esc(c.group.name)}<div class="small muted">${esc(c.group.meaning)}</div></dd>` : ""}
        ${c.remark_code ? `<dt>Remark code</dt><dd><span class="code">${esc(c.remark_code)}</span></dd>` : ""}<dt>Amount denied</dt><dd><b>${money2(c.denied_amount)}</b> of ${money2(c.billed_amount)} billed</dd><dt>Service date</dt><dd>${fmtDate(c.service_date)}</dd><dt>Denied on</dt><dd>${fmtDate(c.denied_on)}</dd>
        <dt>Appeal deadline</dt><dd>${deadlineBadge(c.deadline)} <span class="small muted">${c.deadline.window_days}-day window</span> ${c.deadline.verified ? '<span class="badge ok">verified rule</span>' : '<span class="badge">unverified baseline: confirm with payer</span>'}<div class="small muted">${esc(c.deadline.basis)}</div></dd></dl></div>
      <div class="stack"><div class="card"><h3>Suggested approach</h3><p style="margin:0">${esc(c.denial.strategy)}</p></div><div class="card"><h3>Appeals</h3>${c.appeals.length ? c.appeals.map((a) => `<div class="li"><a href="#/${key}/appeal/${a.id}">Draft from ${fmtDate(a.created_at)}</a>${pill(a.status)}</div>`).join("") : '<p class="muted">No appeal yet.</p>'}
        ${c.denial.appealable ? `<button class="btn btn-primary btn-sm" style="margin-top:12px" id="gen1">${icon("ai")} Generate appeal</button>` : `<div class="alert info" style="margin-top:12px">${icon("alert")}<div>${esc(c.denial.category_label)} adjustments are not normally appealable.</div></div>`}</div></div></div>`;
      $("#gen1", T)?.addEventListener("click", () => generate(c, key));
    } else if (tab === "notes") {
      T.innerHTML = `<div class="card"><h3>Patient chart notes</h3><p class="muted small">Paste notes from the EHR, or upload .txt, .docx or .pdf (scanned PDFs are read with OCR when the server has it). The appeal uses only what is written here.</p><textarea class="inp" id="notes" style="min-height:280px" placeholder="Visit notes, exam findings, labs, failed treatments...">${esc(c.ehr_notes || "")}</textarea>
        <div class="row wrap" style="margin-top:14px"><button class="btn btn-primary" id="sn">Save notes</button><label class="btn btn-ghost" for="nf" style="cursor:pointer">${icon("upload")} Upload file</label><input type="file" id="nf" accept=".txt,.md,.pdf,.docx" class="hide">${fhir ? `<button class="btn btn-ghost" id="fh">${icon("link")} Import from FHIR</button>` : ""}</div></div>`;
      $("#sn", T).addEventListener("click", (e) => withBusy(e.currentTarget, async () => { try { c = keep((await api(`/claims/${id}`, { method: "PATCH", body: { ehr_notes: $("#notes", T).value } })).claim); analysis = null; toast("Notes saved", "ok"); } catch (er) { toast(er.message, "err"); } }));
      $("#nf", T).addEventListener("change", async (e) => { const f = e.target.files[0]; if (!f) return; const fd = new FormData(); fd.append("file", f); try { c = keep((await api(`/claims/${id}/notes-file`, { method: "POST", form: fd })).claim); analysis = null; toast("File added to notes", "ok"); draw(); } catch (er) { toast(er.message, "err"); } });
      $("#fh", T)?.addEventListener("click", () => fhirModal(id, async () => { c = keep((await api(`/claims/${id}`)).claim); draw(); }));
    } else if (tab === "analysis") {
      T.innerHTML = `<div class="row wrap" style="margin-bottom:16px"><button class="btn btn-ink" id="run">${icon("search")} ${analysis ? "Re-run analysis" : "Run analysis"}</button>${c.denial.appealable ? `<button class="btn btn-primary" id="gen2">${icon("ai")} Generate appeal</button>` : ""}</div><div id="an">${analysis ? analysisHtml(analysis) : emptyBox("See what the policy and chart say", "Analysis finds the payer's policy clauses, checks them against the chart notes and estimates the appeal's strength.")}</div>`;
      $("#run", T).addEventListener("click", (e) => withBusy(e.currentTarget, async () => { try { analysis = (await api(`/claims/${id}/analyze`, { method: "POST" })).analysis; $("#an", T).innerHTML = analysisHtml(analysis); } catch (er) { toast(er.message, "err"); } }));
      $("#gen2", T)?.addEventListener("click", () => generate(c, key));
    } else {
      T.innerHTML = `<div class="card"><h3>Claim timeline</h3><div id="tl">${skeleton(3)}</div></div>`;
      try {
        const ev = (await api(`/claims/${id}/timeline`)).events;
        $("#tl", T).innerHTML = ev.length ? `<ol class="timeline">${ev.map((e) => `<li class="${/won|partial/.test(e.event) ? "win" : /lost/.test(e.event) ? "lose" : ""}"><b>${esc(EVENT[e.event] || e.event)}</b><small>${fmtDate(e.created_at)}${e.detail ? " · " + esc(e.detail) : ""}</small></li>`).join("")}</ol>` : `<p class="muted">No events yet.</p>`;
      } catch (e) { $("#tl", T).innerHTML = errorBox(e.message); }
    }
  };
  $("#del", root).addEventListener("click", () => { const m = modal(`<h3>Delete this claim?</h3><p class="muted">The claim, its appeals and its timeline will be removed. This cannot be undone.</p><div class="row" style="justify-content:flex-end"><button class="btn btn-ghost" data-close>Keep it</button><button class="btn btn-danger" id="yes">Delete</button></div>`); $("#yes", m.el).addEventListener("click", async () => { try { await api(`/claims/${id}`, { method: "DELETE" }); m.close(); toast("Claim deleted"); go(`#/${key}/claims`); } catch (e) { toast(e.message, "err"); } }); });
  draw();
}

function fhirModal(claimId, done) {
  const m = modal(`<h3>Import from FHIR</h3><p class="muted small">Searches the configured FHIR R4 server. Use test data only unless your organisation has approved it.</p><div class="row"><input class="inp" id="fn" placeholder="Patient name"><button class="btn btn-ink" id="fs">Search</button></div><div id="fr" style="margin-top:14px"></div>`);
  $("#fs", m.el).addEventListener("click", async () => {
    const box = $("#fr", m.el); box.innerHTML = skeleton(2);
    try {
      const r = (await api("/fhir/patients?name=" + encodeURIComponent($("#fn", m.el).value.trim()))).patients;
      box.innerHTML = r.length ? r.map((p) => `<div class="li"><div><b>${esc(p.name)}</b><div class="small muted">${esc(p.gender || "")} ${esc(p.birthDate || "")} · id ${esc(p.id)}</div></div><button class="btn btn-primary btn-sm" data-p="${esc(p.id)}">Import</button></div>`).join("") : emptyBox("No patients found", "Try another name.");
      $$("[data-p]", box).forEach((b) => b.addEventListener("click", () => withBusy(b, async () => { try { const x = await api(`/fhir/claims/${claimId}/import`, { method: "POST", body: { patient_id: b.dataset.p } }); toast(`Imported ${x.imported} items`, "ok"); m.close(); done(); } catch (er) { toast(er.message, "err"); } })));
    } catch (e) { box.innerHTML = errorBox(e.message); }
  });
}

export async function importView(root, key) {
  const F = frame(root, key, "/import", "Import 835", "Upload a remittance (ERA) file. Denials are found and added automatically.");
  F.view.innerHTML = `<div class="dz" id="dz" tabindex="0" role="button" aria-label="Choose an 835 file">${icon("upload")}<h3 style="margin-bottom:4px">Drop an 835 file here, or click to browse</h3><p class="muted" style="margin:0">.edi, .835, .txt up to 5 MB</p><input type="file" id="fi" class="hide" accept=".edi,.835,.txt,.x12"></div>
    <div class="card" style="margin-top:16px"><h3>Try the fictional sample files</h3><p class="muted small">Both files are synthetic. The first comes with matching demo chart notes. The second has procedures with no payer policy, so you can see the honest "no policy found" letter.</p>
    <div class="row wrap"><button class="btn btn-ink btn-sm" data-s="main">Load sample 1 (with charts)</button><button class="btn btn-ghost btn-sm" data-s="synthetic">Load sample 2 (no policies)</button></div></div><div id="res" style="margin-top:20px"></div>`;
  const show = (r) => { $("#res", F.view).innerHTML = `<div class="alert ok">${icon("checkc")}<div><b>${r.imported} denied claim${r.imported === 1 ? "" : "s"} imported</b>${r.skipped_duplicates ? `, ${r.skipped_duplicates} duplicates skipped` : ""}. Patient-responsibility lines were ignored.</div></div><a class="btn btn-ink" href="#/b/claims">Open denials</a>`; };
  const fail = (e) => { $("#res", F.view).innerHTML = errorBox(e.message); };
  const send = async (file) => { const fd = new FormData(); fd.append("file", file); $("#res", F.view).innerHTML = skeleton(1); try { show(await api("/claims/import-835", { method: "POST", form: fd })); } catch (e) { fail(e); } };
  const dz = $("#dz", F.view), fi = $("#fi", F.view);
  dz.addEventListener("click", () => fi.click()); dz.addEventListener("keydown", (e) => (e.key === "Enter" || e.key === " ") && fi.click());
  fi.addEventListener("change", () => fi.files[0] && send(fi.files[0]));
  ["dragover", "dragenter"].forEach((ev) => dz.addEventListener(ev, (e) => { e.preventDefault(); dz.classList.add("drag"); }));
  ["dragleave", "drop"].forEach((ev) => dz.addEventListener(ev, () => dz.classList.remove("drag")));
  dz.addEventListener("drop", (e) => { e.preventDefault(); e.dataTransfer.files[0] && send(e.dataTransfer.files[0]); });
  $$("[data-s]", F.view).forEach((b) => b.addEventListener("click", () => withBusy(b, async () => { try { show(await api("/claims/seed-demo?sample=" + b.dataset.s, { method: "POST" })); } catch (e) { fail(e); } })));
}

export async function startAppeal(root, key) {
  const F = frame(root, key, "/start", "Start an appeal", "Five short steps. You review the letter before anything is sent.");
  let reasons = [], payers = [];
  try { [reasons, payers] = await Promise.all([api("/codes/list?appealable=true&limit=12").then((r) => r.codes), api("/payers").then((r) => r.payers)]); } catch (e) { F.view.innerHTML = errorBox(e.message); return; }
  const a = { payer: "", claim_no: "", procedure_desc: "", procedure_code: "", billed_amount: "", denial_code: reasons[0]?.code || "", denied_on: new Date().toISOString().slice(0, 10), notes: "", file: null };
  let s = 0; const V = F.view;
  const draw = () => {
    const bar = `<div class="prog"><i style="width:${(s / 4) * 100}%"></i></div>`; const W = (h) => `<div class="wiz" style="margin:0">${bar}${h}</div>`;
    if (s === 0) V.innerHTML = W(`<h2 style="font-size:28px">Who denied it?</h2><div class="field"><label class="lb" for="a1">Insurance company</label><input class="inp" id="a1" list="pl" value="${esc(a.payer)}"><datalist id="pl">${payers.map((p) => `<option value="${esc(p)}">`).join("")}</datalist><p class="hint">Use the name on your insurance card or denial letter.</p></div><div class="field"><label class="lb" for="a2">Claim or reference number (optional)</label><input class="inp" id="a2" value="${esc(a.claim_no)}"></div><button class="btn btn-ink" id="nx">Continue</button>`);
    if (s === 1) V.innerHTML = W(`<h2 style="font-size:28px">What did they deny?</h2><div class="field"><label class="lb" for="a1">Service or treatment</label><input class="inp" id="a1" value="${esc(a.procedure_desc)}" placeholder="Start typing: MRI, knee, therapy" autocomplete="off"></div><div class="field"><label class="lb" for="a2">Amount denied (USD)</label><input class="inp" id="a2" type="number" min="0" value="${esc(a.billed_amount)}"></div><div class="row"><button class="btn btn-ghost" id="bk">Back</button><button class="btn btn-ink" id="nx">Continue</button></div>`);
    if (s === 2) V.innerHTML = W(`<h2 style="font-size:28px">Why did they say no?</h2><div class="field"><label class="lb" for="a3">Search the reason or code</label><input class="inp" id="a3" placeholder="Type authorization, necessity, 197..." autocomplete="off"></div><div id="opts">${reasons.map((r) => `<button class="opt ${a.denial_code === r.code ? "on" : ""}" data-c="${esc(r.code)}"><div><span class="code">${esc(r.code)}</span> ${esc(r.description)}</div></button>`).join("")}</div><div class="field" style="margin-top:12px"><label class="lb" for="a2">Date on the denial letter</label><input class="inp" id="a2" type="date" value="${a.denied_on}"></div><div class="row"><button class="btn btn-ghost" id="bk">Back</button><button class="btn btn-ink" id="nx">Continue</button></div>`);
    if (s === 3) V.innerHTML = W(`<h2 style="font-size:28px">Add your medical records</h2><p class="muted">Paste your doctor's notes, or upload a .txt, .docx or .pdf. Include dates, treatments you tried and test results. The letter only uses what you add here.</p><div class="field"><textarea class="inp" id="a1" style="min-height:200px" aria-label="Medical notes">${esc(a.notes)}</textarea></div><div class="field"><input type="file" id="a2" accept=".txt,.md,.pdf,.docx" aria-label="Upload records"></div><div class="row"><button class="btn btn-ghost" id="bk">Back</button><button class="btn btn-ink" id="nx">Review</button></div>`);
    if (s === 4) V.innerHTML = W(`<h2 style="font-size:28px">Ready to build your appeal</h2><dl class="kv"><dt>Insurer</dt><dd>${esc(a.payer)}</dd><dt>Service</dt><dd>${esc(a.procedure_desc)}</dd><dt>Amount</dt><dd>${money(a.billed_amount)}</dd><dt>Reason</dt><dd>CARC ${esc(a.denial_code)}</dd><dt>Records</dt><dd>${a.notes.trim() || a.file ? "Added" : '<span style="color:var(--red)">None. The letter will be weak without them.</span>'}</dd></dl><div class="row" style="margin-top:20px"><button class="btn btn-ghost" id="bk">Back</button><button class="btn btn-primary btn-lg" id="nx">${icon("ai")} Build my appeal</button></div>`);
    $("#bk", V)?.addEventListener("click", () => { s--; draw(); });
    if (s === 1) autocomplete($("#a1", V), async (q) => (await api("/procedures?q=" + encodeURIComponent(q))).procedures.map((p) => ({ value: p.description, label: p.description, sub: "CPT " + p.code, code: p.code })), (i) => { $("#a1", V).value = i.value; a.procedure_code = i.code; });
    if (s === 2) {
      const bindOpts = () => $$(".opt", V).forEach((b) => b.addEventListener("click", () => { a.denial_code = b.dataset.c; $$(".opt", V).forEach((x) => x.classList.toggle("on", x === b)); }));
      bindOpts();
      $("#a3", V).addEventListener("input", debounce(async (e) => { const q = e.target.value.trim(); try { const r = (await api(`/codes/list?appealable=true&limit=10&q=${encodeURIComponent(q)}`)).codes; $("#opts", V).innerHTML = r.map((x) => `<button class="opt ${a.denial_code === x.code ? "on" : ""}" data-c="${esc(x.code)}"><div><span class="code">${esc(x.code)}</span> ${esc(x.description)}</div></button>`).join("") || `<p class="muted">No matching reason.</p>`; bindOpts(); } catch { /* keep list */ } }));
    }
    $("#nx", V).addEventListener("click", async (e) => {
      if (s === 0) { a.payer = $("#a1", V).value.trim(); a.claim_no = $("#a2", V).value.trim(); if (!a.payer) return fieldError($("#a1", V), "Enter the insurer's name."); }
      if (s === 1) { a.procedure_desc = $("#a1", V).value.trim(); a.billed_amount = $("#a2", V).value; if (!a.procedure_desc) return fieldError($("#a1", V), "Tell us what was denied."); if (a.billed_amount === "" || !(parseFloat(a.billed_amount) >= 0)) return fieldError($("#a2", V), "Enter the amount."); }
      if (s === 2) { a.denied_on = $("#a2", V).value || a.denied_on; if (!a.denial_code) return toast("Pick a reason", "err"); }
      if (s === 3) { a.notes = $("#a1", V).value; a.file = $("#a2", V).files[0] || null; }
      if (s < 4) { s++; return draw(); }
      await withBusy(e.currentTarget, async () => {
        try {
          const body = { claim_no: a.claim_no || "PT-" + Date.now().toString().slice(-7), patient_name: auth.user.name, payer: a.payer, procedure_code: a.procedure_code, procedure_desc: a.procedure_desc, billed_amount: parseFloat(a.billed_amount) || 0, denial_code: a.denial_code, denied_on: a.denied_on, ehr_notes: a.notes };
          const c = (await api("/claims", { method: "POST", body })).claim;
          if (a.file) { const fd = new FormData(); fd.append("file", a.file); await api(`/claims/${c.id}/notes-file`, { method: "POST", form: fd }); }
          const r = await api(`/claims/${c.id}/appeal`, { method: "POST" });
          toast("Your appeal draft is ready", "ok"); go(`#/${key}/appeal/${r.appeal_id}`);
        } catch (er) { toast(er.message, "err"); }
      });
    });
  };
  draw();
}
