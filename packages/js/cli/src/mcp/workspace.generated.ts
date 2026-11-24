export interface WorkspacePackage {
  name: string;
  version: string;
  role: string;
}

export const WORKSPACE_PACKAGES: readonly WorkspacePackage[] = [
  {
    "name": "@lumeo_hq/openbooks",
    "version": "0.2.4",
    "role": "Open Books CLI: verify bank statements, settlements and tax documents and get one proven JSON per file, or a typed refusal."
  },
  {
    "name": "@lumeo_hq/openbooks/core",
    "version": "0.2.4",
    "role": "Typed wrapper around the Open Books Python engine: run a financial document, get an openbooks.v1 document or a typed refusal."
  },
  {
    "name": "@lumeo_hq/openbooks/statements",
    "version": "0.2.4",
    "role": "Typed access to the Python engine, restricted to the bank-statement layouts."
  },
  {
    "name": "@lumeo_hq/openbooks/gateways",
    "version": "0.2.4",
    "role": "Typed access to the Python engine, restricted to the payment-gateway layouts."
  },
  {
    "name": "@lumeo_hq/openbooks/tax",
    "version": "0.2.4",
    "role": "Typed access to the Python engine, restricted to the tax-document layouts."
  },
  {
    "name": "@lumeo_hq/openbooks/doctor",
    "version": "0.2.4",
    "role": "Typed access to the Python engine, restricted to the doctor layouts."
  },
  {
    "name": "@lumeo_hq/openbooks/mcp",
    "version": "0.2.4",
    "role": "MCP server that lets AI agents verify bank statements, settlements and tax documents and get proven JSON or a typed refusal."
  }
];
