// Shared app frame: sidebar, header tools (AI status, notifications bell, theme toggle), autocomplete helper.
import { api, auth, clearUser } from "../api.js";
import { $, $$, applyTheme, brand, currentTheme, debounce, esc, fmtDate, go, icon } from "../ui.js";

export const NAV = {
  b: [["", "home", "Dashboard"], ["/claims", "file", "Denials"], ["/import", "upload", "Import 835"], ["/policies", "book", "Policy library"], ["/codes", "search", "Code lookup"], ["/appeals", "ai", "Appeals"], ["/settings", "settings", "Settings"]],
  p: [["", "home", "Overview"], ["/start", "plus", "Start an appeal"], ["/claims", "file", "My cases"], ["/appeals", "ai", "My appeals"], ["/settings", "settings", "Settings"]],
  a: [["", "grid", "Overview"], ["/users", "users", "Users"], ["/messages", "mail", "Messages"], ["/audit", "history", "Audit log"], ["/system", "settings", "System health"]],
};
const TITLE = { b: "Billing Portal", p: "Patient Portal", a: "Admin Console" };
const initials = (n) => (n || "?").split(/\s+/).map((x) => x[0]).slice(0, 2).join("").toUpperCase();

export async function logout() {
  try { await api("/auth/logout", { method: "POST", silent401: true }); } catch { /* already ended */ }
  clearUser(); go("#/");
}

export function frame(root, key, sub, title, lead, actions = "") {
  const B = "#/" + key;
  const items = NAV[key].map(([p, ic, l]) => `<a href="${B}${p}" class="${sub === p ? "on" : ""}">${icon(ic)}<span>${l}</span></a>`).join("");
  root.innerHTML = `<div class="mbar"><button id="mopen" aria-label="Open menu">${icon("menu")}</button>${brand(B)}<span style="width:34px"></span></div>
  <div class="shell"><aside class="side" id="side" aria-label="Sidebar">${brand(B)}<div class="portal-tag">${TITLE[key]}</div><nav aria-label="Portal">${items}</nav>
    <div class="me"><div class="av" aria-hidden="true">${esc(initials(auth.user.name))}</div><div style="min-width:0"><b>${esc(auth.user.name)}</b><span>${esc(auth.user.org || auth.user.email)}</span></div><button id="lo" aria-label="Sign out" title="Sign out">${icon("logout")}</button></div></aside>
  <main class="main" id="main"><div class="top"><div><h1>${esc(title)}</h1>${lead ? `<p class="muted" style="margin:0">${lead}</p>` : ""}</div>
    <div class="row wrap"><div class="tools" id="tools"></div>${actions}</div></div><div id="view"><div class="skel"></div><div class="skel" style="width:60%"></div><div class="skel" style="width:80%"></div></div></main></div>`;
  $("#lo", root).addEventListener("click", logout);
  $("#mopen", root).addEventListener("click", () => $("#side", root).classList.toggle("open"));
  $$("#side a", root).forEach((a) => a.addEventListener("click", () => $("#side", root).classList.remove("open")));
  mountTools(root, key);
  return { B, view: $("#view", root), root, key };
}

function mountTools(root, key) {
  const t = $("#tools", root);
  t.innerHTML = `<span class="pillbtn" id="ai" title="Whether an AI provider is configured. The app works offline either way."><span class="dot"></span><span>AI</span></span>
    <div style="position:relative"><button class="iconbtn" id="bell" aria-label="Notifications" aria-haspopup="true" aria-expanded="false">${icon("bell")}<span class="cnt hide" id="bc">0</span></button><div class="pop hide" id="pop" role="menu"></div></div>
    <button class="iconbtn" id="theme" aria-label="Toggle dark mode">${icon(currentTheme() === "dark" ? "sun" : "moon")}</button>`;
  api("/health").then((h) => { const i = h.integrations, ai = i.ai, nm = { anthropic: "Claude", gemini: "Gemini", ollama: "Ollama", openai_compatible: "Custom API" }[i.ai_provider] || "on"; $("#ai .dot", t).classList.toggle("on", ai); $("#ai span:last-child", t).textContent = ai ? `AI: ${nm}` : "AI: off"; $("#ai", t).title = ai ? `${nm} (${i.ai_model}) writes the letters; identifiers are removed first.` : "Using the built-in cited template. Set an AI provider in .env (Gemini, Ollama or Claude) to enable AI letters."; }).catch(() => {});
  $("#theme", t).addEventListener("click", async () => {
    const next = currentTheme() === "dark" ? "light" : "dark"; applyTheme(next);
    try { await api("/auth/theme", { method: "PUT", body: { theme: next } }); auth.user.theme = next; } catch { /* local only */ }
    window.dispatchEvent(new HashChangeEvent("hashchange"));
  });
  if (key === "a") { $("#bell", t).parentElement.classList.add("hide"); return; }
  const pop = $("#pop", t), bell = $("#bell", t);
  const load = async () => {
    try {
      const r = await api("/notifications"); const c = $("#bc", t); c.textContent = r.unread; c.classList.toggle("hide", !r.unread);
      pop.innerHTML = `<h4>Notifications</h4>` + (r.notifications.length ? r.notifications.map((n) => `<a class="nitem ${n.is_read ? "" : "unread"}" href="${esc(n.link || "#")}"><b>${esc(n.title)}</b><span>${esc(n.body)}</span><span style="display:block;font-size:12px">${fmtDate(n.created_at)}</span></a>`).join("") : `<div class="nitem"><span>You are all caught up.</span></div>`);
      $$(".nitem[href]", pop).forEach((a) => a.addEventListener("click", () => pop.classList.add("hide")));
    } catch { pop.innerHTML = `<div class="nitem"><span>Could not load notifications.</span></div>`; }
  };
  load();
  bell.addEventListener("click", async (e) => {
    e.stopPropagation(); const open = pop.classList.toggle("hide") === false; bell.setAttribute("aria-expanded", String(open));
    if (open) { await load(); try { await api("/notifications/read-all", { method: "POST" }); $("#bc", t).classList.add("hide"); } catch { /* ignore */ } }
  });
  document.addEventListener("click", () => pop.classList.add("hide"));
}

/** Debounced autocomplete for an input. fetcher(q) -> [{value,label,sub}] */
export function autocomplete(input, fetcher, onPick) {
  const wrap = input.parentElement; wrap.classList.add("ac");
  const list = document.createElement("div"); list.className = "aclist hide"; list.setAttribute("role", "listbox"); wrap.appendChild(list);
  const run = debounce(async () => {
    const q = input.value.trim(); if (q.length < 1) return list.classList.add("hide");
    try {
      const items = await fetcher(q);
      list.innerHTML = items.map((i, n) => `<button type="button" role="option" data-n="${n}"><b>${esc(i.label)}</b>${i.sub ? `<small>${esc(i.sub)}</small>` : ""}</button>`).join("");
      list.classList.toggle("hide", !items.length);
      $$("button", list).forEach((b) => b.addEventListener("click", () => { onPick(items[+b.dataset.n]); list.classList.add("hide"); }));
    } catch { list.classList.add("hide"); }
  }, 250);
  input.addEventListener("input", run);
  input.addEventListener("keydown", (e) => e.key === "Escape" && list.classList.add("hide"));
  document.addEventListener("click", (e) => { if (!wrap.contains(e.target)) list.classList.add("hide"); });
}
