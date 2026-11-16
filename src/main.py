import asyncio
import os
import tempfile
from urllib.parse import urlparse

import flet as ft
import yt_dlp


def download_video(url, folder):
    options = {
        "format": "best[ext=mp4]/best",
        "outtmpl": os.path.join(
            folder, "%(title).60s [%(id)s].%(ext)s"
        ),
        "noplaylist": True,
        "quiet": True,
        "no_warnings": True,
        "socket_timeout": 30,
    }

    with yt_dlp.YoutubeDL(options) as ydl:
        info = ydl.extract_info(url, download=True)
        return ydl.prepare_filename(info)


async def main(page: ft.Page):
    page.title = "BAHMED Downloader"
    page.theme_mode = ft.ThemeMode.DARK
    page.bgcolor = "#10131C"
    page.padding = 20

    link = ft.TextField(
        hint_text="ضع رابط الفيديو هنا...",
        border_radius=15,
        bgcolor="#202637",
        border_color="#343D52",
        prefix_icon=ft.Icons.LINK,
    )

    status = ft.Text(
        "جاهز للتنزيل",
        color="#AAB2C5",
    )

    history = ft.Column(spacing=8)

    async def start_download(e):
        url = (link.value or "").strip()
        host = urlparse(url).hostname or ""

        allowed = (
            host == "youtu.be"
            or host.endswith(("youtube.com", "tiktok.com",
                              "instagram.com", "x.com",
                              "twitter.com"))
        )

        if urlparse(url).scheme not in ("http", "https") or not allowed:
            status.value = "أدخل رابطًا صحيحًا من المنصات المدعومة"
            page.update()
            return

        download_button.disabled = True
        status.value = "جارٍ تنزيل الفيديو..."
        page.update()

        try:
            folder = tempfile.mkdtemp(prefix="bahmed_")

            filename = await asyncio.to_thread(
                download_video, url, folder
            )

            if not os.path.isfile(filename):
                raise Exception("لم يتم العثور على ملف الفيديو")

            status.value = "اختر مكان حفظ الفيديو"

            with open(filename, "rb") as file:
                video_data = file.read()

            saved = await ft.FilePicker().save_file(
                file_name=os.path.basename(filename),
                src_bytes=video_data,
            )

            if saved:
                status.value = "تم حفظ الفيديو بنجاح"
                history.controls.insert(
                    0,
                    ft.Text(os.path.basename(filename),
                            color="#AAB2C5"),
                )
            else:
                status.value = "تم إلغاء الحفظ"

        except Exception as error:
            status.value = "تعذر التنزيل: " + str(error)[:150]

        finally:
            download_button.disabled = False
            page.update()

    download_button = ft.Button(
        content=ft.Text("تحميل الفيديو"),
        icon=ft.Icons.DOWNLOAD,
        width=350,
        height=55,
        style=ft.ButtonStyle(
            bgcolor="#526FFF",
            color="white",
        ),
        on_click=start_download,
    )

    page.add(
        ft.Column(
            [
                ft.Text(
                    "BAHMED",
                    size=30,
                    weight="bold",
                    color="#6C8CFF",
                ),
                ft.Text(
                    "حمّل فيديوهاتك بسهولة",
                    color="#AAB2C5",
                ),
                ft.Container(height=35),
                ft.Text(
                    "تحميل فيديو",
                    size=23,
                    weight="bold",
                ),
                link,
                download_button,
                status,
                ft.Divider(height=40, color="#343D52"),
                ft.Text(
                    "التحميلات الأخيرة",
                    size=20,
                    weight="bold",
                ),
                history,
            ],
            spacing=18,
        )
    )


ft.run(main)
