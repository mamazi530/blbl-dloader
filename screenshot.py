"""开发者工具：对四个页面自动截图，便于与设计稿核对。

用法：python screenshot.py [输出目录]（默认 data/screenshots）
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication

from bilidownloader import theme
from bilidownloader.gui import MainWindow

OUT = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("data/screenshots")
OUT.mkdir(parents=True, exist_ok=True)

app = QApplication(sys.argv)
app.setStyle("Fusion")

win = MainWindow()
win.set_theme_mode(theme.THEME_LIGHT)   # 第一轮强制亮色（避免上次的暗色被持久化）
win.resize(1280, 840)
win.show()

shots = []


def snap(name):
    win.grab().save(str(OUT / f"{name}.png"))
    shots.append(name)
    print("saved", name)


def step():
    order = [
        ("home", lambda: win.navigate("home")),
        ("detail", lambda: win.navigate("detail")),
        ("settings", lambda: win.navigate("settings")),
        ("login", lambda: win.navigate("login")),
    ]
    idx = 0

    def next_page():
        nonlocal idx
        if idx < len(order):
            name, nav = order[idx]
            nav()
            idx += 1
            QTimer.singleShot(300, lambda: (snap("light-" + name), next_page()))
        else:
            # 皮肤预览一轮（亮色主题 + 内置预设）
            win.set_theme_mode(theme.THEME_LIGHT)
            win.settings.set("skin_id", "pink")
            win.apply_skin()
            idx = 0

            def next_skin():
                nonlocal idx
                if idx < len(order):
                    name, nav = order[idx]
                    if name == "settings":
                        win.view_settings.refresh_skins()
                    nav()
                    idx += 1
                    QTimer.singleShot(300, lambda: (snap("skin-" + name), next_skin()))
                else:
                    # 恢复无皮肤
                    win.settings.set("skin_id", "")
                    win.apply_skin()
                    # 暗色主题再来一轮
                    win.set_theme_mode(theme.THEME_DARK)
                    idx = 0

                    def next_dark():
                        nonlocal idx
                        if idx < len(order):
                            name, nav = order[idx]
                            nav()
                            idx += 1
                            QTimer.singleShot(300, lambda: (snap("dark-" + name), next_dark()))
                        else:
                            win.view_login.stop_worker()
                            app.quit()

                    next_dark()

            next_skin()

    next_page()


QTimer.singleShot(900, step)
app.exec()
print(f"\n{len(shots)} screenshots -> {OUT.resolve()}")
