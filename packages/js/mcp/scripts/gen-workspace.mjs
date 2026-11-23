import { readdirSync, readFileSync, writeFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const here = dirname(fileURLToPath(import.meta.url));
const root = join(here, "..", "..");
const ROLE_LENGTH = 120;

const packages = readdirSync(root, { withFileTypes: true })
  .filter((entry) => entry.isDirectory() && entry.name !== "node_modules")
  .flatMap((entry) => {
    try {
      const manifest = JSON.parse(readFileSync(join(root, entry.name, "package.json"), "utf8"));
      if (manifest.private === true) return [];
      const role = String(manifest.description ?? "").split(/(?<=\.)\s/)[0].slice(0, ROLE_LENGTH);
      return [{ name: manifest.name, version: manifest.version, role }];
    } catch {
      return [];
    }
  })
  .sort((a, b) => a.name.localeCompare(b.name));

const body = `export interface WorkspacePackage {
  name: string;
  version: string;
  role: string;
}

export const WORKSPACE_PACKAGES: readonly WorkspacePackage[] = ${JSON.stringify(packages, null, 2)};
`;
writeFileSync(join(here, "..", "src", "workspace.generated.ts"), body);
