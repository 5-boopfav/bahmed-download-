import asyncio
import threading
from pathlib import Path
from urllib.parse import urlparse

import flet as ft
import yt_dlp


THEMES = {
    "royal": {
        "name": "الأسود الملكي",
        "bg": "#090909",
        "panel": "#171717",
        "panel2": "#222222",
        "text": "#F7F3EA",
        "muted": "#B5AA98",
        "accent": "#D6B45C",
        "border": "#51452B",
        "good": "#36B37E",
        "warn": "#E6A23C",
        "bad": "#E45B5B",
    },
    "light": {
        "name": "الأبيض والذهبي",
        "bg": "#F5F2EA",
        "panel": "#FFFFFF",
        "panel2": "#F0EBDD",
        "text": "#25231F",
        "muted": "#777064",
        "accent": "#B58A2A",
        "border": "#D9C99E",
        "good": "#23865D",
        "warn": "#B7791F",
        "bad": "#C33D3D",
    },
    "neon": {
        "name": "الأزرق النيوني",
        "bg": "#080D1B",
        "panel": "#111A2E",
        "panel2": "#18243D",
        "text": "#F4F7FF",
        "muted": "#91A0BA",
        "accent": "#36D9FF",
        "border": "#263653",
        "good": "#22C55E",
        "warn": "#F59E0B",
        "bad": "#EF4444",
    },
}


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
    page.rtl = True
    page.padding = 0
    page.theme_mode = ft.ThemeMode.DARK

    folder = Path.home() / "Downloads" / "BAHMED"

    try:
        folder.mkdir(parents=True, exist_ok=True)
    except OSError:
        folder = Path.cwd() / "BAHMED_DOWNLOADS"
        folder.mkdir(parents=True, exist_ok=True)

    settings = {
        "theme": "royal",
        "sound": True,
        "haptic": True,
    }

    theme = THEMES["royal"]

    jobs = []
    history = []

    active_job = {"job": None}
    worker_lock = threading.Lock()

    current_page = {"name": "الرئيسية"}

    def color(name):
        return theme[name]

    def update():
        try:
            page.update()
        except Exception:
            pass

    def show_message(message):
        status.value = message
        update()

    def text(value, size=13, color_value=None, bold=False):
        return ft.Text(
            str(value),
            size=size,
            color=color_value or color("text"),
            weight=(
                ft.FontWeight.BOLD
                if bold
                else ft.FontWeight.NORMAL
            ),
        )

    def make_card(content, padding=10):
        return ft.Container(
            content=content,
            bgcolor=color("panel"),
            border=ft.Border.all(1, color("border")),
            border_radius=15,
            padding=padding,
        )

    def valid_link(value):
        try:
            parsed = urlparse(value.strip())

            return (
                parsed.scheme in ("http", "https")
                and bool(parsed.netloc)
            )

        except Exception:
            return False

    # ------------------------------
    # التفاعل والاهتزاز
    # ------------------------------

    haptics = None

    try:
        haptics = ft.HapticFeedback()
        page.services.append(haptics)
    except Exception:
        haptics = None

    async def feedback():
        if not settings["haptic"]:
            return

        if haptics is not None:
            try:
                await haptics.selection_click()
            except Exception:
                pass

    def click_feedback():
        try:
            page.run_task(feedback)
        except Exception:
            pass

    def make_button(
        label,
        icon,
        handler,
        button_color=None,
        disabled=False,
        expand=False,
    ):

        async def clicked(e):
            click_feedback()
            await handler(e)

        return ft.Button(
            label,
            icon=icon,
            on_click=clicked,
            disabled=disabled,
            expand=expand,
            style=ft.ButtonStyle(
                bgcolor=button_color or color("accent"),
                color=(
                    "#111111"
                    if button_color is None
                    or button_color == color("accent")
                    else color("text")
                ),
                padding=10,
                shape=ft.RoundedRectangleBorder(
                    radius=11
                ),
                overlay_color="#55FFFFFF",
                animation_duration=100,
            ),
        )

    # ------------------------------
    # عناصر الإدخال
    # ------------------------------

    url_field = ft.TextField(
        label="رابط الفيديو أو قائمة التشغيل",
        hint_text="الصق الرابط هنا...",
        text_align=ft.TextAlign.RIGHT,
        bgcolor=color("panel2"),
        border_color=color("border"),
        focused_border_color=color("accent"),
        cursor_color=color("accent"),
        text_size=13,
        dense=True,
    )

    media_type = ft.Dropdown(
        label="نوع الملف",
        value="video",
        options=[
            ft.DropdownOption(
                key="video",
                text="فيديو MP4",
            ),
            ft.DropdownOption(
                key="audio",
                text="صوت",
            ),
        ],
        bgcolor=color("panel2"),
        border_color=color("border"),
        dense=True,
    )

    quality = ft.Dropdown(
        label="الجودة",
        value="720",
        options=[
            ft.DropdownOption(
                key=q,
                text=q + "p",
            )
            for q in ("360", "480", "720", "1080")
        ],
        bgcolor=color("panel2"),
        border_color=color("border"),
        dense=True,
    )

    status = text(
        "جاهز لاستقبال الروابط",
        11,
        color("muted"),
    )

    preview_title = text(
        "معاينة الفيديو",
        13,
        color("text"),
        True,
    )

    preview_description = text(
        "ألصق رابطًا لجلب معلومات المحتوى",
        10,
        color("muted"),
    )

    preview_loading = ft.ProgressRing(
        width=20,
        height=20,
        visible=False,
    )

    queue_column = ft.Column(
        spacing=7,
        tight=True,
    )

    history_column = ft.Column(
        spacing=7,
        tight=True,
    )

    # ------------------------------
    # تحديث قائمة التنزيل
    # ------------------------------

    def refresh_queue():

        queue_column.controls.clear()

        for index, job in enumerate(jobs):

            link_name = job.link

            if len(link_name) > 45:
                link_name = link_name[:42] + "..."

            queue_column.controls.append(
                ft.Container(
                    content=ft.Column(
                        [
                            ft.Row(
                                [
                                    text(
                                        f"{index + 1}. {link_name}",
                                        10,
                                        color("text"),
                                    ),
                                    text(
                                        job.state,
                                        10,
                                        color("accent"),
                                        True,
                                    ),
                                ],
                                alignment=(
                                    ft.MainAxisAlignment
                                    .SPACE_BETWEEN
                                ),
                            ),
                            ft.ProgressBar(
                                value=job.progress,
                                color=color("accent"),
                                bgcolor=color("border"),
                                height=5,
                            ),
                            text(
                                job.message,
                                9,
                                color("muted"),
                            ),
                        ],
                        spacing=4,
                    ),
                    bgcolor=color("panel2"),
                    border_radius=10,
                    padding=8,
                )
            )

        update()

    def refresh_history():

        history_column.controls.clear()

        for link, result in history[:15]:

            history_column.controls.append(
                ft.Container(
                    content=ft.Row(
                        [
                            ft.Icon(
                                ft.Icons.DOWNLOAD_DONE,
                                color=color("good"),
                                size=18,
                            ),
                            ft.Column(
                                [
                                    text(
                                        link[:65],
                                        10,
                                        color("text"),
                                    ),
                                    text(
                                        result,
                                        9,
                                        color("muted"),
                                    ),
                                ],
                                spacing=2,
                                expand=True,
                            ),
                        ]
                    ),
                    bgcolor=color("panel2"),
                    border_radius=9,
                    padding=8,
                )
            )

        update()

    # ------------------------------
    # معاينة الرابط
    # ------------------------------

    async def preview_link(e=None):

        link = (url_field.value or "").strip()

        if not valid_link(link):
            show_message("أدخل رابطًا صحيحًا.")
            return

        preview_loading.visible = True
        preview_title.value = "جارٍ جلب معلومات المحتوى..."
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
                return ydl.extract_info(
                    link,
                    download=False,
                )

        try:

            info = await asyncio.to_thread(extract)

            title = info.get("title") or "تم التعرف على المحتوى"

            duration = info.get("duration")

            preview_title.value = title

            if duration:
                preview_description.value = (
                    f"مدة المحتوى: {duration} ثانية"
                )
            else:
                preview_description.value = (
                    "تم التعرف على الرابط"
                )

        except Exception as exc:

            preview_title.value = "تعذرت المعاينة"

            preview_description.value = str(exc)[:140]

        finally:

            preview_loading.visible = False
            update()

    # ------------------------------
    # إضافة روابط متعددة
    # ------------------------------

    async def add_downloads(e=None):

        links = [
            item.strip()
            for item in (url_field.value or "").splitlines()
            if item.strip()
        ]

        if not links:
            show_message("أضف رابطًا واحدًا على الأقل.")
            return

        invalid_links = [
            link for link in links
            if not valid_link(link)
        ]

        if invalid_links:
            show_message("يوجد رابط غير صحيح في القائمة.")
            return

        for link in links:

            job = DownloadJob(
                link,
                media_type.value or "video",
                quality.value or "720",
            )

            jobs.append(job)

        url_field.value = ""

        refresh_queue()

        show_message(
            f"تمت إضافة {len(links)} رابط إلى قائمة التنزيل."
        )

        start_queue()

    # ------------------------------
    # تنزيل الملفات
    # ------------------------------

    def progress_hook(job, data):

        if job.cancelled.is_set():
            raise yt_dlp.utils.DownloadError(
                "تم إلغاء التنزيل"
            )

        while not job.paused.wait(timeout=0.25):

            if job.cancelled.is_set():
                raise yt_dlp.utils.DownloadError(
                    "تم إلغاء التنزيل"
                )

        if job.cancelled.is_set():
            raise yt_dlp.utils.DownloadError(
                "تم إلغاء التنزيل"
            )

        if data.get("status") == "downloading":

            downloaded = data.get(
                "downloaded_bytes",
                0,
            )

            total = (
                data.get("total_bytes")
                or data.get("total_bytes_estimate")
            )

            if total:
                job.progress = min(
                    1,
                    downloaded / total,
                )

            speed = data.get("speed")

            if speed:
                job.message = (
                    f"{format_size(downloaded)} • "
                    f"{format_size(speed)}/s"
                )
            else:
                job.message = format_size(downloaded)

            page.run_thread(refresh_queue)

        elif data.get("status") == "finished":

            job.progress = 1

            job.message = "جارٍ تجهيز الملف..."

            page.run_thread(refresh_queue)

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

                history.insert(
                    0,
                    (job.link, "ملغى"),
                )

            else:

                job.state = "مكتمل"
                job.progress = 1
                job.message = "اكتمل التنزيل"

                history.insert(
                    0,
                    (job.link, "اكتمل"),
                )

        except Exception as exc:

            job.state = "فشل"

            job.message = str(exc)[:140]

            history.insert(
                0,
                (job.link, "تعذر التنزيل"),
            )

        finally:

            refresh_queue()
            refresh_history()

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

        status.value = "انتهت قائمة التنزيل."

        page.run_thread(update)

    def start_queue():

        if active_job["job"] is None:

            page.run_thread(queue_worker)

    # ------------------------------
    # التحكم في التنزيل
    # ------------------------------

    async def pause_download(e):

        job = active_job["job"]

        if job:

            job.paused.clear()

            job.state = "متوقف مؤقتًا"

            job.message = "التنزيل متوقف مؤقتًا"

            refresh_queue()

    async def resume_download(e):

        job = active_job["job"]

        if job:

            job.paused.set()

            job.state = "جارٍ التنزيل"

            job.message = "تم استئناف التنزيل"

            refresh_queue()

        else:

            start_queue()

    async def cancel_download(e):

        job = active_job["job"]

        if job:

            job.cancelled.set()

            job.paused.set()

            job.message = "جارٍ الإلغاء..."

            refresh_queue()

    async def clear_finished(e):

        jobs[:] = [
            job for job in jobs
            if job.state not in (
                "مكتمل",
                "فشل",
                "ملغى",
            )
        ]

        refresh_queue()

    # ------------------------------
    # الأزرار
    # ------------------------------

    preview_button = make_button(
        "معاينة الرابط",
        ft.Icons.PREVIEW,
        preview_link,
        color("panel2"),
        expand=True,
    )

    add_button = make_button(
        "إضافة إلى القائمة",
        ft.Icons.ADD_TO_QUEUE,
        add_downloads,
        expand=True,
    )

    pause_button = make_button(
        "إيقاف مؤقت",
        ft.Icons.PAUSE,
        pause_download,
        color("warn"),
        expand=True,
    )

    resume_button = make_button(
        "استئناف",
        ft.Icons.PLAY_ARROW,
        resume_download,
        color("good"),
        expand=True,
    )

    cancel_button = make_button(
        "إلغاء الحالي",
        ft.Icons.CLOSE,
        cancel_download,
        color("bad"),
        expand=True,
    )

    # ------------------------------
    # إعدادات الثيم
    # ------------------------------

    theme_picker = ft.Dropdown(
        label="اختر المظهر",
        value="royal",
        options=[
            ft.DropdownOption(
                key="royal",
                text="الأسود الملكي",
            ),
            ft.DropdownOption(
                key="light",
                text="الأبيض والذهبي",
            ),
            ft.DropdownOption(
                key="neon",
                text="الأزرق النيوني",
            ),
        ],
        bgcolor=color("panel2"),
        border_color=color("border"),
        dense=True,
    )

    sound_switch = ft.Switch(
        label="أصوات النقر والتنبيه",
        value=True,
    )

    haptic_switch = ft.Switch(
        label="الاهتزاز عند النقر",
        value=True,
    )

    async def apply_theme(e):

        nonlocal theme

        settings["theme"] = theme_picker.value

        theme = THEMES[settings["theme"]]

        page.bgcolor = color("bg")

        show_message(
            "تم تغيير المظهر."
        )

    async def save_sound_setting(e):

        settings["sound"] = sound_switch.value

        click_feedback()

    async def save_haptic_setting(e):

        settings["haptic"] = haptic_switch.value

        click_feedback()

    sound_switch.on_change = save_sound_setting

    haptic_switch.on_change = save_haptic_setting

    # ------------------------------
    # الواجهة الرئيسية
    # ------------------------------

    preview_card = make_card(
        ft.Row(
            [
                preview_loading,
                ft.Column(
                    [
                        preview_title,
                        preview_description,
                    ],
                    spacing=3,
                    expand=True,
                ),
            ]
        ),
        9,
    )

    home_view = ft.Column(
        [
            make_card(
                ft.Column(
                    [
                        text(
                            "تنزيل جديد",
                            16,
                            color("text"),
                            True,
                        ),

                        url_field,

                        ft.Row(
                            [
                                media_type,
                                quality,
                            ],
                            spacing=7,
                        ),

                        ft.Row(
                            [
                                preview_button,
                                add_button,
                            ],
                            spacing=7,
                        ),
                    ],
                    spacing=7,
                ),
                10,
            ),

            preview_card,

            make_card(
                ft.Column(
                    [
                        text(
                            "حالة التنزيل",
                            14,
                            color("text"),
                            True,
                        ),

                        status,

                        ft.Row(
                            [
                                pause_button,
                                resume_button,
                                cancel_button,
                            ],
                            spacing=5,
                        ),
                    ],
                    spacing=8,
                ),
                10,
            ),
        ],
        spacing=8,
        expand=True,
        tight=True,
    )

    # ------------------------------
    # صفحة قائمة التنزيل
    # ------------------------------

    queue_view = ft.Column(
        [
            make_card(
                ft.Column(
                    [
                        ft.Row(
                            [
                                text(
                                    "قائمة التنزيل",
                                    16,
                                    color("text"),
                                    True,
                                ),

                                make_button(
                                    "مسح المكتمل",
                                    ft.Icons.CLEANING_SERVICES,
                                    clear_finished,
                                    color("panel2"),
                                ),
                            ],
                            alignment=(
                                ft.MainAxisAlignment
                                .SPACE_BETWEEN
                            ),
                        ),

                        queue_column,
                    ],
                    spacing=8,
                ),
                10,
            ),
        ],
        expand=True,
        scroll=ft.ScrollMode.AUTO,
    )

    # ------------------------------
    # صفحة الملفات
    # ------------------------------

    files_view = make_card(
        ft.Column(
            [
                text(
                    "مجلد الملفات",
                    17,
                    color("text"),
                    True,
                ),

                text(
                    str(folder),
                    11,
                    color("accent"),
                ),

                text(
                    "تُحفظ الملفات المكتملة في مجلد BAHMED.",
                    11,
                    color("muted"),
                ),
            ],
            spacing=8,
        )
    )

    # ------------------------------
    # صفحة الإعدادات
    # ------------------------------

    settings_view = make_card(
        ft.Column(
            [
                text(
                    "الإعدادات",
                    17,
                    color("text"),
                    True,
                ),

                theme_picker,

                make_button(
                    "تطبيق المظهر",
                    ft.Icons.PALETTE,
                    apply_theme,
                ),

                sound_switch,

                haptic_switch,

                text(
                    "الصوت يحتاج إضافة ملف صوتي ومكتبة تشغيل.",
                    10,
                    color("muted"),
                ),

                text(
                    "نزّل فقط المحتوى المسموح بتنزيله.",
                    10,
                    color("muted"),
                ),
            ],
            spacing=9,
        ),
        12,
    )

    # ------------------------------
    # التنقل بين الصفحات
    # ------------------------------

    content = ft.Column(
        [home_view],
        expand=True,
    )

    def show_section(name):

        current_page["name"] = name

        if name == "الرئيسية":

            content.controls = [home_view]

        elif name == "قائمة التنزيل":

            content.controls = [queue_view]

        elif name == "الملفات":

            content.controls = [files_view]

        else:

            content.controls = [settings_view]

        update()

    def navigation_button(name, icon):

        async def clicked(e):

            click_feedback()

            show_section(name)

        return ft.Button(
            content=ft.Column(
                [
                    ft.Icon(
                        icon,
                        color=color("accent"),
                        size=19,
                    ),

                    text(
                        name,
                        9,
                        color("text"),
                    ),
                ],
                spacing=2,
                horizontal_alignment=(
                    ft.CrossAxisAlignment.CENTER
                ),
            ),

            on_click=clicked,

            expand=True,

            style=ft.ButtonStyle(
                bgcolor=color("panel2"),
                padding=5,
                shape=ft.RoundedRectangleBorder(
                    radius=10
                ),
                overlay_color="#55FFFFFF",
                animation_duration=100,
            ),
        )

    bottom_navigation = make_card(
        ft.Row(
            [
                navigation_button(
                    "الرئيسية",
                    ft.Icons.HOME_ROUNDED,
                ),

                navigation_button(
                    "قائمة التنزيل",
                    ft.Icons.DOWNLOAD_ROUNDED,
                ),

                navigation_button(
                    "الملفات",
                    ft.Icons.FOLDER_ROUNDED,
                ),

                navigation_button(
                    "الإعدادات",
                    ft.Icons.SETTINGS_ROUNDED,
                ),
            ],
            spacing=4,
        ),
        5,
    )

    # ------------------------------
    # رأس التطبيق
    # ------------------------------

    header = make_card(
        ft.Row(
            [
                ft.Column(
                    [
                        text(
                            "BAHMED",
                            21,
                            color("text"),
                            True,
                        ),

                        text(
                            "DOWNLOADER",
                            12,
                            color("accent"),
                            True,
                        ),

                        text(
                            "Download from Social Media",
                            9,
                            color("muted"),
                        ),
                    ],
                    spacing=0,
                    expand=True,
                ),

                ft.Container(
                    content=text(
                        "B",
                        25,
                        color("accent"),
                        True,
                    ),

                    width=54,
                    height=54,

                    alignment=ft.Alignment(0, 0),

                    border=ft.Border.all(
                        2,
                        color("accent"),
                    ),

                    border_radius=50,

                    bgcolor=color("panel2"),
                ),
            ],
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
        ),
        8,
    )

    main_layout = ft.Column(
        [
            header,
            content,
            bottom_navigation,
        ],
        spacing=7,
        expand=True,
    )

    # ------------------------------
    # معالجة حجم الشاشة
    # ------------------------------

    def resize(e=None):

        height = page.height or 700

        compact = height < 700

        header.padding = 6 if compact else 8

        bottom_navigation.padding = (
            4 if compact else 5
        )

        content.spacing = (
            5 if compact else 8
        )

        update()

    page.on_resize = resize

    # SafeArea لحماية الواجهة من شريط الحالة
    page.add(
        ft.SafeArea(
            content=main_layout,
            expand=True,
        )
    )

    # ------------------------------
    # فحص الحافظة عند فتح التطبيق
    # ------------------------------

    async def check_clipboard():

        try:

            copied = await page.get_clipboard()

            if (
                copied
                and valid_link(copied)
                and not url_field.value
            ):

                url_field.value = copied.strip()

                await preview_link()

        except Exception:
            pass

    try:
        page.run_task(check_clipboard)
    except Exception:
        pass

    resize()


if __name__ == "__main__":
    ft.run(main)
