#!/usr/bin/env python3
"""Phone media sorter. Polls landing folder, sorts to year-organized destinations."""
import logging, os, shutil, sys, time
from datetime import datetime
from pathlib import Path
from PIL import Image, ExifTags
from pymediainfo import MediaInfo

# --- CONFIG: change paths if  drives are mounted differently ---
LANDING_DIR = Path("/mnt/Drive1/phone-inbox")
PHOTO_DEST  = Path("/mnt/Drive1/Pictures/Camera Roll")
VIDEO_DEST  = Path("/mnt/Drive2/Videos/Camera Roll")
LOG_FILE    = "/home/user/scripts/media-sorter/sorter.log"

PHOTO_EXTS = {".jpg", ".jpeg", ".png", ".heic", ".heif", ".webp", ".bmp", ".tif", ".tiff", ".dng", ".raw"}
VIDEO_EXTS = {".mp4", ".mov", ".mkv", ".webm", ".avi", ".m4v", ".3gp"}

QUIESCE_SECONDS = 60   # file must be unmodified this long before processing
POLL_INTERVAL   = 30   # seconds between scans

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.FileHandler(LOG_FILE), logging.StreamHandler()]
)
log = logging.getLogger("sorter")

def extract_photo_datetime(path):
    try:
        with Image.open(path) as im:
            exif = im._getexif()
            if not exif: return None
            for tag_id, value in exif.items():
                if ExifTags.TAGS.get(tag_id) == "DateTimeOriginal" and isinstance(value, str):
                    try: return datetime.strptime(value, "%Y:%m:%d %H:%M:%S")
                    except ValueError: return None
    except Exception: pass
    return None

def extract_video_datetime(path):
    try:
        mi = MediaInfo.parse(str(path))
        for track in mi.tracks:
            if track.track_type != "General": continue
            for attr in ("encoded_date", "tagged_date", "recorded_date"):
                val = getattr(track, attr, None)
                if not val: continue
                cleaned = val.replace("UTC", "").replace("T", " ").strip()
                try: return datetime.strptime(cleaned.split(".")[0], "%Y-%m-%d %H:%M:%S")
                except ValueError: continue
    except Exception: pass
    return None

def process_file(path):
    ext = path.suffix.lower()
    if ext in PHOTO_EXTS:
        kind, dest_root, dt = "photo", PHOTO_DEST, extract_photo_datetime(path)
    elif ext in VIDEO_EXTS:
        kind, dest_root, dt = "video", VIDEO_DEST, extract_video_datetime(path)
    else:
        return "skip"