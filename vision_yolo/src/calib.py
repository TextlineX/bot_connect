import numpy as np
from typing import Dict, List


class Calibrator:
    def __init__(self, homography: np.ndarray):
        self.H = homography

    def pixel_to_robot(self, bbox: List[float], z: float = 0.0) -> Dict[str, float]:
        x1, y1, x2, y2 = bbox
        cx = (x1 + x2) / 2
        cy = (y1 + y2) / 2
        pt = np.array([cx, cy, 1.0])
        mapped = self.H @ pt
        mapped = mapped / mapped[2]
        return {"x": float(mapped[0]), "y": float(mapped[1]), "z": float(z), "rz": 0.0}

