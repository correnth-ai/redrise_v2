#!/usr/bin/env node
// Deterministic SHA-256 digest of the tracked-candidate source tree.
// Used by evidence records while HEAD is unborn or the tree is uncommitted.
// Excludes ignored/local/generated paths; prints {digest, files} as JSON.
import { createHash } from "node:crypto";
import { readdirSync, readFileSync, statSync } from "node:fs";
import { join, relative, sep } from "node:path";
import { fileURLToPath } from "node:url";

const root = fileURLToPath(new URL("..", import.meta.url));
const EXCLUDED_DIRS = new Set([
  ".git", ".local", "node_modules", ".venv", "__pycache__", ".pytest_cache",
  ".ruff_cache", "target", "dist", "build", ".runtime", ".cache",
  "data", "recordings", "captures", "raw", "logs", "tmp",
]);
const EXCLUDED_FILES = [/\.log$/, /\.pyc$/, /^\.env/, /\.(pem|key|pfx|p12)$/];

function walk(dir, out) {
  for (const name of readdirSync(dir).sort()) {
    const full = join(dir, name);
    const st = statSync(full);
    if (st.isDirectory()) {
      if (!EXCLUDED_DIRS.has(name)) walk(full, out);
    } else if (!EXCLUDED_FILES.some((re) => re.test(name))) {
      out.push(full);
    }
  }
  return out;
}

const verbose = process.argv.includes("--list");
const files = walk(root, []).map((f) => ({
  path: relative(root, f).split(sep).join("/"),
  sha256: createHash("sha256").update(readFileSync(f)).digest("hex"),
}));
const tree = createHash("sha256");
for (const f of files) tree.update(`${f.sha256}  ${f.path}\n`);
const result = { digest: tree.digest("hex"), file_count: files.length };
if (verbose) result.files = files;
console.log(JSON.stringify(result, null, verbose ? 2 : 0));
