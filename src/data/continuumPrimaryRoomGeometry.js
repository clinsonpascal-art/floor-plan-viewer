// Static snapshot of REAL backend geometry - not invented data.
//
// This is exactly what GET /api/v1/jobs/{job_id}/geometry (or /rooms) already
// returns today for room_id "primary", unit "continuum-residence-01", from
// room_geometry.build_room_geometry() in the LUXE backend, reached through
// the real analyze.get_rooms() path with source_continuum_residence_01.jpg
// attached (source: "uploaded-plan-region", source_fidelity:
// "source_shape_plus_inferred_3d_openings"). Captured read-only for this
// browser-only proof of concept per the no-new-backend-work constraint - no
// backend files were touched to produce this file.
//
// Units: feet. coordinate_system "room_local_ft" means (x, y) is a flat
// plan-local footprint (x = width axis, y = depth axis); wall endpoints carry
// a 3rd coordinate that is always 0 here (it is NOT vertical height - height
// comes separately from height_ft/ceiling_ft). This file's consumer
// (PrimaryRoomPOC.jsx) is responsible for mapping plan (x, y) -> three.js
// (x, z) and treating height_ft as the vertical (three.js Y) extrusion.
export const CONTINUUM_PRIMARY_ROOM = {
  unit: "continuum-residence-01",
  room_id: "primary",
  name: "Primary Bedroom",
  coordinate_system: "room_local_ft",
  width_ft: 17.64,
  depth_ft: 12.68,
  ceiling_ft: 11.0,
  boundary: [
    [0, 0],
    [17.64, 0],
    [17.64, 12.68],
    [0, 12.68],
  ],
  walls: [
    { id: "wall_north", a: [0, 0, 0], b: [17.64, 0, 0], height_ft: 11.0 },
    { id: "wall_east", a: [17.64, 0, 0], b: [17.64, 12.68, 0], height_ft: 11.0 },
    { id: "wall_south", a: [17.64, 12.68, 0], b: [0, 12.68, 0], height_ft: 11.0 },
    { id: "wall_west", a: [0, 12.68, 0], b: [0, 0, 0], height_ft: 11.0 },
  ],
  // Present in the real backend data but intentionally NOT rendered by this
  // POC (doors/windows were out of scope for this pass) - kept here only so
  // the next increment doesn't have to re-fetch/re-derive them.
  doors: [
    { id: "door_01", wall: "wall_north", offset_ft: 8.82, width_ft: 3.0, height_ft: 7.0 },
  ],
  windows: [
    {
      id: "window_01", wall: "wall_east", offset_ft: 6.34, width_ft: 10.144,
      sill_height_ft: 0.3, head_height_ft: 10.4,
    },
  ],
};
