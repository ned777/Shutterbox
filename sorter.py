#!/usr/bin/env python3

"""Phone media sorter. Polls landing folder, sorts to year-organized destinations."""
import logging, os, shutil, sys, time
from datetime import datetime
from pathlib import Path
from PIL import Image, ExifTags
from pymediainfo import MediaInfo

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.FileHandler(LOG_FILE), logging.StreamHandler()]
)
log = logging.getLogger("sorter")