#!/usr/bin/env python3

"""Phone media sorter. Polls landing folder, sorts to year-organized destinations."""
import logging, os, shutil, sys, time
from datetime import datetime
from pathlib import Path
from PIL import Image, ExifTags
from pymediainfo import MediaInfo

