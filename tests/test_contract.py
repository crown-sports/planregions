import json

import numpy as np
import pytest
from PIL import Image

from planregions.io import check_wall_contract, read_mask


def test_wall_contract_checks_size_polarity_and_coordinate_system(tmp_path):
    data = {
        "schema_version": "wallgraph/1",
        "image": {"height": 20, "width": 40},
        "coordinates": {"origin": "top_left", "x": "right", "y": "down", "unit": "px"},
        "mask": {"wall_value": 255},
    }
    metadata = tmp_path / "walls.json"
    metadata.write_text(json.dumps(data))
    check_wall_contract(metadata, (20, 40), 255)
    with pytest.raises(ValueError, match="dimensions"):
        check_wall_contract(metadata, (40, 20), 255)
    with pytest.raises(ValueError, match="polarity"):
        check_wall_contract(metadata, (20, 40), 0)
    data["coordinates"]["y"] = "up"
    metadata.write_text(json.dumps(data))
    with pytest.raises(ValueError, match="coordinate"):
        check_wall_contract(metadata, (20, 40), 255)


def test_legacy_black_walls_need_explicit_polarity(tmp_path):
    values = np.full((20, 40), 255, np.uint8)
    values[:, 20] = 0
    Image.fromarray(values).save(tmp_path / "walls.png")
    mask = read_mask(tmp_path / "walls.png", 0)
    assert (mask[:, 20] == 255).all()
    assert not mask[:, :20].any()
