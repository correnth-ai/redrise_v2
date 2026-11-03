import { readFileSync, existsSync, lstatSync } from 'node:fs';
import { createHash } from 'node:crypto';
import { execFileSync } from 'node:child_process';
import { dirname, resolve, sep } from 'node:path';
import { fileURLToPath } from 'node:url';

// Foundation checks only. This script never installs dependencies or launches the app.
const root = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const checks = [];
const fail = (message) => { throw new Error(message); };
const check = (name, condition) => { if (!condition) fail(name); checks.push(name); };
const hash = (bytes) => createHash('sha256').update(bytes).digest('hex');
const inside = (relative) => {
  const path = resolve(root, relative);
  if (!path.startsWith(root + sep)) fail(`Outside repository: ${relative}`);
  return path;
};
const json = (relative) => JSON.parse(readFileSync(inside(relative), 'utf8').replace(/^\uFEFF/, ''));

try {
  const args = process.argv.slice(2);
  check('known arguments', args.every((arg) => arg === '--check-sources'));
  for (const file of ['AGENTS.md', 'README.md', '.ai-memory.toml', 'docs/BASELINE.md',
    'docs/ENGINE.md', 'docs/ENGINE-INVESTIGATION-PLAN.md', 'docs/TESTING-STRATEGY.md', 'docs/ERROR-DIAGNOSTICS.md', 'docs/AGENT-START-BETA.md', 'docs/ROADMAP.md', 'docs/BETA-ACCEPTANCE.md', 'docs/WORK-ORDER.md', 'docs/EVIDENCE.md']) {
    check(`nonempty ${file}`, readFileSync(inside(file), 'utf8').trim().length > 0);
  }
  for (const file of ['AGENTS.md', 'README.md', 'docs/BASELINE.md', 'docs/ROADMAP.md',
    'docs/ENGINE.md', 'docs/ENGINE-INVESTIGATION-PLAN.md', 'docs/TESTING-STRATEGY.md', 'docs/ERROR-DIAGNOSTICS.md', 'docs/AGENT-START-BETA.md', 'docs/BETA-ACCEPTANCE.md', 'docs/WORK-ORDER.md', 'docs/EVIDENCE.md',
    'assets/brand/redrise/README.md']) {
    const content = readFileSync(inside(file), 'utf8');
    for (const match of content.matchAll(/\[[^\]]*\]\(([^)]+)\)/g)) {
      const target = match[1].split('#')[0];
      if (!target || /^[a-z]+:/i.test(target)) continue;
      const path = resolve(dirname(inside(file)), target);
      check(`document link ${file} -> ${target}`, path.startsWith(root + sep) && existsSync(path));
    }
  }
  const identity = json('project.json');
  check('separate product and repository IDs', identity.product_id === 'product:redrise-v2' && identity.repository_id === 'repo:redrise-v2');
  check('expected commercial identity', identity.commercial_name === 'RedRise' && identity.working_label === 'RedRise v2');
  check('owned Engine direction explicit', identity.engine?.implementation === 'owned-from-scratch' && identity.engine.openadapt_runtime_required === false && identity.engine.upstream_cloud_mcp_qualification_required === false);
  check('per-user Windows installation', identity.windows_installation?.scope === 'per-user' && identity.windows_installation.default_directory === '%LOCALAPPDATA%\\Programs\\@redrise' && identity.windows_installation.customer_manual_plugin_or_port_setup === false && identity.windows_installation.data_and_vault_separate === true);
  const origin = execFileSync('git', ['remote', 'get-url', 'origin'], { cwd: root, encoding: 'utf8' }).trim();
  check('authorized origin', origin === 'https://github.com/correnth-ai/redrise_v2.git' && identity.remote === origin);
  const marker = readFileSync(inside('.ai-memory.toml'), 'utf8');
  check('isolated memory marker', /^workspace = "correnth"$/m.test(marker) && /^project = "redrise-v2"$/m.test(marker));

  const state = json('delivery/status.json');
  const phases = ['P00', 'I00', 'E01', 'E02', 'E03', 'E04', ...Array.from({ length: 14 }, (_, i) => `P${String(i + 1).padStart(2, '0')}`)];
  check('roadmap revision 4', state.roadmap_revision === 4);
  check('sequential unique step IDs', JSON.stringify(state.steps.map((step) => step.id)) === JSON.stringify(phases));
  const roadmap = readFileSync(inside('docs/ROADMAP.md'), 'utf8');
  const positions = phases.map((id) => roadmap.indexOf(`## ${id} — `));
  check('every ordered step documented', positions.every((pos, i) => pos >= 0 && (i === 0 || pos > positions[i - 1])));
  for (const [index, step] of state.steps.entries()) {
    check(`${step.id} allowed state`, ['not_started', 'in_progress', 'blocked', 'verified'].includes(step.status));
    check(`${step.id} exact predecessor`, JSON.stringify(step.depends_on) === JSON.stringify(index ? [phases[index - 1]] : []));
    if (step.status === 'verified') {
      check(`${step.id} verified predecessor`, !index || state.steps[index - 1].status === 'verified');
      check(`${step.id} evidence exists`, typeof step.evidence === 'string' && existsSync(inside(step.evidence)));
      const evidence = json(step.evidence);
      check(`${step.id} evidence identity`, evidence.step === step.id && evidence.status === 'verified');
      check(`${step.id} actual checks recorded`, Array.isArray(evidence.checks) && evidence.checks.length > 0 && evidence.checks.every((item) => item.result === 'passed'));
    }
  }
  check('internal closed-beta availability explicit', typeof state.closed_beta_available === 'boolean');
  if (state.closed_beta_available) {
    check('internal availability has evidence', typeof state.closed_beta_evidence === 'string' && existsSync(inside(state.closed_beta_evidence)));
  }
  if (state.beta_ready) check('Beta requires installed build and all steps verified', state.closed_beta_available && state.steps.every((step) => step.status === 'verified'));
  if (state.published) check('publication distinct from readiness', state.beta_ready && typeof state.publication_evidence === 'string' && existsSync(inside(state.publication_evidence)));
  check('prior OpenAdapt attempts are not active tasks', !state.historical_runs?.some((run) => run.id === 'P01-openadapt-20261024') && (state.next_step === null || phases.includes(state.next_step)));
  check('verification scope is limited to delivered features', identity.validation_policy?.functional_verifiers === 'implemented-in-scope-features-only' && identity.validation_policy.excluded_features_have_functional_gates === false);
  check('practical testing policy explicit', identity.validation_policy.clean_machine_required === false && identity.validation_policy.construction === 'localized-capability-and-relevant-contract-checks' && identity.validation_policy.full_e2e === 'manual-practical-after-installed-internal-closed-beta');
  check('diagnostic direction explicit', identity.error_diagnostics?.specification === 'docs/ERROR-DIAGNOSTICS.md' && identity.error_diagnostics.module_hints_are_confirmed_root_cause === false);

  const requirements = json('docs/requirements.json');
  check('exact D01-D51 traceability', JSON.stringify(requirements.requirements.map((item) => item.id)) === JSON.stringify(Array.from({ length: 51 }, (_, i) => `D${String(i + 1).padStart(2, '0')}`)));
  for (const item of requirements.requirements) {
    check(`${item.id} source and steps`, item.source.file === '01-DECISOES-CANONICAS.md' && item.source.anchor === item.id && item.steps.length > 0 && item.steps.every((id) => phases.includes(id)));
    check(`${item.id} source state explicit`, ['confirmed', 'proposal', 'superseded', 'technical_fact', 'derived_requirement'].includes(item.source_status));
  }
  const desktopExclusion = requirements.requirements.find((item) => item.id === 'D25');
  check('D25 is an explicit desktop exclusion', desktopExclusion.source_status === 'superseded' && desktopExclusion.requirement_kind === 'exclusion' && /Next\.js.*React.*desktop/.test(desktopExclusion.summary));
  for (const id of ['D02', 'D07', 'D08', 'D10', 'D11', 'D13', 'D23', 'D28', 'D29', 'D30', 'D48']) {
    const item = requirements.requirements.find((entry) => entry.id === id);
    check(`${id} current amendment preserves origin`, typeof item.original_summary === 'string' && item.original_summary.length > 0 && item.effective?.supplements?.includes('U26-ENGINE') && item.effective.change_status === 'amended-in-v2');
  }

  const provenance = json('assets/brand/redrise/provenance.json');
  check('logo reuse authorization', provenance.authorization === 'user-follow-up:2026-10-24:reuse-existing-redrise-logos');
  check('only 15 unique approved logos', provenance.assets.length === 15 && new Set(provenance.assets.map((asset) => asset.file)).size === 15);
  for (const asset of provenance.assets) {
    check(`logo name ${asset.file}`, /^redrise-(icon-\d+x\d+\.png|lockup-(light|dark)\.svg)$/.test(asset.file));
    const path = inside(`assets/brand/redrise/${asset.file}`);
    check(`logo regular file ${asset.file}`, lstatSync(path).isFile() && !lstatSync(path).isSymbolicLink());
    check(`logo digest ${asset.file}`, hash(readFileSync(path)) === asset.sha256);
  }

  const lock = json('docs/sources.lock.json');
  check('source package version and identity', lock.product_id === identity.product_id && lock.package_version === '1.1');
  check('canonical source filenames locked', lock.files.length === 11 && new Set(lock.files.map((item) => item.file)).size === 11 && lock.files.every((item) => /^[a-f0-9]{64}$/.test(item.sha256)));
  for (const id of ['U24-DEV-C', 'U25-INSTALL-DIR', 'U26-ENGINE', 'U26-INSTALL', 'U26-RECORDS', 'U26-VALIDATION-SCOPE', 'U26-INVESTIGATION', 'U27-PRACTICAL-TESTING', 'U27-ERROR-DIAGNOSTICS']) check(`direction supplement ${id}`, lock.supplements.some((item) => item.id === id) && requirements.supplements.includes(id));
  const catalogue = lock.external_references?.find((item) => item.id === 'REF-RE-CATALOGUE');
  check('RE catalogue is reference only', catalogue?.kind === 'curated-tools-and-learning-catalogue' && catalogue.runtime_dependency === false && catalogue.tools_installed_or_executed === false);
  check('catalogue investigation prerequisite explicit', catalogue.required_research_usage === true && catalogue.investigation_plan === 'docs/ENGINE-INVESTIGATION-PLAN.md' && identity.engine.investigation_prerequisite === 'I00');
  let sourceStatus = 'not-checked';
  if (args.includes('--check-sources')) {
    const sourceRoot = resolve(lock.source_root);
    for (const item of lock.files) {
      const path = resolve(sourceRoot, item.file);
      check(`source path bounded ${item.file}`, path.startsWith(sourceRoot + sep));
      check(`source digest ${item.file}`, hash(readFileSync(path)) === item.sha256);
    }
    sourceStatus = 'verified';
  }
  console.log(JSON.stringify({ status: 'passed', scope: 'foundation-only', checks: checks.length, source_package: sourceStatus, beta_ready: state.beta_ready, published: state.published }));
} catch (error) {
  console.error(JSON.stringify({ status: 'failed', scope: 'foundation-only', passed_checks: checks.length, reason: error.message }));
  process.exitCode = 1;
}
