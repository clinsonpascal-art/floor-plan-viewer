// Static snapshot of REAL backend geometry for every Continuum Residence 01
// room that has usable geometry (9 of the 10 rooms in the unit template -
// see "Excluded: terrace" below). Captured read-only via
// room_geometry.build_room_geometry() through the real analyze.get_rooms()
// path with source_continuum_residence_01.jpg attached, same method as
// continuumPrimaryRoomGeometry.js. No backend files were touched to produce
// this file.
//
// GLOBAL PLACEMENT (Requirement: normalize into one shared coordinate
// system). Every room's `boundary`/`walls` are LOCAL (room's own (0,0)
// origin), exactly as the backend returns them - the backend has no
// whole-unit coordinate frame at all (each room is computed independently).
// `global_origin_ft` is derived here, not by the backend, as follows:
//   - Every room's bbox_px comes from the SAME shared 810x490px plan image
//     (continuum_plan.py's RESIDENCE_01_SOURCE_ROOMS, PLAN_SIZE).
//   - continuum_template.py's _estimate_dims() computes each room's
//     width_ft/depth_ft as (pixel width or height) * a single constant
//     scale factor sqrt(2080 sqft / (565*303 px^2)) (~0.1102 ft/px) - this
//     was verified by direct derivation to be ONE consistent linear scale
//     applied identically to every room, not a per-room independent fit.
//   - Applying that SAME scale factor directly to each room's bbox_px
//     top-left corner gives a global origin in feet that is consistent
//     with every room's own local size, since adjacent rooms' bboxes
//     already share edges in the same shared pixel space.
// A consumer places each room by translating its local group by
// (global_origin_ft[0], 0, global_origin_ft[1]) (x, z in three.js).
//
// KNOWN GEOMETRY PROBLEM FOUND while building this (see chat report for
// full detail): room_geometry.py's door/window heuristic hardcodes
// "wall_north"/"wall_{view_wall}" as the opening's `wall` reference, but
// for every one of these source-grounded rooms the actual wall list is
// numbered wall_01..wall_04 (source_geometry.walls_from_polygon) - the
// hardcoded names never match, so consumed as-is every door/window would
// silently fail to render anywhere. Verified structurally that, for all 9
// rooms, wall_01=north/wall_02=east/wall_03=south/wall_04=west (identical
// boundary point order in every room), so the `wall` fields below have been
// translated from the semantic direction to the real matching wall id
// (e.g. "wall_north" -> "wall_01"). This is a data reconciliation done
// here in the frontend, NOT a backend change - the backend's real API
// response still has this bug today.
//
// Excluded: "terrace" - CONTINUUM_RESIDENCE_01 lists it with
// width_ft/length_ft = None ("Terrace is intentionally not assigned a fake
// room dimension" per continuum_template.py) and it has no entry in
// RESIDENCE_01_SOURCE_ROOMS, so build_room_geometry() returns an empty
// shell (no boundary/walls/doors/windows) for it. Nothing to render.
export const CONTINUUM_ROOMS = [
  {
    "room_id": "great",
    "name": "Living Room",
    "view": true,
    "links": ["bed2", "bed3", "kitchen", "primary", "terrace"],
    "global_origin_ft": [52.909, 17.085],
    "width_ft": 17.42,
    "depth_ft": 13.78,
    "ceiling_ft": 11.0,
    "boundary": [[0.0, 0.0], [17.42, 0.0], [17.42, 13.78], [0.0, 13.78]],
    "walls": [
      { "id": "wall_01", "a": [0.0, 0.0, 0], "b": [17.42, 0.0, 0], "height_ft": 11.0 },
      { "id": "wall_02", "a": [17.42, 0.0, 0], "b": [17.42, 13.78, 0], "height_ft": 11.0 },
      { "id": "wall_03", "a": [17.42, 13.78, 0], "b": [0.0, 13.78, 0], "height_ft": 11.0 },
      { "id": "wall_04", "a": [0.0, 13.78, 0], "b": [0.0, 0.0, 0], "height_ft": 11.0 }
    ],
    "doors": [{ "id": "door_01", "wall": "wall_01", "offset_ft": 8.71, "width_ft": 3.0, "height_ft": 7.0 }],
    "windows": [{ "id": "window_01", "wall": "wall_01", "offset_ft": 8.71, "width_ft": 13.936, "sill_height_ft": 0.3, "head_height_ft": 10.4 }]
  },
  {
    "room_id": "kitchen",
    "name": "Kitchen",
    "view": false,
    "links": ["great", "primary"],
    "global_origin_ft": [56.767, 30.863],
    "width_ft": 13.78,
    "depth_ft": 8.27,
    "ceiling_ft": 11.0,
    "boundary": [[0.0, 0.0], [13.78, 0.0], [13.78, 8.27], [0.0, 8.27]],
    "walls": [
      { "id": "wall_01", "a": [0.0, 0.0, 0], "b": [13.78, 0.0, 0], "height_ft": 11.0 },
      { "id": "wall_02", "a": [13.78, 0.0, 0], "b": [13.78, 8.27, 0], "height_ft": 11.0 },
      { "id": "wall_03", "a": [13.78, 8.27, 0], "b": [0.0, 8.27, 0], "height_ft": 11.0 },
      { "id": "wall_04", "a": [0.0, 8.27, 0], "b": [0.0, 0.0, 0], "height_ft": 11.0 }
    ],
    "doors": [{ "id": "door_01", "wall": "wall_01", "offset_ft": 6.89, "width_ft": 3.0, "height_ft": 7.0 }],
    "windows": []
  },
  {
    "room_id": "primary",
    "name": "Primary Bedroom",
    "view": true,
    "links": ["great", "pbath"],
    "global_origin_ft": [70.545, 30.312],
    "width_ft": 17.64,
    "depth_ft": 12.68,
    "ceiling_ft": 11.0,
    "boundary": [[0.0, 0.0], [17.64, 0.0], [17.64, 12.68], [0.0, 12.68]],
    "walls": [
      { "id": "wall_01", "a": [0.0, 0.0, 0], "b": [17.64, 0.0, 0], "height_ft": 11.0 },
      { "id": "wall_02", "a": [17.64, 0.0, 0], "b": [17.64, 12.68, 0], "height_ft": 11.0 },
      { "id": "wall_03", "a": [17.64, 12.68, 0], "b": [0.0, 12.68, 0], "height_ft": 11.0 },
      { "id": "wall_04", "a": [0.0, 12.68, 0], "b": [0.0, 0.0, 0], "height_ft": 11.0 }
    ],
    "doors": [{ "id": "door_01", "wall": "wall_01", "offset_ft": 8.82, "width_ft": 3.0, "height_ft": 7.0 }],
    "windows": [{ "id": "window_01", "wall": "wall_02", "offset_ft": 6.34, "width_ft": 10.144, "sill_height_ft": 0.3, "head_height_ft": 10.4 }]
  },
  {
    "room_id": "pbath",
    "name": "Primary Bath",
    "view": false,
    "links": ["primary"],
    "global_origin_ft": [66.136, 42.988],
    "width_ft": 22.05,
    "depth_ft": 7.5,
    "ceiling_ft": 11.0,
    "boundary": [[0.0, 0.0], [22.05, 0.0], [22.05, 7.5], [0.0, 7.5]],
    "walls": [
      { "id": "wall_01", "a": [0.0, 0.0, 0], "b": [22.05, 0.0, 0], "height_ft": 11.0 },
      { "id": "wall_02", "a": [22.05, 0.0, 0], "b": [22.05, 7.5, 0], "height_ft": 11.0 },
      { "id": "wall_03", "a": [22.05, 7.5, 0], "b": [0.0, 7.5, 0], "height_ft": 11.0 },
      { "id": "wall_04", "a": [0.0, 7.5, 0], "b": [0.0, 0.0, 0], "height_ft": 11.0 }
    ],
    "doors": [{ "id": "door_01", "wall": "wall_01", "offset_ft": 11.025, "width_ft": 3.0, "height_ft": 7.0 }],
    "windows": []
  },
  {
    "room_id": "bed2",
    "name": "Bedroom 2",
    "view": true,
    "links": ["bath2", "great"],
    "global_origin_ft": [43.209, 17.085],
    "width_ft": 9.7,
    "depth_ft": 13.34,
    "ceiling_ft": 11.0,
    "boundary": [[0.0, 0.0], [9.7, 0.0], [9.7, 13.34], [0.0, 13.34]],
    "walls": [
      { "id": "wall_01", "a": [0.0, 0.0, 0], "b": [9.7, 0.0, 0], "height_ft": 11.0 },
      { "id": "wall_02", "a": [9.7, 0.0, 0], "b": [9.7, 13.34, 0], "height_ft": 11.0 },
      { "id": "wall_03", "a": [9.7, 13.34, 0], "b": [0.0, 13.34, 0], "height_ft": 11.0 },
      { "id": "wall_04", "a": [0.0, 13.34, 0], "b": [0.0, 0.0, 0], "height_ft": 11.0 }
    ],
    "doors": [{ "id": "door_01", "wall": "wall_01", "offset_ft": 4.85, "width_ft": 3.0, "height_ft": 7.0 }],
    "windows": [{ "id": "window_01", "wall": "wall_01", "offset_ft": 4.85, "width_ft": 7.76, "sill_height_ft": 0.3, "head_height_ft": 10.4 }]
  },
  {
    "room_id": "bath2",
    "name": "Bath 2",
    "view": false,
    "links": ["bed2"],
    "global_origin_ft": [49.602, 30.312],
    "width_ft": 7.16,
    "depth_ft": 8.82,
    "ceiling_ft": 11.0,
    "boundary": [[0.0, 0.0], [7.16, 0.0], [7.16, 8.82], [0.0, 8.82]],
    "walls": [
      { "id": "wall_01", "a": [0.0, 0.0, 0], "b": [7.16, 0.0, 0], "height_ft": 11.0 },
      { "id": "wall_02", "a": [7.16, 0.0, 0], "b": [7.16, 8.82, 0], "height_ft": 11.0 },
      { "id": "wall_03", "a": [7.16, 8.82, 0], "b": [0.0, 8.82, 0], "height_ft": 11.0 },
      { "id": "wall_04", "a": [0.0, 8.82, 0], "b": [0.0, 0.0, 0], "height_ft": 11.0 }
    ],
    "doors": [{ "id": "door_01", "wall": "wall_01", "offset_ft": 3.58, "width_ft": 3.0, "height_ft": 7.0 }],
    "windows": []
  },
  {
    "room_id": "bed3",
    "name": "Bedroom 3",
    "view": true,
    "links": ["bath3", "great"],
    "global_origin_ft": [25.903, 30.312],
    "width_ft": 13.23,
    "depth_ft": 9.92,
    "ceiling_ft": 11.0,
    "boundary": [[0.0, 0.0], [13.23, 0.0], [13.23, 9.92], [0.0, 9.92]],
    "walls": [
      { "id": "wall_01", "a": [0.0, 0.0, 0], "b": [13.23, 0.0, 0], "height_ft": 11.0 },
      { "id": "wall_02", "a": [13.23, 0.0, 0], "b": [13.23, 9.92, 0], "height_ft": 11.0 },
      { "id": "wall_03", "a": [13.23, 9.92, 0], "b": [0.0, 9.92, 0], "height_ft": 11.0 },
      { "id": "wall_04", "a": [0.0, 9.92, 0], "b": [0.0, 0.0, 0], "height_ft": 11.0 }
    ],
    "doors": [{ "id": "door_01", "wall": "wall_01", "offset_ft": 6.615, "width_ft": 3.0, "height_ft": 7.0 }],
    "windows": [{ "id": "window_01", "wall": "wall_04", "offset_ft": 4.96, "width_ft": 7.936, "sill_height_ft": 0.3, "head_height_ft": 10.4 }]
  },
  {
    "room_id": "bath3",
    "name": "Bath 3",
    "view": false,
    "links": ["bed3"],
    "global_origin_ft": [43.539, 38.579],
    "width_ft": 6.61,
    "depth_ft": 8.27,
    "ceiling_ft": 11.0,
    "boundary": [[0.0, 0.0], [6.61, 0.0], [6.61, 8.27], [0.0, 8.27]],
    "walls": [
      { "id": "wall_01", "a": [0.0, 0.0, 0], "b": [6.61, 0.0, 0], "height_ft": 11.0 },
      { "id": "wall_02", "a": [6.61, 0.0, 0], "b": [6.61, 8.27, 0], "height_ft": 11.0 },
      { "id": "wall_03", "a": [6.61, 8.27, 0], "b": [0.0, 8.27, 0], "height_ft": 11.0 },
      { "id": "wall_04", "a": [0.0, 8.27, 0], "b": [0.0, 0.0, 0], "height_ft": 11.0 }
    ],
    "doors": [{ "id": "door_01", "wall": "wall_01", "offset_ft": 3.305, "width_ft": 3.0, "height_ft": 7.0 }],
    "windows": []
  },
  {
    "room_id": "powder",
    "name": "Powder Room",
    "view": false,
    "links": ["great"],
    "global_origin_ft": [50.153, 40.784],
    "width_ft": 6.61,
    "depth_ft": 8.27,
    "ceiling_ft": 11.0,
    "boundary": [[0.0, 0.0], [6.61, 0.0], [6.61, 8.27], [0.0, 8.27]],
    "walls": [
      { "id": "wall_01", "a": [0.0, 0.0, 0], "b": [6.61, 0.0, 0], "height_ft": 11.0 },
      { "id": "wall_02", "a": [6.61, 0.0, 0], "b": [6.61, 8.27, 0], "height_ft": 11.0 },
      { "id": "wall_03", "a": [6.61, 8.27, 0], "b": [0.0, 8.27, 0], "height_ft": 11.0 },
      { "id": "wall_04", "a": [0.0, 8.27, 0], "b": [0.0, 0.0, 0], "height_ft": 11.0 }
    ],
    "doors": [{ "id": "door_01", "wall": "wall_01", "offset_ft": 3.305, "width_ft": 3.0, "height_ft": 7.0 }],
    "windows": []
  }
];
