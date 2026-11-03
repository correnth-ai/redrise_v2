// Copies the UI locale mask (reference copy; the UI bundles it) and the authorized logo assets into dist/ (after vite build).
import fs from "node:fs";
import path from "node:path";

const root = path.resolve(path.dirname(new URL(import.meta.url).pathname.replace(/^\/([A-Za-z]:)/, "$1")), "..");
const dist = path.join(root, process.argv[2] ?? "dist"); // "public" for the local demo server
const brand = process.env.REDRISE_BRAND_DIR ?? path.join(root, "..", "assets", "brand", "redrise");
fs.mkdirSync(path.join(dist, "assets"), { recursive: true });
fs.cpSync(path.join(root, "locale"), path.join(dist, "locale"), { recursive: true }); // UI locale mask
for (const f of ["redrise-lockup-light.svg", "redrise-lockup-dark.svg", "redrise-icon-32x32.png", "redrise-icon-64x64.png"]) {
  fs.copyFileSync(path.join(brand, f), path.join(dist, "assets", f));
}
fs.copyFileSync(path.join(brand, "..", "..", "auth", "login-register-background.png"), path.join(dist, "assets", "login-register-background.png"));
console.log("static copied to", dist);
