// Login / sign up (per portal), 2FA step, email verification, forgot + reset password, optional Google sign-in.
import { api, setUser } from "./api.js";
import { stampCardHtml } from "./public.js";
import { $, $$, applyTheme, brand, esc, fieldError, go, icon, passwordScore, toast, withBusy } from "./ui.js";

const COPY = {
  patient: { name: "Patient Portal", h: "Your insurer said no. Let's check their paperwork.", p: "Answer a few questions and get an appeal letter that quotes your insurer's own policy.", home: "#/p", role: "patient" },
  billing: { name: "Billing Portal", h: "Work the denial queue, not the policy manuals.", p: "Import remittances, see what is worth appealing first and send cited letters in minutes.", home: "#/b", role: "biller" },
  admin: { name: "Admin Console", h: "Keep the platform healthy.", p: "Users, messages, audit trail and system health in one place.", home: "#/a", role: "admin" },
};
let gisLoaded = null;
const EMAIL = /^\S+@\S+\.\S+$/;

const shell = (portal, inner) => `<div class="auth"><aside class="auth-side">${brand()}<div><h2>${COPY[portal].h}</h2><p>${COPY[portal].p}</p></div>${stampCardHtml()}</aside><main class="auth-main" id="main"><div class="auth-card">${inner}</div></main></div>`;
const seg = (mode, portal) => portal === "admin" ? "" : `<div class="seg" role="tablist"><a href="#/${mode}/patient" class="${portal === "patient" ? "on" : ""}">Patient</a><a href="#/${mode}/billing" class="${portal === "billing" ? "on" : ""}">Billing</a></div>`;
const pwField = (id, label) => `<div class="field"><label class="lb" for="${id}">${label}</label><div class="pw"><input class="inp" id="${id}" type="password" autocomplete="${id === "pw" ? "current-password" : "new-password"}" maxlength="72"><button type="button" data-eye="${id}" aria-label="Show password">${icon("eye")}</button></div></div>`;
const showErr = (root, m) => { const a = $("#err", root); a.innerHTML = `${icon("alert")}<div>${esc(m)}</div>`; a.classList.remove("hide"); a.scrollIntoView({ block: "nearest" }); };

function bindEyes(root) {
  $$("[data-eye]", root).forEach((b) => b.addEventListener("click", () => {
    const i = $("#" + b.dataset.eye, root); const show = i.type === "password";
    i.type = show ? "text" : "password"; b.innerHTML = icon(show ? "eyeoff" : "eye"); b.setAttribute("aria-label", show ? "Hide password" : "Show password");
  }));
}
function finish(r, portal) { setUser(r.user); if (r.user.theme) applyTheme(r.user.theme); toast("Signed in", "ok"); go(COPY[portal].home); }

async function googleButton(root, portal, mode) {
  const slot = $("#gbtn", root); if (!slot) return;
  let cfg; try { cfg = await api("/auth/google-config"); } catch { return; }
  if (!cfg.enabled) { slot.innerHTML = ""; slot.closest(".gwrap")?.classList.add("hide"); return; }   // hide features whose keys are missing
  if (!gisLoaded) gisLoaded = new Promise((res, rej) => { const s = document.createElement("script"); s.src = "https://accounts.google.com/gsi/client"; s.onload = res; s.onerror = rej; document.head.appendChild(s); });
  try { await gisLoaded; } catch { slot.closest(".gwrap")?.classList.add("hide"); return; }
  window.google.accounts.id.initialize({ client_id: cfg.client_id, callback: async (resp) => {
    try { finish(await api("/auth/google", { method: "POST", body: { credential: resp.credential, role: COPY[portal].role, portal: mode === "login" ? COPY[portal].role : null }, silent401: true }), portal); }
    catch (e) { showErr(root, e.message); } } });
  window.google.accounts.id.renderButton(slot, { theme: "outline", size: "large", width: 380, text: mode === "login" ? "signin_with" : "signup_with", shape: "pill" });
}
const googleBlock = `<div class="gwrap"><div class="divider">or</div><div class="gbtn" id="gbtn"></div></div>`;

function login(root, portal) {
  const c = COPY[portal];
  root.innerHTML = shell(portal, `${seg("login", portal)}<h1>Welcome back</h1><p class="muted">Sign in to the ${c.name}.</p><div id="err" class="alert err hide" role="alert"></div>
    <form id="f" novalidate><div class="field"><label class="lb" for="em">Email address</label><input class="inp" id="em" type="email" autocomplete="email" placeholder="you@example.com"></div>${pwField("pw", "Password")}
    <div class="field hide" id="totpw"><label class="lb" for="totp">Authenticator code</label><input class="inp" id="totp" inputmode="numeric" autocomplete="one-time-code" maxlength="8" placeholder="6-digit code"><p class="hint">Open your authenticator app and enter the current code.</p></div>
    <div class="row between field"><span class="small muted">Sessions end automatically after inactivity.</span><a href="#/forgot" class="small">Forgot password?</a></div>
    <button class="btn btn-primary btn-lg" style="width:100%" id="go">Sign in</button></form>${portal === "admin" ? "" : googleBlock}
    ${portal === "admin" ? "" : `<p class="muted small" style="text-align:center;margin-top:22px">New to Pramaan AI? <a href="#/signup/${portal}"><b>Create an account</b></a></p>`}`);
  bindEyes(root); googleButton(root, portal, "login");
  $("#f", root).addEventListener("submit", async (e) => {
    e.preventDefault(); $("#err", root).classList.add("hide");
    const email = $("#em", root).value.trim(), password = $("#pw", root).value;
    fieldError($("#em", root), EMAIL.test(email) ? "" : "Enter a valid email address."); fieldError($("#pw", root), password ? "" : "Enter your password.");
    if (!EMAIL.test(email) || !password) return;
    await withBusy($("#go", root), async () => {
      try { finish(await api("/auth/login", { method: "POST", body: { email, password, portal: c.role, totp_code: $("#totp", root).value.trim() }, silent401: true }), portal); }
      catch (err) { if (err.data?.need_2fa) { $("#totpw", root).classList.remove("hide"); $("#totp", root).focus(); } showErr(root, err.message); }
    });
  });
}

function signup(root, portal) {
  const c = COPY[portal]; const biller = portal === "billing";
  root.innerHTML = shell(portal, `${seg("signup", portal)}<h1>Create your account</h1><p class="muted">Free access to the ${c.name}.</p><div id="err" class="alert err hide" role="alert"></div>
    <form id="f" novalidate><div class="field"><label class="lb" for="nm">Full name</label><input class="inp" id="nm" autocomplete="name" maxlength="80"></div>
    ${biller ? `<div class="field"><label class="lb" for="org">Practice or billing company</label><input class="inp" id="org" autocomplete="organization" maxlength="120"><p class="hint">Joining a teammate? <a href="#" id="hasinv">Use an invite code instead</a></p></div>
      <div class="field hide" id="invw"><label class="lb" for="inv">Invite code</label><input class="inp" id="inv" maxlength="24" placeholder="From your organisation's settings page"></div>` : ""}
    <div class="field"><label class="lb" for="em">Email address</label><input class="inp" id="em" type="email" autocomplete="email"></div>${pwField("pw", "Password")}
    <div class="meter" id="meter" data-s="0" style="margin-top:-8px;margin-bottom:6px"><i></i><i></i><i></i><i></i></div><p class="hint" id="pwh" style="margin:0 0 16px">At least 8 characters with a letter and a number.</p>
    <label class="check field"><input type="checkbox" id="tos"> I understand Pramaan AI is a decision-support tool and not legal or medical advice.</label>
    <button class="btn btn-primary btn-lg" style="width:100%" id="go">Create account</button></form>${googleBlock}
    <p class="muted small" style="text-align:center;margin-top:22px">Already registered? <a href="#/login/${portal}"><b>Sign in</b></a></p>`);
  bindEyes(root); googleButton(root, portal, "signup");
  const upd = () => { const s = passwordScore($("#pw", root).value, $("#em", root).value); $("#meter", root).dataset.s = s; $("#pwh", root).textContent = ["At least 8 characters with a letter and a number.", "Too weak. Add more characters.", "Okay. A longer password is safer.", "Good.", "Strong."][s]; };
  $("#pw", root).addEventListener("input", upd); $("#em", root).addEventListener("input", upd);
  $("#hasinv", root)?.addEventListener("click", (e) => { e.preventDefault(); $("#invw", root).classList.toggle("hide"); });
  $("#f", root).addEventListener("submit", async (e) => {
    e.preventDefault(); $("#err", root).classList.add("hide");
    const body = { name: $("#nm", root).value.trim(), email: $("#em", root).value.trim(), password: $("#pw", root).value, org: biller ? $("#org", root).value.trim() : "", role: c.role, invite_code: biller ? ($("#inv", root).value.trim()) : "" };
    let bad = false; const chk = (el, cond, msg) => { fieldError(el, cond ? "" : msg); if (!cond) bad = true; };
    chk($("#nm", root), body.name.length >= 2, "Enter your full name."); chk($("#em", root), EMAIL.test(body.email), "Enter a valid email address.");
    if (biller) chk($("#org", root), !!(body.org || body.invite_code), "Enter your practice name, or an invite code.");
    chk($("#pw", root), body.password.length >= 8 && /\d/.test(body.password) && /[A-Za-z]/.test(body.password), "Use 8+ characters with a letter and a number.");
    if (!$("#tos", root).checked) { showErr(root, "Please confirm the note about decision support."); bad = true; }
    if (bad) return;
    await withBusy($("#go", root), async () => {
      try {
        const r = await api("/auth/register", { method: "POST", body, silent401: true });
        if (r.verification_required) {
          $("#f", root).innerHTML = `<div class="alert ok">${icon("checkc")}<div>Account created. Check your inbox for a verification link, then sign in.</div></div>` + (r.dev_verify_link ? `<div class="alert info">${icon("alert")}<div><b>Dev mode:</b> <a href="${esc(r.dev_verify_link)}">open verification link</a></div></div>` : "");
          return;
        }
        setUser(r.user); toast("Account created. Welcome!", "ok"); go(c.home);
      } catch (err) { showErr(root, err.message); }
    });
  });
}

function forgot(root) {
  root.innerHTML = shell("patient", `<h1>Reset your password</h1><p class="muted">Enter your email and we'll send a reset link.</p><div id="err" class="alert err hide" role="alert"></div><div id="ok"></div>
    <form id="f" novalidate><div class="field"><label class="lb" for="em">Email address</label><input class="inp" id="em" type="email" autocomplete="email"></div><button class="btn btn-primary btn-lg" style="width:100%" id="go">Send reset link</button></form>
    <p class="muted small" style="text-align:center;margin-top:22px"><a href="#/login/patient">Back to sign in</a></p>`);
  $("#f", root).addEventListener("submit", async (e) => {
    e.preventDefault(); const email = $("#em", root).value.trim();
    fieldError($("#em", root), EMAIL.test(email) ? "" : "Enter a valid email address."); if (!EMAIL.test(email)) return;
    await withBusy($("#go", root), async () => {
      try {
        const d = await api("/auth/forgot", { method: "POST", body: { email } });
        $("#ok", root).innerHTML = `<div class="alert ok">${icon("checkc")}<div>${esc(d.message)}</div></div>` + (!d.mail_configured && !d.dev_reset_link ? `<div class="alert info">${icon("alert")}<div>Email is not configured on this server, so no message can be sent. Ask an administrator to reset your password.</div></div>` : "") +
          (d.dev_reset_link ? `<div class="alert info">${icon("alert")}<div><b>Dev mode:</b> <a href="${esc(d.dev_reset_link)}">open reset page</a></div></div>` : "");
      } catch (err) { showErr(root, err.message); }
    });
  });
}

function reset(root, params) {
  const token = new URLSearchParams(params || "").get("token") || "";
  root.innerHTML = shell("patient", `<h1>Choose a new password</h1><p class="muted">Pick something you have not used before.</p><div id="err" class="alert err hide" role="alert"></div>
    <form id="f" novalidate>${pwField("np", "New password")}<div class="meter" id="meter" data-s="0" style="margin-top:-8px;margin-bottom:16px"><i></i><i></i><i></i><i></i></div><button class="btn btn-primary btn-lg" style="width:100%" id="go">Update password</button></form>`);
  bindEyes(root);
  $("#np", root).addEventListener("input", () => ($("#meter", root).dataset.s = passwordScore($("#np", root).value)));
  $("#f", root).addEventListener("submit", async (e) => {
    e.preventDefault(); const pw = $("#np", root).value;
    if (!token) return showErr(root, "This reset link is incomplete. Request a new one.");
    if (pw.length < 8 || !/\d/.test(pw) || !/[A-Za-z]/.test(pw)) return fieldError($("#np", root), "Use 8+ characters with a letter and a number.");
    await withBusy($("#go", root), async () => {
      try { await api("/auth/reset", { method: "POST", body: { token, new_password: pw } }); toast("Password updated. Sign in now.", "ok"); go("#/login/patient"); }
      catch (err) { showErr(root, err.message); }
    });
  });
}

async function verify(root, params) {
  const token = new URLSearchParams(params || "").get("token") || "";
  root.innerHTML = shell("patient", `<h1>Verifying your email</h1><div id="v" class="muted">Please wait…</div>`);
  try { const r = await api("/auth/verify", { method: "POST", body: { token } }); $("#v", root).innerHTML = `<div class="alert ok">${icon("checkc")}<div>${esc(r.message)}</div></div><a class="btn btn-primary" href="#/login/patient">Sign in</a>`; }
  catch (e) { $("#v", root).innerHTML = `<div class="alert err">${icon("alert")}<div>${esc(e.message)}</div></div>`; }
}

export function renderAuth(root, kind, portal, params) {
  portal = ["billing", "admin"].includes(portal) ? portal : "patient";
  if (kind === "login") login(root, portal);
  else if (kind === "signup") signup(root, portal === "admin" ? "patient" : portal);
  else if (kind === "forgot") forgot(root);
  else if (kind === "verify") verify(root, params);
  else reset(root, params);
}
