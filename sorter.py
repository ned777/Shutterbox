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
    
        if dt is None:
        dt = datetime.fromtimestamp(path.stat().st_mtime)

    target_dir = dest_root / str(dt.year)
    target_dir.mkdir(parents=True, exist_ok=True)
    target = target_dir / path.name

    if target.exists():
        log.info("DUP skip: %s already in %s — deleting from inbox", path.name, target_dir)
        try: path.unlink()
        except Exception as e: log.warning("Couldn't delete duplicate %s: %s", path.name, e)
        return "dup"

    try:
        shutil.move(str(path), str(target))
        log.info("MOVED %s: %s -> %s", kind, path.name, target)
        return "moved"
    except Exception as e:
        log.error("Move failed for %s: %s", path.name, e)
        return "error"
    
    def is_quiesced(path):
    try: return (time.time() - path.stat().st_mtime) >= QUIESCE_SECONDS
    except Exception: return False

def is_temp(path):
    """Skip Samsung temp files, hidden files, and partial transfers."""
    name = path.name
    return (name.startswith(".") or
            name.endswith(".tmp") or
            "_BACK" in name or
            "_BACK_SEAMLESS" in name)

def walk_landing():
    if not LANDING_DIR.exists():
        log.error("Landing dir missing: %s", LANDING_DIR)
        return
    stats = {"moved": 0, "dup": 0, "skip": 0, "error": 0, "not_quiesced": 0}
    for path in LANDING_DIR.rglob("*"):
        if not path.is_file() or is_temp(path): continue
        if not is_quiesced(path):
            stats["not_quiesced"] += 1
            continue
        stats[process_file(path)] += 1
    if any(v > 0 for v in stats.values()):
        log.info("Pass: %s", stats)

def main():
    log.info("Sorter starting | Landing: %s | Photos: %s | Videos: %s",
             LANDING_DIR, PHOTO_DEST, VIDEO_DEST)
    while True:
        try: walk_landing()
        except KeyboardInterrupt: sys.exit(0)
        except Exception: log.exception("Error in walk_landing")
        time.sleep(POLL_INTERVAL)

if __name__ == "__main__":
    main()