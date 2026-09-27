"""All settings in one place. Values come from environment variables / the .env file."""
import os
from pathlib import Path
from zoneinfo import ZoneInfo

try:  # load .env if python-dotenv is installed (uv add python-dotenv)
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# ---- B4H box ---------------------------------------------------------------
B4H_BASE_URL = os.getenv("B4H_BASE_URL", "https://192.168.90.200")
B4H_USER = os.getenv("B4H_USER", "admin")
B4H_PASS = os.getenv("B4H_PASS", "")                 # keep the real password in .env only
B4H_USE_WS = os.getenv("B4H_USE_WS", "0") == "1"     # live alarms over the box websocket

# ---- App -------------------------------------------------------------------
FRONTEND_ORIGINS = [o.strip() for o in os.getenv("FRONTEND_ORIGINS", "http://localhost:3000").split(",")]
MEDIA_DIR = Path(os.getenv("MEDIA_DIR", "./media"))
TIMEZONE = ZoneInfo(os.getenv("TZ_NAME", "Asia/Dhaka"))

# ---- Recognition records ---------------------------------------------------
# Recognitions are stored on the box as alarms of this major type.
RECOG_MAJOR = os.getenv("RECOG_MAJOR", "face_basic_business")
# "face_comparison_successful" is confirmed. The stranger name is a guess:
# check GET /api/recognition/types and set RECOG_MINOR_STRANGER in .env if it differs.
RECOG_MINOR_MATCHED = os.getenv("RECOG_MINOR_MATCHED", "face_comparison_successful")
RECOG_MINOR_STRANGER = os.getenv("RECOG_MINOR_STRANGER", "face_comparison_failed")

BOX_MAX_PAGE_SIZE = 30       # box refuses more than 30 records per request
MERGE_MAX_DEPTH = 600        # "all results" merges two lists; don't page deeper than this
