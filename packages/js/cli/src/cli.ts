#!/usr/bin/env node
if (process.argv[2] === "mcp") {
  process.argv.splice(2, 1);
  await import("./mcp/cli.js");
} else {
  const { main } = await import("./main.js");
  process.exitCode = await main(process.argv.slice(2));
}
