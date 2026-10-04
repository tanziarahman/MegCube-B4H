"""Downloads the three models (OpenCV Zoo: YuNet, MIT; SFace and YouTu ReID, Apache-2.0) into FACE_MODEL_DIR.

    uv run python -m faces.download

Each file is checked against its known SHA-256, so a changed or broken download is refused.
"""
import hashlib
import sys
import urllib.request

from .embedder import DETECTOR_FILE, MODEL_DIR, RECOGNIZER_FILE, REID_FILE

ZOO = "https://github.com/opencv/opencv_zoo/raw/main/models"
FILES = {
    DETECTOR_FILE: (f"{ZOO}/face_detection_yunet/{DETECTOR_FILE}",
                    "8f2383e4dd3cfbb4553ea8718107fc0423210dc964f9f4280604804ed2552fa4"),
    RECOGNIZER_FILE: (f"{ZOO}/face_recognition_sface/{RECOGNIZER_FILE}",
                      "0ba9fbfa01b5270c96627c4ef784da859931e02f04419c829e83484087c34e79"),
    REID_FILE: (f"{ZOO}/person_reid_youtureid/{REID_FILE}",
                "0579683334d4b9440221606dcb461656dd0dc64143b18f48faedaced9b4f580d"),
}


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def main() -> int:
    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    for name, (url, expected) in FILES.items():
        target = MODEL_DIR / name
        if target.is_file() and sha256(target.read_bytes()) == expected:
            print(f"{name}: already there")
            continue
        print(f"{name}: downloading…", flush=True)
        with urllib.request.urlopen(url, timeout=120) as response:
            data = response.read()
        if sha256(data) != expected:
            print(f"{name}: the download doesn't match the expected file; not saved", file=sys.stderr)
            return 1
        target.write_bytes(data)
        print(f"{name}: saved ({len(data) / 1e6:.1f} MB)")
    print(f"The models are in {MODEL_DIR}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
