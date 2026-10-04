import numpy as np
import pytest

from planregions.onnx_attributes import OnnxAttributes

onnx = pytest.importorskip("onnx")
pytest.importorskip("onnxruntime")


def test_onnx_attribute_adapter_preserves_shape_and_color_contract(tmp_path):
    helper = onnx.helper
    graph = helper.make_graph(
        [helper.make_node("Identity", ["images"], ["output"])],
        "test",
        [helper.make_tensor_value_info("images", onnx.TensorProto.FLOAT, [1, 3, 32, 32])],
        [helper.make_tensor_value_info("output", onnx.TensorProto.FLOAT, [1, 3, 32, 32])],
    )
    model = helper.make_model(graph, opset_imports=[helper.make_opsetid("", 17)])
    model.ir_version = 8
    path = tmp_path / "test.onnx"
    onnx.save(model, path)
    labels = np.ones((20, 80), np.int32)
    rgb = np.zeros((20, 80, 3), np.uint8)
    rgb[..., 0] = 255
    names = {0: "red", 2: "blue"}
    assert OnnxAttributes(path, names).classify(labels, rgb)[1].label == "red"
    assert OnnxAttributes(path, names, color="bgr").classify(labels, rgb)[1].label == "blue"
    with pytest.raises(ValueError):
        OnnxAttributes(path, names).classify(labels, None)
