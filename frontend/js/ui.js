// Small UI helpers shared by every page.
export const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
export const $ = (sel, root = document) => root.querySelector(sel);
export const $$ = (sel, root = document) => [...root.querySelectorAll(sel)];

const P = {
  home: "M3 11l9-8 9 8v9a1 1 0 0 1-1 1h-5v-6H9v6H4a1 1 0 0 1-1-1z",
  file: "M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8z M14 3v5h5 M9 13h6 M9 17h6",
  upload: "M12 16V4 M7 9l5-5 5 5 M4 20h16",
  book: "M4 19.5A2.5 2.5 0 0 1 6.5 17H20V3H6.5A2.5 2.5 0 0 0 4 5.5z M20 17v4H6.5A2.5 2.5 0 0 1 4 18.5",
  settings: "M4 6h10 M18 6h2 M4 12h4 M12 12h8 M4 18h12 M20 18h0 M14 4v4 M8 10v4 M16 16v4",
  logout: "M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4 M16 17l5-5-5-5 M21 12H9",
  shield: "M12 3l8 3v6c0 5-3.5 8-8 9-4.5-1-8-4-8-9V6z",
  bolt: "M13 2L4 14h7l-1 8 9-12h-7z",
  clock: "M12 7v5l3 2 M21 12a9 9 0 1 1-18 0 9 9 0 0 1 18 0",
  check: "M5 12.5l4.5 4.5L19 7.5",
  checkc: "M21 12a9 9 0 1 1-18 0 9 9 0 0 1 18 0 M8 12.5l3 3 5-6",
  plus: "M12 5v14 M5 12h14",
  search: "M21 21l-4.3-4.3 M17 11a6 6 0 1 1-12 0 6 6 0 0 1 12 0",
  chart: "M4 20V10 M10 20V4 M16 20v-7 M22 20H2",
  users: "M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2 M9 11a4 4 0 1 0 0-8 4 4 0 0 0 0 8 M22 21v-2a4 4 0 0 0-3-3.9 M16 3.1a4 4 0 0 1 0 7.8",
  menu: "M4 6h16 M4 12h16 M4 18h16",
  x: "M6 6l12 12 M18 6L6 18",
  download: "M12 4v12 M7 11l5 5 5-5 M4 20h16",
  copy: "M9 9h11v11H9z M5 15V5a1 1 0 0 1 1-1h10",
  eye: "M2 12s4-7 10-7 10 7 10 7-4 7-10 7S2 12 2 12z M12 15a3 3 0 1 0 0-6 3 3 0 0 0 0 6",
  eyeoff: "M3 3l18 18 M10.6 6.2A9.8 9.8 0 0 1 12 6c6 0 10 6 10 6a17 17 0 0 1-3.2 3.7 M6.5 6.9A16.7 16.7 0 0 0 2 12s4 7 10 7a9.5 9.5 0 0 0 4-.9",
  arrow: "M5 12h14 M13 6l6 6-6 6",
  chev: "M6 9l6 6 6-6",
  steth: "M6 3v6a4 4 0 0 0 8 0V3 M10 13v2a5 5 0 0 0 10 0v-2 M20 8a2 2 0 1 0 0 4 2 2 0 0 0 0-4",
  building: "M4 21V4a1 1 0 0 1 1-1h9a1 1 0 0 1 1 1v17 M15 9h4a1 1 0 0 1 1 1v11 M3 21h18 M8 7h3 M8 11h3 M8 15h3",
  user: "M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2 M12 11a4 4 0 1 0 0-8 4 4 0 0 0 0 8",
  layers: "M12 3l9 5-9 5-9-5z M3 13l9 5 9-5",
  lock: "M6 11h12v9H6z M8 11V8a4 4 0 0 1 8 0v3",
  dollar: "M12 2v20 M17 6.5C16 5 14 4.5 12 4.5c-2.5 0-4.5 1.2-4.5 3.2 0 4.8 9.5 2.3 9.5 7 0 2-2 3.3-4.5 3.3-2.2 0-4.2-.7-5.2-2.3",
  spark: "M12 3l2 6 6 2-6 2-2 6-2-6-6-2 6-2z",
  trash: "M4 7h16 M9 7V4h6v3 M6 7l1 13h10l1-13",
  print: "M7 9V3h10v6 M6 17H4v-6h16v6h-2 M7 14h10v7H7z",
  link: "M10 14a5 5 0 0 0 7 0l3-3a5 5 0 0 0-7-7l-1 1 M14 10a5 5 0 0 0-7 0l-3 3a5 5 0 0 0 7 7l1-1",
  alert: "M12 3l10 18H2z M12 10v5 M12 18h0",
  bell: "M18 8a6 6 0 0 0-12 0c0 7-3 9-3 9h18s-3-2-3-9 M13.7 21a2 2 0 0 1-3.4 0",
  moon: "M21 12.8A9 9 0 1 1 11.2 3a7 7 0 0 0 9.8 9.8z",
  sun: "M12 17a5 5 0 1 0 0-10 5 5 0 0 0 0 10 M12 1v2 M12 21v2 M4.2 4.2l1.4 1.4 M18.4 18.4l1.4 1.4 M1 12h2 M21 12h2 M4.2 19.8l1.4-1.4 M18.4 5.6l1.4-1.4",
  mail: "M4 4h16a1 1 0 0 1 1 1v14a1 1 0 0 1-1 1H4a1 1 0 0 1-1-1V5a1 1 0 0 1 1-1z M22 6l-10 7L2 6",
  filter: "M3 5h18l-7 8v6l-4 2v-8z",
  refresh: "M21 12a9 9 0 0 1-15.5 6.2 M3 12A9 9 0 0 1 18.5 5.8 M21 4v5h-5 M3 20v-5h5",
  history: "M3 12a9 9 0 1 0 3-6.7 M3 4v5h5 M12 7v5l3 2",
  key: "M21 2l-2 2 M15.5 7.5l3 3L22 7l-3-3 M7.8 15.2a5 5 0 1 1 1 1L3 22v-3h3v-3h3z",
  grid: "M3 3h8v8H3z M13 3h8v8h-8z M3 13h8v8H3z M13 13h8v8h-8z",
  ai: "M12 3v3 M12 18v3 M3 12h3 M18 12h3 M7 7l2 2 M15 15l2 2 M17 7l-2 2 M9 15l-2 2 M12 9a3 3 0 1 0 0 6 3 3 0 0 0 0-6",
};
export const icon = (n, cls = "") => `<svg class="ico ${cls}" viewBox="0 0 24 24" aria-hidden="true">${P[n].split(" M").map((d, i) => `<path d="${i ? "M" : ""}${d}"/>`).join("")}</svg>`;

export const logo = () => `<svg viewBox="0 0 64 64" aria-hidden="true"><rect width="64" height="64" rx="16" fill="#0B1B2B"/><circle cx="32" cy="32" r="19" fill="none" stroke="#8C8CFF" stroke-width="3.5"/><circle cx="32" cy="32" r="13" fill="none" stroke="#8C8CFF" stroke-width="1.5" stroke-dasharray="2.5 3"/><path d="M24 33l6 6 11-13" fill="none" stroke="#fff" stroke-width="4.5" stroke-linecap="round" stroke-linejoin="round"/></svg>`;
export const brand = (href = "#/") => `<a class="brand" href="${href}" aria-label="Pramaan AI home">${logo()}<span>Pramaan</span><small>AI</small></a>`;

export const money = (n) => "$" + Number(n || 0).toLocaleString("en-US", { maximumFractionDigits: 0 });
export const money2 = (n) => "$" + Number(n || 0).toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
export const pct = (n) => (n == null ? "–" : Math.round(n * 100) + "%");
export const fmtDate = (s) => { if (!s) return "–"; const d = new Date(s.length <= 10 ? s + "T00:00:00" : s.replace(" ", "T") + (s.includes("Z") ? "" : "Z")); return isNaN(d) ? s : d.toLocaleDateString("en-GB", { day: "numeric", month: "short", year: "numeric" }); };
const LABEL = { denied: "Denied", appeal_ready: "Appeal ready", appealed: "Appeal sent", recovered: "Recovered", lost: "Lost", written_off: "Written off", drafted: "Drafted", submitted: "Submitted", won: "Won", partial: "Partly won" };
export const statusLabel = (s) => LABEL[s] || s;
export const pill = (s) => `<span class="pill ${esc(s)}">${esc(LABEL[s] || s)}</span>`;

export function toast(msg, kind = "") {
  const t = document.createElement("div");
  t.className = "toast " + kind; t.textContent = msg; t.setAttribute("role", "status");
  $("#toasts").appendChild(t);
  setTimeout(() => t.remove(), 4200);
}

export function modal(html, { large = false } = {}) {
  const bg = document.createElement("div");
  bg.className = "modal-bg";
  bg.innerHTML = `<div class="modal ${large ? "lg" : ""}" role="dialog" aria-modal="true">${html}</div>`;
  const close = () => { bg.remove(); document.removeEventListener("keydown", onKey); };
  const onKey = (e) => e.key === "Escape" && close();
  bg.addEventListener("mousedown", (e) => e.target === bg && close());
  document.addEventListener("keydown", onKey);
  document.body.appendChild(bg);
  $$("[data-close]", bg).forEach((b) => b.addEventListener("click", close));
  const first = $("input,select,textarea,button", bg); first && first.focus();
  return { el: bg, close };
}

export const go = (hash) => { if (location.hash === hash) window.dispatchEvent(new HashChangeEvent("hashchange")); else location.hash = hash; };
export const debounce = (fn, ms = 250) => { let t; return (...a) => { clearTimeout(t); t = setTimeout(() => fn(...a), ms); }; };

export function passwordScore(pw, email = "") {
  let s = 0;
  if (pw.length >= 8) s++;
  if (/[A-Za-z]/.test(pw) && /\d/.test(pw)) s++;
  if (pw.length >= 12 || (/[A-Z]/.test(pw) && /[a-z]/.test(pw))) s++;
  if (/[^A-Za-z0-9]/.test(pw) && pw.length >= 10) s++;
  const local = email.split("@")[0].toLowerCase();
  if (local.length >= 4 && pw.toLowerCase().includes(local)) s = Math.min(s, 1);
  return pw ? Math.max(1, s) : 0;
}

export async function withBusy(btn, fn) {
  const html = btn.innerHTML; btn.disabled = true; btn.innerHTML = `<span class="spin"></span>`;
  try { return await fn(); } finally { btn.disabled = false; btn.innerHTML = html; }
}

/* ---------- theme (light/dark), saved per user on the server and mirrored locally for first paint ---------- */
export function applyTheme(t) {
  document.documentElement.dataset.theme = t === "dark" ? "dark" : "light";
  try { localStorage.setItem("pramaan_theme", t); } catch { /* private mode */ }
}
export const currentTheme = () => document.documentElement.dataset.theme || "light";
export function initTheme(serverTheme) {
  let t = serverTheme; try { t ||= localStorage.getItem("pramaan_theme"); } catch { /* ignore */ }
  applyTheme(t || (matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light"));
}

/* ---------- small helpers ---------- */
export function animateCount(el, to, { format = (n) => Math.round(n).toLocaleString("en-US"), ms = 900 } = {}) {
  if (matchMedia("(prefers-reduced-motion: reduce)").matches || !isFinite(to)) { el.textContent = format(to); return; }
  const t0 = performance.now();
  const tick = (t) => { const k = Math.min(1, (t - t0) / ms); el.textContent = format(to * (1 - Math.pow(1 - k, 3))); if (k < 1) requestAnimationFrame(tick); };
  requestAnimationFrame(tick);
}
export const skeleton = (n = 3) => Array.from({ length: n }, (_, i) => `<div class="skel" style="width:${90 - i * 14}%"></div>`).join("");
export const errorBox = (m, retry) => `<div class="alert err" role="alert">${icon("alert")}<div>${esc(m)}${retry ? ` <button class="btn btn-ghost btn-sm" data-retry style="margin-left:8px">Retry</button>` : ""}</div></div>`;
export const emptyBox = (title, text, action = "") => `<div class="card empty"><h3>${esc(title)}</h3><p>${esc(text)}</p>${action}</div>`;
export function fieldError(input, msg) {
  input.classList.toggle("err", !!msg); input.setAttribute("aria-invalid", msg ? "true" : "false");
  let h = input.parentElement.querySelector(".ferr");
  if (msg) { if (!h) { h = document.createElement("div"); h.className = "ferr"; h.setAttribute("role", "alert"); input.parentElement.appendChild(h); } h.textContent = msg; } else h?.remove();
}
