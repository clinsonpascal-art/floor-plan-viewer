from app.room_geometry import build_room_geometry


def test_source_polygon_drives_room_boundary():
    room = {
        "name": "Living Room",
        "width_ft": 18,
        "length_ft": 12,
        "view": True,
        "view_wall": "north",
        "links": [{"to": "kitchen"}],
        "source_plan": {"bbox_px": [100, 100, 200, 200]},
        "source_polygon_px": [[100,100],[200,100],[190,200],[100,200]],
        "dimension_source": "estimated",
    }
    g = build_room_geometry(room)
    assert g["source_fidelity"] == "source_shape_plus_inferred_3d_openings"
    assert g["boundary"][2] == [16.2, 12.0]
    assert len(g["walls"]) == 4
    assert g["windows"][0]["inferred"] is True
