export interface WorkspacePackage {
  name: string;
  version: string;
  role: string;
}

export const WORKSPACE_PACKAGES: readonly WorkspacePackage[] = [
  {
    "name": "@lumeo_hq/openbooks",
    "version": "0.2.3",
    "role": "Open Books CLI: verify bank statements, settlements and tax documents and get one proven JSON per file, or a typed refus"
  },
  {
    "name": "@lumeo_hq/openbooks-core",
    "version": "0.2.3",
    "role": "Typed wrapper around the Open Books Python engine: run a financial document, get an openbooks.v1 document or a typed ref"
  },
  {
    "name": "@lumeo_hq/openbooks-doctor",
    "version": "0.2.3",
    "role": "Open Books doctor wrapper: typed access to the Python engine, restricted to the doctor layouts"
  },
  {
    "name": "@lumeo_hq/openbooks-gateways",
    "version": "0.2.3",
    "role": "Open Books gateways wrapper: typed access to the Python engine, restricted to the gateways layouts"
  },
  {
    "name": "@lumeo_hq/openbooks-mcp",
    "version": "0.2.3",
    "role": "MCP server that lets AI agents verify bank statements, settlements and tax documents with Open Books and get proven JSON"
  },
  {
    "name": "@lumeo_hq/openbooks-statements",
    "version": "0.2.3",
    "role": "Open Books statements wrapper: typed access to the Python engine, restricted to the statements layouts"
  },
  {
    "name": "@lumeo_hq/openbooks-tax",
    "version": "0.2.3",
    "role": "Open Books tax wrapper: typed access to the Python engine, restricted to the tax layouts"
  }
];
