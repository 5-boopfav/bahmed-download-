import asyncio
import os
import tempfile
import threading
import time
from urllib.parse import urlparse

import flet as ft
import yt_dlp


class DownloadCancelled(Exception):
    pass


class DownloadState:
    def __init__(self):
        self.paused = threading.Event()
        self.paused.set()
        self.cancelled = threading.Event()


def format_size(value):
    if not value:
        return "غير معروف"

    value = float(value)

    for unit in ("B", "KB", "MB", "GB"):
        if value < 1024:
            return f"{value:.1f} {unit}"
        value /= 1024

    return f"{value:.1f} TB"


def download_video(url, folder, state, speed_limit, callback):
    def progress_hook(data):
        while not state.paused.wait(timeout=0.3):
            if state.cancelled.is_set():
                raise DownloadCancelled()

        if state.cancelled.is_set():
            raise DownloadCancelled()

        if data["status"] == "downloading":
            callback({
                "percent": data.get("_percent_str", "0%"),
                "downloaded": data.get("downloaded_bytes", 0),
                "total": data.get("total_bytes")
                         or data.get("total_bytes_estimate"),
                "speed": data.get("speed"),
                "eta": data.get("eta"),
            })

    options = {
        "format": "best[ext=mp4]/best",
        "outtmpl": os.path.join(
            folder, "%(title).60s [%(id)s].%(ext)s"
        ),
        "noplaylist": True,
        "quiet": True,
        "no_warnings": True,
        "socket_timeout": 30,
        "continuedl": True,
        "progress_hooks": [progress_hook],
    }

    if speed_limit:
        options["ratelimit"] = speed_limit

    with yt_dlp.YoutubeDL(options) as ydl:
        info = ydl.extract_info(url, download=True)
        return ydl.prepare_filename(info)


async def main(page: ft.Page):
    page.title = "BAHMED DOWNLOADER"
    page.theme_mode = ft.ThemeMode.LIGHT
    page.bgcolor = "#F3F6FC"
    page.padding = 20
    page.scroll = ft.ScrollMode.AUTO

    state = None
    downloading = False

    link = ft.TextField(
        hint_text="ضع رابط الفيديو هنا...",
        border_radius=14,
        bgcolor="white",
        border_color="#DCE3F0",
        prefix_icon=ft.Icons.LINK,
    )

    speed_limit = ft.TextField(
        label="حد السرعة بالكيلوبايت/ثانية",
        hint_text="اتركه فارغًا للسرعة غير المحدودة",
        keyboard_type=ft.KeyboardType.NUMBER,
        border_radius=12,
        bgcolor="white",
    )

    progress = ft.ProgressBar(
        value=0,
        color="#526FFF",
        bgcolor="#E1E7F2",
        height=10,
        border_radius=10,
    )

    percent_text = ft.Text(
        "0%",
        size=25,
        weight="bold",
        color="#526FFF",
    )

    size_text = ft.Text("الحجم: --")
    speed_text = ft.Text("السرعة: --")
    eta_text = ft.Text("الوقت المتبقي: --")

    status = ft.Text(
        "جاهز للتنزيل",
        color="#64748B",
        size=14,
    )

    history = ft.Column(spacing=10)

    def update_status(message):
        status.value = message
        page.update()

    async def show_progress(data):
        percent = data["percent"].replace("%", "").strip()

        try:
            value = float(percent) / 100
        except ValueError:
            value = 0

        progress.value = max(0, min(1, value))
        percent_text.value = f"{value * 100:.1f}%"

        size_text.value = (
            f"الحجم: {format_size(data['downloaded'])}"
            f" / {format_size(data['total'])}"
        )

        speed = data["speed"]
        speed_text.value = (
            f"السرعة: {format_size(speed)}/ث"
            if speed else "السرعة: --"
        )

        eta = data["eta"]
        eta_text.value = (
            f"الوقت المتبقي: {int(eta)} ثانية"
            if eta is not None else "الوقت المتبقي: --"
        )

        page.update()

    def progress_callback(data):
        page.run_task(show_progress, data)

    async def pause_download(e):
        if state and downloading:
            state.paused.clear()
            update_status("تم إيقاف التنزيل مؤقتًا")

    async def resume_download(e):
        if state and downloading:
            state.paused.set()
            update_status("تم استئناف التنزيل")

    async def cancel_download(e):
        if state and downloading:
            state.cancelled.set()
            state.paused.set()
            update_status("جارٍ إلغاء التنزيل...")

    async def start_download(e):
        nonlocal state, downloading

        if downloading:
            return

        url = (link.value or "").strip()
        host = urlparse(url).hostname or ""

        allowed = (
            host == "youtu.be"
            or host == "youtube.com"
            or host.endswith((
                ".youtube.com",
                ".tiktok.com",
                ".instagram.com",
                ".x.com",
                ".twitter.com",
            ))
        )

        if (
            urlparse(url).scheme not in ("http", "https")
            or not allowed
        ):
            update_status("أدخل رابطًا صحيحًا من المنصات المدعومة")
            return

        limit = None

        if (speed_limit.value or "").strip():
            try:
                limit = int(speed_limit.value) * 1024
                if limit <= 0:
                    raise ValueError()
            except ValueError:
                update_status("أدخل سرعة صحيحة أو اترك الخانة فارغة")
                return

        state = DownloadState()
        downloading = True

        download_button.disabled = True
        pause_button.disabled = False
        resume_button.disabled = False
        cancel_button.disabled = False

        progress.value = 0
        percent_text.value = "0%"
        update_status("جارٍ بدء التنزيل...")

        try:
            folder = tempfile.mkdtemp(prefix="bahmed_")

            filename = await asyncio.to_thread(
                download_video,
                url,
                folder,
                state,
                limit,
                progress_callback,
            )

            if not os.path.isfile(filename):
                raise Exception("لم يتم العثور على ملف الفيديو")

            if state.cancelled.is_set():
                raise DownloadCancelled()

            progress.value = 1
            percent_text.value = "100%"
            update_status("اكتمل التنزيل! اختر مكان الحفظ")

            with open(filename, "rb") as file:
                video_data = file.read()

            saved = await ft.FilePicker().save_file(
                file_name=os.path.basename(filename),
                src_bytes=video_data,
            )

            if saved:
                update_status("تم حفظ الفيديو بنجاح")

                history.controls.insert(
                    0,
                    ft.Container(
                        content=ft.Text(
                            "✓ " + os.path.basename(filename),
                            color="#334155",
                        ),
                        padding=12,
                        bgcolor="white",
                        border_radius=12,
                    ),
                )
            else:
                update_status("تم إلغاء الحفظ")

        except DownloadCancelled:
            update_status("تم إلغاء التنزيل")

        except Exception as error:
            update_status("تعذر التنزيل: " + str(error)[:120])

        finally:
            downloading = False
            download_button.disabled = False
            pause_button.disabled = True
            resume_button.disabled = True
            cancel_button.disabled = True
            page.update()

    download_button = ft.Button(
        content=ft.Text("بدء التحميل"),
        width=350,
        height=52,
        style=ft.ButtonStyle(
            bgcolor="#526FFF",
            color="white",
        ),
        on_click=start_download,
    )

    pause_button = ft.Button(
        content=ft.Text("إيقاف مؤقت"),
        disabled=True,
        on_click=pause_download,
    )

    resume_button = ft.Button(
        content=ft.Text("استئناف"),
        disabled=True,
        on_click=resume_download,
    )

    cancel_button = ft.Button(
        content=ft.Text("إلغاء"),
        disabled=True,
        on_click=cancel_download,
    )

    page.add(
        ft.Column(
            [
                ft.Text(
                    "BAHMED",
                    size=32,
                    weight="bold",
                    color="#526FFF",
                ),
                ft.Text(
                    "DOWNLOADER",
                    size=13,
                    color="#64748B",
                ),

                ft.Container(height=15),

                ft.Container(
                    content=ft.Column(
                        [
                            ft.Text(
                                "تحميل فيديو",
                                size=22,
                                weight="bold",
                                color="#1E293B",
                            ),
                            link,
                            speed_limit,
                            download_button,
                        ],
                        spacing=15,
                    ),
                    bgcolor="white",
                    padding=18,
                    border_radius=18,
                ),

                ft.Container(
                    content=ft.Column(
                        [
                            ft.Text(
                                "تقدم التنزيل",
                                size=20,
                                weight="bold",
                                color="#1E293B",
                            ),
                            percent_text,
                            progress,
                            size_text,
                            speed_text,
                            eta_text,
                            ft.Row(
                                [
                                    pause_button,
                                    resume_button,
                                    cancel_button,
                                ],
                                wrap=True,
                            ),
                            status,
                        ],
                        spacing=12,
                    ),
                    bgcolor="white",
                    padding=18,
                    border_radius=18,
                ),

                ft.Text(
                    "التحميلات الأخيرة",
                    size=20,
                    weight="bold",
                    color="#1E293B",
                ),

                history,
            ],
            spacing=18,
        )
    )


ft.run(main)
