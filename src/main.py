import asyncio
import os
import tempfile
import threading
from urllib.parse import urlparse

import flet as ft
import yt_dlp


BLUE = "#1769F5"
BLUE_DARK = "#0647C7"
BG = "#F4F7FF"
INK = "#17233C"
MUTED = "#77839A"
BORDER = "#E5EAF4"
GREEN = "#16A36A"
WHITE = "#FFFFFF"


class DownloadCancelled(Exception):
    pass


class DownloadState:
    def __init__(self):
        self.paused = threading.Event()
        self.paused.set()
        self.cancelled = threading.Event()


def format_size(value):
    if value is None:
        return "--"
    value = float(value)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if value < 1024:
            return f"{value:.1f} {unit}"
        value /= 1024
    return f"{value:.1f} PB"


def download_media(url, folder, state, speed_limit, media_kind, quality, callback):
    def progress_hook(data):
        while not state.paused.wait(timeout=0.25):
            if state.cancelled.is_set():
                raise DownloadCancelled()

        if state.cancelled.is_set():
            raise DownloadCancelled()

        if data.get("status") == "downloading":
            callback({
                "percent": data.get("_percent_str", "0%"),
                "downloaded": data.get("downloaded_bytes", 0),
                "total": data.get("total_bytes") or data.get("total_bytes_estimate"),
                "speed": data.get("speed"),
                "eta": data.get("eta"),
            })

    if media_kind == "audio":
        fmt = "bestaudio/best"
    else:
        height = quality.replace("p", "")
        fmt = f"best[height<={height}][ext=mp4]/best[height<={height}]/best"

    options = {
        "format": fmt,
        "outtmpl": os.path.join(folder, "%(title).70s [%(id)s].%(ext)s"),
        "noplaylist": True,
        "quiet": True,
        "no_warnings": True,
        "socket_timeout": 30
