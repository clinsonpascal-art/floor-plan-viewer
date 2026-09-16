/* Smoke test: build every room, assert clean SVG.  Run: node test-engine.js */
const { buildRoomSVG, ORDER } = require("./scene-engine.js");
let ok = true;
for (const id of ORDER) {
  try {
    const s = buildRoomSVG(id);
    if (!s.startsWith("<svg") || s.length < 800) { console.log("BAD", id, s.length); ok = false; }
    if (s.includes(".replace")) { console.log("LEAK", id); ok = false; }
    console.log(id.padEnd(10), s.length, "bytes");
  } catch (e) { console.log("THREW", id, e.message); ok = false; }
}
console.log(ok ? "ALL OK" : "FAILURES");
process.exit(ok ? 0 : 1);
