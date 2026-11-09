import fs from 'node:fs';
import path from 'node:path';

const manifestPath = process.argv[2] ?? 'diagram-manifest.json';
const root = path.resolve(process.argv[3] ?? process.cwd());
const absoluteManifest = path.resolve(root, manifestPath);

function fail(message) {
  console.error(`Manifest validation failed: ${message}`);
  process.exitCode = 1;
}

if (!fs.existsSync(absoluteManifest)) {
  fail(`manifest does not exist: ${manifestPath}`);
  process.exit();
}

let manifest;
try {
  manifest = JSON.parse(fs.readFileSync(absoluteManifest, 'utf8'));
} catch (error) {
  fail(`invalid JSON: ${error.message}`);
  process.exit();
}

const allowedProfiles = new Set([
  'tracked-source',
  'local-source/published-artifacts',
  'local-only-preview',
]);
if (!allowedProfiles.has(manifest.profile)) {
  fail(`profile must be one of ${[...allowedProfiles].join(', ')}`);
}
if (!Array.isArray(manifest.diagrams) || manifest.diagrams.length === 0) {
  fail('diagrams must be a non-empty array');
  process.exit();
}

const ids = new Set();
const sources = new Set();
const outputs = new Set();
const localPath = (value) => path.resolve(root, value);
const isRemote = (value) => /^(?:https?:|mailto:|data:|#)/i.test(value);

for (const diagram of manifest.diagrams) {
  const required = ['id', 'purpose', 'source', 'renderer', 'outputs', 'documents', 'publication'];
  if (!diagram || typeof diagram !== 'object' || Array.isArray(diagram)) {
    fail('each diagram entry must be an object');
    continue;
  }
  let missingField = false;
  for (const field of required) {
    if (!(field in diagram)) {
      fail(`${diagram.id ?? '<unknown>'} is missing ${field}`);
      missingField = true;
    }
  }
  if (missingField) continue;
  const validId = typeof diagram.id === 'string' && diagram.id.length > 0;
  const validPurpose = typeof diagram.purpose === 'string' && diagram.purpose.length > 0;
  const validSource = typeof diagram.source === 'string' && diagram.source.length > 0;
  const validRenderer = typeof diagram.renderer === 'string' && diagram.renderer.length > 0;
  const validOutputs = Array.isArray(diagram.outputs) && diagram.outputs.length > 0 && diagram.outputs.every((value) => typeof value === 'string');
  const validDocuments = Array.isArray(diagram.documents) && diagram.documents.every((value) => typeof value === 'string');
  if (!validId) fail('diagram id must be a non-empty string');
  if (!validPurpose) fail(`${diagram.id ?? '<unknown>'}: purpose must be a non-empty string`);
  if (!validSource) fail(`${diagram.id ?? '<unknown>'}: source must be a non-empty string`);
  if (!validRenderer) fail(`${diagram.id ?? '<unknown>'}: renderer must be a non-empty string`);
  if (!validOutputs) fail(`${diagram.id ?? '<unknown>'}: outputs must be a non-empty array of strings`);
  if (!validDocuments) fail(`${diagram.id ?? '<unknown>'}: documents must be an array of strings`);
  if (!validId || !validSource || !validOutputs || !validDocuments) continue;
  if (ids.has(diagram.id)) fail(`duplicate diagram id: ${diagram.id}`);
  ids.add(diagram.id);
  if (sources.has(diagram.source)) fail(`source is reused by multiple diagrams: ${diagram.source}`);
  sources.add(diagram.source);
  if (!fs.existsSync(localPath(diagram.source))) fail(`${diagram.id}: source is missing: ${diagram.source}`);
  if (!['source', 'output', 'both', 'local'].includes(diagram.publication)) {
    fail(`${diagram.id}: publication must be source, output, both, or local`);
  }
  const allowedPublication = {
    'tracked-source': new Set(['source', 'output', 'both']),
    'local-source/published-artifacts': new Set(['output']),
    'local-only-preview': new Set(['local']),
  };
  if (allowedPublication[manifest.profile] && !allowedPublication[manifest.profile].has(diagram.publication)) {
    fail(`${diagram.id}: publication ${diagram.publication} is incompatible with profile ${manifest.profile}`);
  }

  const referencedPaths = new Set();
  for (const document of diagram.documents ?? []) {
    const documentPath = localPath(document);
    if (!fs.existsSync(documentPath)) {
      fail(`${diagram.id}: document is missing: ${document}`);
      continue;
    }
    const text = fs.readFileSync(documentPath, 'utf8');
    const links = [...text.matchAll(/(?<!!)\[[^\]]*\]\(([^)\s]+)(?:\s+[^)]*)?\)/g)].map((match) => match[1]);
    for (const ref of links) {
      if (isRemote(ref)) continue;
      const resolved = path.resolve(path.dirname(documentPath), ref.split('#')[0]);
      referencedPaths.add(resolved);
      if (!fs.existsSync(resolved)) fail(`${document}: link target is missing: ${ref}`);
    }
    const imageRefs = [...text.matchAll(/!\[[^\]]*\]\(([^)\s]+)(?:\s+[^)]*)?\)/g)].map((match) => match[1]);
    for (const ref of imageRefs) {
      if (isRemote(ref)) continue;
      const resolved = path.resolve(path.dirname(documentPath), ref.split('#')[0]);
      referencedPaths.add(resolved);
      if (!fs.existsSync(resolved)) fail(`${document}: image reference is missing: ${ref}`);
    }
  }

  for (const output of diagram.outputs ?? []) {
    if (outputs.has(output)) fail(`output is reused by multiple diagrams: ${output}`);
    outputs.add(output);
    if (!fs.existsSync(localPath(output))) fail(`${diagram.id}: rendered output is missing: ${output}`);
    const sourceStem = path.basename(diagram.source).replace(path.extname(diagram.source), '');
    const outputStem = path.basename(output).replace(path.extname(output), '');
    if (sourceStem !== outputStem) {
      console.warn(`Warning: ${diagram.id} source/output basenames differ: ${sourceStem} -> ${outputStem}`);
    }
    if (diagram.documents?.length && ['output', 'both'].includes(diagram.publication) && !referencedPaths.has(localPath(output))) {
      console.warn(`Warning: ${diagram.id} output is not referenced by its declared documents: ${output}`);
    }
  }
}

if (process.exitCode) process.exit();
console.log(`Validated ${manifest.diagrams.length} diagram entries from ${manifestPath}`);
