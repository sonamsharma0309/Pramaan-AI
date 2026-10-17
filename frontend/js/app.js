// Hash router + route guards. The session lives in httpOnly cookies, so we ask the server who we are before routing.
import { auth, boot, setExpireHandler } from "./api.js";
import { renderAuth } from "./auth.js";
import { renderPortal } from "./portal/index.js";
import { renderPublic } from "./public.js";
import { go, initTheme } from "./ui.js";

const root = document.getElementById("app");
const KEY = { biller: "b", patient: "p", admin: "a" };
const home = () => `#/${KEY[auth.user?.role] || "p"}`;
let lastPortal = "patient";
setExpireHandler(() => go(`#/login/${lastPortal}`));

function route() {
  const raw = (location.hash || "#/").slice(1) || "/";
  const [path, query] = raw.split("?");
  const seg = path.split("/").filter(Boolean); const top = seg[0] || "";
  window.scrollTo(0, 0);
  if (["p", "b", "a"].includes(top)) {
    lastPortal = top === "b" ? "billing" : top === "a" ? "admin" : "patient";
    if (!auth.user) return go(`#/login/${lastPortal}`);
    if (top !== KEY[auth.user.role]) return go(home());
    return renderPortal(root, top, seg.slice(1));
  }
  if (top === "login" || top === "signup") { if (auth.user) return go(home()); return renderAuth(root, top, seg[1], query); }
  if (["forgot", "reset", "verify"].includes(top)) return renderAuth(root, top, "patient", query);
  if (top === "eligibility" || top === "contact") return renderPublic(root, top);
  if (["about", "partners", "resources"].includes(top)) return renderPublic(root, `${top}/${seg[1] || ""}`);
  return renderPublic(root, "home");
}

initTheme();
window.addEventListener("hashchange", route);
boot().then(() => { if (auth.user?.theme) initTheme(auth.user.theme); route(); });
