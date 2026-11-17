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
        "socket_timeout": 30,
        "continuedl": True,
        "progress_hooks": [progress_hook],
    }
    if speed_limit:
        options["ratelimit"] = speed_limit

    with yt_dlp.YoutubeDL(options) as ydl:
        info = ydl.extract_info(url, download=True)
        filename = ydl.prepare_filename(info)
        # yt-dlp may change the extension after post-processing.
        if os.path.isfile(filename):
            return filename
        base, _ = os.path.splitext(filename)
        for candidate in (base + ".mp4", base + ".m4a", base + ".webm", base + ".mkv"):
            if os.path.isfile(candidate):
                return candidate
        candidates = [
            os.path.join(folder, name)
            for name in os.listdir(folder)
            if os.path.isfile(os.path.join(folder, name))
        ]
        if candidates:
            return max(candidates, key=os.path.getsize)
        raise FileNotFoundError("لم يتم العثور على الملف بعد اكتمال التنزيل")


async def main(page: ft.Page):
    page.title = "BAHMED DOWNLOADER"
    page.theme_mode = ft.ThemeMode.LIGHT
    page.bgcolor = BG
    page.padding = 0
    page.rtl = True
    page.window_min_width = 340
    page.window_min_height = 620

    state = None
    downloading = False
    history_items = []
    active_tab = "الرئيسية"

    picker = ft.FilePicker()
    page.overlay.append(picker)

    link = ft.TextField(
        hint_text="الصق رابط الفيديو هنا...",
        prefix_icon=ft.Icons.LINK,
        text_size=15,
        border=ft.InputBorder.NONE,
        bgcolor=WHITE,
        expand=True,
        text_align=ft.TextAlign.RIGHT,
    )
    speed_limit = ft.TextField(
        label="حد السرعة KB/s",
        hint_text="اختياري",
        width=150,
        keyboard_type=ft.KeyboardType.NUMBER,
        border_radius=12,
        text_align=ft.TextAlign.CENTER,
    )
    kind = ft.SegmentedButton(
        selected={"video"},
        allow_multiple_selection=False,
        segments=[
            ft.Segment(value="video", label=ft.Text("فيديو MP4"), icon=ft.Icon(ft.Icons.VIDEOCAM)),
            ft.Segment(value="audio", label=ft.Text("صوت"), icon=ft.Icon(ft.Icons.MUSIC_NOTE)),
        ],
        on_change=None,
    )
    quality = ft.Dropdown(
        label="الجودة",
        value="720p",
        options=[
            ft.dropdown.Option("360p"),
            ft.dropdown.Option("480p"),
            ft.dropdown.Option("720p"),
            ft.dropdown.Option("1080p"),
        ],
        width=130,
        border_radius=12,
    )

    progress = ft.ProgressBar(value=0, color=BLUE, bgcolor="#E4EAF6", height=8)
    percent = ft.Text("0%", size=25, weight=ft.FontWeight.BOLD, color=BLUE)
    size_text = ft.Text("الحجم: --", size=12, color=MUTED)
    speed_text = ft.Text("السرعة: --", size=12, color=MUTED)
    eta_text = ft.Text("المتبقي: --", size=12, color=MUTED)
    status = ft.Text("جاهز للتنزيل", color=MUTED, size=12)
    history_column = ft.Column(spacing=10)
    body = ft.Column(spacing=16, scroll=ft.ScrollMode.AUTO, expand=True)

    def card(content, padding=16):
        return ft.Container(
            content=content,
            bgcolor=WHITE,
            padding=padding,
            border=ft.Border.all(1, BORDER),
            border_radius=20,
            shadow=ft.BoxShadow(
                blur_radius=14,
                spread_radius=0,
                color="#0D2440" + "0A",
                offset=ft.Offset(0, 4),
            ),
        )

    def set_status(message):
        status.value = message
        page.update()

    async def update_progress(data):
        raw = str(data.get("percent", "0%")).replace("%", "").strip()
        try:
            val = max(0, min(1, float(raw) / 100))
        except ValueError:
            val = 0
        progress.value = val
        percent.value = f"{val * 100:.1f}%"
        size_text.value = f"الحجم: {format_size(data.get('downloaded'))} / {format_size(data.get('total'))}"
        speed_text.value = f"السرعة: {format_size(data.get('speed'))}/ث"
        eta = data.get("eta")
        eta_text.value = f"المتبقي: {int(eta)} ثانية" if eta is not None else "المتبقي: --"
        page.update()

    def progress_callback(data):
        page.run_task(update_progress, data)

    async def pause_download(e):
        if state and downloading:
            state.paused.clear()
            set_status("تم إيقاف التنزيل مؤقتًا")

    async def resume_download(e):
        if state and downloading:
            state.paused.set()
            set_status("تم استئناف التنزيل")

    async def cancel_download(e):
        if state and downloading:
            state.cancelled.set()
            state.paused.set()
            set_status("جارٍ إلغاء التنزيل...")

    async def start_download(e):
        nonlocal state, downloading
        if downloading:
            return

        url = (link.value or "").strip()
        parsed = urlparse(url)
        if parsed.scheme not in ("http", "https") or not parsed.hostname:
            set_status("أدخل رابطًا صحيحًا يبدأ بـ https:// أو http://")
            return

        limit = None
        if (speed_limit.value or "").strip():
            try:
                limit = int(speed_limit.value) * 1024
                if limit <= 0:
                    raise ValueError
            except ValueError:
                set_status("حد السرعة يجب أن يكون رقمًا أكبر من صفر")
                return

        media_kind = "audio" if "audio" in kind.selected else "video"
        chosen_quality = quality.value or "720p"
        state = DownloadState()
        downloading = True
        start_button.disabled = True
        pause_button.disabled = False
        resume_button.disabled = False
        cancel_button.disabled = False
        progress.value = 0
        percent.value = "0%"
        set_status("جارٍ تحليل الرابط وبدء التنزيل...")
        page.update()

        try:
            folder = tempfile.mkdtemp(prefix="bahmed_")
            filename = await asyncio.to_thread(
                download_media, url, folder, state, limit,
                media_kind, chosen_quality, progress_callback
            )
            if state.cancelled.is_set():
                raise DownloadCancelled()
            if not os.path.isfile(filename):
                raise FileNotFoundError("لم يتم العثور على الملف")
            progress.value = 1
            percent.value = "100%"
            set_status("اكتمل التنزيل. اختر مكان حفظ الملف.")

            # Android needs src_bytes with FilePicker.save_file().
            # Read in chunks is not supported by this API; very large files
            # may require substantial memory on the phone.
            with open(filename, "rb") as f:
                data = f.read()

            page.update()
            saved_path = await picker.save_file(
                dialog_title="اختر مكان حفظ الملف",
                file_name=os.path.basename(filename),
                src_bytes=data,
            )
            if saved_path:
                set_status("تم حفظ الملف بنجاح")
                history_items.insert(0, os.path.basename(filename))
                render_history()
            else:
                set_status("تم إلغاء اختيار مكان الحفظ")
        except DownloadCancelled:
            set_status("تم إلغاء التنزيل")
        except Exception as ex:
            set_status("تعذر التنزيل: " + str(ex)[:180])
        finally:
            downloading = False
            start_button.disabled = False
            pause_button.disabled = True
            resume_button.disabled = True
            cancel_button.disabled = True
            page.update()

    def render_history():
        history_column.controls.clear()
        if not history_items:
            history_column.controls.append(
                ft.Container(
                    content=ft.Text("لا توجد تنزيلات محفوظة حتى الآن", color=MUTED),
                    padding=16,
                    alignment=ft.Alignment.CENTER,
                )
            )
        else:
            for name in history_items:
                history_column.controls.append(
                    ft.Container(
                        content=ft.Row(
                            [
                                ft.Icon(ft.Icons.MOVIE, color=BLUE),
                                ft.Text(name, color=INK, expand=True, max_lines=2, overflow=ft.TextOverflow.ELLIPSIS),
                                ft.Icon(ft.Icons.CHECK_CIRCLE, color=GREEN),
                            ],
                        ),
                        padding=12,
                        bgcolor="#F8FAFF",
                        border_radius=14,
                    )
                )
        page.update()

    start_button = ft.Button(
        content="تنزيل الآن",
        icon=ft.Icons.DOWNLOAD,
        height=52,
        expand=True,
        style=ft.ButtonStyle(
            bgcolor=BLUE,
            color=WHITE,
            shape=ft.RoundedRectangleBorder(radius=16),
        ),
        on_click=start_download,
    )
    pause_button = ft.Button("إيقاف مؤقت", icon=ft.Icons.PAUSE, disabled=True, on_click=pause_download)
    resume_button = ft.Button("استئناف", icon=ft.Icons.PLAY_ARROW, disabled=True, on_click=resume_download)
    cancel_button = ft.Button("إلغاء", icon=ft.Icons.CLOSE, disabled=True, on_click=cancel_download)

    def build_home():
        return [
            ft.Container(
                content=ft.Column(
                    [
                        ft.Row(
                            [
                                ft.IconButton(ft.Icons.SETTINGS_OUTLINED, icon_color=INK, tooltip="الإعدادات"),
                                ft.Container(expand=True),
                                ft.Column(
                                    [
                                        ft.Text("بحمد", size=38, weight=ft.FontWeight.BOLD, color=INK),
                                        ft.Text("BAHMED DOWNLOADER", size=11, weight=ft.FontWeight.BOLD, color=BLUE),
                                    ],
                                    spacing=0,
                                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                                ),
                                ft.Container(expand=True),
                                ft.Icon(ft.Icons.DOWNLOAD_FOR_OFFLINE, color=BLUE, size=28),
                            ],
                            vertical_alignment=ft.CrossAxisAlignment.CENTER,
                        ),
                        ft.Container(height=3, bgcolor=BLUE, border_radius=10, width=90),
                    ],
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    spacing=8,
                ),
                padding=ft.Padding(18, 18, 18, 12),
            ),
            card(
                ft.Column(
                    [
                        ft.Text("أدخل رابط الفيديو", size=19, weight=ft.FontWeight.BOLD, color=INK),
                        ft.Container(
                            content=ft.Row([link, ft.IconButton(ft.Icons.CONTENT_PASTE, tooltip="لصق الرابط")]),
                            padding=ft.Padding(10, 2, 6, 2),
                            bgcolor="#F7F9FE",
                            border=ft.Border.all(1, BORDER),
                            border_radius=15,
                        ),
                        ft.Text("اختر نوع الملف والجودة", color=MUTED, size=12),
                        ft.Row([kind, quality], alignment=ft.MainAxisAlignment.SPACE_BETWEEN, wrap=True),
                        ft.Row([speed_limit], alignment=ft.MainAxisAlignment.END),
                        start_button,
                    ],
                    spacing=14,
                )
            ),
            card(
                ft.Column(
                    [
                        ft.Row(
                            [
                                ft.Text("مراقبة التنزيل", size=18, weight=ft.FontWeight.BOLD, color=INK),
                                ft.Container(expand=True),
                                percent,
                            ],
                        ),
                        progress,
                        ft.Row([size_text, speed_text], wrap=True, alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                        ft.Row([eta_text, status], wrap=True, alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                        ft.Row([pause_button, resume_button, cancel_button], wrap=True),
                    ],
                    spacing=12,
                )
            ),
            card(
                ft.Column(
                    [
                        ft.Row(
                            [
                                ft.Text("آخر التنزيلات", size=18, weight=ft.FontWeight.BOLD, color=INK),
                                ft.Container(expand=True),
                                ft.TextButton("عرض الكل", on_click=lambda e: show_tab("التنزيلات")),
                            ],
                        ),
                        history_column,
                    ],
                    spacing=10,
                )
            ),
        ]

    def show_tab(tab):
        nonlocal active_tab
        active_tab = tab
        body.controls.clear()
        if tab == "الرئيسية":
            body.controls.extend(build_home())
        elif tab == "التنزيلات":
            body.controls.append(card(ft.Column([ft.Text("التنزيلات", size=22, weight=ft.FontWeight.BOLD, color=INK), history_column])))
        elif tab == "الملفات":
            body.controls.append(card(ft.Column([
                ft.Text("الملفات", size=22, weight=ft.FontWeight.BOLD, color=INK),
                ft.Text("تظهر هنا الملفات التي أكملت تنزيلها داخل التطبيق.", color=MUTED),
            ])))
        else:
            body.controls.append(card(ft.Column([
                ft.Text("الإعدادات", size=22, weight=ft.FontWeight.BOLD, color=INK),
                ft.Text("إعدادات التنزيل الأساسية", color=MUTED),
                speed_limit,
                ft.Text("تنبيه: حفظ الملفات الكبيرة قد يحتاج ذاكرة إضافية.", color=MUTED, size=12),
            ])))
        page.update()

    nav = ft.NavigationBar(
        selected_index=0,
        destinations=[
            ft.NavigationBarDestination(icon=ft.Icons.HOME_OUTLINED, selected_icon=ft.Icons.HOME, label="الرئيسية"),
            ft.NavigationBarDestination(icon=ft.Icons.DOWNLOAD_OUTLINED, selected_icon=ft.Icons.DOWNLOAD, label="التنزيلات"),
            ft.NavigationBarDestination(icon=ft.Icons.FOLDER_OUTLINED, selected_icon=ft.Icons.FOLDER, label="الملفات"),
            ft.NavigationBarDestination(icon=ft.Icons.SETTINGS_OUTLINED, selected_icon=ft.Icons.SETTINGS, label="الإعدادات"),
        ],
        on_change=lambda e: show_tab(["الرئيسية", "التنزيلات", "الملفات", "الإعدادات"][e.control.selected_index]),
        bgcolor=WHITE,
        indicator_color="#E7EFFF",
    )

    page.add(
        ft.SafeArea(
            content=ft.Column(
                [
                    body,
                    nav,
                ],
                spacing=0,
                expand=True,
            ),
            expand=True,
        )
    )
    render_history()
    show_tab("الرئيسية")


ft.run(main)
