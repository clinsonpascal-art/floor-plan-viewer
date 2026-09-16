/* LUXE scene engine — procedural furnished interiors (pure, testable). */
"use strict";

const VB = { w: 1600, h: 900 };
const cx = 800;

/* one-point perspective helpers (v: 0 near .. 1 far wall) */
const hw = v => 800 + (330 - 800) * v;           // half floor width at depth v
const fy = v => 900 + (470 - 900) * v;           // floor screen-y
const cyy = v => 0 + (150 - 0) * v;              // ceiling screen-y
const floorPt = (u, v) => [cx + u * hw(v), fy(v)];
const ceilPt  = (u, v) => [cx + u * hw(v), cyy(v)];
const pt3 = (u, v, hf) => { const [x, yf] = floorPt(u, v); return [x, yf + (cyy(v) - yf) * hf]; };
const P = pts => pts.map(p => p[0].toFixed(1) + "," + p[1].toFixed(1)).join(" ");
const poly = (pts, fill, extra) => `<polygon points="${P(pts)}" fill="${fill}" ${extra || ""}/>`;

const COL = {
  sofa:  { t: "#d3c8b6", f: "#c1b49d", s: "#ad9f86" },
  sofaB: { t: "#c4b9a5", f: "#b2a58d", s: "#9c8e75" },
  walnut:{ t: "#8a6a48", f: "#74553a", s: "#5e442d" },
  stone: { t: "#efe9dd", f: "#ddd4c3", s: "#c8bda8" },
  dark:  { t: "#3a4048", f: "#2c3138", s: "#22262b" },
  bed:   { t: "#e7e0d2", f: "#d7cebd", s: "#c2b8a3" },
  wood2: { t: "#9c8262", f: "#84694b", s: "#6c5239" },
};

/* shadow ellipse grounding a footprint centred at (u,v) */
function shadow(u, v, hu) {
  const [x, y] = floorPt(u, v);
  const rx = Math.abs(floorPt(u + hu, v)[0] - floorPt(u - hu, v)[0]) / 2 * 1.15;
  return `<ellipse cx="${x.toFixed(1)}" cy="${y.toFixed(1)}" rx="${rx.toFixed(1)}" ry="${(rx*0.26).toFixed(1)}" fill="url(#sh)"/>`;
}

/* 3D-ish box: centre u, near depth v0, depth dv, half-width hu, height frac hf */
function box(u, v0, dv, hu, hf, c) {
  const nL = floorPt(u - hu, v0), nR = floorPt(u + hu, v0);
  const fL = floorPt(u - hu, v0 + dv), fR = floorPt(u + hu, v0 + dv);
  const TnL = pt3(u - hu, v0, hf), TnR = pt3(u + hu, v0, hf);
  const TfL = pt3(u - hu, v0 + dv, hf), TfR = pt3(u + hu, v0 + dv, hf);
  let g = "";
  if (u <= 0) g += poly([nR, fR, TfR, TnR], c.s);      // right side visible
  else        g += poly([nL, fL, TfL, TnL], c.s);      // left side visible
  g += poly([nL, nR, TnR, TnL], c.f);                  // front face
  g += poly([TnL, TnR, TfR, TfL], c.t);                // top face
  return g;
}

/* rug: translucent floor quad */
function rug(u, v, hu, dv) {
  const q = [floorPt(u-hu,v), floorPt(u+hu,v), floorPt(u+hu,v+dv), floorPt(u-hu,v+dv)];
  return poly(q, "url(#rugG)", 'stroke="rgba(120,105,80,.25)" stroke-width="1.5"');
}

/* wall-mounted rect (side wall side=-1 left / +1 right) between depths & heights */
function wallRect(side, v0, v1, h0, h1, fill, extra) {
  const q = [pt3(side,v0,h0), pt3(side,v1,h0), pt3(side,v1,h1), pt3(side,v0,h1)];
  return poly(q, fill, extra);
}

/* ---------- furniture pieces ---------- */
const sofa = (u,v) => shadow(u,v+0.07,0.30)
  + box(u,v,0.15,0.28,0.13,COL.sofa)
  + box(u,v+0.11,0.05,0.28,0.30,COL.sofaB)
  + box(u-0.27,v,0.15,0.05,0.20,COL.sofaB)
  + box(u+0.27,v,0.15,0.05,0.20,COL.sofaB);

const coffee = (u,v) => shadow(u,v+0.03,0.14) + box(u,v,0.07,0.13,0.07,COL.walnut);

const diningSet = (u,v) => {
  let g = shadow(u,v+0.06,0.20) + box(u,v,0.12,0.20,0.10,COL.stone);
  [-0.16,0.16].forEach(dx => { g += box(u+dx,v-0.02,0.05,0.05,0.20,COL.walnut)+box(u+dx,v+0.14,0.05,0.05,0.20,COL.walnut); });
  g += pendant(u,v+0.05,0.72);
  return g;
};

const island = (u,v) => {
  let g = shadow(u,v+0.05,0.36) + box(u,v,0.12,0.34,0.17,COL.stone);
  g += `<rect x="${(floorPt(u-0.12,v+0.02)[0]).toFixed(1)}" y="${(pt3(u,v+0.02,0.17)[1]-4).toFixed(1)}" width="${(Math.abs(floorPt(u+0.12,v)[0]-floorPt(u-0.12,v)[0])).toFixed(1)}" height="8" fill="#2b3036" rx="2"/>`; // cooktop
  [-0.22,0,0.22].forEach(dx => g += pendant(u+dx, v+0.03, 0.74));
  [-0.22,0,0.22].forEach(dx => g += box(u+dx, v-0.12, 0.05,0.05,0.13, COL.dark)); // stools
  return g;
};

const bed = (u,v) => shadow(u,v+0.08,0.32)
  + box(u,v,0.24,0.30,0.11,COL.bed)
  + box(u,v+0.20,0.06,0.30,0.34,COL.wood2)              // headboard
  + box(u,v-0.02,0.06,0.24,0.14,"#f2ede2"===0?COL.bed:{t:"#f4efe6",f:"#e8e1d4",s:"#d8cfbe"}) // duvet fold
  + box(u-0.36,v+0.14,0.06,0.05,0.16,COL.walnut)        // nightstands
  + box(u+0.36,v+0.14,0.06,0.05,0.16,COL.walnut);

const bench = (u,v) => shadow(u,v+0.03,0.20) + box(u,v,0.05,0.18,0.07,COL.sofaB);

const tub = (u,v) => {
  const [x,y] = floorPt(u,v);
  const rx = Math.abs(floorPt(u+0.16,v)[0]-floorPt(u-0.16,v)[0])/2;
  return shadow(u,v+0.02,0.18)
    + `<ellipse cx="${x.toFixed(1)}" cy="${(y-14).toFixed(1)}" rx="${rx.toFixed(1)}" ry="${(rx*0.42).toFixed(1)}" fill="#e9e3d7" stroke="#cfc6b4" stroke-width="2"/>`
    + `<ellipse cx="${x.toFixed(1)}" cy="${(y-18).toFixed(1)}" rx="${(rx*0.78).toFixed(1)}" ry="${(rx*0.30).toFixed(1)}" fill="#f5f1e9"/>`;
};

const vanity = (u,v) => shadow(u,v+0.03,0.18) + box(u,v,0.06,0.16,0.14,COL.walnut)
  + wallRect(1,v-0.04,v+0.16,0.42,0.74,"#dfe6ea",'stroke="#c8a24a" stroke-width="2"'); // mirror on right wall

const console_ = (u,v) => shadow(u,v+0.02,0.16) + box(u,v,0.05,0.16,0.13,COL.walnut);

const desk = (u,v) => shadow(u,v+0.03,0.20) + box(u,v,0.06,0.20,0.13,COL.walnut)
  + box(u-0.05,v-0.08,0.05,0.05,0.16,COL.dark); // chair

const planter = (u,v) => { const [x,y]=floorPt(u,v);
  return box(u,v,0.03,0.04,0.10,COL.stone)
   + `<ellipse cx="${x.toFixed(1)}" cy="${(pt3(u,v,0.10)[1]-6).toFixed(1)}" rx="20" ry="12" fill="#5f7d55"/>`
   + `<ellipse cx="${x.toFixed(1)}" cy="${(pt3(u,v,0.16)[1]).toFixed(1)}" rx="14" ry="20" fill="#6f8c62"/>`;
};

const lounge = (u,v) => shadow(u,v+0.05,0.16) + box(u,v,0.14,0.13,0.09,{t:"#e7e0d2",f:"#d6cdb9",s:"#c0b5a0"})
  + box(u,v+0.10,0.04,0.13,0.24,{t:"#e7e0d2",f:"#d6cdb9",s:"#c0b5a0"});

function pendant(u,v,hf){ const [x,yc]=[cx+u*hw(v), cyy(v)]; const y=pt3(u,v,hf)[1];
  return `<line x1="${x.toFixed(1)}" y1="${yc.toFixed(1)}" x2="${x.toFixed(1)}" y2="${y.toFixed(1)}" stroke="#3a3a3a" stroke-width="1.5"/>`
   + `<circle cx="${x.toFixed(1)}" cy="${y.toFixed(1)}" r="9" fill="url(#bulb)"/>`;
}

/* ---------- shell ---------- */
function shell(view) {
  const nLf=floorPt(-1,0),nRf=floorPt(1,0),bLf=floorPt(-1,1),bRf=floorPt(1,1);
  const nLc=ceilPt(-1,0),nRc=ceilPt(1,0),bLc=ceilPt(-1,1),bRc=ceilPt(1,1);
  let g = "";
  g += poly([nLc,nRc,bRc,bLc],"url(#ceilG)");
  g += poly([nLf,nRf,bRf,bLf], view?"url(#floorV)":"url(#floorI)");
  g += poly([nLf,bLf,bLc,nLc],"url(#wallL)");
  g += poly([nRf,bRf,bRc,nRc],"url(#wallR)");
  for(let i=1;i<5;i++){const v=i/5;g+=`<line x1="${floorPt(-1,v)[0].toFixed(1)}" y1="${fy(v).toFixed(1)}" x2="${floorPt(1,v)[0].toFixed(1)}" y2="${fy(v).toFixed(1)}" stroke="rgba(120,105,80,.10)" stroke-width="1"/>`;}
  for(let i=-2;i<=2;i++){const u=i/2.1;g+=`<line x1="${floorPt(u,0)[0].toFixed(1)}" y1="${fy(0).toFixed(1)}" x2="${floorPt(u,1)[0].toFixed(1)}" y2="${fy(1).toFixed(1)}" stroke="rgba(120,105,80,.08)" stroke-width="1"/>`;}
  [[-0.5,0.55],[0.5,0.55],[0,0.85]].forEach(([u,v])=>{const c=ceilPt(u,v);g+=`<ellipse cx="${c[0].toFixed(1)}" cy="${c[1].toFixed(1)}" rx="9" ry="4" fill="url(#recess)"/>`;});
  g += poly([nLf,bLf,bLc,nLc],"url(#aoL)");
  g += poly([nRf,bRf,bRc,nRc],"url(#aoR)");
  return g;
}

function bayGlass() {
  const x0=cx-330,x1=cx+330,y0=cyy(1),y1=fy(1), w=x1-x0;
  const wy=y0+(y1-y0)*0.54;
  let g = `<rect x="${x0}" y="${y0}" width="${w}" height="${y1-y0}" fill="url(#sky)"/>`;
  g += `<rect x="${x0}" y="${(wy-3).toFixed(1)}" width="${w}" height="7" fill="#6a7860" opacity=".85"/>`;
  g += `<rect x="${x0}" y="${wy}" width="${w}" height="${(y1-wy).toFixed(1)}" fill="url(#water)"/>`;
  g += `<circle cx="${cx}" cy="${(wy-16).toFixed(1)}" r="30" fill="url(#sun)"/>`;
  g += `<rect x="${cx-34}" y="${wy}" width="68" height="${(y1-wy).toFixed(1)}" fill="url(#glint)"/>`;
  for(let i=1;i<6;i++){const mx=x0+w*i/6;g+=`<rect x="${(mx-2).toFixed(1)}" y="${y0}" width="4" height="${y1-y0}" fill="#aeb4bd" opacity=".92"/>`;}
  g += `<rect x="${x0}" y="${y0}" width="${w}" height="5" fill="#aeb4bd"/><rect x="${x0}" y="${(y1-6).toFixed(1)}" width="${w}" height="6" fill="#98a0a8"/>`;
  return `<g id="viewpar">${g}</g>`;
}

function backWall(door) {
  const x0=cx-330,x1=cx+330,y0=cyy(1),y1=fy(1),w=x1-x0;
  let g = `<rect x="${x0}" y="${y0}" width="${w}" height="${y1-y0}" fill="url(#wallG)"/>`;
  g += `<rect x="${x0}" y="${(y1-13).toFixed(1)}" width="${w}" height="6" fill="#d7cfbe"/>`;
  if (door) g += `<rect x="${cx-70}" y="${(y0+34).toFixed(1)}" width="140" height="${(y1-y0-40).toFixed(1)}" fill="url(#doorG)"/>`;
  else g += `<rect x="${cx-72}" y="${(y0+66).toFixed(1)}" width="144" height="150" fill="#ece6da" stroke="#c8a24a" stroke-width="3"/>`;
  return `<g id="viewpar">${g}</g>`;
}

/* terrace: open-air deck */
function terrace() {
  const nLf=floorPt(-1,0),nRf=floorPt(1,0),bLf=floorPt(-1,1),bRf=floorPt(1,1);
  const wy = 300;
  let g = `<rect x="0" y="0" width="${VB.w}" height="${VB.h}" fill="url(#sky)"/>`;
  g += `<rect x="0" y="${wy-4}" width="${VB.w}" height="8" fill="#6a7860" opacity=".8"/>`;
  g += `<rect x="0" y="${wy}" width="${VB.w}" height="${470-wy}" fill="url(#water)"/>`;
  g += `<circle cx="${cx}" cy="${wy-18}" r="34" fill="url(#sun)"/>`;
  g += `<rect x="${cx-40}" y="${wy}" width="80" height="${470-wy}" fill="url(#glint)"/>`;
  g += poly([nLf,nRf,bRf,bLf],"url(#deck)");        // deck
  for(let i=1;i<6;i++){const v=i/6;g+=`<line x1="${floorPt(-1,v)[0].toFixed(1)}" y1="${fy(v).toFixed(1)}" x2="${floorPt(1,v)[0].toFixed(1)}" y2="${fy(v).toFixed(1)}" stroke="rgba(90,70,50,.20)" stroke-width="1.5"/>`;}
  g += `<line x1="0" y1="470" x2="${VB.w}" y2="470" stroke="#cfd4da" stroke-width="3"/>`; // glass rail cap
  for(let i=0;i<=16;i++){const x=i*VB.w/16;g+=`<line x1="${x}" y1="430" x2="${x}" y2="470" stroke="rgba(180,190,200,.5)" stroke-width="1.5"/>`;}
  g += lounge(-0.45,0.28) + lounge(0.10,0.28) + planter(0.72,0.35);
  g += `<g id="viewpar"></g>`;
  return g;
}

/* per-room furniture */
function furniture(id) {
  switch(id){
    case "foyer":    return console_(-0.02,0.55) + planter(0.6,0.42);
    case "corridor": return rug(0,0.15,0.16,0.7) + console_(0.72,0.4) + planter(-0.72,0.4);
    case "den":      return rug(0,0.35,0.4,0.45) + desk(0.15,0.5) + console_(-0.55,0.45);
    case "great":    return rug(-0.05,0.30,0.5,0.5) + sofa(-0.28,0.42) + coffee(-0.05,0.5) + diningSet(0.5,0.35);
    case "kitchen":  return island(0,0.42) + wallRect(1,0.1,0.9,0.45,0.85,"#efe9dd",'stroke="#d8cfbe" stroke-width="1.5"') + planter(-0.7,0.35);
    case "primary":  return rug(-0.15,0.28,0.42,0.5) + bed(-0.12,0.34) + bench(-0.12,0.14);
    case "pbath":    return tub(-0.15,0.5) + vanity(0.6,0.4);
    case "bed2":     return rug(0.05,0.28,0.4,0.5) + bed(0.05,0.34);
    case "terrace":  return "";
    default:         return "";
  }
}

const DEFS = `<defs>
  <linearGradient id="sky" x1="0" y1="0" x2="0" y2="1">
    <stop offset="0" stop-color="#aecbe4"/><stop offset="0.55" stop-color="#f2d6a9"/>
    <stop offset="0.8" stop-color="#f8c877"/><stop offset="1" stop-color="#f6e6c2"/></linearGradient>
  <linearGradient id="water" x1="0" y1="0" x2="0" y2="1">
    <stop offset="0" stop-color="#3d78a0"/><stop offset="1" stop-color="#1d4a6b"/></linearGradient>
  <radialGradient id="sun"><stop offset="0" stop-color="#ffffff"/><stop offset="0.4" stop-color="#ffe7ad"/>
    <stop offset="1" stop-color="#f8c87700"/></radialGradient>
  <linearGradient id="glint" x1="0" y1="0" x2="0" y2="1">
    <stop offset="0" stop-color="#ffeec2" stop-opacity=".9"/><stop offset="1" stop-color="#ffeec2" stop-opacity="0"/></linearGradient>
  <linearGradient id="wallG" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#f1ebe0"/><stop offset="1" stop-color="#e2dbcb"/></linearGradient>
  <linearGradient id="doorG" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#5b5346"/><stop offset="1" stop-color="#3d382f"/></linearGradient>
  <linearGradient id="wallL" x1="0" y1="0" x2="1" y2="0"><stop offset="0" stop-color="#d9d1c0"/><stop offset="1" stop-color="#ece5d8"/></linearGradient>
  <linearGradient id="wallR" x1="1" y1="0" x2="0" y2="0"><stop offset="0" stop-color="#d9d1c0"/><stop offset="1" stop-color="#ece5d8"/></linearGradient>
  <linearGradient id="ceilG" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#f6f1e8"/><stop offset="1" stop-color="#e9e3d7"/></linearGradient>
  <radialGradient id="floorV" cx="0.5" cy="0.15" r="0.9"><stop offset="0" stop-color="#f0e7d5"/><stop offset="1" stop-color="#cdc0a5"/></radialGradient>
  <radialGradient id="floorI" cx="0.5" cy="0.2" r="0.9"><stop offset="0" stop-color="#e7ded0"/><stop offset="1" stop-color="#cabfa8"/></radialGradient>
  <linearGradient id="deck" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#b79a76"/><stop offset="1" stop-color="#8a6c4c"/></linearGradient>
  <radialGradient id="rugG"><stop offset="0" stop-color="#b9ac93" stop-opacity=".55"/><stop offset="1" stop-color="#9c8f76" stop-opacity=".45"/></radialGradient>
  <radialGradient id="sh"><stop offset="0" stop-color="rgba(30,22,12,.32)"/><stop offset="1" stop-color="rgba(30,22,12,0)"/></radialGradient>
  <radialGradient id="recess"><stop offset="0" stop-color="#fff3d6"/><stop offset="1" stop-color="#fff3d600"/></radialGradient>
  <radialGradient id="bulb"><stop offset="0" stop-color="#fff6df"/><stop offset="1" stop-color="#f6d99b00"/></radialGradient>
  <linearGradient id="aoL" x1="0" y1="0" x2="1" y2="0"><stop offset="0" stop-color="rgba(40,30,18,.22)"/><stop offset="0.25" stop-color="rgba(40,30,18,0)"/></linearGradient>
  <linearGradient id="aoR" x1="1" y1="0" x2="0" y2="0"><stop offset="0" stop-color="rgba(40,30,18,.22)"/><stop offset="0.25" stop-color="rgba(40,30,18,0)"/></linearGradient>
  <radialGradient id="sunwash" cx="0.5" cy="0.6" r="0.6"><stop offset="0" stop-color="rgba(255,226,160,.35)"/><stop offset="1" stop-color="rgba(255,226,160,0)"/></radialGradient>
  <radialGradient id="vig" cx="0.5" cy="0.5" r="0.75"><stop offset="0.6" stop-color="rgba(0,0,0,0)"/><stop offset="1" stop-color="rgba(0,0,0,.32)"/></radialGradient>
</defs>`;

function buildRoomSVG(id) {
  const r = ROOMS[id];
  let inner;
  if (id === "terrace") inner = terrace();
  else inner = shell(r.view) + (r.view ? bayGlass() : backWall(!!r.backDoor)) + furniture(id);
  const overlays = (r.view ? `<ellipse cx="800" cy="770" rx="560" ry="190" fill="url(#sunwash)"/>` : "")
    + `<rect x="0" y="0" width="${VB.w}" height="${VB.h}" fill="url(#vig)"/>`;
  return `<svg viewBox="0 0 ${VB.w} ${VB.h}" xmlns="http://www.w3.org/2000/svg" preserveAspectRatio="xMidYMid slice">${DEFS}${inner}${overlays}</svg>`;
}

/* ---------- room graph (Residence A) ---------- */
function _defaultRooms(){ return {
  foyer:{name:"Private Foyer",dim:"20′ × 6′",view:false,backDoor:true,
    feat:"Double-door entry · private elevator vestibule",x:96,y:20,w:34,h:22,
    links:[{to:"corridor",label:"Corridor",px:50,py:80,chev:"↓"}]},
  corridor:{name:"Corridor",dim:"Gallery hall",view:false,backDoor:true,
    feat:"Connects foyer, den, great room and the primary wing",x:60,y:44,w:24,h:40,
    links:[{to:"foyer",label:"Foyer",px:80,py:24,chev:"↑"},{to:"den",label:"Den",px:16,py:44,chev:"←"},
      {to:"great",label:"Great Room",px:52,py:84,chev:"↓"},{to:"primary",label:"Primary",px:18,py:80,chev:"↙"}]},
  den:{name:"Den",dim:"12′6″ × 8′4″",view:false,backDoor:false,
    feat:"Flex study / media · en-suite Bath 3 adjacent",x:16,y:20,w:34,h:22,
    links:[{to:"corridor",label:"Corridor",px:82,py:60,chev:"→"}]},
  great:{name:"Great Room",dim:"18′ × 15′4″",view:true,
    feat:"East floor-to-ceiling glass · opens to the Sunrise Terrace",x:46,y:88,w:46,h:44,
    links:[{to:"corridor",label:"Corridor",px:50,py:16,chev:"↑"},{to:"kitchen",label:"Kitchen",px:88,py:42,chev:"→"},
      {to:"bed2",label:"Bedroom 2",px:90,py:72,chev:"↘"},{to:"terrace",label:"Terrace",px:50,py:90,chev:"↓"}]},
  kitchen:{name:"Kitchen",dim:"15′4″ × 13′6″",view:false,backDoor:false,
    feat:"Center island · Gaggenau cooktop, double oven, fridge/freezer · wine cooler · pantry",x:96,y:64,w:34,h:30,
    links:[{to:"great",label:"Great Room",px:14,py:52,chev:"←"}]},
  primary:{name:"Primary Bedroom",dim:"15′8″ × 12′3″",view:true,
    feat:"East / bay view · en-suite Primary Bath · walk-in closet",x:10,y:104,w:34,h:34,
    links:[{to:"corridor",label:"Corridor",px:80,py:16,chev:"↗"},{to:"pbath",label:"Primary Bath",px:16,py:52,chev:"←"}]},
  pbath:{name:"Primary Bath",dim:"14′ × 12′4″",view:false,backDoor:false,
    feat:"Freestanding tub · dual vanity · Arclinea detailing · high-efficiency WC",x:10,y:62,w:34,h:34,
    links:[{to:"primary",label:"Primary Bedroom",px:56,py:86,chev:"↓"}]},
  bed2:{name:"Bedroom 2",dim:"15′7″ × 11′",view:true,
    feat:"East / bay view · en-suite Bath 2 · walk-in closet",x:96,y:104,w:34,h:34,
    links:[{to:"great",label:"Great Room",px:14,py:36,chev:"←"}]},
  terrace:{name:"Sunrise Terrace",dim:"40′ × 12′3″",view:true,
    feat:"Wraparound east terrace · summer kitchen · glass rail over Biscayne Bay",x:40,y:140,w:70,h:16,
    links:[{to:"great",label:"Great Room",px:50,py:14,chev:"↑"}]},
}; }
const _DORDER = ["foyer","corridor","den","great","kitchen","primary","pbath","bed2","terrace"];
let ROOMS, ORDER;
if (typeof window !== "undefined" && window.LUXE_ROOMS) { ROOMS = window.LUXE_ROOMS; ORDER = window.LUXE_ORDER || Object.keys(ROOMS); }
else { ROOMS = _defaultRooms(); ORDER = _DORDER.slice(); }
/* Photoreal drop-in: panos override scenes without replacing the graph. */
if (typeof window !== "undefined" && window.LUXE_PANOS) { for (const k in window.LUXE_PANOS) { if (ROOMS[k]) ROOMS[k].panorama_url = window.LUXE_PANOS[k]; } }

if (typeof module !== "undefined") module.exports = { buildRoomSVG, ROOMS, ORDER, VB };
