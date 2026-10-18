// Portal router: patient (#/p), billing (#/b), admin (#/a).
import { adminPage } from "./admin.js";
import { appealView, appealsList } from "./appeals.js";
import { claimDetail, claimsList, importView, startAppeal } from "./claims.js";
import { dashboard } from "./dashboard.js";
import { codesPage, policiesPage } from "./library.js";
import { settings } from "./settings.js";

export { logout } from "./shell.js";

export function renderPortal(root, key, rest) {
  const [sub, id] = rest;
  if (key === "a") return adminPage(root, sub || "");
  if (!sub) return dashboard(root, key);
  if (sub === "claims") return claimsList(root, key);
  if (sub === "claim") return claimDetail(root, key, id);
  if (sub === "appeals") return appealsList(root, key);
  if (sub === "appeal") return appealView(root, key, id);
  if (sub === "settings") return settings(root, key);
  if (sub === "policies") return policiesPage(root, key);
  if (sub === "import" && key === "b") return importView(root, key);
  if (sub === "codes" && key === "b") return codesPage(root, key);
  if (sub === "start" && key === "p") return startAppeal(root, key);
  return dashboard(root, key);
}
