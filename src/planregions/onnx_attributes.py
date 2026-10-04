import hashlib
from pathlib import Path

import cv2
import numpy as np

from .attributes import ClassMapAttributes


class OnnxAttributes:
    """Adapter for existing RGB/BGR semantic segmentation models; CPU inference."""

    name = "onnx-semantic-map"

    def __init__(
        self,
        model: Path,
        names: dict[int, str],
        *,
        color: str = "rgb",
        min_coverage: float = 0.6,
        input_size: tuple[int, int] = (512, 512),
    ):
        import onnxruntime as ort

        if color not in {"rgb", "bgr"} or min(input_size) < 1:
            raise ValueError("color must be rgb or bgr; input dimensions must be positive")
        self.names = names
        self.color = color
        self.min_coverage = min_coverage
        options = ort.SessionOptions()
        options.intra_op_num_threads = 4
        self.session = ort.InferenceSession(
            str(model), sess_options=options, providers=["CPUExecutionProvider"]
        )
        inputs = self.session.get_inputs()
        if len(inputs) != 1 or len(inputs[0].shape) != 4 or inputs[0].type != "tensor(float)":
            raise ValueError("expected one float32 NCHW semantic model input")
        if inputs[0].shape[1] != 3:
            raise ValueError("semantic model must have three input channels")
        if isinstance(inputs[0].shape[0], int) and inputs[0].shape[0] != 1:
            raise ValueError("semantic model fixed batch size must be one")
        self.input_name = inputs[0].name
        self.input_size = tuple(
            value if isinstance(value, int) and value > 0 else fallback
            for value, fallback in zip(inputs[0].shape[2:], input_size, strict=True)
        )
        self.output_name = self.session.get_outputs()[0].name
        self.providers = self.session.get_providers()
        digest = hashlib.sha256()
        with model.open("rb") as source:
            for chunk in iter(lambda: source.read(1 << 20), b""):
                digest.update(chunk)
        self.model_sha256 = digest.hexdigest()

    def classify(self, labels: np.ndarray, rgb: np.ndarray | None) -> dict:
        if rgb is None:
            raise ValueError("ONNX attribute inference requires the aligned original RGB image")
        image = rgb if self.color == "rgb" else rgb[..., ::-1]
        height, width = self.input_size
        tensor = cv2.resize(image, (width, height), interpolation=cv2.INTER_NEAREST)
        tensor = np.ascontiguousarray(tensor.transpose(2, 0, 1)[None], dtype=np.float32) / 255
        output = self.session.run([self.output_name], {self.input_name: tensor})[0]
        if output.ndim != 4 or output.shape[0] != 1 or not np.isfinite(output).all():
            raise ValueError("semantic model must return finite NCHW scores")
        if not self.names or min(self.names) < 0 or max(self.names) >= output.shape[1]:
            raise ValueError("class names must match output channels")
        class_map = output[0].argmax(axis=0).astype(np.int32)
        class_map = cv2.resize(
            class_map, (labels.shape[1], labels.shape[0]), interpolation=cv2.INTER_NEAREST
        )
        result = ClassMapAttributes(class_map, self.names, self.min_coverage).classify(labels, rgb)
        return result
