# Provenance and licenses

Region partitioning, geometry contracts, hole-preserving output, explicit merging, evaluation, and the CLI were independently implemented for this repository. Legacy region-growth, inner-rectangle, vectorization, OCR business code, model files, and parent Git history are not included.

Connected components, watershed, distance transforms, contour hierarchy, and Hungarian matching are established techniques. OpenCV, SciPy, scikit-image, NumPy, Pillow, and optional ONNX Runtime retain their own licenses. Software citation metadata does not claim a new foundational algorithm or an associated research paper.

Aggregate evaluation used human annotations from [CubiCasa5k](https://github.com/CubiCasa/CubiCasa5k), distributed under CC BY-NC 4.0; no dataset images, annotations, sample lists, or legacy model weights are distributed here. That dataset license and any external model license are separate from this repository's MIT license. Model evaluation does not grant redistribution rights.

MIT covers the new implementation in this repository. External weights, private data, and dependencies retain their existing terms. [WallGraph](https://github.com/chrischen-coder/wallgraph) is an optional upstream source, not a package dependency. PlanRegions includes no image assets; its demo geometry is generated in memory.
