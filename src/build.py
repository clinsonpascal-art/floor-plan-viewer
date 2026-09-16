#!/usr/bin/env python3
"""Assemble the single-file tour: inject scene-engine.js into tour-template.html.

    python3 build.py            -> ../dist/luxe_virtual_tour.html
"""
import re, pathlib

HERE = pathlib.Path(__file__).parent
eng = (HERE / "scene-engine.js").read_text()
# strip the node-only export so the engine runs as a plain browser script
eng = re.sub(r'if \(typeof module.*?\};', '', eng, flags=re.S)
tpl = (HERE / "tour-template.html").read_text()
out = tpl.replace("__ENGINE__", eng)

assert "__ENGINE__" not in out, "token not replaced"
assert "function buildRoomSVG" in out, "engine missing"

dest = HERE.parent / "dist" / "luxe_virtual_tour.html"
dest.parent.mkdir(exist_ok=True)
dest.write_text(out)
print(f"built {dest} ({len(out)} bytes)")
