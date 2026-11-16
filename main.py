import flet as ft
import yt_dlp
import threading
import os

def main(page: ft.Page):
    page.title = "محمل الفيديوهات الاحترافي"
    page.theme_mode = ft.ThemeMode.DARK
    page.rtl = True
    page.horizontal_alignment = ft.CrossAxisAlignment.CENTER
    page.vertical_alignment = ft.MainAxisAlignment.CENTER
    page.padding = 20

    header = ft.Column(
        [
            ft.Icon(ft.Icons.CLOUD_DOWNLOAD_ROUNDED, size=70, color=ft.Colors.GREEN_400),
            ft.Text("محمل السوشيال ميديا", size=24, weight=ft.FontWeight.BOLD),
            ft.Text("أدخل رابط الفيديو للتحميل المباشر إلى هاتفك", size=13, color=ft.Colors.GREY_400),
        ],
        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
    )

    url_input = ft.TextField(
        label="رابط الفيديو",
        hint_text="https://...",
        border_radius=12,
        prefix_icon=ft.Icons.LINK,
        width=350,
    )

    quality_dropdown = ft.Dropdown(
        label="اختر الجودة",
        value="hd",
        border_radius=12,
        width=350,
        options=[
            ft.dropdown.Option("hd", "جودة عالية (MP4)"),
            ft.dropdown.Option("sd", "جودة متوسطة (توفير بيانات)"),
            ft.dropdown.Option("audio", "صوت فقط (MP3)"),
        ],
    )

    progress_ring = ft.ProgressRing(visible=False, color=ft.Colors.GREEN_400)
    status_text = ft.Text("", size=14, text_align=ft.TextAlign.CENTER)

    def download_task(url, quality):
        download_path = "/storage/emulated/0/Download"
        if not os.path.exists(download_path):
            download_path = "."

        if quality == "audio":
            ydl_opts = {
                "format": "bestaudio/best",
                "outtmpl": f"{download_path}/%(title).40s.%(ext)s",
                "postprocessors": [{"key": "FFmpegExtractAudio", "preferredcodec": "mp3"}],
                "quiet": True,
            }
        elif quality == "sd":
            ydl_opts = {
                "format": "best[height<=480][ext=mp4]/best[ext=mp4]/best",
                "outtmpl": f"{download_path}/%(title).40s.%(ext)s",
                "quiet": True,
            }
        else:
            ydl_opts = {
                "format": "best[ext=mp4]/best",
                "outtmpl": f"{download_path}/%(title).40s.%(ext)s",
                "quiet": True,
            }

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([url])
            status_text.value = "✅ تم التحميل بنجاح! ستجد الملف في مجلد التنزيلات (Downloads)."
            status_text.color = ft.Colors.GREEN_400
        except Exception as e:
            status_text.value = "❌ فشل التحميل: تأكد من صحة الرابط أو اتصالك بالإنترنت."
            status_text.color = ft.Colors.RED_400
        finally:
            progress_ring.visible = False
            download_btn.disabled = False
            page.update()

    def on_download_click(e):
        url = url_input.value.strip()
        if not url:
            status_text.value = "⚠️ يرجى لصق الرابط أولاً"
            status_text.color = ft.Colors.AMBER_400
            page.update()
            return

        download_btn.disabled = True
        progress_ring.visible = True
        status_text.value = "⏳ جاري سحب الفيديو وتجهيزه..."
        status_text.color = ft.Colors.BLUE_300
        page.update()

        threading.Thread(target=download_task, args=(url, quality_dropdown.value), daemon=True).start()

    download_btn = ft.ElevatedButton(
        text="تحميل الآن",
        icon=ft.Icons.DOWNLOAD,
        style=ft.ButtonStyle(
            bgcolor=ft.Colors.GREEN_600,
            color=ft.Colors.WHITE,
            shape=ft.RoundedRectangleBorder(radius=12),
            padding=15,
        ),
        width=350,
        on_click=on_download_click,
    )

    page.add(
        header,
        ft.Divider(height=20, color=ft.Colors.TRANSPARENT),
        url_input,
        quality_dropdown,
        ft.Divider(height=10, color=ft.Colors.TRANSPARENT),
        download_btn,
        ft.Divider(height=15, color=ft.Colors.TRANSPARENT),
        progress_ring,
        status_text,
    )

ft.run(main, port=8550, host="0.0.0.0")
