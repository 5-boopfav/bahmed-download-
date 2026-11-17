import threading
from pathlib import Path
import flet as ft
import yt_dlp

BG = "#080D1B"
PANEL = "#111A2E"
PANEL2 = "#18243D"
CYAN = "#36D9FF"
PURPLE = "#8B5CF6"
GOLD = "#F5C45E"
WHITE = "#F4F7FF"
MUTED = "#91A0BA"
GREEN = "#22C55E"
ORANGE = "#F59E0B"
RED = "#EF4444"
BORDER = "#263653"


class DownloadState:
    def __init__(self):
        self.paused = threading.Event()
        self.paused.set()
        self.cancelled = threading.Event()


def fmt_size(value):
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
    page.theme_mode = ft.ThemeMode.DARK
    page.padding = 6
    page.rtl = True

    folder = Path.home() / "Downloads" / "BAHMED"

    try:
        folder.mkdir(parents=True, exist_ok=True)
    except OSError:
        folder = Path.cwd() / "BAHMED_DOWNLOADS"
        folder.mkdir(parents=True, exist_ok=True)

    active = {"state": None}
    history = []
    current_section = {"name": "الرئيسية"}

    def txt(value, size=14, color=WHITE, bold=False):
        return ft.Text(
            value,
            size=size,
            color=color,
            weight=ft.FontWeight.BOLD if bold else ft.FontWeight.NORMAL,
        )

    def card(content, padding=10):
        return ft.Container(
            content=content,
            bgcolor=PANEL,
            border=ft.Border.all(1, BORDER),
            border_radius=15,
            padding=padding,
        )

    def refresh():
        page.update()

    def set_status(message):
        status.value = message
        refresh()

    def update_progress(fraction):
        fraction = max(0, min(float(fraction), 1))
        progress.value = fraction
        progress_ring.value = fraction
        percent_text.value = f"{fraction * 100:.0f}%"

    url = ft.TextField(
        label="رابط الفيديو أو الملف",
        hint_text="الصق الرابط هنا...",
        text_align=ft.TextAlign.RIGHT,
        expand=True,
        bgcolor=PANEL2,
        border_color=BORDER,
        focused_border_color=CYAN,
        cursor_color=CYAN,
        text_size=13,
        dense=True,
    )

    kind = ft.Dropdown(
        label="نوع الملف",
        value="video",
        expand=True,
        options=[
            ft.DropdownOption(key="video", text="فيديو MP4"),
            ft.DropdownOption(key="audio", text="صوت"),
        ],
        bgcolor=PANEL2,
        border_color=BORDER,
        dense=True,
    )

    quality = ft.Dropdown(
        label="الجودة",
        value="720",
        expand=True,
        options=[
            ft.DropdownOption(key=x, text=x + "p")
            for x in ("360", "480", "720", "1080")
        ],
        bgcolor=PANEL2,
        border_color=BORDER,
        dense=True,
    )

    status = txt("جاهز لاستقبال رابط", 11, MUTED)

    progress = ft.ProgressBar(
        value=0,
        color=CYAN,
        bgcolor=BORDER,
        height=6,
    )

    progress_ring = ft.ProgressRing(
        value=0,
        width=64,
        height=64,
        stroke_width=6,
        color=CYAN,
        bgcolor=BORDER,
    )

    percent_text = txt("0%", 15, WHITE, True)

    details = txt(
        "ستظهر السرعة والحجم والوقت المتبقي هنا",
        10,
        MUTED,
    )

    history_col = ft.Column(spacing=6)

    def add_history(link, result):
        history.insert(0, (link, result))
        del history[10:]

        history_col.controls.clear()

        for link_text, result_text in history:
            history_col.controls.append(
                ft.Container(
                    content=ft.Row(
                        [
                            ft.Icon(
                                ft.Icons.DOWNLOAD_DONE,
                                color=CYAN,
                                size=19,
                            ),
                            ft.Column(
                                [
                                    txt(link_text, 11),
                                    txt(result_text, 10, MUTED),
                                ],
                                spacing=2,
                                expand=True,
                            ),
                        ],
                        spacing=8,
                    ),
                    padding=8,
                    bgcolor=PANEL2,
                    border_radius=9,
                )
            )

        refresh()

    def hook(data):
        state = active["state"]

        if state:
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
            got = data.get("downloaded_bytes", 0)

            total = (
                data.get("total_bytes")
                or data.get("total_bytes_estimate")
            )

            fraction = got / total if total else 0
            update_progress(fraction)

            speed = data.get("speed")
            eta = data.get("eta")

            details.value = (
                f"{fraction * 100:.1f}% • "
                f"{fmt_size(got)} / {fmt_size(total)} • "
                f"{fmt_size(speed) + '/s' if speed else '--'} • "
                f"المتبقي: {eta if eta is not None else '--'} ث"
            )

            page.update()

        elif data.get("status") == "finished":
            update_progress(1)
            details.value = "اكتمل نقل البيانات، جارٍ تجهيز الملف..."
            page.update()

    def worker(link, media_type, selected_quality, state):
        try:
            if media_type == "audio":
                fmt = "bestaudio/best"
            else:
                fmt = f"best[height<={selected_quality}]/best"

            options = {
                "format": fmt,

                "extractor_args": {
                    "youtube": {
                        "player_client": ["android"]
                    }
                },

                "outtmpl": str(
                    folder / "%(title).70s [%(id)s].%(ext)s"
                ),

                "noplaylist": True,
                "quiet": True,
                "no_warnings": True,
                "socket_timeout": 30,
                "progress_hooks": [hook],
                "continuedl": True,
                "overwrites": False,
            }

            with yt_dlp.YoutubeDL(options) as ydl:
                ydl.download([link])

            if state.cancelled.is_set():
                set_status("تم إلغاء التنزيل.")
                add_history(link, "أُلغي")
            else:
                update_progress(1)
                set_status("اكتمل التنزيل بنجاح.")
                details.value = f"مكان الحفظ: {folder}"
                add_history(link, "اكتمل")
                page.update()

        except Exception as exc:
            set_status(f"تعذر التنزيل: {exc}")
            add_history(link, "تعذر التنزيل")
            details.value = str(exc)
            page.update()

        finally:
            start.disabled = False
            pause.disabled = True
            resume.disabled = True
            cancel.disabled = True
            active["state"] = None
            page.update()

    def start_click(e):
        link = (url.value or "").strip()

        if not link.startswith(("http://", "https://")):
            set_status("أدخل رابطًا صحيحًا يبدأ بـ http أو https.")
            return

        if active["state"] is not None:
            set_status("يوجد تنزيل جارٍ بالفعل.")
            return

        state = DownloadState()
        active["state"] = state

        update_progress(0)
        details.value = "يتم تجهيز الاتصال..."

        start.disabled = True
        pause.disabled = False
        resume.disabled = True
        cancel.disabled = False

        set_status("بدأ التنزيل...")

        page.run_thread(
            worker,
            link,
            kind.value,
            quality.value,
            state,
        )

    def pause_click(e):
        if active["state"]:
            active["state"].paused.clear()
            pause.disabled = True
            resume.disabled = False
            set_status("التنزيل متوقف مؤقتًا.")

    def resume_click(e):
        if active["state"]:
            active["state"].paused.set()
            pause.disabled = False
            resume.disabled = True
            set_status("تم استئناف التنزيل.")

    def cancel_click(e):
        if active["state"]:
            active["state"].cancelled.set()
            active["state"].paused.set()
            set_status("جارٍ إلغاء التنزيل...")

    start = ft.Button(
        "بدء التحميل",
        icon=ft.Icons.DOWNLOAD,
        on_click=start_click,
        style=ft.ButtonStyle(
            bgcolor=CYAN,
            color="#06111F",
            padding=11,
            shape=ft.RoundedRectangleBorder(radius=10),
        ),
    )

    pause = ft.Button(
        "إيقاف مؤقت",
        icon=ft.Icons.PAUSE,
        disabled=True,
        on_click=pause_click,
        style=ft.ButtonStyle(
            bgcolor=ORANGE,
            color="#101827",
        ),
    )

    resume = ft.Button(
        "استئناف",
        icon=ft.Icons.PLAY_ARROW,
        disabled=True,
        on_click=resume_click,
        style=ft.ButtonStyle(
            bgcolor=GREEN,
            color="#07130B",
        ),
    )

    cancel = ft.Button(
        "إلغاء",
        icon=ft.Icons.CLOSE,
        disabled=True,
        on_click=cancel_click,
        style=ft.ButtonStyle(
            bgcolor=RED,
            color=WHITE,
        ),
    )

    logo = ft.Container(
        content=txt("s♡s", 22, GOLD, True),
        width=56,
        height=56,
        alignment=ft.Alignment(0, 0),
        bgcolor="#1A2140",
        border=ft.Border.all(2, GOLD),
        border_radius=50,
    )

    header = card(
        ft.Row(
            [
                ft.Column(
                    [
                        txt("BAHMED", 21, WHITE, True),
                        txt("DOWNLOADER", 13, GOLD, True),
                        txt("Download from Social Media", 9, MUTED),
                    ],
                    spacing=1,
                    expand=True,
                ),
                logo,
            ],
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
        ),
        padding=8,
    )

    new_download = card(
        ft.Column(
            [
                ft.Row(
                    [
                        txt("تنزيل جديد", 16, WHITE, True),
                        txt("MP4 • MP3", 10, CYAN, True),
                    ],
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                ),
                url,
                ft.Row([kind, quality], spacing=7),
                start,
            ],
            spacing=7,
        ),
        padding=9,
    )

    progress_display = ft.Row(
        [
            ft.Container(
                content=ft.Stack(
                    [
                        progress_ring,
                        ft.Container(
                            content=percent_text,
                            alignment=ft.Alignment(0, 0),
                        ),
                    ],
                    width=70,
                    height=70,
                ),
                alignment=ft.Alignment(0, 0),
            ),
            ft.Column(
                [
                    txt("نسبة الإنجاز", 10, MUTED),
                    txt("التنزيل الحالي", 13, WHITE, True),
                    status,
                ],
                spacing=4,
                expand=True,
            ),
        ],
        spacing=8,
        vertical_alignment=ft.CrossAxisAlignment.CENTER,
    )

    active_card = card(
        ft.Column(
            [
                txt("التنزيل النشط", 14, WHITE, True),
                progress_display,
                progress,
                details,
                ft.Row(
                    [pause, resume, cancel],
                    wrap=True,
                    spacing=5,
                ),
            ],
            spacing=7,
        ),
        padding=9,
    )

    history_card = card(
        ft.Column(
            [
                txt("آخر التنزيلات", 16, WHITE, True),
                history_col,
            ],
            spacing=8,
        )
    )

    content = ft.Column(
        [
            new_download,
            active_card,
        ],
        spacing=7,
        expand=True,
        scroll=None,
    )

    def show_section(section):
        current_section["name"] = section

        if section == "الرئيسية":
            content.controls = [
                new_download,
                active_card,
            ]

        elif section == "التنزيلات":
            content.controls = [
                active_card,
                history_card,
            ]

        elif section == "الملفات":
            content.controls = [
                card(
                    ft.Column(
                        [
                            txt("مجلد الملفات", 17, WHITE, True),
                            txt(str(folder), 11, CYAN),
                            txt(
                                "تُحفظ الملفات المكتملة في هذا المجلد.",
                                11,
                                MUTED,
                            ),
                        ],
                        spacing=8,
                    )
                )
            ]

        else:
            content.controls = [
                card(
                    ft.Column(
                        [
                            txt("الإعدادات", 17, WHITE, True),
                            txt("مجلد الحفظ", 11, MUTED),
                            txt(str(folder), 11, CYAN),
                            txt(
                                "نزّل فقط الملفات التي تملكها أو لديك إذن بتنزيلها.",
                                11,
                                MUTED,
                            ),
                        ],
                        spacing=8,
                    )
                )
            ]

        page.update()

    def nav(label, icon):
        return ft.Button(
            content=ft.Column(
                [
                    ft.Icon(icon, color=CYAN, size=19),
                    txt(label, 9, WHITE),
                ],
                spacing=2,
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            on_click=lambda e: show_section(label),
            style=ft.ButtonStyle(
                bgcolor=PANEL2,
                color=WHITE,
                padding=6,
                shape=ft.RoundedRectangleBorder(radius=10),
            ),
            expand=True,
        )

    bottom_nav = card(
        ft.Row(
            [
                nav("الرئيسية", ft.Icons.HOME_ROUNDED),
                nav("التنزيلات", ft.Icons.DOWNLOAD_ROUNDED),
                nav("الملفات", ft.Icons.FOLDER_ROUNDED),
                nav("الإعدادات", ft.Icons.SETTINGS_ROUNDED),
            ],
            spacing=5,
            alignment=ft.MainAxisAlignment.SPACE_AROUND,
        ),
        padding=6,
    )

    main_layout = ft.Column(
        [
            header,
            content,
            bottom_nav,
        ],
        spacing=6,
        expand=True,
        horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
    )

    page.add(main_layout)


ft.run(main)
