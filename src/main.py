import asyncio
import threading
from pathlib import Path
from urllib.parse import urlparse

import flet as ft
import yt_dlp


# ==========================================
# BAHMED DOWNLOADER - NEON BLUE EDITION
# ==========================================

BG = "#080D1B"
PANEL = "#111A2E"
PANEL2 = "#18243D"
CYAN = "#36D9FF"
PURPLE = "#8B5CF6"
GOLD = "#F5C45E"
WHITE = "#F4F7FF"
MUTED = "#91A0BA"
GREEN = "#22C55E"
RED = "#EF4444"
BORDER = "#263653"

AVATAR = "assets/file_00000000c39c81f8821057c3f83bc170.png"


class DownloadJob:
    def __init__(self, link, media_type, quality):
        self.link = link
        self.media_type = media_type
        self.quality = quality
        self.state = "في الانتظار"
        self.progress = 0
        self.message = "في قائمة الانتظار"
        self.cancelled = threading.Event()
        self.paused = threading.Event()
        self.paused.set()


def valid_link(value):
    try:
        parsed = urlparse(value.strip())
        return parsed.scheme in ("http", "https") and bool(parsed.netloc)
    except Exception:
        return False


def format_size(value):
    if value is None:
        return "--"

    value = float(value)

    for unit in ("B", "KB", "MB", "GB"):
        if value < 1024:
            return f"{value:.1f} {unit}"
        value /= 1024

    return f"{value:.1f} TB"


def main(page: ft.Page):

    page.title = "BAHMED DOWNLOADER"
    page.rtl = True
    page.padding = 12
    page.bgcolor = BG
    page.theme_mode = ft.ThemeMode.DARK
    page.window_min_width = 320

    folder = Path.home() / "Downloads" / "BAHMED"

    try:
        folder.mkdir(parents=True, exist_ok=True)
    except OSError:
        folder = Path.cwd() / "BAHMED_DOWNLOADS"
        folder.mkdir(parents=True, exist_ok=True)

    jobs = []
    history = []
    active_job = {"job": None}
    worker_lock = threading.Lock()

    # ==========================================
    # أدوات التصميم
    # ==========================================

    def txt(value, size=13, color=WHITE, bold=False):
        return ft.Text(
            str(value),
            size=size,
            color=color,
            weight=ft.FontWeight.BOLD if bold else ft.FontWeight.NORMAL,
        )

    def card(content, padding=12):
        return ft.Container(
            content=content,
            bgcolor=PANEL,
            padding=padding,
            border_radius=17,
            border=ft.Border.all(1, BORDER),
        )

    def update():
        try:
            page.update()
        except Exception:
            pass

    def message(value):
        status_text.value = value
        update()

    def button(label, icon, handler, bg=CYAN, expand=False):
        return ft.Button(
            label,
            icon=icon,
            on_click=handler,
            expand=expand,
            style=ft.ButtonStyle(
                bgcolor=bg,
                color="#07111F" if bg == CYAN else WHITE,
                padding=12,
                shape=ft.RoundedRectangleBorder(radius=12),
            ),
        )

    # ==========================================
    # رأس التطبيق والشعار
    # ==========================================

    avatar = ft.Container(
        content=ft.Image(
            src=AVATAR,
            width=76,
            height=76,
            fit=ft.BoxFit.COVER,
            border_radius=50,
        ),
        width=82,
        height=82,
        border_radius=50,
        border=ft.Border.all(3, GOLD),
        alignment=ft.Alignment(0, 0),
        bgcolor=PANEL2,
    )

    header = card(
        ft.Row(
            [
                ft.Column(
                    [
                        txt("BAHMED", 24, WHITE, True),
                        txt("DOWNLOADER", 14, CYAN, True),
                        txt("SOCIAL MEDIA DOWNLOADER", 9, MUTED),
                    ],
                    spacing=2,
                    expand=True,
                ),
                avatar,
            ],
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        ),
        14,
    )

    # ==========================================
    # شريط العنوان
    # ==========================================

    welcome = ft.Column(
        [
            txt("مرحباً بك في", 12, MUTED),
            txt("مركز التحميل الخاص بك", 19, WHITE, True),
            txt("حمّل المحتوى المسموح لك بتنزيله بسهولة", 10, MUTED),
        ],
        spacing=3,
    )

    # ==========================================
    # حقول الإدخال
    # ==========================================

    url_field = ft.TextField(
        label="رابط الفيديو",
        hint_text="الصق الرابط هنا...",
        text_align=ft.TextAlign.RIGHT,
        bgcolor=PANEL2,
        border_color=BORDER,
        focused_border_color=CYAN,
        cursor_color=CYAN,
        text_size=13,
        multiline=True,
        min_lines=1,
        max_lines=3,
    )

    media_type = ft.Dropdown(
        label="نوع الملف",
        value="video",
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
        options=[
            ft.DropdownOption(key=q, text=q + "p")
            for q in ("360", "480", "720", "1080")
        ],
        bgcolor=PANEL2,
        border_color=BORDER,
        dense=True,
    )

    status_text = txt("جاهز لاستقبال الروابط", 11, MUTED)

    preview_title = txt("معاينة المحتوى", 13, WHITE, True)
    preview_description = txt("ألصق رابطاً للتعرف على المحتوى", 10, MUTED)

    preview_loading = ft.ProgressRing(
        width=20,
        height=20,
        visible=False,
        color=CYAN,
    )

    # ==========================================
    # مؤشر التنزيل الدائري
    # ==========================================

    progress_ring = ft.ProgressRing(
        width=76,
        height=76,
        stroke_width=7,
        value=0,
        color=CYAN,
        bgcolor=PANEL2,
    )

    progress_label = txt("0%", 18, WHITE, True)

    progress_display = ft.Container(
        content=ft.Stack(
            [
                progress_ring,
                ft.Container(
                    content=progress_label,
                    alignment=ft.Alignment(0, 0),
                    width=76,
                    height=76,
                ),
            ],
            width=76,
            height=76,
        ),
        alignment=ft.Alignment(0, 0),
    )

    # ==========================================
    # قوائم التنزيل
    # ==========================================

    queue_column = ft.Column(spacing=9, tight=True)
    history_column = ft.Column(spacing=8, tight=True)

    def refresh_queue():

        queue_column.controls.clear()

        for index, job in enumerate(jobs):

            title = job.link
            if len(title) > 42:
                title = title[:39] + "..."

            percentage = int(job.progress * 100)

            queue_column.controls.append(
                card(
                    ft.Column(
                        [
                            ft.Row(
                                [
                                    txt(f"تنزيل {index + 1}", 12, WHITE, True),
                                    txt(job.state, 10, CYAN, True),
                                ],
                                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                            ),
                            txt(title, 10, MUTED),
                            ft.ProgressBar(
                                value=job.progress,
                                color=CYAN,
                                bgcolor=BORDER,
                                height=6,
                            ),
                            ft.Row(
                                [
                                    txt(job.message, 9, MUTED),
                                    txt(f"{percentage}%", 10, GOLD, True),
                                ],
                                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                            ),
                        ],
                        spacing=6,
                    ),
                    10,
                )
            )

        update()

    def refresh_history():

        history_column.controls.clear()

        for link, result in history[:15]:

            history_column.controls.append(
                card(
                    ft.Row(
                        [
                            ft.Icon(
                                ft.Icons.DOWNLOAD_DONE,
                                color=GREEN,
                                size=20,
                            ),
                            ft.Column(
                                [
                                    txt(link[:55], 9, WHITE),
                                    txt(result, 9, MUTED),
                                ],
                                spacing=2,
                                expand=True,
                            ),
                        ]
                    ),
                    8,
                )
            )

        update()

    # ==========================================
    # معاينة الرابط
    # ==========================================

    async def preview_link(e=None):

        link = (url_field.value or "").strip()

        if not valid_link(link):
            message("أدخل رابطاً صحيحاً.")
            return

        preview_loading.visible = True
        preview_title.value = "جارٍ فحص الرابط..."
        update()

        def extract():

            options = {
                "quiet": True,
                "no_warnings": True,
                "skip_download": True,
                "noplaylist": True,
                "socket_timeout": 15,
            }

            with yt_dlp.YoutubeDL(options) as ydl:
                return ydl.extract_info(link, download=False)

        try:

            info = await asyncio.to_thread(extract)

            preview_title.value = info.get("title") or "تم التعرف على المحتوى"

            duration = info.get("duration")

            preview_description.value = (
                f"مدة المحتوى: {duration} ثانية"
                if duration
                else "تم التعرف على الرابط"
            )

            message("تم التعرف على المحتوى.")

        except Exception as exc:

            preview_title.value = "تعذرت المعاينة"
            preview_description.value = str(exc)[:120]
            message("تعذر جلب معلومات الرابط.")

        finally:
            preview_loading.visible = False
            update()

    # ==========================================
    # مراقبة تقدم التنزيل
    # ==========================================

    def progress_hook(job, data):

        if job.cancelled.is_set():
            raise yt_dlp.utils.DownloadError("تم إلغاء التنزيل")

        while not job.paused.wait(timeout=0.25):
            if job.cancelled.is_set():
                raise yt_dlp.utils.DownloadError("تم إلغاء التنزيل")

        if job.cancelled.is_set():
            raise yt_dlp.utils.DownloadError("تم إلغاء التنزيل")

        if data.get("status") == "downloading":

            downloaded = data.get("downloaded_bytes", 0)

            total = (
                data.get("total_bytes")
                or data.get("total_bytes_estimate")
            )

            if total:
                job.progress = min(1, downloaded / total)

            speed = data.get("speed")

            job.message = (
                f"{format_size(downloaded)} • {format_size(speed)}/s"
                if speed
                else format_size(downloaded)
            )

            page.run_thread(refresh_queue)

            if active_job["job"] is job:
                page.run_thread(update_progress, job.progress)

        elif data.get("status") == "finished":

            job.progress = 1
            job.message = "جارٍ تجهيز الملف..."
            page.run_thread(refresh_queue)

    def update_progress(value):
        progress_ring.value = value
        progress_label.value = f"{int(value * 100)}%"
        update()

    # ==========================================
    # محرك التنزيل
    # ==========================================

    def download_job(job):

        job.state = "جارٍ التنزيل"
        job.message = "جارٍ الاتصال..."

        refresh_queue()

        if job.media_type == "audio":
            selected_format = "bestaudio/best"
        else:
            selected_format = (
                f"best[height<={job.quality}][ext=mp4]/"
                f"best[height<={job.quality}]/best"
            )

        options = {
            "format": selected_format,
            "outtmpl": str(
                folder / "%(title).70s [%(id)s].%(ext)s"
            ),
            "noplaylist": False,
            "quiet": True,
            "no_warnings": True,
            "socket_timeout": 30,
            "continuedl": True,
            "overwrites": False,
            "progress_hooks": [
                lambda data: progress_hook(job, data)
            ],
        }

        try:

            with yt_dlp.YoutubeDL(options) as ydl:
                ydl.download([job.link])

            if job.cancelled.is_set():

                job.state = "ملغى"
                job.message = "تم إلغاء المهمة"
                history.insert(0, (job.link, "ملغى"))

            else:

                job.state = "مكتمل"
                job.progress = 1
                job.message = "اكتمل التنزيل"
                history.insert(0, (job.link, "اكتمل"))

        except Exception as exc:

            job.state = "فشل"
            job.message = str(exc)[:120]
            history.insert(0, (job.link, "تعذر التنزيل"))

        finally:

            refresh_queue()
            refresh_history()

            if active_job["job"] is job:
                page.run_thread(update_progress, job.progress)

    def queue_worker():

        with worker_lock:

            while True:

                next_job = next(
                    (
                        job for job in jobs
                        if job.state == "في الانتظار"
                    ),
                    None,
                )

                if next_job is None:
                    break

                active_job["job"] = next_job

                download_job(next_job)

                active_job["job"] = None

        page.run_thread(message, "انتهت قائمة التنزيل.")

    def start_queue():

        if active_job["job"] is None:
            page.run_thread(queue_worker)

    # ==========================================
    # إضافة روابط
    # ==========================================

    async def add_downloads(e=None):

        links = [
            item.strip()
            for item in (url_field.value or "").splitlines()
            if item.strip()
        ]

        if not links:
            message("أضف رابطاً واحداً على الأقل.")
            return

        if any(not valid_link(link) for link in links):
            message("يوجد رابط غير صحيح.")
            return

        for link in links:
            jobs.append(
                DownloadJob(
                    link,
                    media_type.value or "video",
                    quality.value or "720",
                )
            )

        url_field.value = ""

        refresh_queue()
        message(f"تمت إضافة {len(links)} رابط.")

        start_queue()

    # ==========================================
    # أزرار التحكم
    # ==========================================

    async def pause_download(e):

        job = active_job["job"]

        if job:
            job.paused.clear()
            job.state = "متوقف مؤقتاً"
            job.message = "التنزيل متوقف مؤقتاً"
            refresh_queue()
            message("تم الإيقاف المؤقت.")

    async def resume_download(e):

        job = active_job["job"]

        if job:
            job.paused.set()
            job.state = "جارٍ التنزيل"
            job.message = "تم استئناف التنزيل"
            refresh_queue()
            message("تم استئناف التنزيل.")
        else:
            start_queue()

    async def cancel_download(e):

        job = active_job["job"]

        if job:
            job.cancelled.set()
            job.paused.set()
            job.message = "جارٍ الإلغاء..."
            refresh_queue()
            message("جارٍ إلغاء التنزيل.")

    async def clear_finished(e):

        jobs[:] = [
            job for job in jobs
            if job.state not in ("مكتمل", "فشل", "ملغى")
        ]

        refresh_queue()

    # ==========================================
    # منطقة التنزيل
    # ==========================================

    preview_card = card(
        ft.Row(
            [
                preview_loading,
                ft.Column(
                    [
                        preview_title,
                        preview_description,
                    ],
                    spacing=4,
                    expand=True,
                ),
            ]
        ),
        10,
    )

    download_card = card(
        ft.Column(
            [
                txt("تنزيل جديد", 16, WHITE, True),
                url_field,
                ft.Row(
                    [media_type, quality],
                    spacing=8,
                ),
                ft.Row(
                    [
                        button(
                            "معاينة",
                            ft.Icons.PREVIEW,
                            preview_link,
                            PANEL2,
                            True,
                        ),
                        button(
                            "بدء التحميل",
                            ft.Icons.DOWNLOAD_ROUNDED,
                            add_downloads,
                            CYAN,
                            True,
                        ),
                    ],
                    spacing=8,
                ),
            ],
            spacing=10,
        )
    )

    progress_card = card(
        ft.Column(
            [
                txt("حالة التنزيل", 15, WHITE, True),
                ft.Row(
                    [
                        progress_display,
                        ft.Column(
                            [
                                status_text,
                                txt("مؤشر تقدم التنزيل", 10, MUTED),
                                txt("BAHMED DOWNLOAD ENGINE", 9, CYAN),
                            ],
                            spacing=5,
                            expand=True,
                        ),
                    ],
                    spacing=15,
                ),
                ft.Row(
                    [
                        button("إيقاف", ft.Icons.PAUSE, pause_download, "#B7791F", True),
                        button("استئناف", ft.Icons.PLAY_ARROW, resume_download, GREEN, True),
                        button("إلغاء", ft.Icons.CLOSE, cancel_download, RED, True),
                    ],
                    spacing=5,
                ),
            ],
            spacing=10,
        )
    )

    # ==========================================
    # الصفحات
    # ==========================================

    home_view = ft.Column(
        [
            welcome,
            download_card,
            preview_card,
            progress_card,
        ],
        spacing=12,
        scroll=ft.ScrollMode.AUTO,
        expand=True,
    )

    queue_view = ft.Column(
        [
            card(
                ft.Column(
                    [
                        ft.Row(
                            [
                                txt("قائمة التنزيل", 17, WHITE, True),
                                button(
                                    "مسح المكتمل",
                                    ft.Icons.CLEANING_SERVICES,
                                    clear_finished,
                                    PANEL2,
                                ),
                            ],
                            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                        ),
                        queue_column,
                    ],
                    spacing=10,
                )
            )
        ],
        scroll=ft.ScrollMode.AUTO,
        expand=True,
    )

    files_view = card(
        ft.Column(
            [
                txt("ملفاتي", 18, WHITE, True),
                ft.Icon(ft.Icons.FOLDER_ROUNDED, size=55, color=CYAN),
                txt("مجلد حفظ الملفات", 12, MUTED),
                txt(str(folder), 11, GOLD),
                txt("تُحفظ التنزيلات المكتملة في هذا المجلد.", 10, MUTED),
            ],
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            spacing=12,
        ),
        20,
    )

    settings_view = card(
        ft.Column(
            [
                txt("الإعدادات", 18, WHITE, True),
                txt("BAHMED DOWNLOADER", 12, CYAN, True),
                txt("الإصدار 1.0", 10, MUTED),
                txt("احفظ الملفات المسموح لك بتنزيلها فقط.", 11, MUTED),
            ],
            spacing=12,
        ),
        18,
    )

    # ==========================================
    # التنقل السفلي
    # ==========================================

    content = ft.Column(
        [home_view],
        expand=True,
    )

    def show_section(name):

        if name == "الرئيسية":
            content.controls = [home_view]
        elif name == "التنزيلات":
            content.controls = [queue_view]
        elif name == "ملفاتي":
            content.controls = [files_view]
        else:
            content.controls = [settings_view]

        update()

    def nav_button(name, icon):

        async def clicked(e):
            show_section(name)

        return ft.Button(
            content=ft.Column(
                [
                    ft.Icon(icon, color=CYAN, size=21),
                    txt(name, 9, WHITE),
                ],
                spacing=4,
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            on_click=clicked,
            expand=True,
            style=ft.ButtonStyle(
                bgcolor=PANEL2,
                padding=7,
                shape=ft.RoundedRectangleBorder(radius=12),
            ),
        )

    bottom_navigation = card(
        ft.Row(
            [
                nav_button("الرئيسية", ft.Icons.HOME_ROUNDED),
                nav_button("التنزيلات", ft.Icons.DOWNLOAD_ROUNDED),
                nav_button("ملفاتي", ft.Icons.FOLDER_ROUNDED),
                nav_button("الإعدادات", ft.Icons.SETTINGS_ROUNDED),
            ],
            spacing=5,
        ),
        7,
    )

    # ==========================================
    # بناء الواجهة
    # ==========================================

    page.add(
        ft.Column(
            [
                header,
                content,
                bottom_navigation,
            ],
            spacing=12,
            expand=True,
        )
    )

    # ==========================================
    # فحص الحافظة
    # ==========================================

    async def check_clipboard():

        try:

            copied = await page.get_clipboard()

            if copied and valid_link(copied) and not url_field.value:
                url_field.value = copied.strip()
                await preview_link()

        except Exception:
            pass

    try:
        page.run_task(check_clipboard)
    except Exception:
        pass


if __name__ == "__main__":
    ft.run(main)
