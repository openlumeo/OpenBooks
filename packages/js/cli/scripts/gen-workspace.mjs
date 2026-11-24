import { readFileSync, writeFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const here = dirname(fileURLToPath(import.meta.url));
const manifest = JSON.parse(readFileSync(join(here, "..", "package.json"), "utf8"));

const MODULES = [
  ["", "Open Books CLI: verify bank statements, settlements and tax documents and get one proven JSON per file, or a typed refusal."],
  ["core", "Typed wrapper around the Open Books Python engine: run a financial document, get an openbooks.v1 document or a typed refusal."],
  ["statements", "Typed access to the Python engine, restricted to the bank-statement layouts."],
  ["gateways", "Typed access to the Python engine, restricted to the payment-gateway layouts."],
  ["tax", "Typed access to the Python engine, restricted to the tax-document layouts."],
  ["doctor", "Typed access to the Python engine, restricted to the doctor layouts."],
  ["mcp", "MCP server that lets AI agents verify bank statements, settlements and tax documents and get proven JSON or a typed refusal."],
];

const packages = MODULES.map(([module, role]) => ({
  name: module === "" ? manifest.name : `${manifest.name}/${module}`,
  version: manifest.version,
  role,
}));

const body = `export interface WorkspacePackage {
  name: string;
  version: string;
  role: string;
}

export const WORKSPACE_PACKAGES: readonly WorkspacePackage[] = ${JSON.stringify(packages, null, 2)};
`;
writeFileSync(join(here, "..", "src", "mcp", "workspace.generated.ts"), body);
