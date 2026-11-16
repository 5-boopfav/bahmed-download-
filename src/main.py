import flet as ft

def main(page: ft.Page):
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

    def paste(e):
        page.set_clipboard(link.value or "")

    page.add(
        ft.Column(
            [
                ft.Text("BAHMED", size=30, weight="bold", color="#6C8CFF"),
                ft.Text("حمّل فيديوهاتك بسهولة", color="#AAB2C5"),
                ft.Container(height=35),
                ft.Text("تحميل فيديو", size=23, weight="bold"),
                link,
                ft.Button(
                    "تحميل الفيديو",
                    icon=ft.Icons.DOWNLOAD,
                    width=350,
                    height=55,
                    bgcolor="#526FFF",
                    color="white",
                ),
                ft.Divider(height=40, color="#343D52"),
                ft.Text("التحميلات الأخيرة", size=20, weight="bold"),
                ft.Text("لا توجد تحميلات حتى الآن", color="#8993A8"),
            ],
            spacing=18,
        )
    )

ft.run(main)







