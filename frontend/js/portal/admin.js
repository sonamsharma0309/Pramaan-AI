// Admin console: overview, users, contact messages, audit log, system health. Admins are created only via scripts/create_admin.py.
import { api } from "../api.js";
import { $, $$, emptyBox, errorBox, esc, fmtDate, modal, skeleton, toast } from "../ui.js";
import { frame } from "./shell.js";

const table = (cols, rows) => `<div class="tbl-wrap"><table class="tbl" style="min-width:640px"><thead><tr>${cols.map((c) => `<th>${c}</th>`).join("")}</tr></thead><tbody>${rows.join("")}</tbody></table></div>`;
const yes = (v) => (v ? '<span class="badge ok">yes</span>' : '<span class="badge off">no</span>');

export async function adminPage(root, sub) {
  const titles = { "": "Overview", users: "Users", messages: "Contact messages", audit: "Audit log", system: "System health" };
  const F = frame(root, "a", sub, titles[sub] || "Overview", "Administration");
  const V = F.view;
  try {
    if (sub === "users") {
      const draw = async () => {
        const r = await api("/admin/users");
        V.innerHTML = table(["Name", "Email", "Role", "Organisation", "Provider", "Verified", "2FA", "Last login", ""], r.users.map((u) => `<tr style="cursor:default"><td>${esc(u.name)}</td><td>${esc(u.email)}</td><td><span class="badge info">${esc(u.role)}</span></td><td>${esc(u.org || "")}</td><td>${esc(u.auth_provider)}</td><td>${yes(u.email_verified)}</td><td>${yes(u.totp_enabled)}</td><td>${fmtDate(u.last_login)}</td><td>${u.role === "admin" ? "" : `<button class="btn btn-danger btn-sm" data-del="${u.id}" data-name="${esc(u.email)}">Delete</button>`}</td></tr>`));
        $$("[data-del]", V).forEach((b) => b.addEventListener("click", () => { const m = modal(`<h3>Delete ${esc(b.dataset.name)}?</h3><p class="muted">Their claims, appeals and sessions are removed permanently.</p><div class="row" style="justify-content:flex-end"><button class="btn btn-ghost" data-close>Cancel</button><button class="btn btn-danger" id="yes">Delete user</button></div>`); $("#yes", m.el).addEventListener("click", async () => { try { await api(`/admin/users/${b.dataset.del}`, { method: "DELETE" }); m.close(); toast("User deleted"); draw(); } catch (e) { toast(e.message, "err"); } }); }));
      };
      await draw();
    } else if (sub === "messages") {
      const r = await api("/admin/messages");
      V.innerHTML = r.messages.length ? r.messages.map((m) => `<div class="card" style="margin-bottom:12px"><div class="row between wrap"><b>${esc(m.name)} <span class="muted small">&lt;${esc(m.email)}&gt;</span></b><span><span class="badge info">${esc(m.kind)}</span> ${m.emailed ? '<span class="badge ok">emailed</span>' : '<span class="badge off">stored only</span>'} <span class="small muted">${fmtDate(m.created_at)}</span></span></div><p style="margin:10px 0 0;white-space:pre-wrap">${esc(m.message)}</p></div>`).join("") : emptyBox("No messages yet", "Messages from the Contact page appear here.");
    } else if (sub === "audit") {
      const draw = async (action = "") => {
        const r = await api("/admin/audit" + (action ? "?action=" + encodeURIComponent(action) : ""));
        $("#al", V).innerHTML = r.events.length ? table(["When", "User", "Action", "Detail", "IP", "Request"], r.events.map((e) => `<tr style="cursor:default"><td>${esc(e.created_at)}</td><td>${esc(e.email || "–")}</td><td><span class="code">${esc(e.action)}</span></td><td>${esc(e.detail || "")}</td><td>${esc(e.ip || "")}</td><td class="mono small">${esc(e.request_id || "")}</td></tr>`)) : emptyBox("No events", "Nothing matches this filter.");
      };
      V.innerHTML = `<div class="toolbar"><select class="inp" id="af" aria-label="Filter by action"><option value="">All actions</option>${["login", "login_failed", "logout", "register", "password_changed", "password_reset", "refresh_replay", "appeal_viewed", "appeal_pdf", "appeal_generated", "policy_uploaded", "export_claims", "export_packets", "import_835", "2fa_enabled"].map((a) => `<option>${a}</option>`).join("")}</select></div><div id="al">${skeleton(4)}</div>`;
      $("#af", V).addEventListener("change", (e) => draw(e.target.value)); await draw();
    } else if (sub === "system") {
      const h = (await api("/admin/system"));
      V.innerHTML = `<div class="kpis"><div class="kpi"><span>Status</span><b>${esc(h.status)}</b><small>version ${esc(h.version)}</small></div><div class="kpi"><span>Database</span><b>${esc(h.db)}</b></div><div class="kpi"><span>Policy passages</span><b>${h.policy_chunks}</b></div><div class="kpi"><span>Win model</span><b>${esc(h.model.kind)}</b><small>trained on ${h.model.n} rows</small></div></div>
        <div class="card"><h3>Integrations</h3>${Object.entries(h.integrations).map(([k, v]) => `<div class="li"><span>${esc(k)}</span>${yes(v)}</div>`).join("")}<p class="srcnote">Keys are set in .env. Features without keys are hidden or degrade gracefully.</p></div>`;
    } else {
      const o = await api("/admin/overview");
      V.innerHTML = `<div class="kpis"><div class="kpi hl"><span>Users</span><b>${o.users}</b><small>${Object.entries(o.by_role).map(([r, n]) => `${n} ${r}`).join(" · ")}</small></div><div class="kpi"><span>Claims</span><b>${o.claims}</b></div><div class="kpi"><span>Appeals</span><b>${o.appeals}</b></div><div class="kpi"><span>Messages</span><b>${o.messages}</b><small>${o.audit_events} audit events</small></div></div>`;
    }
  } catch (e) { V.innerHTML = errorBox(e.message); }
}
