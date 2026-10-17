// Public website. Every number, list and text block is fetched from the API (see /api/site/content and /api/public/stats).
import { api, auth } from "./api.js";
import { $, $$, animateCount, brand, debounce, emptyBox, errorBox, esc, fieldError, icon, money, skeleton, toast, withBusy } from "./ui.js";

const DD = {
  about: { label: "About Us", items: [["#/about/support", "link", "What we support", "Denial types and payer policies we handle"], ["#/about/approach", "shield", "Our approach", "How every appeal is built from proof"], ["#/about/pramaan", "users", "About Pramaan AI", "The team and the idea behind it"]] },
  partners: { label: "For Partners", items: [["#/partners/providers", "steth", "For Providers", "Put denial recovery on autopilot"], ["#/partners/billing", "building", "For Billing Companies", "AI-assisted denial management at scale"]] },
  resources: { label: "Resources", items: [["#/resources/codes", "book", "Denial code guide", "Search the CARC, RARC and EOB dataset"], ["#/resources/playbook", "file", "Appeal playbook", "A routine for a first-level appeal"], ["#/resources/faq", "alert", "FAQ", "Deadlines, records and privacy"], ["#/contact", "mail", "Contact and partnerships", "Talk to the team"]] },
};
const LOGIN = [["#/login/patient", "user", "Patient Portal", "Track your own appeals"], ["#/login/billing", "building", "Billing Portal", "Denials, policies and revenue"]];
let contentCache = null;
export const getContent = () => (contentCache ||= api("/site/content").catch((e) => { contentCache = null; throw e; }));

const menu = (items) => `<div class="dd-menu" role="menu">${items.map(([h, i, t, d]) => `<a class="dd-item" role="menuitem" href="${h}"><span class="ib">${icon(i)}</span><div><b>${t}</b>${d ? `<span>${d}</span>` : ""}</div></a>`).join("")}</div>`;
const dd = (key, d, right = false) => `<div class="dd ${right ? "right" : ""}" data-dd="${key}"><button aria-haspopup="true" aria-expanded="false">${d.label} ${icon("chev")}</button>${menu(d.items)}</div>`;

export function navbar() {
  const home = auth.user ? (auth.user.role === "biller" ? "#/b" : auth.user.role === "admin" ? "#/a" : "#/p") : null;
  const right = home ? `<a class="btn btn-ink" href="${home}">Open dashboard</a>` : `${dd("login", { label: "Log in", items: LOGIN }, true)}<a class="btn btn-primary" href="#/eligibility">Start appeal</a>`;
  return `<header class="nav" id="nav"><div class="container nav-in">${brand()}
    <nav class="nav-links" aria-label="Main">${dd("about", DD.about)}${dd("partners", DD.partners)}${dd("resources", DD.resources)}</nav>
    <div class="nav-right">${right}</div><button class="burger" id="burger" aria-label="Open menu">${icon("menu")}</button></div>
    <div class="mnav" id="mnav">${["about", "partners", "resources"].map((k) => `<h6>${DD[k].label.toUpperCase()}</h6>${DD[k].items.map((i) => `<a href="${i[0]}">${i[2]}</a>`).join("")}`).join("")}
    <h6>LOG IN</h6>${LOGIN.map((i) => `<a href="${i[0]}">${i[2]}</a>`).join("")}<a class="btn btn-primary" style="margin-top:16px;color:#fff" href="#/eligibility">Start appeal</a></div></header>`;
}

export function footer() {
  return `<footer class="foot"><div class="container"><div class="foot-grid">
    <div>${brand()}<p style="margin-top:14px;max-width:26em">Pramaan means proof. We turn a denied claim into an appeal that shows its proof, line by line.</p></div>
    <div><h6>Product</h6><a href="#/about/approach">Our approach</a><a href="#/about/support">What we support</a><a href="#/eligibility">Eligibility check</a></div>
    <div><h6>Portals</h6><a href="#/login/patient">Patient Portal</a><a href="#/login/billing">Billing Portal</a><a href="#/signup/patient">Create account</a></div>
    <div><h6>Resources</h6><a href="#/resources/codes">Denial codes</a><a href="#/resources/faq">FAQ</a><a href="#/contact">Contact</a></div>
  </div><div class="foot-bot" id="foot-note"><span></span><span></span></div></div></footer>`;
}

export function mountNav(root) {
  const nav = $("#nav", root); if (!nav) return;
  const onScroll = () => nav.classList.toggle("scrolled", window.scrollY > 8);
  onScroll(); window.addEventListener("scroll", onScroll, { passive: true });
  const closeAll = () => $$(".dd", root).forEach((d) => { d.classList.remove("open"); $("button", d).setAttribute("aria-expanded", "false"); });
  $$(".dd", root).forEach((d) => {
    const b = $("button", d); const open = () => { closeAll(); d.classList.add("open"); b.setAttribute("aria-expanded", "true"); };
    b.addEventListener("click", (e) => { e.stopPropagation(); d.classList.contains("open") ? closeAll() : open(); });
    d.addEventListener("mouseenter", () => matchMedia("(hover:hover)").matches && open());
    d.addEventListener("mouseleave", () => matchMedia("(hover:hover)").matches && closeAll());
  });
  document.addEventListener("click", closeAll);
  document.addEventListener("keydown", (e) => e.key === "Escape" && closeAll());
  $("#burger", root).addEventListener("click", () => $("#mnav", root).classList.toggle("open"));
  $$("a", root).forEach((a) => a.addEventListener("click", () => { closeAll(); $("#mnav", root).classList.remove("open"); window.scrollTo(0, 0); }));
  getContent().then((c) => { const f = $("#foot-note", root); if (f) f.innerHTML = `<span>${esc(c.footer.note)}</span><span>${esc(c.footer.disclaimer)}</span>`; }).catch(() => {});
}

const page = (inner) => `${navbar()}<main id="main">${inner}</main>${footer()}`;
const ctaBand = () => `<section class="section tight"><div class="container"><div class="cta-band"><h2>Check your denial in two minutes.</h2><div class="row wrap"><a class="btn btn-primary btn-lg" href="#/eligibility">Check my eligibility ${icon("arrow")}</a><a class="btn btn-light btn-lg" href="#/signup/billing">Open billing portal</a></div></div></div></section>`;
const hero = (eyebrow, title, lead, extra = "") => `<section class="page-hero"><div class="container"><span class="eyebrow">${esc(eyebrow)}</span><h1 style="font-size:clamp(34px,4.5vw,54px)">${esc(title)}</h1>${lead ? `<p>${esc(lead)}</p>` : ""}${extra}</div></section>`;

/* hero card is illustrative; it is labelled as an example, and its values come from the fictional sample data endpoint */
export const stampCardHtml = () => `<div class="paper" aria-label="Illustration of a denial becoming an appeal">
  <div class="hd"><span>EXAMPLE · FICTIONAL DATA</span><span>835 · CLP MC1001</span></div>
  <div class="nm">Sample claim: MRI lumbar spine</div><div class="muted small">Denied by a sample payer · $1,800.00</div>
  <span class="tag">CARC 50 · Not deemed a medical necessity</span>
  <div class="step-l">${icon("checkc")}<div>Policy clause found: coverage needs 6 weeks of failed conservative therapy<em>P1</em></div></div>
  <div class="step-l">${icon("checkc")}<div>Chart shows 9 weeks of pain, naproxen and 12 physical therapy sessions<em>E1</em></div></div>
  <div class="step-l">${icon("checkc")}<div>Neurological findings documented in the notes<em>E2</em></div></div>
  <div class="step-l">${icon("checkc")}<div>Appeal drafted, every line cited back to policy and chart</div></div>
  <div class="pad"></div><div class="stamp">APPEAL READY<small>REVIEW &amp; SEND</small></div></div>`;

async function home(root) {
  root.innerHTML = page(`<div id="home">${skeleton(5)}</div>`); mountNav(root);
  const box = $("#home", root);
  try {
    const [c, s] = await Promise.all([getContent(), api("/public/stats")]);
    const live = (k, label, fmt) => `<div><div class="counter" data-count="${s[k] ?? ""}" data-fmt="${fmt || ""}">${s[k] == null ? "–" : ""}</div><span>${label}</span></div>`;
    box.outerHTML = `
    <section class="hero"><div class="container hero-grid"><div><h1>${esc(c.hero.title)}</h1><p class="lead">${esc(c.hero.lead)}</p>
      <div class="cta"><a class="btn btn-ink btn-lg" href="#/eligibility">Check my eligibility ${icon("arrow")}</a><a class="btn btn-ghost btn-lg" href="#/login/billing">Open billing portal</a></div>
      <div class="proof">${c.hero.proof.map((p) => `<span>${icon("checkc")} ${esc(p)}</span>`).join("")}</div></div>${stampCardHtml()}</div></section>
    <section class="section tight"><div class="container"><div class="livestats" aria-label="Live platform statistics">
      ${live("codes", "denial and remark codes in the dataset")}${live("policies", "payer policies indexed")}${live("appeals", "appeals generated")}${live("avg_win_probability", "average estimated win probability", "pct")}</div>
      <p class="srcnote">Live from the database. Win probabilities are estimates until real outcomes are recorded.</p></div></section>
    <section class="section tight"><div class="container"><div class="stats">${c.stats.map((x) => `<div><b>${esc(x.value)}</b><span>${esc(x.label)}</span></div>`).join("")}<div><b>${s.policy_chunks}</b><span>policy passages searchable right now</span></div></div>
      <p class="srcnote">${esc(c.stats.map((x) => x.source).filter(Boolean)[0] || "")}</p></div></section>
    <section class="section"><div class="container"><div class="sec-head"><span class="eyebrow">What changes</span><h2>The five-step chase, done in one pass</h2></div>
      <div class="flow">${c.flow.map((f, i) => `<div><span class="n">${i + 1}</span><h4>${esc(f.title)}</h4><p>${esc(f.text)}</p></div>`).join("")}</div></div></section>
    <section class="section white"><div class="container"><div class="sec-head"><span class="eyebrow">Two portals</span><h2>One engine, built for both sides of the denial</h2></div><div class="split">
      <div class="portal p1">${icon("user")}<h3>Patient Portal</h3><p style="opacity:.8">Denied a scan, surgery or therapy? Get a ready-to-review appeal.</p><ul>${c.portals.patient.map((x) => `<li>${icon("check")}${esc(x)}</li>`).join("")}</ul>
        <div class="row wrap"><a class="btn btn-light" href="#/signup/patient">Create patient account</a><a class="btn btn-ghost" style="color:#fff;border-color:#3A5675" href="#/login/patient">Log in</a></div></div>
      <div class="portal p2">${icon("building")}<h3>Billing Portal</h3><p style="opacity:.9">Import remittances, work the queue and see what you recovered.</p><ul>${c.portals.billing.map((x) => `<li>${icon("check")}${esc(x)}</li>`).join("")}</ul>
        <div class="row wrap"><a class="btn btn-light" href="#/signup/billing">Create billing account</a><a class="btn btn-ghost" style="color:#fff;border-color:#B7B7FF" href="#/login/billing">Log in</a></div></div></div></div></section>
    <section class="section"><div class="container"><div class="sec-head"><span class="eyebrow">Inside the engine</span><h2>Retrieval, extraction and a win estimate</h2></div>
      <div class="feat">${c.features.map((f) => `<div><span class="ib">${icon(f.icon)}</span><div><h4>${esc(f.title)}</h4><p>${esc(f.text)}</p></div></div>`).join("")}</div></div></section>${ctaBand()}`;
    $$("[data-count]", root).forEach((el) => {
      const v = parseFloat(el.dataset.count); if (isNaN(v)) { el.textContent = "–"; return; }
      animateCount(el, el.dataset.fmt === "pct" ? v * 100 : v, { format: (n) => (el.dataset.fmt === "pct" ? Math.round(n) + "%" : Math.round(n).toLocaleString("en-US")) });
    });
  } catch (e) { box.innerHTML = errorBox(e.message, true); $("[data-retry]", box)?.addEventListener("click", () => home(root)); }
}

const simplePage = (loader) => async (root, param) => {
  root.innerHTML = page(`<div class="container" style="padding:40px 24px">${skeleton(4)}</div>`); mountNav(root);
  try { const c = await getContent(); $("#main", root).innerHTML = await loader(c, root, param); const hook = $("#main", root).__after; hook && hook(); }
  catch (e) { $("#main", root).innerHTML = `<div class="container" style="padding:40px 24px">${errorBox(e.message)}</div>`; }
};
const items = (arr, cols = true) => `<div class="feat">${arr.map((x, i) => `<div><span class="ib mono">${i + 1}</span><div><h4>${esc(x.title)}</h4><p>${esc(x.text)}</p></div></div>`).join("")}</div>`;

const support = simplePage((c) => `${hero("What we support", "Denial types we can work today", "The bundled library covers sample payers. Billing teams add their own payer manuals as text, Word or PDF (with OCR for scans).")}
  <section class="section tight"><div class="container prose"><table class="codes"><thead><tr><th>Denial family</th><th>Typical cases</th></tr></thead><tbody>${c.support.map((r) => `<tr><td><b>${esc(r.family)}</b></td><td>${esc(r.cases)}</td></tr>`).join("")}</tbody></table>
  <h3>Not appealable</h3><p>Patient responsibility (CARC 1, 2, 3) and contractual fee-schedule adjustments are flagged, and no appeal is drafted.</p></div></section>${ctaBand()}`);
const approach = simplePage((c) => `${hero("Our approach", "An appeal is only as strong as its proof", "The letter never asserts something the chart does not show. Missing criteria are listed so staff can fix the gap before sending.")}
  <section class="section tight"><div class="container">${items(c.approach)}<div class="alert info" style="margin-top:30px">${icon("alert")}<div>The win estimate is labelled <b>synthetic</b> until at least 50 real outcomes are recorded and the model is retrained. Treat it as a way to sort work, not a promise.</div></div></div></section>${ctaBand()}`);
const about = simplePage((c) => `${hero("About Pramaan AI", c.about.title, c.about.lead)}
  <section class="section tight"><div class="container"><div class="team">${c.team.map((p) => `<div class="person"><div class="av">${esc(p.initials)}</div><b>${esc(p.name)}</b><span>${esc(p.role)} · ${esc(p.detail)}</span></div>`).join("")}</div><div class="prose" style="margin-top:36px"><h3>Why the name</h3><p>${esc(c.about.name_note)}</p></div></div></section>${ctaBand()}`);
const partners = (kind) => simplePage(() => `${hero(kind === "providers" ? "For providers" : "For billing companies", kind === "providers" ? "Put denial recovery on autopilot" : "Denial management that scales with your clients", "", `<a class="btn btn-ink btn-lg" href="#/signup/billing">Create billing account</a> <a class="btn btn-ghost btn-lg" href="#/contact">Talk to us</a>`)}
  <section class="section tight"><div class="container" id="pp">${skeleton(3)}</div></section>${ctaBand()}`);
const playbook = simplePage((c) => `${hero("Resources", "Appeal playbook", "")}<section class="section tight"><div class="container prose"><ol>${c.playbook.map((p) => `<li><b>${esc(p.title)}.</b> ${esc(p.text)}</li>`).join("")}</ol></div></section>${ctaBand()}`);
const faq = simplePage((c) => `${hero("Resources", "Frequently asked questions", "")}<section class="section tight"><div class="container faq prose">${c.faq.map((q) => `<details><summary>${esc(q.q)}</summary><p class="muted" style="margin:0">${esc(q.a)}</p></details>`).join("")}</div></section>${ctaBand()}`);

/* ---------- denial code lookup (CARC / RARC / EOB dataset) ---------- */
export function mountCodeLookup(box) {
  box.innerHTML = `<div class="card" style="margin-bottom:16px"><div class="row"><input class="inp" id="cq" placeholder="Search a code or words: 50, N115, authorization, modifier..." aria-label="Search denial codes"><button class="btn btn-ink" id="cb">${icon("search")} Search</button></div><p class="small muted" id="cs" style="margin:10px 0 0"></p></div><div id="cr"></div>`;
  api("/codes/stats").then((d) => ($("#cs", box).textContent = `${d.carc} CARC · ${d.rarc} RARC · ${d.eob} EOB codes. Source: ${d.source}`)).catch(() => {});
  const run = async () => {
    const q = $("#cq", box).value.trim(); if (!q) return;
    $("#cr", box).innerHTML = skeleton(3);
    try {
      const r = await api("/codes/search?q=" + encodeURIComponent(q));
      const sec = (t, rows) => rows.length ? `<h4 style="margin:22px 0 10px">${t} <span class="muted small">(${rows.length})</span></h4><div class="tbl-wrap"><table class="tbl" style="min-width:560px"><tbody>${rows.join("")}</tbody></table></div>` : "";
      const carc = r.carc.map((c) => `<tr style="cursor:default"><td style="width:90px"><span class="code">${esc(c.code)}</span></td><td><b>${esc(c.description)}</b><div class="small muted">${esc(c.category)}: ${esc(c.strategy)}</div></td></tr>`);
      const rarc = r.rarc.map((c) => `<tr style="cursor:default"><td style="width:90px"><span class="code">${esc(c.code)}</span></td><td>${esc(c.description)}</td></tr>`);
      const eob = r.eob.map((c) => `<tr style="cursor:default"><td style="width:90px"><span class="code">${esc(c.eob)}</span></td><td><b>${esc(c.desc)}</b><div class="small muted">CARC ${esc(c.carc || "–")}: ${esc(c.carc_desc)}${c.rarc ? `<br>RARC ${esc(c.rarc)}: ${esc(c.rarc_desc)}` : ""}</div></td></tr>`);
      $("#cr", box).innerHTML = carc.length + rarc.length + eob.length ? sec("Claim adjustment reason codes", carc) + sec("Remittance advice remark codes", rarc) + sec("EOB codes", eob) : emptyBox("No match", "Try a code like 197 or a word like modifier.");
    } catch (e) { $("#cr", box).innerHTML = errorBox(e.message); }
  };
  $("#cb", box).addEventListener("click", run); $("#cq", box).addEventListener("keydown", (e) => e.key === "Enter" && run());
}
const codes = simplePage(() => `${hero("Resources", "Denial code guide", "Search the official CARC, RARC and EOB code descriptions bundled with this project.")}<section class="section tight"><div class="container"><div id="lookup"></div></div></section>${ctaBand()}`);

/* ---------- contact / partner form ---------- */
function contact(root) {
  root.innerHTML = page(`${hero("Contact", "Talk to the team", "Questions, partnership ideas or a demo request. We read every message.")}<section class="section tight"><div class="container"><div class="card" style="max-width:640px">
    <form id="cf" novalidate><div class="fgrid"><div class="field"><label class="lb" for="cn">Your name</label><input class="inp" id="cn" maxlength="120" autocomplete="name"></div>
    <div class="field"><label class="lb" for="ce">Email</label><input class="inp" id="ce" type="email" autocomplete="email"></div></div>
    <div class="field"><label class="lb" for="ck">Topic</label><select class="inp" id="ck"><option value="general">General question</option><option value="partner">Partnership</option><option value="demo">Request a demo</option><option value="support">Support</option></select></div>
    <div class="field"><label class="lb" for="cm">Message</label><textarea class="inp" id="cm" maxlength="4000"></textarea></div>
    <div id="cmsg"></div><button class="btn btn-primary" id="cs">${icon("mail")} Send message</button></form></div></div></section>`);
  mountNav(root);
  const f = $("#cf", root);
  f.addEventListener("submit", async (e) => {
    e.preventDefault();
    const v = { name: $("#cn", root).value.trim(), email: $("#ce", root).value.trim(), kind: $("#ck", root).value, message: $("#cm", root).value.trim() };
    let bad = false;
    fieldError($("#cn", root), v.name.length < 2 ? (bad = true, "Enter your name.") : ""); fieldError($("#ce", root), /^\S+@\S+\.\S+$/.test(v.email) ? "" : (bad = true, "Enter a valid email."));
    fieldError($("#cm", root), v.message.length < 10 ? (bad = true, "Please write at least 10 characters.") : "");
    if (bad) return;
    await withBusy($("#cs", root), async () => {
      try { const r = await api("/contact", { method: "POST", body: v }); f.reset(); $("#cmsg", root).innerHTML = `<div class="alert ok">${icon("checkc")}<div>${esc(r.message)}</div></div>`; toast("Message sent", "ok"); }
      catch (er) { $("#cmsg", root).innerHTML = `<div class="alert err">${icon("alert")}<div>${esc(er.message)}</div></div>`; }
    });
  });
}

/* ---------- eligibility wizard (works without an account; options come from the API) ---------- */
async function eligibility(root) {
  root.innerHTML = page(`<section class="section tight"><div class="container"><div class="wiz" id="wiz">${skeleton(3)}</div></div></section>`); mountNav(root);
  const w = $("#wiz", root);
  let reasons = [], payers = [];
  try { [reasons, payers] = await Promise.all([api("/codes/list?appealable=true&limit=12").then((r) => r.codes), api("/payers").then((r) => r.payers)]); }
  catch (e) { w.innerHTML = errorBox(e.message, true); $("[data-retry]", w)?.addEventListener("click", () => eligibility(root)); return; }
  const a = { payer: "", denial_code: "", procedure: "", amount: 0, days_since_denial: 30, has_records: false };
  let step = 0; const N = 5; const next = () => { step++; draw(); };
  function draw() {
    const prog = `<div class="prog"><i style="width:${(step / N) * 100}%"></i></div><p class="small muted">Step ${Math.min(step + 1, N)} of ${N}</p>`;
    if (step === 0) w.innerHTML = prog + `<h2 style="font-size:30px">Who denied your claim?</h2><div class="field"><input class="inp" id="payer" list="pl" placeholder="Insurance company name" value="${esc(a.payer)}"><datalist id="pl">${payers.map((p) => `<option value="${esc(p)}">`).join("")}</datalist></div><button class="btn btn-ink" id="n">Continue</button>`;
    if (step === 1) w.innerHTML = prog + `<h2 style="font-size:30px">What reason did they give?</h2>${reasons.map((r) => `<button class="opt ${a.denial_code === r.code ? "on" : ""}" data-c="${esc(r.code)}"><div><span class="code">${esc(r.code)}</span> ${esc(r.description)}</div></button>`).join("")}`;
    if (step === 2) w.innerHTML = prog + `<h2 style="font-size:30px">What was denied?</h2><div class="field ac"><input class="inp" id="proc" placeholder="Type a procedure, for example knee" value="${esc(a.procedure)}" autocomplete="off"><div class="aclist hide" id="acl"></div></div><button class="btn btn-ink" id="n">Continue</button>`;
    if (step === 3) w.innerHTML = prog + `<h2 style="font-size:30px">How much is in dispute?</h2><div class="field"><input class="inp" id="amt" type="number" min="0" placeholder="Amount in USD" value="${a.amount || ""}"></div><button class="btn btn-ink" id="n">Continue</button>`;
    if (step === 4) w.innerHTML = prog + `<h2 style="font-size:30px">Two last questions</h2><div class="field"><label class="lb" for="days">Days since the denial</label><input class="inp" id="days" type="number" min="0" value="${a.days_since_denial}"></div><label class="check field"><input type="checkbox" id="rec" ${a.has_records ? "checked" : ""}> I have my doctor's notes or test results</label><button class="btn btn-ink" id="n">See my result</button>`;
    if (step === 5) return result();
    if (step === 1) { $$(".opt", w).forEach((b) => b.addEventListener("click", () => { a.denial_code = b.dataset.c; next(); })); return; }
    if (step === 2) wireProcedure();
    $("#n", w).addEventListener("click", () => {
      if (step === 0) { a.payer = $("#payer", w).value.trim(); if (!a.payer) return fieldError($("#payer", w), "Enter the insurer's name."); }
      if (step === 2) { a.procedure = $("#proc", w).value.trim(); if (!a.procedure) return fieldError($("#proc", w), "Tell us what was denied."); }
      if (step === 3) a.amount = Math.max(0, parseFloat($("#amt", w).value) || 0);
      if (step === 4) { a.days_since_denial = Math.max(0, parseInt($("#days", w).value, 10) || 0); a.has_records = $("#rec", w).checked; }
      next();
    });
  }
  function wireProcedure() {
    const inp = $("#proc", w), list = $("#acl", w);
    const run = debounce(async () => {
      const q = inp.value.trim(); if (q.length < 2) return list.classList.add("hide");
      try { const r = (await api("/procedures?q=" + encodeURIComponent(q))).procedures; list.innerHTML = r.map((p) => `<button type="button" data-d="${esc(p.description)}"><b>${esc(p.code)}</b> <small>${esc(p.description)}</small></button>`).join(""); list.classList.toggle("hide", !r.length);
        $$("button", list).forEach((b) => b.addEventListener("click", () => { inp.value = b.dataset.d; list.classList.add("hide"); })); } catch { list.classList.add("hide"); }
    });
    inp.addEventListener("input", run);
  }
  async function result() {
    w.innerHTML = skeleton(3);
    try {
      const r = await api("/public/eligibility", { method: "POST", body: { ...a } });
      w.innerHTML = `<div class="prog"><i style="width:100%"></i></div><div class="verdict ${r.verdict}"><h3>${esc(r.label)}</h3><div>Estimated chance: <b>${Math.round(r.probability * 100)}%</b> for ${esc(a.procedure)}${a.amount ? " (" + money(a.amount) + ")" : ""} <span class="badge">${r.model_kind === "trained" ? "learned from outcomes" : "estimate on synthetic data"}</span></div></div>
        <h4>What to do next</h4><ul class="nextl">${r.next_steps.map((s) => `<li>${icon("checkc")}<span>${esc(s)}</span></li>`).join("")}</ul>
        <div class="row wrap"><a class="btn btn-primary btn-lg" href="#/signup/patient">Build my appeal letter</a><button class="btn btn-ghost" id="again">Start over</button></div>
        <p class="small muted" style="margin:16px 0 0">A quick estimate from your answers, not a decision by your insurer.</p>`;
      $("#again", w).addEventListener("click", () => { step = 0; draw(); });
    } catch (e) { w.innerHTML = errorBox(e.message) + `<button class="btn btn-ink" id="again">Try again</button>`; $("#again", w).addEventListener("click", () => { step = 0; draw(); }); }
  }
  draw();
}

export function renderPublic(root, name) {
  if (name === "eligibility") return eligibility(root);
  if (name === "contact") return contact(root);
  const map = { home, "about/support": support, "about/approach": approach, "about/pramaan": about, "partners/providers": partners("providers"), "partners/billing": partners("billing"), "resources/codes": codes, "resources/playbook": playbook, "resources/faq": faq };
  const fn = map[name] || home;
  const done = fn(root);
  Promise.resolve(done).then(() => {
    const lk = $("#lookup", root); if (lk) mountCodeLookup(lk);
    const pp = $("#pp", root);
    if (pp) getContent().then((c) => { pp.innerHTML = items(name.endsWith("billing") ? c.portals.billing.map((t) => ({ title: t, text: "Included in the Billing Portal." })) : c.features.slice(0, 3)); });
  });
}
