"use strict";
const assert = require("node:assert/strict");
const { readFileSync } = require("node:fs");
const { createHash } = require("node:crypto");
const { resolve } = require("node:path");

const root = resolve(__dirname, "..");
const documentation = readFileSync(resolve(root, "SYSTEM_DOCUMENTATION.md"), "utf8");
const markers = [...documentation.matchAll(/<!-- docs-check: (\S+) ([a-f0-9]{64}) -->/g)];
assert.equal(markers.length, 2, "Document both server.py and index.html with docs-check markers");
for (const name of ["server.py", "index.html"]) {
  const marker = markers.find((match) => match[1] === name);
  assert.ok(marker, `Missing docs-check marker for ${name}`);
  const digest = createHash("sha256").update(readFileSync(resolve(root, name))).digest("hex");
  assert.equal(marker[2], digest, `${name} changed: review SYSTEM_DOCUMENTATION.md and update its docs-check marker`);
}
console.log("docs-check: OK");
