// Settings: profile, appearance, password, optional 2FA (TOTP), organisation invite code.
import { api, auth, setUser } from "../api.js";
import { $, applyTheme, currentTheme, esc, fieldError, fmtDate, icon, modal, passwordScore, toast, withBusy } from "../ui.js";
import { frame, logout } from "./shell.js";

export async function settings(root, key) {
  const u = auth.user;
  const F = frame(root, key, "/settings", "Settings", "Your profile and security.");
  F.view.innerHTML = `<div class="grid2e"><div class="stack"><div class="card"><h3>Profile</h3><form id="pf" novalidate><div class="field"><label class="lb" for="pn">Full name</label><input class="inp" id="pn" name="name" value="${esc(u.name)}"></div><div class="field"><label class="lb">Email</label><input class="inp" value="${esc(u.email)}" disabled aria-label="Email"></div>${key === "b" ? `<div class="field"><label class="lb">Organisation</label><input class="inp" value="${esc(u.org)}" disabled aria-label="Organisation"></div>` : ""}<button class="btn btn-ink" id="sp">Save profile</button></form>
      <p class="small muted" style="margin:14px 0 0">Signed in with ${esc(u.auth_provider)}. Member since ${fmtDate(u.created_at)}. ${u.email_verified ? '<span class="badge ok">email verified</span>' : '<span class="badge">email not verified</span>'}</p></div>
      <div class="card"><h3>Appearance</h3><label class="check"><input type="checkbox" id="dk" ${currentTheme() === "dark" ? "checked" : ""}> Dark mode (saved to your account)</label></div>
      ${key === "b" ? `<div class="card" id="org"><h3>Organisation</h3><div class="skel"></div></div>` : ""}</div>
    <div class="stack"><div class="card"><h3>Change password</h3>${u.auth_provider === "google" ? '<p class="muted">This account uses Google sign-in. Use "Forgot password" on the sign-in page to add a password.</p>' : `<form id="cf" novalidate><div class="field"><label class="lb" for="cur">Current password</label><input class="inp" type="password" id="cur" autocomplete="current-password" maxlength="72"></div><div class="field"><label class="lb" for="np">New password</label><input class="inp" type="password" id="np" autocomplete="new-password" maxlength="72"><div class="meter" id="meter" data-s="0"><i></i><i></i><i></i><i></i></div></div><div id="ce" class="alert err hide"></div><button class="btn btn-ink" id="sc">Update password</button></form>`}</div>
      <div class="card" id="tf"></div><div class="card"><h3>Session</h3><p class="muted small">Access lasts 15 minutes and renews quietly while you work. Signing out ends it on the server immediately.</p><button class="btn btn-ghost" id="so">${icon("logout")} Sign out</button></div></div></div>`;
  $("#pf", F.view).addEventListener("submit", async (e) => { e.preventDefault(); const name = $("#pn", F.view).value.trim(); if (name.length < 2) return fieldError($("#pn", F.view), "Enter your name."); await withBusy($("#sp", F.view), async () => { try { setUser((await api("/auth/me", { method: "PATCH", body: { name } })).user); toast("Profile saved", "ok"); } catch (er) { toast(er.message, "err"); } }); });
  $("#dk", F.view).addEventListener("change", async (e) => { const t = e.target.checked ? "dark" : "light"; applyTheme(t); try { await api("/auth/theme", { method: "PUT", body: { theme: t } }); auth.user.theme = t; } catch { /* local only */ } window.dispatchEvent(new HashChangeEvent("hashchange")); });
  $("#np", F.view)?.addEventListener("input", (e) => ($("#meter", F.view).dataset.s = passwordScore(e.target.value, u.email)));
  $("#cf", F.view)?.addEventListener("submit", async (e) => {
    e.preventDefault(); const cur = $("#cur", F.view).value, np = $("#np", F.view).value;
    fieldError($("#cur", F.view), cur ? "" : "Enter your current password."); if (!cur) return;
    if (np.length < 8 || !/\d/.test(np) || !/[A-Za-z]/.test(np)) return fieldError($("#np", F.view), "Use 8+ characters with a letter and a number.");
    await withBusy($("#sc", F.view), async () => { try { setUser((await api("/auth/change-password", { method: "POST", body: { current_password: cur, new_password: np } })).user); e.target.reset(); toast("Password updated. Other sessions were signed out.", "ok"); } catch (er) { const a = $("#ce", F.view); a.textContent = er.message; a.classList.remove("hide"); } });
  });
  $("#so", F.view).addEventListener("click", logout);
  const drawTfa = () => {
    const t = $("#tf", F.view);
    t.innerHTML = `<h3>Two-factor authentication</h3>${auth.user.totp_enabled ? `<p class="muted small"><span class="badge ok">on</span> You will be asked for a code from your authenticator app when you sign in.</p><button class="btn btn-danger btn-sm" id="t0">Turn off</button>` : `<p class="muted small">Add a second step at sign-in with an authenticator app (Google Authenticator, Microsoft Authenticator, Authy).</p><button class="btn btn-ink btn-sm" id="t1">Set up</button>`}`;
    $("#t1", t)?.addEventListener("click", async () => {
      try {
        const s = await api("/auth/2fa/setup", { method: "POST" });
        const m = modal(`<h3>Scan with your authenticator app</h3><img class="qr" src="${s.qr}" alt="QR code to add Pramaan AI to your authenticator app"><p class="small muted">Cannot scan? Enter this key manually: <span class="mono">${esc(s.secret)}</span></p><div class="field"><label class="lb" for="tc">6-digit code</label><input class="inp" id="tc" inputmode="numeric" maxlength="8" autocomplete="one-time-code"></div><div id="te" class="alert err hide"></div><div class="row" style="justify-content:flex-end"><button class="btn btn-ghost" data-close>Cancel</button><button class="btn btn-primary" id="tv">Turn on</button></div>`);
        $("#tv", m.el).addEventListener("click", (e) => withBusy(e.currentTarget, async () => { try { await api("/auth/2fa/enable", { method: "POST", body: { code: $("#tc", m.el).value.trim() } }); auth.user.totp_enabled = true; m.close(); toast("Two-factor authentication is on", "ok"); drawTfa(); } catch (er) { const a = $("#te", m.el); a.textContent = er.message; a.classList.remove("hide"); } }));
      } catch (e) { toast(e.message, "err"); }
    });
    $("#t0", t)?.addEventListener("click", () => { const m = modal(`<h3>Turn off two-factor?</h3><div class="field"><label class="lb" for="tc">Current 6-digit code</label><input class="inp" id="tc" inputmode="numeric" maxlength="8"></div><div id="te" class="alert err hide"></div><div class="row" style="justify-content:flex-end"><button class="btn btn-ghost" data-close>Cancel</button><button class="btn btn-danger" id="tv">Turn off</button></div>`);
      $("#tv", m.el).addEventListener("click", (e) => withBusy(e.currentTarget, async () => { try { await api("/auth/2fa/disable", { method: "POST", body: { code: $("#tc", m.el).value.trim() } }); auth.user.totp_enabled = false; m.close(); toast("Two-factor authentication is off"); drawTfa(); } catch (er) { const a = $("#te", m.el); a.textContent = er.message; a.classList.remove("hide"); } })); });
  };
  drawTfa();
  if (key === "b") api("/auth/org").then((r) => { $("#org", F.view).innerHTML = `<h3>Organisation</h3><p class="small muted">Teammates who sign up with this invite code join your organisation and share its private policy library.</p><div class="field"><label class="lb">Name</label><input class="inp" value="${esc(r.org?.name || "")}" disabled></div><div class="field"><label class="lb">Invite code</label><input class="inp mono" value="${esc(r.org?.invite_code || "")}" readonly aria-label="Invite code"></div><p class="small muted">${r.members.length} member${r.members.length === 1 ? "" : "s"}: ${r.members.map((m) => esc(m.name)).join(", ")}</p>`; }).catch((e) => { $("#org", F.view).innerHTML = `<h3>Organisation</h3><p class="muted">${esc(e.message)}</p>`; });
}
