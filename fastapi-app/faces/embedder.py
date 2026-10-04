"""Fingerprints of the box's pictures: faces with OpenCV's YuNet (find + landmarks) and SFace
(128-number fingerprint), whole bodies with OpenCV Zoo's YouTu ReID (clothing). The ONNX files are
kept in FACE_MODEL_DIR, downloaded once with `uv run python -m faces.download`.

The box's face captures are already cropped tightly around the face, which is too tight for the
detector, so the picture gets a border first. Faces the detector isn't sure about, or that are too
small, get no fingerprint: a wrong fingerprint would merge two people, a missing one only means that
walk-past counts as its own person.
"""
import logging
import os
from dataclasses import dataclass
from pathlib import Path

log = logging.getLogger("b4h.faces")

MODEL_DIR = Path(os.getenv("FACE_MODEL_DIR", Path(__file__).resolve().parent.parent / "face_models"))
DETECTOR_FILE = "face_detection_yunet_2023mar.onnx"
RECOGNIZER_FILE = "face_recognition_sface_2021dec.onnx"
MODEL_NAME = "sface-2021dec"          # stored with every fingerprint: never compare across models

MIN_DETECTION_SCORE = float(os.getenv("FACE_MIN_DETECTION_SCORE", "0.85"))
MIN_FACE_PIXELS = int(os.getenv("FACE_MIN_PIXELS", "40"))     # face width/height in the box's picture
DETECT_SIZE = 320                     # pictures are scaled so their longer side is about this


@dataclass(frozen=True)
class Fingerprint:
    vector: list[float]               # unit length: cosine similarity = dot product
    detection_score: float
    face_pixels: int


def models_present() -> bool:
    return all((MODEL_DIR / name).is_file() for name in (DETECTOR_FILE, RECOGNIZER_FILE, REID_FILE))


class FaceEmbedder:
    """Not thread-safe: call it from one thread at a time (the worker does)."""

    def __init__(self, model_dir: Path = MODEL_DIR):
        import cv2                    # imported here so the app starts without OpenCV installed
        self._cv2 = cv2
        self._detector = cv2.FaceDetectorYN.create(str(model_dir / DETECTOR_FILE), "", (DETECT_SIZE, DETECT_SIZE),
                                                   score_threshold=0.5)
        self._recognizer = cv2.FaceRecognizerSF.create(str(model_dir / RECOGNIZER_FILE), "")

    def fingerprint(self, data: bytes) -> Fingerprint | None:
        """The fingerprint of the clearest face in this picture, or None."""
        import numpy as np
        cv2 = self._cv2
        image = cv2.imdecode(np.frombuffer(data, np.uint8), cv2.IMREAD_COLOR)
        if image is None:
            return None
        h, w = image.shape[:2]
        pad = max(h, w) // 3
        padded = cv2.copyMakeBorder(image, pad, pad, pad, pad, cv2.BORDER_CONSTANT, value=(0, 0, 0))
        scale = DETECT_SIZE / max(padded.shape[:2])
        if scale != 1:
            padded = cv2.resize(padded, None, fx=scale, fy=scale,
                                interpolation=cv2.INTER_LINEAR if scale > 1 else cv2.INTER_AREA)
        self._detector.setInputSize((padded.shape[1], padded.shape[0]))
        _, faces = self._detector.detect(padded)
        if faces is None or not len(faces):
            return None
        face = max(faces, key=lambda f: f[2] * f[3])                  # the biggest face is the subject
        score = float(face[14])
        size = int(min(face[2], face[3]) / scale)                     # in the box's picture's pixels
        if score < MIN_DETECTION_SCORE or size < MIN_FACE_PIXELS:
            return None
        aligned = self._recognizer.alignCrop(padded, face)
        vector = self._recognizer.feature(aligned).flatten().astype("float64")
        norm = float(np.linalg.norm(vector))
        if not norm:
            return None
        return Fingerprint(vector=[float(v) for v in vector / norm], detection_score=round(score, 3), face_pixels=size)


# ---------- whole body (clothing) ----------

REID_FILE = "person_reid_youtu_2021nov.onnx"
BODY_MODEL_NAME = "youtu-reid-2021nov"
_REID_SIZE = (128, 256)               # width, height the model expects
_REID_MEAN = (0.485, 0.456, 0.406)
_REID_STD = (0.229, 0.224, 0.225)
MIN_BODY_PIXELS = int(os.getenv("BODY_MIN_PIXELS", "64"))    # body picture height


class BodyEmbedder:
    """Whole-body fingerprints (OpenCV Zoo's YouTu ReID): mostly clothing and build, so they tell
    people apart within a day, not across days. Not thread-safe, like FaceEmbedder."""

    def __init__(self, model_dir: Path = MODEL_DIR):
        import cv2
        self._cv2 = cv2
        self._net = cv2.dnn.readNet(str(model_dir / REID_FILE))

    def fingerprint(self, data: bytes) -> list[float] | None:
        import numpy as np
        cv2 = self._cv2
        image = cv2.imdecode(np.frombuffer(data, np.uint8), cv2.IMREAD_COLOR)
        if image is None or image.shape[0] < MIN_BODY_PIXELS:
            return None
        rgb = cv2.resize(image, _REID_SIZE)[:, :, ::-1] / 255.0
        normalized = ((rgb - _REID_MEAN) / _REID_STD).astype(np.float32)
        self._net.setInput(cv2.dnn.blobFromImage(normalized))
        vector = self._net.forward().flatten().astype("float64")
        norm = float(np.linalg.norm(vector))
        return [float(v) for v in vector / norm] if norm else None
