"""Color themes for the live grid. Each theme is a token set; the stylesheet is built from tokens only."""
from __future__ import annotations


THEMES: dict[str, dict[str, str]] = {
    "midnight": {
        "label": "深夜藍",
        "bg": "#070a0f", "surface": "#0d121a", "surface_alt": "#101722", "header": "#0c1118",
        "border": "#1f2937", "border_strong": "#2b3a4c", "text": "#e5edf8", "muted": "#8f9bad",
        "button": "#182231", "button_hover": "#213047", "input": "#060a10",
        "accent": "#3b82f6", "accent_text": "#ffffff",
        "ok": "#22c55e", "warn": "#f59e0b", "danger": "#ef4444", "idle": "#64748b",
    },
    "oled": {
        "label": "OLED 純黑",
        "bg": "#000000", "surface": "#0a0a0a", "surface_alt": "#111111", "header": "#050505",
        "border": "#1c1c1c", "border_strong": "#2e2e2e", "text": "#f2f2f2", "muted": "#9a9a9a",
        "button": "#161616", "button_hover": "#222222", "input": "#000000",
        "accent": "#22c55e", "accent_text": "#03140a",
        "ok": "#22c55e", "warn": "#facc15", "danger": "#f87171", "idle": "#737373",
    },
    "graphite": {
        "label": "石墨灰",
        "bg": "#18181b", "surface": "#232326", "surface_alt": "#2a2a2e", "header": "#1f1f22",
        "border": "#34343a", "border_strong": "#45454d", "text": "#f4f4f5", "muted": "#a1a1aa",
        "button": "#2f2f34", "button_hover": "#3a3a41", "input": "#141416",
        "accent": "#60a5fa", "accent_text": "#0b1220",
        "ok": "#4ade80", "warn": "#fbbf24", "danger": "#f87171", "idle": "#8b8b94",
    },
    "theater": {
        "label": "劇院紫金",
        "bg": "#0f0f23", "surface": "#1b1b30", "surface_alt": "#222240", "header": "#15152a",
        "border": "#312e81", "border_strong": "#4338ca", "text": "#f8fafc", "muted": "#a5a8c8",
        "button": "#27273b", "button_hover": "#33335a", "input": "#0b0b1c",
        "accent": "#ca8a04", "accent_text": "#0f172a",
        "ok": "#4ade80", "warn": "#fbbf24", "danger": "#f87171", "idle": "#8085a8",
    },
    "light": {
        "label": "明亮",
        "bg": "#e9edf3", "surface": "#ffffff", "surface_alt": "#f6f8fb", "header": "#f3f5f9",
        "border": "#d3dae5", "border_strong": "#b9c3d2", "text": "#0f172a", "muted": "#526070",
        "button": "#ffffff", "button_hover": "#eef3fb", "input": "#ffffff",
        "accent": "#2563eb", "accent_text": "#ffffff",
        "ok": "#15803d", "warn": "#b45309", "danger": "#dc2626", "idle": "#64748b",
    },
}

DEFAULT_THEME = "midnight"


def get_theme(name: str) -> dict[str, str]:
    return THEMES.get(name) or THEMES[DEFAULT_THEME]


def build_stylesheet(t: dict[str, str]) -> str:
    return f"""
QMainWindow, QWidget#root, QWidget#mainPanel {{ background: {t['bg']}; }}
QWidget#root {{
    color: {t['text']};
    font-family: "Microsoft JhengHei UI", "Segoe UI", Arial, sans-serif;
    font-size: 13px;
}}
QFrame#topBar {{ background: {t['surface']}; border: 1px solid {t['border']}; border-radius: 8px; }}
QLabel#appTitle {{ color: {t['text']}; font-size: 16px; font-weight: 700; }}
QLabel#appMeta, QLabel#statusText, QLabel#metricLabel, QLabel#hintText {{ color: {t['muted']}; }}
QLabel#metricValue {{ color: {t['ok']}; font-weight: 700; }}
QLabel#sectionTitle {{ color: {t['muted']}; font-size: 12px; font-weight: 700; }}
QPushButton {{
    background: {t['button']}; color: {t['text']};
    border: 1px solid {t['border_strong']}; border-radius: 6px;
    padding: 5px 11px; min-height: 22px;
}}
QPushButton:hover {{ background: {t['button_hover']}; border-color: {t['accent']}; }}
QPushButton:pressed {{ background: {t['surface']}; }}
QPushButton:focus {{ border-color: {t['accent']}; }}
QPushButton:checked {{ background: {t['accent']}; color: {t['accent_text']}; border-color: {t['accent']}; }}
QPushButton:disabled {{ color: {t['idle']}; border-color: {t['border']}; }}
QPushButton#primaryButton {{ background: {t['accent']}; color: {t['accent_text']}; border-color: {t['accent']}; font-weight: 600; }}
QPushButton#dangerButton {{ color: {t['danger']}; border-color: {t['danger']}; }}
QFrame#slotFrame {{ background: #000000; border: 1px solid {t['border']}; border-radius: 6px; }}
QFrame#slotFrame[active="true"] {{ border-color: {t['border_strong']}; }}
QFrame#slotFrame[audio="true"] {{ border: 2px solid {t['accent']}; }}
QFrame#slotHeader {{ background: {t['header']}; border: 0; border-bottom: 1px solid {t['border']}; border-radius: 0; }}
QLabel#slotIndex {{ color: {t['muted']}; font-size: 12px; font-weight: 700; }}
QLabel#slotTitle {{ color: {t['text']}; font-size: 13px; font-weight: 600; }}
QLabel#statusDot {{ font-size: 13px; }}
QLabel#slotStatus {{ color: {t['muted']}; font-size: 12px; }}
QPushButton#slotButton {{ padding: 1px 7px; min-height: 18px; font-size: 12px; }}
QWidget#chromeContainer {{ background: #000000; }}
QWidget#sidebar {{ background: {t['surface']}; border-right: 1px solid {t['border']}; }}
QLabel#sidebarTitle {{ color: {t['text']}; font-size: 15px; font-weight: 700; }}
QScrollArea {{ background: transparent; border: 0; }}
QScrollArea > QWidget > QWidget {{ background: transparent; }}
QFrame#linkRow {{ background: {t['surface_alt']}; border: 1px solid {t['border']}; border-radius: 6px; }}
QLabel#rowIndex {{ background: {t['button']}; color: {t['accent']}; border-radius: 4px; padding: 3px 6px; font-weight: 700; }}
QLineEdit, QComboBox {{
    background: {t['input']}; color: {t['text']};
    border: 1px solid {t['border_strong']}; border-radius: 4px; padding: 4px 6px;
    selection-background-color: {t['accent']}; selection-color: {t['accent_text']};
}}
QLineEdit:focus, QComboBox:focus {{ border-color: {t['accent']}; }}
QComboBox QAbstractItemView {{ background: {t['surface']}; color: {t['text']}; selection-background-color: {t['accent']}; }}
QCheckBox {{ color: {t['text']}; }}
QCheckBox::indicator {{ width: 15px; height: 15px; }}
QToolTip {{ background: {t['surface']}; color: {t['text']}; border: 1px solid {t['border_strong']}; }}
"""
