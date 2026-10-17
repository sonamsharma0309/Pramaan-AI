// API client: cookie sessions (httpOnly, set by the server), CSRF header, silent refresh. No tokens live in JS.
export const auth = { user: null };
const readCookie = (n) => document.cookie.split("; ").find((c) => c.startsWith(n + "="))?.split("=")[1] || "";

export function errMsg(detail) {
  if (!detail) return "Something went wrong. Please try again.";
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) {
    return detail.map((d) => {
      const f = (d.loc || []).slice(-1)[0];
      if (f === "email") return "Enter a valid email address.";
      if (f === "password" || f === "new_password") return "Password must be 8 to 72 characters.";
      if (f === "message") return "Please write a little more (at least 10 characters).";
      return `${f ? f + ": " : ""}${d.msg}`;
    }).join(" ");
  }
  return String(detail);
}

let onExpire = () => {};
export const setExpireHandler = (fn) => (onExpire = fn);
export const setUser = (u) => (auth.user = u);
export const clearUser = () => (auth.user = null);

let refreshing = null;
function refresh() {
  refreshing ||= fetch("/api/auth/refresh", { method: "POST", headers: { "X-CSRF-Token": readCookie("pr_csrf") } })
    .then((r) => r.ok).catch(() => false).finally(() => setTimeout(() => (refreshing = null), 0));
  return refreshing;
}

async function raw(path, { method, body, form }) {
  const headers = {};
  const tok = readCookie("pr_csrf");
  if (tok) headers["X-CSRF-Token"] = tok;
  let payload;
  if (form) payload = form;
  else if (body !== undefined) { headers["Content-Type"] = "application/json"; payload = JSON.stringify(body); }
  try { return await fetch("/api" + path, { method, headers, body: payload }); }
  catch { throw new Error("Cannot reach the server. Is it running?"); }
}

export async function api(path, { method = "GET", body, form, blob = false, silent401 = false } = {}) {
  let res = await raw(path, { method, body, form });
  if (res.status === 401 && auth.user && !silent401 && !path.startsWith("/auth/")) {
    if (await refresh()) res = await raw(path, { method, body, form });   // one silent retry after rotating the refresh token
    if (res.status === 401) { clearUser(); onExpire(); throw new Error("Your session ended. Please sign in again."); }
  }
  if (!res.ok) {
    let d, extra = {}; try { const j = await res.json(); d = j.detail; extra = j; } catch { /* not json */ }
    const e = new Error(errMsg(d)); e.status = res.status; e.data = extra; throw e;
  }
  return blob ? res.blob() : res.json();
}

/** Called once at startup: asks the server who we are (the cookie is httpOnly, so JS cannot read it). */
export async function boot() {
  try { setUser((await api("/auth/me", { silent401: true })).user); }
  catch { if (await refresh()) { try { setUser((await api("/auth/me", { silent401: true })).user); return; } catch { /* fallthrough */ } } clearUser(); }
}

export async function download(path, filename) {
  const b = await api(path, { blob: true });
  const u = URL.createObjectURL(b); const a = document.createElement("a");
  a.href = u; a.download = filename; document.body.appendChild(a); a.click(); a.remove();
  setTimeout(() => URL.revokeObjectURL(u), 4000);
}
