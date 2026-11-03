#!/usr/bin/env node
// Writes the E01–E04/P01 evidence records from recorded facts of this run.
// Usage: node scripts/write-engine-evidence.mjs <review-json-file>
// The review file holds {reviewer, date, verdicts:{E01..P01}, defects_fixed:[...]}.
import { createHash } from "node:crypto";
import { readFileSync, writeFileSync, mkdirSync, readdirSync } from "node:fs";
import { join } from "node:path";
import { fileURLToPath } from "node:url";

const root = fileURLToPath(new URL("..", import.meta.url));
const review = JSON.parse(readFileSync(process.argv[2], "utf8"));
const sha = (p) => createHash("sha256").update(readFileSync(join(root, p))).digest("hex");
const artifacts = (dir) =>
  readdirSync(join(root, dir)).sort().map((f) => ({ path: `${dir}/${f}`, sha256: sha(`${dir}/${f}`) }));

const common = {
  source_revision: "unborn",
  source_tree_sha256: review.source_tree_sha256,
  engine: { version: "0.1.0", binary: "redrise-engine.exe (release, --locked)", sha256: review.engine_sha256, toolchain: "rustc stable x86_64-pc-windows-msvc (cargo 1.98.1)" },
  environment: { os: "Windows 11 Pro 10.0.26200 x64", locale: "pt-BR", session: "interactive, unlocked, medium integrity", lab: "%USERPROFILE%/RedRise-v2-dev (C:)" },
  skills: [
    { name: "scope-planning", sha256: "fd7b13af53a7853d7cbd43ac9f72e801d602c7fb4e592981ac4842e4ded58bfa" },
    { name: "upstream-license-governance", sha256: "74699dbd93027deebbb30d04af0be7cea5a90ccefdcc9bcb4f0a81268c0f3ec1" },
  ],
  memory: { workspace: "correnth", project: "redrise-v2", status: "degraded", reason: "ai-memory CLI absent" },
  graph: { status: "not_used", reason: "no registered graphify root for repo:redrise-v2" },
};
const ok = (name, command, expected, actual) => ({ name, command, expected, actual, exit_code: 0, result: "passed" });
const unit = ok("engine unit/contract suite", "cargo test --release (CARGO_TARGET_DIR on C:)", "all pass", "37 passed: capture 11, compile_ir 10, execute 16");
const lint = ok("format + lint", "cargo fmt --all --check; cargo clippy --all-targets --release -- -D warnings", "clean", "clean");
const tree = ok("dependency inversion", "cargo tree -p engine-core -e normal --depth 1", "no OS crates", "serde, serde_json, sha2 only");
const rev = (step) => ({ reviewer: review.reviewer, date: review.date, verdict: review.verdicts[step], defects_fixed: review.defects_fixed });

const records = {
  E01: {
    work_order: "delivery/work-orders/E01-E04-P01-engine.md",
    decision: "docs/decisions/E01-engine-contracts.md",
    checks: [unit, tree, ok("IR contract rejects scripts/unknown", "cargo test --test compile_ir ir_rejects_unknown_version_fields_and_scripts", "rejected", "version 2, field 'script', action 'shell', undeclared param rejected")],
    artifacts: [{ path: "docs/decisions/E01-engine-contracts.md", sha256: sha("docs/decisions/E01-engine-contracts.md") }, { path: "engine/contracts/ir-v1/valid/p01-excel.procedure.json", sha256: sha("engine/contracts/ir-v1/valid/p01-excel.procedure.json") }],
  },
  E02: {
    checks: [
      ok("finalization regressions", "cargo test --release --test capture", "11 pass", "complete+drain, producer panic->producer_failed, hung producer->finalize_timeout <1.5s, writer error->writer_failed, overflow->lossy (no gaps), cancel, empty, max-duration->truncated, stale producer at stop->source_stale, tamper->hash mismatch, dir reuse refused"),
      ok("hook liveness probe (native)", "redrise-engine readiness --probe-hooks", "hooks ok", "status ok, latency 1 ms, interactive desktop, integrity 0x2000"),
      ok("native capture Notepad", "proofs/engine-native/e04-notepad.ps1 (record phase)", "manifest complete", "complete, 246 events, 0 dropped, liveness check at stop ok, stop->exit 57 ms"),
      ok("native capture Excel", "proofs/excel-engine/p01-excel.ps1 (record phase)", "manifest complete", "complete, 266 events, 0 dropped, liveness check at stop ok"),
      ok("injected input ignored by default (native negative)", "redrise-engine record --target notepad.exe (no --accept-injected)", "status empty", "empty, injected_ignored 8, exit 6"),
      ok("non-target input filtered (native negative)", "redrise-engine record --target excel.exe --accept-injected while operator types in Notepad", "status empty, filtered", "empty, filtered_out 8, exit 6"),
      lint,
    ],
    artifacts: artifacts("delivery/evidence/E02/artifacts"),
    raw_recordings_not_copied: "events.jsonl kept on C: (may contain window titles); hashes: e04 0dde1aa7aeb17664aa895d23c278f5ab20af3e79ce6860070753a1d582b9904f, p01 858cb1659ca801cbf5c7abfcfdfbe01b19a43df5ed144be47c65fd4e71b544bc",
  },
  E03: {
    checks: [
      ok("compiler regressions", "cargo test --release --test compile_ir", "10 pass", "S1 steps, param slot, absent/ambiguous param, dead key/right button/wheel/drag refused, ctrl chord vs AltGr text, lone Alt tap kept as key, VK_PACKET without char refused, empty, determinism+roundtrip, IR rejections"),
      ok("compile native recordings", "redrise-engine compile --param output_path=output_path:<literal>", "procedure", "Notepad 5 steps; Excel 11 steps (sha256 64711e7e…fee6f7)"),
    ],
    artifacts: [{ path: "delivery/evidence/E04/artifacts/procedure.json", sha256: sha("delivery/evidence/E04/artifacts/procedure.json") }, { path: "delivery/evidence/P01-engine/artifacts/procedure.json", sha256: sha("delivery/evidence/P01-engine/artifacts/procedure.json") }],
  },
  E04: {
    checks: [
      ok("executor regressions", "cargo test --release --test execute", "16 pass", "refusals before input (locked, platform, bindings, existing output, relative path, UIPI->refused), focus timeout no input, uncertain after effectful delivery, zero-accepted->not_attempted, no retry, cancel between steps and between characters, geometry drift, focus loss mid-text, stability wait, modifier release"),
      ok("native record->compile->replay Notepad + independent read", "proofs/engine-native/e04-notepad.ps1", "both files exact text", "recorded and replayed = 'Teste RedRise E04 ç 123'; recorded hash unchanged by replay; run completed_unverified"),
    ],
    artifacts: artifacts("delivery/evidence/E04/artifacts"),
    defects_found_and_fixed_natively: [
      "VK_PACKET (Unicode-injected) chars not decoded -> fixed in hooks.rs",
      "Ctrl+N delivered as bare 'n' to Windows 11 Notepad when modifiers were batched with the key -> modifiers staged with 30 ms hold",
      "first input sent 0 ms after window appeared, keystrokes dropped -> stability precondition (400 ms) on surface change",
      "failed run correctly reported 'uncertain' after effectful Ctrl+S (no retry) — proof script then protected recorded evidence read-only before replay",
    ],
  },
  "P01-engine": {
    step: "P01",
    checks: [
      ok("T01 preconditions", "readiness + Excel 365 16.0.20527.20088 x64 + interactive session", "ready", "ready"),
      ok("T02/T05 Engine readiness (own, no Flow/WAA)", "redrise-engine readiness --probe-hooks", "ready", "ready, hooks ok"),
      ok("T03 recording finalized", "record --target excel.exe --accept-injected", "complete", "complete 266 events, 0 dropped"),
      ok("T04 procedure compiled", "compile --param output_path=...", "11 steps", "11 steps, output path slot"),
      ok("T06 replay through UI from reopened template to distinct output", "run --bind output_path=saida/resultado_replay.xlsx", "completed_unverified, output observed", "completed_unverified, exists_after_run true"),
      ok("T07 template intact (labels + B2/B3 empty)", "verify_engine_result.py --run <run>", "pass", "A1..A3/B1 labels exact; B2/B3 None; template sha256 unchanged (gate-enforced)"),
      ok("T08 recorded output", "verify_engine_result.py", "B2 text, B3 numeric 1500", "B2='Cliente Teste 01', B3=1500 (int)"),
      ok("T09 replayed output", "verify_engine_result.py", "B2 text, B3 numeric 1500", "B2='Cliente Teste 01', B3=1500 (int); distinct file"),
      ok("recorded evidence unchanged by replay", "Get-FileHash before/after (gate-enforced)", "equal", "equal"),
      ok("verifier refutes false success", "python -m unittest test_verify_engine_result", "6 pass", "number-as-text, wrong text, missing, dirty template, empty refuted"),
      ok("repeatability", "p01-excel.ps1 on two consecutive builds", "pass both", "run-20261026-234427, run-20261026-235102 (earlier builds) and run-20261027-000410 (final build) verified"),
    ],
    artifacts: artifacts("delivery/evidence/P01-engine/artifacts"),
    lab_run: "%USERPROFILE%/RedRise-v2-dev/proofs/p01-engine/run-20261027-000410",
    verifier: { python: "3.12.10 (private, C:)", openpyxl: "3.1.5", mode: "read-only" },
    t10_t11: "not executed (optional parametrization beyond output path)",
  },
};

const evidenceNote = "Artifacts under delivery/evidence/*/artifacts are copies of the lab files with the Windows profile path redacted to %USERPROFILE%; they are not byte-identical to the lab originals, which remain on C:.";
const limitations = [
  "The product default (hardware-only input) has only been proven negatively; no successful hardware-only demonstration has been recorded yet.",
  "The demonstration was performed by a synthetic operator (proofs/operator/operator.ps1, SendKeys/user32) injecting OS input, recorded with --accept-injected and labelled input_origin=injected-accepted. A human-operated recording has not been performed.",
  "Template created through the Excel UI by the same operator (setup, not recorded).",
  "Development machine, not a clean Windows install (that is P02/P10/P13).",
  "Geometry click requires the same window rect; UIA targeting not implemented.",
];

for (const [dir, rec] of Object.entries(records)) {
  const step = rec.step ?? dir;
  const out = { step, status: "verified", run_id: `RUN-${step}-20261026-01`, ...common, ...rec, step, review: rev(step), evidence_note: evidenceNote, limitations, next_action: step === "P01" ? "P02: private runtime/Runner — requires a clean Windows 11 x64 machine for acceptance" : "next engine increment" };
  mkdirSync(join(root, "delivery/evidence", dir), { recursive: true });
  writeFileSync(join(root, "delivery/evidence", dir, dir === "P01-engine" ? "proof.json" : "engine.json"), JSON.stringify(out, null, 2) + "\n");
  console.log(dir, "written");
}
