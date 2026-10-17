"""
主题系统
设计令牌与《B站下载器 · 设计资产包》theme-tokens.css 对齐：
语义化命名、亮/暗双主题、跟随系统自动切换。
所有颜色集中在此定义，界面代码不写死颜色值。
"""

from dataclasses import dataclass, replace


# 会被"半透明化"的字段（表面/背景/描边类）
# 文字类字段保持不变，避免自定义皮肤背景时文字对比度不足
_ALPHA_FIELDS = (
    "bg", "bg_sidebar", "surface", "bg_subtle", "bg_footer",
    "bg_input", "bg_control", "overlay",
    "border_card", "border", "border_hi", "border_divider", "border_progress",
)


def _rgba(color: str, alpha: float) -> str:
    """#RRGGBB → rgba(r,g,b,alpha)；已经是 rgba 的原样返回"""
    c = (color or "").strip()
    if c.startswith("#") and len(c) == 7:
        try:
            r, g, b = int(c[1:3], 16), int(c[3:5], 16), int(c[5:7], 16)
        except ValueError:
            return c
        return f"rgba({r}, {g}, {b}, {alpha:.3f})"
    if c.startswith("#") and len(c) == 4:
        try:
            r, g, b = (int(ch * 2, 16) for ch in c[1:4])
        except ValueError:
            return c
        return f"rgba({r}, {g}, {b}, {alpha:.3f})"
    return c


@dataclass(frozen=True)
class Palette:
    """一套完整的设计令牌（与 design-assets/tokens/theme-tokens.css 同源）"""

    name: str
    is_dark: bool

    # ---------- 表面 / 背景 ----------
    bg: str              # --bg-window  内容区背景
    bg_sidebar: str      # --bg-sidebar 侧边栏、标题栏
    surface: str         # --bg-card    卡片、任务行
    bg_subtle: str       # --bg-subtle  选项卡、操作栏底
    bg_footer: str       # --bg-footer  底部汇总栏
    bg_input: str        # --bg-input   输入框、图标按钮底
    bg_control: str      # --bg-control 次要按钮、chip、分隔
    overlay: str         # 悬浮菜单

    # ---------- 描边 ----------
    border_card: str     # --border-card
    border: str          # --border-strong 输入框、按钮描边
    border_hi: str       # 悬停/更强描边（= border-strong 深一档）
    border_divider: str  # --border-divider
    border_progress: str # --border-progress

    # ---------- 文字 ----------
    text: str            # --text-primary
    text_secondary: str  # --text-secondary
    text_dim: str        # --text-regular
    text_muted: str      # --text-muted
    text_faint: str      # --text-faint
    text_icon: str       # --text-icon SVG stroke
    text_on_accent: str  # --text-on-accent

    # ---------- 品牌 ----------
    accent: str          # --accent B站粉
    accent_hover: str
    accent_pressed: str
    accent_soft: str     # --accent-soft 选中导航底、chip底
    accent_text: str     # --accent-text 浅色底上的粉字

    # ---------- 状态 ----------
    success: str
    success_soft: str
    success_text: str
    warning: str
    warning_soft: str
    warning_text: str
    info: str
    info_soft: str
    info_text: str
    danger: str
    danger_soft: str
    danger_text: str

    # 特殊：二维码底板（两种模式都是白色）
    qr_bg: str = "#ffffff"
    shadow: str = "rgba(0,0,0,0.06)"

    def with_alpha(self, alpha: float) -> "Palette":
        """
        返回"半透明化"的调色板副本：表面/背景/描边类字段加上 alpha，
        文字与品牌色不变。用于自定义皮肤背景时让壁纸透出来。

        alpha=1.0 返回自身（不做任何换算）。
        """
        a = max(0.05, min(1.0, float(alpha)))
        if a >= 0.995:
            return self
        return replace(self, **{f: _rgba(getattr(self, f), a) for f in _ALPHA_FIELDS})


DARK = Palette(
    name="暗色",
    is_dark=True,
    bg="#1C1D21",
    bg_sidebar="#17181C",
    surface="#1C1D21",
    bg_subtle="#232429",
    bg_footer="#191A1E",
    bg_input="#2A2C32",
    bg_control="#2A2C32",
    overlay="#26272C",
    border_card="#2E3137",
    border="#363A41",
    border_hi="#454954",
    border_divider="#2E3137",
    border_progress="#303338",
    text="#E9EBEE",
    text_secondary="#C3C9D2",
    text_dim="#98A1B0",
    text_muted="#8F97A5",
    text_faint="#7C8493",
    text_icon="#99A2AF",
    text_on_accent="#ffffff",
    accent="#FB7299",
    accent_hover="#FF8FAD",
    accent_pressed="#E0598A",
    accent_soft="#3D2530",
    accent_text="#FF8FAD",
    success="#17B26A",
    success_soft="#1E3429",
    success_text="#55D6A6",
    warning="#FDBA74",
    warning_soft="#3A2A17",
    warning_text="#FDBA74",
    info="#89B0FF",
    info_soft="#1F2A45",
    info_text="#89B0FF",
    danger="#F97066",
    danger_soft="#3D2523",
    danger_text="#FF8F85",
    shadow="rgba(0,0,0,0.55)",
)

LIGHT = Palette(
    name="亮色",
    is_dark=False,
    bg="#FFFFFF",
    bg_sidebar="#F7F8FA",
    surface="#FFFFFF",
    bg_subtle="#FAFBFC",
    bg_footer="#FCFCFD",
    bg_input="#F5F6F8",
    bg_control="#F2F4F7",
    overlay="#FFFFFF",
    border_card="#EDF0F3",
    border="#E4E7EC",
    border_hi="#D0D3D9",
    border_divider="#F2F4F7",
    border_progress="#EEF0F3",
    text="#16171A",
    text_secondary="#3D434B",
    text_dim="#6E7480",
    text_muted="#8A9099",
    text_faint="#A0A6AE",
    text_icon="#5A6068",
    text_on_accent="#ffffff",
    accent="#FB7299",
    accent_hover="#F2648E",
    accent_pressed="#DC5580",
    accent_soft="#FDEEF3",
    accent_text="#E0456F",
    success="#17B26A",
    success_soft="#E7F6EF",
    success_text="#12805C",
    warning="#F79042",
    warning_soft="#FFF4E5",
    warning_text="#B54708",
    info="#1C56C4",
    info_soft="#E8F0FE",
    info_text="#1C56C4",
    danger="#F97066",
    danger_soft="#FDECEC",
    danger_text="#D0342C",
    shadow="rgba(0,0,0,0.08)",
)

THEME_AUTO, THEME_LIGHT, THEME_DARK = "auto", "light", "dark"

LABELS = {
    THEME_AUTO: "跟随系统",
    THEME_LIGHT: "亮色",
    THEME_DARK: "暗色",
}


def resolve(mode: str, system_is_dark: bool) -> Palette:
    """把用户选择解析为具体调色板"""
    if mode == THEME_LIGHT:
        return LIGHT
    if mode == THEME_DARK:
        return DARK
    return DARK if system_is_dark else LIGHT


def stylesheet(p: Palette) -> str:
    """生成全局样式表（通用控件；页面专属样式在各视图内）"""
    return f"""
QWidget {{
    background:{p.bg};
    color:{p.text};
    font-family:"Microsoft YaHei UI","Segoe UI","PingFang SC",sans-serif;
    font-size:13px;
}}
QMainWindow, QDialog {{ background:{p.bg}; }}

/* ---------- 标签 ----------
   QLabel 继承自 QFrame，必须显式清除边框，
   否则 Fusion 主题会画出默认的输入框边框 */
QLabel {{
    background:transparent;
    border:none;
    padding:0;
    color:{p.text};
}}
QLabel#hint {{ color:{p.text_faint}; font-size:12px; }}
QLabel#dim {{ color:{p.text_dim}; font-size:12px; }}
QLabel#faint {{ color:{p.text_faint}; font-size:11px; }}
QLabel#info {{ color:{p.info_text}; font-size:12px; }}
QLabel#warn {{ color:{p.warning_text}; font-size:12px; }}
QLabel#error {{ color:{p.danger_text}; font-size:12px; }}
QLabel#ok {{ color:{p.success_text}; font-size:12px; }}

/* ---------- 菜单 ---------- */
QMenuBar {{ background:{p.bg_sidebar}; color:{p.text_dim}; font-size:12px; }}
QMenuBar::item {{ background:transparent; padding:5px 11px; border-radius:5px; }}
QMenuBar::item:selected {{ background:{p.bg_control}; color:{p.text}; }}
QMenu {{
    background:{p.overlay}; border:1px solid {p.border_card};
    border-radius:8px; padding:5px;
}}
QMenu::item {{ padding:6px 24px 6px 14px; border-radius:5px; color:{p.text}; }}
QMenu::item:selected {{ background:{p.bg_control}; }}
QMenu::separator {{ height:1px; background:{p.border_divider}; margin:4px 8px; }}

/* ---------- 输入框 ---------- */
QLineEdit {{
    background:{p.bg_input};
    border:1px solid {p.border};
    border-radius:8px;
    padding:8px 12px;
    color:{p.text};
    font-size:13px;
    selection-background-color:{p.accent};
    selection-color:{p.text_on_accent};
}}
QLineEdit:focus {{ border-color:{p.accent}; background:{p.surface}; }}
QLineEdit::placeholder {{ color:{p.text_faint}; }}
QLineEdit:disabled {{ background:{p.bg_subtle}; color:{p.text_faint}; }}

/* ---------- 下拉框 ---------- */
QComboBox {{
    background:{p.bg_input}; border:1px solid {p.border};
    border-radius:7px; padding:6px 10px; color:{p.text}; font-size:12px;
}}
QComboBox:hover {{ border-color:{p.border_hi}; }}
QComboBox:focus {{ border-color:{p.accent}; }}
QComboBox::drop-down {{ border:none; width:18px; }}
QComboBox QAbstractItemView {{
    background:{p.overlay}; border:1px solid {p.border_card};
    border-radius:8px; padding:4px; color:{p.text};
    selection-background-color:{p.accent_soft}; selection-color:{p.accent_text};
    outline:none;
}}

/* ---------- 按钮 ---------- */
QPushButton {{
    background:{p.bg_input}; border:1px solid {p.border};
    border-radius:7px; padding:6px 14px; color:{p.text_secondary}; font-size:12px;
}}
QPushButton:hover {{ background:{p.bg_control}; border-color:{p.border_hi}; }}
QPushButton:pressed {{ background:{p.bg_control}; }}
QPushButton:disabled {{ background:{p.bg_subtle}; color:{p.text_faint}; border-color:{p.border_divider}; }}

QPushButton#primary {{
    background:{p.accent}; border:none; color:{p.text_on_accent};
    border-radius:8px; padding:9px 20px; font-weight:600; font-size:13px;
}}
QPushButton#primary:hover:!disabled {{ background:{p.accent_hover}; }}
QPushButton#primary:pressed:!disabled {{ background:{p.accent_pressed}; }}
QPushButton#primary:disabled {{ background:{p.border_card}; color:{p.text_faint}; }}

QPushButton#ghost {{
    background:transparent; border:none; color:{p.text_dim};
    border-radius:6px; padding:6px 11px; font-size:12px;
}}
QPushButton#ghost:hover {{ background:{p.bg_control}; color:{p.text}; }}
QPushButton#ghost:disabled {{ color:{p.text_faint}; }}

QPushButton#outline {{
    background:{p.surface}; border:1px solid {p.border};
    border-radius:8px; padding:8px 16px; color:{p.text_secondary}; font-size:12px;
}}
QPushButton#outline:hover {{ background:{p.bg_subtle}; border-color:{p.border_hi}; }}
QPushButton#outline:disabled {{ color:{p.text_faint}; border-color:{p.border_divider}; }}

/* ---------- 勾选框 ---------- */
QCheckBox {{ color:{p.text_dim}; font-size:12px; spacing:7px; background:transparent; }}
QCheckBox::indicator {{
    width:15px; height:15px; border-radius:4px;
    border:1.5px solid {p.border_hi}; background:{p.bg_input};
}}
QCheckBox::indicator:hover {{ border-color:{p.accent}; }}
QCheckBox::indicator:checked {{ background:{p.accent}; border-color:{p.accent}; }}

/* ---------- 滚动区域 ---------- */
QScrollArea {{ background:transparent; border:none; }}
QScrollArea > QWidget > QWidget {{ background:transparent; }}

/* ---------- 进度条（默认样式；任务行内会按状态覆盖） ---------- */
QProgressBar {{
    background:{p.border_progress}; border:none; border-radius:3px;
    color:transparent;
}}
QProgressBar::chunk {{ background:{p.accent}; border-radius:3px; }}

/* ---------- 文本域 ---------- */
QTextEdit {{
    background:{p.bg}; border:1px solid {p.border_card}; border-radius:8px;
    padding:9px; color:{p.text_dim};
    font-family:Consolas,"Cascadia Mono",monospace; font-size:11px;
    selection-background-color:{p.accent}; selection-color:{p.text_on_accent};
}}

/* ---------- 滚动条 ---------- */
QScrollBar:vertical {{ background:transparent; width:10px; margin:2px; }}
QScrollBar::handle:vertical {{ background:{p.border_hi}; border-radius:5px; min-height:30px; }}
QScrollBar::handle:vertical:hover {{ background:{p.text_faint}; }}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height:0; }}
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{ background:transparent; }}
QScrollBar:horizontal {{ background:transparent; height:10px; margin:2px; }}
QScrollBar::handle:horizontal {{ background:{p.border_hi}; border-radius:5px; min-width:30px; }}
QScrollBar::handle:horizontal:hover {{ background:{p.text_faint}; }}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{ width:0; }}

/* ---------- 滑块（皮肤设置） ---------- */
QSlider {{ background:transparent; }}
QSlider::groove:horizontal {{
    background:{p.border_progress}; height:4px; border-radius:2px;
}}
QSlider::sub-page:horizontal {{ background:{p.accent}; border-radius:2px; }}
QSlider::add-page:horizontal {{ background:{p.border_progress}; border-radius:2px; }}
QSlider::handle:horizontal {{
    background:{p.accent}; width:14px; height:14px; margin:-5px 0;
    border-radius:7px; border:none;
}}
QSlider::handle:horizontal:hover {{ background:{p.accent_hover}; }}

/* ---------- 提示 ---------- */
QToolTip {{
    background:{p.overlay}; color:{p.text};
    border:1px solid {p.border_card}; border-radius:6px; padding:5px 8px; font-size:12px;
}}
"""
