from app.room_geometry import build_room_geometry


def test_room_geometry_contract():
    room = {
        "id": "great",
        "name": "Living Room",
        "width_ft": 18,
        "length_ft": 15,
        "view": True,
        "view_wall": "north",
        "links": [{"to": "kitchen"}],
        "source_plan": {"bbox_px": [1, 2, 3, 4]},
        "source_polygon_px": [[1, 2], [3, 2], [3, 4], [1, 4]],
        "dimension_source": "estimated",
    }
    g = build_room_geometry(room)
    assert g["source"] == "uploaded-plan-region"
    assert g["width_ft"] == 18.0
    assert g["depth_ft"] == 15.0
    assert len(g["walls"]) == 4
    assert g["doors"][0]["wall"] == "wall_north"
    assert g["windows"][0]["wall"] == "wall_north"
    assert g["connections"] == ["kitchen"]
