import fs from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { Graphviz } from "@hpcc-js/wasm-graphviz";
import { D2 } from "@terrastruct/d2";

const scriptDir = path.dirname(fileURLToPath(import.meta.url));
const repoRoot = path.resolve(scriptDir, "..");
const demoDir = path.join(repoRoot, "examples/ai-algorithms");
const sourceDir = path.join(demoDir, "sources");
const outputDir = path.join(demoDir, "rendered");
await fs.mkdir(outputDir, { recursive: true });

const graphviz = await Graphviz.load();
for (const file of [
  "graphviz-transformer.dot",
  "graphviz-bst.dot",
  "graphviz-graph.dot",
  "graphviz-stack.dot",
  "graphviz-queue.dot",
  "graphviz-hash-table.dot",
]) {
  const source = await fs.readFile(path.join(sourceDir, file), "utf8");
  const svg = graphviz.dot(source);
  const output = path.join(outputDir, `${path.parse(file).name}.svg`);
  await fs.writeFile(output, svg);
  console.log(`${file} -> ${path.basename(output)} (${Buffer.byteLength(svg)} bytes)`);
}

const d2 = new D2();
const file = "d2-moe-inference.d2";
const source = await fs.readFile(path.join(sourceDir, file), "utf8");
const result = await d2.compile(source);
const svg = await d2.render(result.diagram, result.renderOptions);
const output = path.join(outputDir, "d2-moe-inference.svg");
await fs.writeFile(output, svg);
console.log(`${file} -> ${path.basename(output)} (${Buffer.byteLength(svg)} bytes)`);

process.exit(0);
