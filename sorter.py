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

