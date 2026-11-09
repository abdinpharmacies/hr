import fs from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { Graphviz } from "@hpcc-js/wasm-graphviz";
import { D2 } from "@terrastruct/d2";

const scriptDir = path.dirname(fileURLToPath(import.meta.url));
const repoRoot = path.resolve(scriptDir, "..");
const demoDir = path.join(repoRoot, "examples/shop");
const graphviz = await Graphviz.load();

for (const file of ["graphviz-dependencies.dot", "graphviz-states.dot"]) {
  const source = await fs.readFile(path.join(demoDir, "sources", file), "utf8");
  const svg = graphviz.dot(source);
  const output = path.join(demoDir, "rendered", `${path.parse(file).name}.svg`);
  await fs.writeFile(output, svg);
  console.log(`${file} -> ${path.basename(output)} (${Buffer.byteLength(svg)} bytes)`);
}

const d2 = new D2();
for (const file of ["d2-architecture.d2", "d2-checkout.d2"]) {
  const source = await fs.readFile(path.join(demoDir, "sources", file), "utf8");
  const result = await d2.compile(source);
  const svg = await d2.render(result.diagram, result.renderOptions);
  const output = path.join(demoDir, "rendered", `${path.parse(file).name}.svg`);
  await fs.writeFile(output, svg);
  console.log(`${file} -> ${path.basename(output)} (${Buffer.byteLength(svg)} bytes)`);
}

// D2's worker keeps Node's event loop alive after rendering has completed.
process.exit(0);
