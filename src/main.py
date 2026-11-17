import os
import threading
from pathlib import Path

import flet as ft
import yt_dlp


BLUE = "#1769F5"
BG = "#F4F7FF"
INK = "#17233C"
MUTED = "#77839A"


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


def main(page: ft.Page):
    page.title = "BAHMED DOWNLOADER"
    page.bgcolor = BG
    page.rtl = True
    page.padding = 18
    page.theme_mode = ft.ThemeMode.LIGHT

    url_field = ft.TextField(
        label="رابط الفيديو أو الملف",
        hint_text="الصق الرابط هنا",
        text_align=ft.TextAlign.RIGHT,
        border_radius=12,
        expand=True,
    )

    kind = ft.Dropdown(
        label="نوع الملف",
        value="video",
        options=[
            ft.dropdown.Option("video", "فيديو MP4"),
            ft.dropdown.Option("audio", "صوت بأفضل جودة متاحة"),
        ],
        expand=True,
    )

    quality = ft.Dropdown(
        label="جودة الفيديو",
        value="720",
        options=[
            ft.dropdown.Option("360", "360p"),
            ft.dropdown.Option("480", "480p"),
            ft.dropdown.Option("720", "720p"),
            ft.dropdown.Option("1080", "1080p"),
        ],
        expand=True,
    )

    status = ft.Text("جاهز للتنزيل", color=MUTED)
    progress = ft.ProgressBar(
        value=0,
        color=BLUE,
        bgcolor="#DCE6FA",
    )
    details = ft.Text("", color=MUTED, size=12)

    start_button = ft.ElevatedButton(
        "بدء التنزيل",
        icon=ft.Icons.DOWNLOAD,
    )
    pause_button = ft.OutlinedButton("إيقاف مؤقت", disabled=True)
    resume_button = ft.OutlinedButton("استئناف", disabled=True)
    cancel_button = ft.TextButton("إلغاء", disabled=True)

    state_holder = {"state": None}

    download_folder = Path.home() / "Downloads" / "BAHMED"

    try:
        download_folder.mkdir(parents=True, exist_ok=True)
    except OSError:
        download_folder = Path.cwd() / "BAHMED_DOWNLOADS"
        download_folder.mkdir(parents=True, exist_ok=True)

    def set_status(message):
        status.value = message
        page.update()

    def progress_hook(data):
        state = state_holder["state"]

        if state is not None:
            while not state.paused.wait(timeout=0.25):
                if state.cancelled.is_set():
                    raise yt_dlp.utils.DownloadError(
                        "تم إلغاء التنزيل"
                    )

            if state.cancelled.is_set():
                raise yt_dlp.utils.DownloadError(
                    "تم إلغاء التنزيل"
                )

        if data.get("status") == "downloading":
            downloaded = data.get("downloaded_bytes", 0)
            total = (
                data.get("total_bytes")
                or data.get("total_bytes_estimate")
            )

            percent = downloaded / total if total else 0

            progress.value = max(0, min(percent, 1))

            speed = format_size(data.get("speed")) + "/s"
            eta = data.get("eta")

            details.value = (
                f"{progress.value * 100:.1f}%  •  "
                f"{format_size(downloaded)} / "
                f"{format_size(total)}  •  "
                f"{speed}  •  "
                f"الوقت المتبقي: "
                f"{eta if eta is not None else '--'} ث"
            )

            page.update()

        elif data.get("status") == "finished":
            progress.value = 1
            details.value = "اكتمل تنزيل البيانات، جارٍ تجهيز الملف..."
            page.update()

    def worker(url, media_kind, selected_quality, state):
        try:
            if media_kind == "audio":
                fmt = "bestaudio/best"
            else:
                fmt = (
                    f"best[height<={selected_quality}][ext=mp4]/"
                    f"best[height<={selected_quality}]/best"
                )

            options = {
                "format": fmt,
                "outtmpl": str(
                    download_folder
                    / "%(title).70s [%(id)s].%(ext)s"
                ),
                "noplaylist": True,
                "quiet": True,
                "no_warnings": True,
                "socket_timeout": 30,
                "progress_hooks": [progress_hook],
                "continuedl": True,
                "overwrites": False,
            }

            with yt_dlp.YoutubeDL(options) as downloader:
                downloader.download([url])

            if state.cancelled.is_set():
                set_status("تم إلغاء التنزيل.")
            else:
                set_status(
                    f"اكتمل التنزيل. مجلد الحفظ: {download_folder}"
                )
                details.value = (
                    "يمكنك فتح مجلد BAHMED داخل Downloads."
                )
                page.update()

        except Exception as error:
            set_status(f"تعذر التنزيل: {error}")

        finally:
            start_button.disabled = False
            pause_button.disabled = True
            resume_button.disabled = True
            cancel_button.disabled = True
            state_holder["state"] = None
            page.update()

    def start_download(_):
        url = (url_field.value or "").strip()

        if not url.startswith(("http://", "https://")):
            set_status(
                "أدخل رابطًا صحيحًا يبدأ بـ http أو https."
            )
            return

        state = DownloadState()
        state_holder["state"] = state

        progress.value = 0
        details.value = ""

        start_button.disabled = True
        pause_button.disabled = False
        resume_button.disabled = True
        cancel_button.disabled = False

        set_status("بدأ التنزيل...")

        page.run_thread(
            worker,
            url,
            kind.value,
            quality.value,
            state,
        )

    def pause_download(_):
        state = state_holder["state"]

        if state:
            state.paused.clear()
            pause_button.disabled = True
            resume_button.disabled = False
            set_status("التنزيل متوقف مؤقتًا.")

    def resume_download(_):
        state = state_holder["state"]

        if state:
            state.paused.set()
            pause_button.disabled = False
            resume_button.disabled = True
            set_status("تم استئناف التنزيل.")

    def cancel_download(_):
        state = state_holder["state"]

        if state:
            state.cancelled.set()
            state.paused.set()
            set_status("جارٍ إلغاء التنزيل...")

    start_button.on_click = start_download
    pause_button.on_click = pause_download
    resume_button.on_click = resume_download
    cancel_button.on_click = cancel_download

    page.add(
        ft.Column(
            [
                ft.Container(
                    content=ft.Column(
                        [
                            ft.Text(
                                "بحمد",
                                size=38,
                                weight=ft.FontWeight.BOLD,
                                color=BLUE,
                                text_align=ft.TextAlign.CENTER,
                            ),
                            ft.Text(
                                "BAHMED DOWNLOADER",
                                size=13,
                                weight=ft.FontWeight.BOLD,
                                color=INK,
                                text_align=ft.TextAlign.CENTER,
                            ),
                        ],
                        horizontal_alignment=(
                            ft.CrossAxisAlignment.CENTER
                        ),
                        spacing=2,
                    ),
                    padding=ft.padding.only(
                        top=18,
                        bottom=18,
                    ),
                ),

                ft.Container(
                    content=ft.Column(
                        [
                            ft.Text(
                                "تنزيل جديد",
                                size=20,
                                weight=ft.FontWeight.BOLD,
                                color=INK,
                            ),
                            url_field,
                            ft.Row(
                                [kind, quality],
                                spacing=10,
                            ),
                            start_button,
                        ],
                        spacing=14,
                    ),
                    bgcolor="white",
                    border_radius=18,
                    padding=16,
                ),

                ft.Container(
                    content=ft.Column(
                        [
                            ft.Text(
                                "حالة التنزيل",
                                size=17,
                                weight=ft.FontWeight.BOLD,
                                color=INK,
                            ),
                            status,
                            progress,
                            details,
                            ft.Row(
                                [
                                    pause_button,
                                    resume_button,
                                    cancel_button,
                                ],
                                alignment=(
                                    ft.MainAxisAlignment.SPACE_BETWEEN
                                ),
                                wrap=True,
                            ),
                        ],
                        spacing=12,
                    ),
                    bgcolor="white",
                    border_radius=18,
                    padding=16,
                ),

                ft.Text(
                    "نزّل فقط الملفات التي تملكها أو لديك إذن بتنزيلها.",
                    size=11,
                    color=MUTED,
                    text_align=ft.TextAlign.CENTER,
                ),
            ],
            spacing=16,
            expand=True,
            scroll=ft.ScrollMode.AUTO,
        )
    )


ft.run(main)
