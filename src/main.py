import asyncio
import os
import tempfile
import threading
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
    if value is None:
        return "--"

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

    # إعدادات النافذة
    page.title = "BAHMED DOWNLOADER"
    page.theme_mode = ft.ThemeMode.LIGHT
    page.bgcolor = "#F3F6FC"
    page.padding = 20
    page.scroll = ft.ScrollMode.AUTO

    state = None
    downloading = False

    # منتقي حفظ الملفات
    file_picker = ft.FilePicker()
    page.overlay.append(file_picker)

    # الألوان
    BLUE = "#526FFF"
    DARK = "#17243B"
    MUTED = "#8491A8"
    WHITE = "#FFFFFF"

    # حقل الرابط
    link = ft.TextField(
        hint_text="الصق رابط الفيديو هنا...",
        prefix_icon=ft.Icons.LINK,
        border_radius=14,
        bgcolor=WHITE,
        border_color="#E1E7F0",
        text_size=14,
        expand=True,
    )

    speed_limit = ft.TextField(
        label="حد السرعة KB/s",
        hint_text="بدون حد",
        width=180,
        keyboard_type=ft.KeyboardType.NUMBER,
        border_radius=12,
        bgcolor=WHITE,
    )

    # معلومات التنزيل
    progress = ft.ProgressBar(
        value=0,
        color=BLUE,
        bgcolor="#E8EDF6",
        height=9,
        border_radius=10,
    )

    percent = ft.Text(
        "0%",
        size=27,
        weight="bold",
        color=BLUE,
    )

    downloaded_text = ft.Text("الحجم: --", color=MUTED)
    speed_text = ft.Text("السرعة: --", color=MUTED)
    eta_text = ft.Text("الوقت المتبقي: --", color=MUTED)

    status = ft.Text(
        "جاهز لاستقبال رابط جديد",
        color=MUTED,
        size=13,
    )

    history = ft.Column(spacing=10)

    def update_status(message):
        status.value = message
        page.update()

    async def show_progress(data):
        raw = data["percent"].replace("%", "").strip()

        try:
            value = float(raw) / 100
        except ValueError:
            value = 0

        progress.value = max(0, min(1, value))
        percent.value = f"{value * 100:.1f}%"

        downloaded_text.value = (
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

    # أزرار التحكم
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

    # بدء التنزيل
    async def start_download(e):
        nonlocal state, downloading

        if downloading:
            return

        url = (link.value or "").strip()
        parsed = urlparse(url)

        if parsed.scheme not in ("http", "https") or not parsed.hostname:
            update_status("يرجى إدخال رابط صحيح")
            return

        limit = None

        if (speed_limit.value or "").strip():
            try:
                limit = int(speed_limit.value) * 1024
                if limit <= 0:
                    raise ValueError()
            except ValueError:
                update_status("أدخل حد سرعة صحيحًا")
                return

        state = DownloadState()
        downloading = True

        download_button.disabled = True
        pause_button.disabled = False
        resume_button.disabled = False
        cancel_button.disabled = False

        progress.value = 0
        percent.value = "0%"
        page.update()

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

            if state.cancelled.is_set():
                raise DownloadCancelled()

            if not os.path.isfile(filename):
                raise Exception("لم يتم العثور على ملف الفيديو")

            progress.value = 1
            percent.value = "100%"
            update_status("اكتمل التنزيل، اختر مكان الحفظ")

            with open(filename, "rb") as file:
                video_data = file.read()

            saved = await file_picker.save_file(
                file_name=os.path.basename(filename),
                src_bytes=video_data,
            )

            if saved:
                update_status("تم حفظ الملف بنجاح")

                history.controls.insert(
                    0,
                    ft.Container(
                        content=ft.Row(
                            [
                                ft.Icon(
                                    ft.Icons.CHECK_CIRCLE,
                                    color="#16A36A",
                                ),
                                ft.Text(
                                    os.path.basename(filename),
                                    color=DARK,
                                    expand=True,
                                ),
                            ],
                        ),
                        padding=14,
                        bgcolor=WHITE,
                        border_radius=12,
                    ),
                )
            else:
                update_status("تم إلغاء اختيار مكان الحفظ")

        except DownloadCancelled:
            update_status("تم إلغاء التنزيل")

        except Exception as error:
            update_status("تعذر التنزيل: " + str(error)[:150])

        finally:
            downloading = False
            download_button.disabled = False
            pause_button.disabled = True
            resume_button.disabled = True
            cancel_button.disabled = True
            page.update()

    # إنشاء الأزرار
    download_button = ft.Button(
        content="بدء التنزيل",
        icon=ft.Icons.DOWNLOAD,
        height=52,
        style=ft.ButtonStyle(
            bgcolor=BLUE,
            color=WHITE,
            shape=ft.RoundedRectangleBorder(radius=13),
        ),
        on_click=start_download,
    )

    pause_button = ft.Button(
        content="إيقاف مؤقت",
        icon=ft.Icons.PAUSE,
        disabled=True,
        on_click=pause_download,
    )

    resume_button = ft.Button(
        content="استئناف",
        icon=ft.Icons.PLAY_ARROW,
        disabled=True,
        on_click=resume_download,
    )

    cancel_button = ft.Button(
        content="إلغاء",
        icon=ft.Icons.CANCEL,
        disabled=True,
        on_click=cancel_download,
    )

    # بطاقة مموحدة
     def card(content, col=None):
    return ft.Container(
        content=content,
        bgcolor=WHITE,
        padding=20,
        border_radius=18,
        border=ft.Border.all(1, "#E9EEF6"),
        col=col,
     )   

    # القائمة الجانبية
    sidebar = card(
        ft.Column(
            [
                ft.Text(
                    "BAHMED",
                    size=27,
                    weight="bold",
                    color=BLUE,
                ),
                ft.Text(
                    "DOWNLOADER",
                    size=12,
                    color=MUTED,
                ),
                ft.Divider(color="#E9EEF6"),
                ft.Text("القائمة الرئيسية", weight="bold", color=DARK),
                ft.ListTile(
                    leading=ft.Icon(ft.Icons.DOWNLOAD, color=BLUE),
                    title=ft.Text("كل التنزيلات"),
                ),
                ft.ListTile(
                    leading=ft.Icon(ft.Icons.DOWNLOADING, color=BLUE),
                    title=ft.Text("قيد التنزيل"),
                ),
                ft.ListTile(
                    leading=ft.Icon(ft.Icons.CHECK_CIRCLE, color=BLUE),
                    title=ft.Text("المكتملة"),
                ),
                ft.ListTile(
                    leading=ft.Icon(ft.Icons.PAUSE_CIRCLE, color=BLUE),
                    title=ft.Text("المتوقفة"),
                ),
                ft.Divider(color="#E9EEF6"),
                ft.ListTile(
                    leading=ft.Icon(ft.Icons.SETTINGS, color=BLUE),
                    title=ft.Text("الإعدادات"),
                ),
            ],
            spacing=8,
        ),
        col={"xs": 12, "md": 3},
    )

    # منطقة إضافة الرابط
    add_card = card(
        ft.Column(
            [
                ft.Text(
                    "إضافة تنزيل جديد",
                    size=21,
                    weight="bold",
                    color=DARK,
                ),
                ft.Text(
                    "أدخل رابط الفيديو أو الملف الذي تريد تنزيله",
                    color=MUTED,
                    size=13,
                ),
                link,
                ft.Row(
                    [speed_limit],
                    wrap=True,
                ),
                download_button,
            ],
            spacing=15,
        )
    )

    # منطقة التقدم
    progress_card = card(
        ft.Column(
            [
                ft.Row(
                    [
                        ft.Text(
                            "مراقبة التنزيل",
                            size=20,
                            weight="bold",
                            color=DARK,
                        ),
                        ft.Container(expand=True),
                        percent,
                    ],
                ),
                progress,
                ft.Row(
                    [
                        ft.Icon(ft.Icons.FOLDER_OPEN, color=BLUE),
                        downloaded_text,
                    ],
                ),
                ft.Row(
                    [
                        ft.Icon(ft.Icons.SPEED, color=BLUE),
                        speed_text,
                    ],
                ),
                ft.Row(
                    [
                        ft.Icon(ft.Icons.TIMER, color=BLUE),
                        eta_text,
                    ],
                ),
                ft.Row(
                    [
                        pause_button,
                        resume_button,
                        cancel_button,
                    ],
                    wrap=True,
                ),
                ft.Divider(color="#E9EEF6"),
                status,
            ],
            spacing=14,
        )
    )

    # قائمة الملفات
    history_card = card(
        ft.Column(
            [
                ft.Row(
                    [
                        ft.Text(
                            "سجل التنزيلات",
                            size=20,
                            weight="bold",
                            color=DARK,
                        ),
                        ft.Container(expand=True),
                        ft.Icon(
                            ft.Icons.HISTORY,
                            color=BLUE,
                        ),
                    ],
                ),
                history,
            ],
            spacing=14,
        )
    )

    # رأس التطبيق
    header = ft.Row(
        [
            ft.Column(
                [
                    ft.Text(
                        "مرحبًا بك في",
                        color=MUTED,
                        size=13,
                    ),
                    ft.Text(
                        "BAHMED DOWNLOADER",
                        size=25,
                        weight="bold",
                        color=DARK,
                    ),
                ],
                spacing=3,
            ),
            ft.Container(expand=True),
            ft.Container(
                content=ft.Icon(
                    ft.Icons.DOWNLOAD_FOR_OFFLINE,
                    size=32,
                    color=BLUE,
                ),
                bgcolor="#EAF0FF",
                padding=12,
                border_radius=15,
            ),
        ],
    )

    # تخطيط متجاوب
    main_area = ft.Column(
        [
            header,
            add_card,
            progress_card,
            history_card,
        ],
        spacing=18,
        col={"xs": 12, "md": 9},
    )

    page.add(
        ft.ResponsiveRow(
            [
                sidebar,
                main_area,
            ],
            columns=12,
            spacing=18,
            run_spacing=18,
        )
    )


ft.run(main)
