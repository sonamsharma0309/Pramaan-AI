// Policy library (shared read-only + your organisation's private uploads) and the code lookup page.
import { api } from "../api.js";
import { $, $$, emptyBox, errorBox, esc, icon, modal, skeleton, toast, withBusy } from "../ui.js";
import { mountCodeLookup } from "../public.js";
import { frame } from "./shell.js";

export function codesPage(root, key) { const F = frame(root, key, "/codes", "Denial code lookup", "Search the CARC, RARC and EOB dataset."); mountCodeLookup(F.view); }

export async function policiesPage(root, key) {
  const biller = key === "b";
  const F = frame(root, key, "/policies", "Policy library", "Shared sample policies (read-only) plus your organisation's private uploads.", biller ? `<button class="btn btn-primary" id="addp">${icon("plus")} Add policy</button>` : "");
  F.view.innerHTML = `<div class="card" style="margin-bottom:16px"><h3>Ask the policies</h3><div class="row"><input class="inp" id="sq" placeholder="For example: lumbar MRI conservative therapy requirement" aria-label="Search policies"><button class="btn btn-ink" id="sb">${icon("search")} Search</button></div><div id="sr" style="margin-top:14px"></div></div><div id="pl">${skeleton(4)}</div>`;
  const loadList = async () => {
    try {
      const r = await api("/policies");
      $("#pl", F.view).innerHTML = r.policies.length ? `<div class="tbl-wrap"><table class="tbl"><thead><tr><th>Title</th><th>Payer</th><th>Size</th><th>Source</th><th></th></tr></thead><tbody>${r.policies.map((p) => `<tr data-id="${p.id}"><td><b>${esc(p.title)}</b></td><td>${esc(p.payer)}</td><td>${(p.size / 1000).toFixed(1)}k chars</td><td>${p.shared ? '<span class="pill recovered">Shared</span>' : '<span class="pill drafted">Your organisation</span>'}</td><td>${!p.shared && biller ? `<button class="btn btn-danger btn-sm" data-del="${p.id}">Delete</button>` : ""}</td></tr>`).join("")}</tbody></table></div>` : emptyBox("No policies yet", "Add a payer policy to start retrieving clauses.");
      $$("tbody tr", F.view).forEach((tr) => tr.addEventListener("click", async (e) => {
        if (e.target.closest("[data-del]")) return;
        try { const p = (await api(`/policies/${tr.dataset.id}`)).policy; modal(`<h3>${esc(p.title)}</h3><p class="muted small">${esc(p.payer)}</p><div class="quote" style="white-space:pre-wrap">${esc(p.content)}</div><div class="row" style="justify-content:flex-end"><button class="btn btn-ink" data-close>Close</button></div>`, { large: true }); } catch (er) { toast(er.message, "err"); }
      }));
      $$("[data-del]", F.view).forEach((b) => b.addEventListener("click", async () => { try { await api(`/policies/${b.dataset.del}`, { method: "DELETE" }); toast("Policy deleted"); loadList(); } catch (e) { toast(e.message, "err"); } }));
    } catch (e) { $("#pl", F.view).innerHTML = errorBox(e.message, true); $("[data-retry]", F.view)?.addEventListener("click", loadList); }
  };
  const search = async () => {
    const q = $("#sq", F.view).value.trim(); if (q.length < 2) return;
    $("#sr", F.view).innerHTML = skeleton(2);
    try { const r = await api("/policies/search", { method: "POST", body: { query: q } }); $("#sr", F.view).innerHTML = r.hits.length ? r.hits.map((h) => `<div style="margin-bottom:12px"><span class="ref">${h.ref}</span> <b>${esc(h.title)}</b> <span class="small muted">· ${esc(h.payer)} · relevance ${h.score}</span><div class="quote">${esc(h.text).replace(/\n/g, "<br>")}</div></div>`).join("") : `<p class="muted">No matching clauses.</p>`; }
    catch (e) { $("#sr", F.view).innerHTML = errorBox(e.message); }
  };
  $("#sb", F.view).addEventListener("click", search); $("#sq", F.view).addEventListener("keydown", (e) => e.key === "Enter" && search());
  if (biller) $("#addp", root).addEventListener("click", () => {
    const m = modal(`<h3>Add a payer policy</h3><p class="muted small">Visible only to your organisation. Upload .txt, .docx or .pdf (scanned PDFs use OCR when available).</p><form id="pf" novalidate><div class="field"><label class="lb" for="pp">Payer name</label><input class="inp" id="pp" name="payer" required></div><div class="field"><label class="lb" for="pt">Policy title</label><input class="inp" id="pt" name="title"></div><div class="field"><label class="lb" for="pc">Policy text</label><textarea class="inp" id="pc" name="content" style="min-height:140px" placeholder="Paste the coverage policy text, or choose a file below"></textarea></div><div class="field"><input type="file" id="pfile" accept=".txt,.md,.pdf,.docx" aria-label="Policy file"></div><div id="pe" class="alert err hide"></div><div class="row" style="justify-content:flex-end"><button type="button" class="btn btn-ghost" data-close>Cancel</button><button class="btn btn-primary" id="ps">Add to library</button></div></form>`);
    $("#pf", m.el).addEventListener("submit", async (e) => {
      e.preventDefault(); const f = new FormData(e.target); const file = $("#pfile", m.el).files[0]; const err = (t) => { const a = $("#pe", m.el); a.textContent = t; a.classList.remove("hide"); };
      if (!String(f.get("payer")).trim()) return err("Enter the payer name.");
      if (!file && String(f.get("content")).trim().length < 20) return err("Paste at least a few sentences, or choose a file.");
      await withBusy($("#ps", m.el), async () => {
        try {
          if (file) { const fd = new FormData(); fd.append("payer", f.get("payer")); fd.append("title", f.get("title") || ""); fd.append("file", file); await api("/policies/upload", { method: "POST", form: fd }); }
          else await api("/policies", { method: "POST", body: { payer: f.get("payer"), title: f.get("title") || String(f.get("payer")) + " policy", content: f.get("content") } });
          m.close(); toast("Policy added", "ok"); loadList();
        } catch (er) { err(er.message); }
      });
    });
  });
  loadList();
}
