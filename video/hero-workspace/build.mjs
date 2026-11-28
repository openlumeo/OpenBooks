// Usage: node build.mjs dark|light  -> sets theme class on #root in index.html
import { readFileSync, writeFileSync } from "node:fs";
const t = process.argv[2] === "light" ? "light" : "dark";
const s = readFileSync("index.html", "utf8").replace(/class="theme-(dark|light)"/, `class="theme-${t}"`);
writeFileSync("index.html", s);
console.log("theme:", t);
