import sys
import os
import re
import shutil
import subprocess
import webbrowser
import requests
import math
import urllib.parse
import hashlib
import tempfile
from datetime import datetime, timedelta, timezone

from PyQt6 import sip
from PyQt6.QtCore import (
    Qt, QThread, pyqtSignal, QSettings, QTimer, QDate, 
    QRunnable, QThreadPool, QObject, QPointF
)
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
    QGridLayout, QLabel, QPushButton, QScrollArea, QFrame, QMessageBox, 
    QComboBox, QMenu, QDialog, QDialogButtonBox, QCalendarWidget
)
from PyQt6.QtGui import (
    QFont, QPixmap, QCursor, QPainter, QColor, QPen, QBrush, 
    QPainterPath, QLinearGradient, QIcon, QAction
)

if sys.platform == "win32":
    import ctypes
    try:
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("pcjake22.hlh.desktop.main")
    except Exception:
        pass

CURRENT_VERSION = "v1.2.0"
GITHUB_REPO = "pcjake22/hlh"
API_BASE = "https://matchora.to/api/v1"
ESPN_NCAA_API = "https://site.api.espn.com/apis/site/v2/sports/hockey/mens-college-hockey/scoreboard"

CACHE_DIR = os.path.join(tempfile.gettempdir(), "hlh_logo_cache")
try:
    os.makedirs(CACHE_DIR, exist_ok=True)
except Exception:
    pass

MEMORY_CACHE = {}

TIMEZONE_OFFSETS = {
    "Local System Time": None,
    "US Eastern (ET - UTC-4/5)": -5,
    "US Central (CT - UTC-5/6)": -6,
    "US Mountain (MT - UTC-6/7)": -7,
    "US Pacific (PT - UTC-7/8)": -8,
    "Alaska (AKT - UTC-8/9)": -9,
    "Hawaii (HST - UTC-10)": -10,
    "UTC / GMT": 0,
    "Central European (CET - UTC+1/2)": 1
}

NHL_FRANCHISES = {
    "ana": "Anaheim Ducks", "bos": "Boston Bruins", "buf": "Buffalo Sabres",
    "car": "Carolina Hurricanes", "cbj": "Columbus Blue Jackets", "cgy": "Calgary Flames",
    "chi": "Chicago Blackhawks", "col": "Colorado Avalanche", "dal": "Dallas Stars",
    "det": "Detroit Red Wings", "edm": "Edmonton Oilers", "fla": "Florida Panthers",
    "la": "Los Angeles Kings", "lak": "Los Angeles Kings", "min": "Minnesota Wild",
    "mtl": "Montreal Canadiens", "njd": "New Jersey Devils", "nj": "New Jersey Devils",
    "nsh": "Nashville Predators", "nyi": "New York Islanders", "nyr": "New York Rangers",
    "ott": "Ottawa Senators", "phi": "Philadelphia Flyers", "pit": "Pittsburgh Penguins",
    "sea": "Seattle Kraken", "sjs": "San Jose Sharks", "sj": "San Jose Sharks",
    "stl": "St. Louis Blues", "tbl": "Tampa Bay Lightning", "tb": "Tampa Bay Lightning",
    "tor": "Toronto Maple Leafs", "uta": "Utah Hockey Club", "van": "Vancouver Canucks",
    "vgk": "Vegas Golden Knights", "wpg": "Winnipeg Jets", "wsh": "Washington Capitals"
}

ESPN_LOGO_OVERRIDES = {
    "uta": "utah", "mtl": "mon", "cbj": "clb", "njd": "nj", "nj": "nj",
    "tbl": "tb", "tb": "tb", "la": "la", "lak": "la", "sjs": "sj", "sj": "sj",
    "wsh": "was", "cgy": "cgy", "vgk": "vgs", "wpg": "wpg"
}

LEAGUE_BRANDING = {
    "NHL": {
        "badge_text": "NHL",
        "color": "#10B981",
        "full_name": "NATIONAL HOCKEY LEAGUE"
    },
    "NCAA Men's D1": {
        "badge_text": "NCAA",
        "color": "#F59E0B",
        "full_name": "NCAA MEN'S DIVISION I HOCKEY"
    },
    "AHL": {
        "badge_text": "AHL",
        "color": "#38BDF8",
        "full_name": "AMERICAN HOCKEY LEAGUE"
    },
    "ECHL": {
        "badge_text": "ECHL",
        "color": "#EF4444",
        "full_name": "ECHL PROFESSIONAL HOCKEY"
    },
    "SPHL": {
        "badge_text": "SPHL",
        "color": "#A855F7",
        "full_name": "SOUTHERN PROFESSIONAL HOCKEY LEAGUE"
    },
    "QMJHL": {
        "badge_text": "QMJHL",
        "color": "#EC4899",
        "full_name": "QUEBEC MARITIMES JUNIOR HOCKEY LEAGUE"
    },
    "OHL / WHL Juniors": {
        "badge_text": "CHL",
        "color": "#06B6D4",
        "full_name": "CANADIAN HOCKEY LEAGUE (OHL / WHL)"
    },
    "Swedish SHL": {
        "badge_text": "SHL",
        "color": "#FACC15",
        "full_name": "SWEDISH HOCKEY LEAGUE (SHL)"
    },
    "Finnish Liiga": {
        "badge_text": "LIIGA",
        "color": "#60A5FA",
        "full_name": "FINNISH LIIGA"
    },
    "Swiss NL": {
        "badge_text": "NL",
        "color": "#F43F5E",
        "full_name": "SWISS NATIONAL LEAGUE"
    },
    "Other Hockey": {
        "badge_text": "HOCKEY",
        "color": "#94A3B8",
        "full_name": "OTHER HOCKEY COMPETITIONS"
    }
}

LEAGUE_CATEGORIES = [
    "All Hockey", "NHL", "NCAA Men's D1 Hockey", "AHL", "ECHL", "SPHL",
    "QMJHL", "OHL / WHL Juniors", "Swedish Hockey League (SHL)",
    "Finnish Liiga", "Swiss National League (NL)"
]

LEAGUE_PRIORITY = {
    "NHL": 1, "NCAA Men's D1": 2, "AHL": 3, "ECHL": 4, "SPHL": 5,
    "QMJHL": 6, "OHL / WHL Juniors": 7, "Swedish SHL": 8, "Finnish Liiga": 9,
    "Swiss NL": 10, "Other Hockey": 99
}

STYLESHEET = """
QMainWindow { background-color: #05070a; }
QWidget#CentralWidget { background-color: #05070a; }
QScrollArea { border: none; background: transparent; }
QScrollBar:vertical {
    border: none; background: #090c12; width: 6px; margin: 0px; border-radius: 3px;
}
QScrollBar::handle:vertical { background: #192130; min-height: 25px; border-radius: 3px; }
QScrollBar::handle:vertical:hover { background: #10B981; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0px; }

QComboBox {
    background-color: #0d121c; color: #F1F5F9; padding: 7px 14px;
    border: 1px solid #1a2336; border-radius: 6px; font-weight: 700; font-size: 12px;
}
QComboBox:hover { border: 1px solid #10B981; }
QComboBox QAbstractItemView {
    background-color: #0d121c; color: #F1F5F9; selection-background-color: #10B981;
    selection-color: #05070a; border: 1px solid #1a2336; padding: 4px; outline: 0px;
}

QPushButton#NavBtn {
    background-color: #0f1624; color: #E2E8F0; font-weight: 700; font-size: 11px;
    padding: 6px 12px; border-radius: 6px; border: 1px solid #1d2b42;
}
QPushButton#NavBtn:hover { background-color: #172338; border-color: #10B981; color: #10B981; }

QPushButton#DateBtn {
    background-color: #0d121c; color: #10B981; font-weight: 800; font-size: 12px;
    padding: 6px 14px; border-radius: 6px; border: 1px solid #1a2336;
}
QPushButton#DateBtn:hover { background-color: #121927; border-color: #10B981; }

QMenu {
    background-color: #0d121c; color: #F1F5F9;
    border: 1px solid #232d42; border-radius: 6px; padding: 4px;
}
QMenu::item { padding: 8px 18px; border-radius: 4px; font-size: 12px; font-weight: 600; }
QMenu::item:selected { background-color: #10B981; color: #05070a; }

QCalendarWidget QWidget#qt_calendar_navigationbar { background-color: #0b0f17; }
QCalendarWidget QToolButton {
    color: #f8fafc; font-weight: bold; background-color: transparent; border: none; padding: 4px;
}
QCalendarWidget QToolButton:hover { background-color: #162030; border-radius: 4px; }
QCalendarWidget QMenu { background-color: #0b0f17; color: #fff; }
QCalendarWidget QSpinBox { background-color: #0b0f17; color: #fff; border: 1px solid #222d40; }
QCalendarWidget QAbstractItemView:enabled {
    background-color: #07090e; color: #e2e8f0; selection-background-color: #10B981;
    selection-color: #05070a; outline: none;
}
QCalendarWidget QAbstractItemView:disabled { color: #475569; }
"""


def clean_team_name(name):
    return re.sub(r'[^a-zA-Z0-9]', '', str(name or "")).lower()


def get_cache_filename(url):
    url_hash = hashlib.md5(str(url).encode("utf-8")).hexdigest()
    return os.path.join(CACHE_DIR, f"{url_hash}.png")


class ImageTaskSignals(QObject):
    done = pyqtSignal(str, bytes)


class ImageFetchTask(QRunnable):
    def __init__(self, url):
        super().__init__()
        self.url = url
        self.signals = ImageTaskSignals()

    def run(self):
        try:
            cache_path = get_cache_filename(self.url)
            if os.path.exists(cache_path):
                with open(cache_path, "rb") as f:
                    self.signals.done.emit(self.url, f.read())
                    return

            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "Accept": "image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8",
                "Referer": "https://www.google.com/"
            }
            resp = requests.get(self.url, headers=headers, timeout=3.5)
            if resp.status_code == 200 and resp.content:
                try:
                    with open(cache_path, "wb") as f:
                        f.write(resp.content)
                except Exception:
                    pass
                self.signals.done.emit(self.url, resp.content)
        except Exception:
            pass


class SafeAsyncLogoLabel(QLabel):
    def __init__(self, size=40, parent=None):
        super().__init__(parent)
        self.size = size
        self.setFixedSize(size, size)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setStyleSheet("background: transparent; border: none;")

    def load_image(self, url, fallback_text="🏒"):
        if not url:
            self.setText(fallback_text)
            return

        if str(url).startswith("//"):
            url = "https:" + url
        elif str(url).startswith("/"):
            url = "https://matchora.to" + url

        if url in MEMORY_CACHE:
            self.setPixmap(MEMORY_CACHE[url])
            return

        cache_path = get_cache_filename(url)
        if os.path.exists(cache_path):
            pixmap = QPixmap(cache_path)
            if not pixmap.isNull():
                scaled = pixmap.scaled(
                    self.size, self.size,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation
                )
                MEMORY_CACHE[url] = scaled
                self.setPixmap(scaled)
                return

        self.setText(fallback_text)
        task = ImageFetchTask(url)
        task.signals.done.connect(self._on_bytes_received)
        pool = QThreadPool.globalInstance()
        if pool:
            pool.start(task)

    def _on_bytes_received(self, url, raw_bytes):
        if sip.isdeleted(self):
            return

        pixmap = QPixmap()
        if pixmap.loadFromData(raw_bytes):
            scaled = pixmap.scaled(
                self.size, self.size,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation
            )
            MEMORY_CACHE[url] = scaled
            self.setPixmap(scaled)


class LeagueShieldBadge(QWidget):
    def __init__(self, text, accent_color, parent=None):
        super().__init__(parent)
        self.text = text
        self.accent_color = QColor(accent_color)
        self.setFixedSize(48, 28)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        path = QPainterPath()
        path.addRoundedRect(1, 1, self.width() - 2, self.height() - 2, 6, 6)
        painter.fillPath(path, QBrush(QColor("#131a26")))

        pen = QPen(self.accent_color, 1.5)
        painter.setPen(pen)
        painter.drawPath(path)

        painter.setPen(QColor("#FFFFFF"))
        painter.setFont(QFont("Impact" if sys.platform == "win32" else "Arial Black", 10))
        painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, self.text)


class MomentumWaveWidget(QWidget):
    def __init__(self, game, parent=None):
        super().__init__(parent)
        self.game = game or {}
        self.setFixedHeight(85)

    def paintEvent(self, event):
        try:
            w = self.width()
            h = self.height()
            if w < 50 or h < 30:
                return

            painter = QPainter(self)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)

            mid_y = h / 2.0
            left_m = 20.0
            right_m = 15.0
            chart_w = max(10.0, float(w - left_m - right_m))

            pen_base = QPen(QColor("#242d3d"), 1)
            painter.setPen(pen_base)
            painter.drawLine(int(left_m), int(mid_y), int(w - right_m), int(mid_y))

            p1_x = left_m + chart_w * 0.33
            p2_x = left_m + chart_w * 0.66

            pen_dash = QPen(QColor("#1f2838"), 1, Qt.PenStyle.DashLine)
            painter.setPen(pen_dash)
            painter.drawLine(int(p1_x), 6, int(p1_x), int(h - 12))
            painter.drawLine(int(p2_x), 6, int(p2_x), int(h - 12))

            raw_away = str(self.game.get("away_score") or "0").strip()
            raw_home = str(self.game.get("home_score") or "0").strip()
            try:
                a_s = int(re.sub(r'[^0-9]', '', raw_away) or 0)
            except Exception:
                a_s = 0
            try:
                h_s = int(re.sub(r'[^0-9]', '', raw_home) or 0)
            except Exception:
                h_s = 0

            is_live = bool(self.game.get("is_live", False))
            is_final = bool(self.game.get("is_final", False))
            has_score = (a_s > 0 or h_s > 0 or is_live or is_final)

            if not has_score:
                pen_flat = QPen(QColor("#334155"), 1.5)
                painter.setPen(pen_flat)
                painter.drawLine(int(left_m), int(mid_y), int(w - right_m), int(mid_y))
                painter.setFont(QFont("Segoe UI", 8, QFont.Weight.Medium))
                painter.setPen(QColor("#64748B"))
                painter.drawText(int(left_m + chart_w * 0.35), int(mid_y - 4), "Match Scheduled")
                return

            game_progress = 0.65 if is_live else 1.0
            active_w = chart_w * game_progress
            points = []
            step_x = 12.0
            curr_x = left_m
            t = 0.0

            seed_val = str(self.game.get("id") or self.game.get("home") or "hockey")
            seed = abs(hash(seed_val)) % 100
            bias = (a_s - h_s) * 4.0

            while curr_x <= (left_m + active_w):
                wave1 = math.sin(t * 0.5 + seed) * 12.0
                wave2 = math.cos(t * 0.9 + seed) * 7.0
                wave3 = math.sin(t * 1.8) * 3.0
                y_offset = (wave1 + wave2 + wave3) + bias
                y_clamped = max(-26.0, min(26.0, y_offset))
                points.append(QPointF(float(curr_x), float(mid_y - y_clamped)))
                t += 0.8
                curr_x += step_x

            if len(points) >= 2:
                curve_path = QPainterPath()
                curve_path.moveTo(points[0])
                for i in range(len(points) - 1):
                    p0 = points[i]
                    p1 = points[i + 1]
                    c1 = QPointF((p0.x() + p1.x()) / 2.0, p0.y())
                    c2 = QPointF((p0.x() + p1.x()) / 2.0, p1.y())
                    curve_path.cubicTo(c1, c2, p1)

                fill_path = QPainterPath(curve_path)
                fill_path.lineTo(points[-1].x(), mid_y)
                fill_path.lineTo(points[0].x(), mid_y)
                fill_path.closeSubpath()

                grad = QLinearGradient(0, 10, 0, h - 20)
                grad.setColorAt(0.0, QColor(16, 185, 129, 130))
                grad.setColorAt(0.5, QColor(6, 78, 59, 60))
                grad.setColorAt(1.0, QColor(16, 185, 129, 130))
                painter.fillPath(fill_path, QBrush(grad))

                pen_wave = QPen(QColor("#E2E8F0"), 1.4)
                painter.setPen(pen_wave)
                painter.drawPath(curve_path)
        except Exception:
            pass


class InlineGamecastDrawer(QFrame):
    def __init__(self, game, parent=None):
        super().__init__(parent)
        self.game = game or {}
        self.setObjectName("InlineDrawer")
        self.setStyleSheet("""
            QFrame#InlineDrawer {
                background-color: #070a10;
                border: 1px solid #141c2b;
                border-radius: 6px;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(6)

        top_row = QHBoxLayout()
        lbl_title = QLabel("TELEMETRY & MOMENTUM")
        lbl_title.setFont(QFont("Segoe UI", 8, QFont.Weight.Bold))
        lbl_title.setStyleSheet("color: #10B981; letter-spacing: 1px;")
        top_row.addWidget(lbl_title)
        top_row.addStretch()

        is_live = bool(self.game.get("is_live", False))
        is_final = bool(self.game.get("is_final", False))
        status_txt = f"● LIVE - {self.game.get('status', 'LIVE')}" if is_live else ("FINAL" if is_final else "SCHEDULED")

        lbl_status = QLabel(status_txt)
        lbl_status.setFont(QFont("Segoe UI", 7, QFont.Weight.Bold))
        lbl_status.setStyleSheet("color: #34d399;" if is_live else "color: #94a3b8;")
        top_row.addWidget(lbl_status)
        layout.addLayout(top_row)

        stats_frame = QFrame()
        stats_frame.setStyleSheet("background: #0a0f18; border: 1px solid #162030; border-radius: 4px; padding: 4px;")
        stats_layout = QHBoxLayout(stats_frame)
        stats_layout.setContentsMargins(8, 4, 8, 4)

        raw_a = str(self.game.get("away_score") or "0").strip()
        raw_h = str(self.game.get("home_score") or "0").strip()

        away_box = QVBoxLayout()
        away_box.addWidget(QLabel(f"<span style='color:#F8FAFC; font-size:10px; font-weight:bold;'>{self.game.get('away', 'Away')}</span>"), alignment=Qt.AlignmentFlag.AlignLeft)
        away_box.addWidget(QLabel(f"<span style='font-size:13px; font-weight:bold; color:#10B981;'>{raw_a}</span> <span style='color:#64748B; font-size:9px;'>G</span>"), alignment=Qt.AlignmentFlag.AlignLeft)
        stats_layout.addLayout(away_box)

        mid_box = QVBoxLayout()
        mid_box.setAlignment(Qt.AlignmentFlag.AlignCenter)
        mid_box.addWidget(QLabel("<span style='color:#64748B; font-size:8px; font-weight:bold;'>LEAGUE</span>"), alignment=Qt.AlignmentFlag.AlignCenter)
        mid_box.addWidget(QLabel(f"<span style='color:#38BDF8; font-size:9px; font-weight:bold;'>{self.game.get('league', 'Hockey')}</span>"), alignment=Qt.AlignmentFlag.AlignCenter)
        stats_layout.addLayout(mid_box)

        home_box = QVBoxLayout()
        home_box.addWidget(QLabel(f"<span style='color:#F8FAFC; font-size:10px; font-weight:bold;'>{self.game.get('home', 'Home')}</span>"), alignment=Qt.AlignmentFlag.AlignRight)
        home_box.addWidget(QLabel(f"<span style='font-size:13px; font-weight:bold; color:#10B981;'>{raw_h}</span> <span style='color:#64748B; font-size:9px;'>G</span>"), alignment=Qt.AlignmentFlag.AlignRight)
        stats_layout.addLayout(home_box)

        layout.addWidget(stats_frame)
        layout.addWidget(MomentumWaveWidget(self.game))


class GridGameCard(QFrame):
    def __init__(self, game, is_past_date=False, parent=None):
        super().__init__(parent)
        self.game = game or {}
        self.is_past_date = is_past_date
        self.setObjectName("GridGameCard")

        self.league_name = str(self.game.get("league", "")).strip()
        self.has_gamecast = self.league_name in ["NHL", "NCAA Men's D1"]

        self.setStyleSheet("""
            QFrame#GridGameCard {
                background-color: #0b0f17;
                border: 1px solid #1a2233;
                border-top: 2px solid #10B981;
                border-radius: 8px;
            }
            QFrame#GridGameCard:hover {
                border-color: #2b3952;
                background-color: #0e1420;
            }
        """)

        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(14, 12, 14, 10)
        self.main_layout.setSpacing(10)

        # 1. Status Pill & League Tag
        top_row = QHBoxLayout()
        is_final = self.game.get("is_final", False) or (self.game.get("status") == "FINAL")
        lbl_status = QLabel(f"● {self.game.get('status')}" if self.game.get("is_live") else self.game.get("status", "Scheduled"))
        lbl_status.setFont(QFont("Segoe UI", 8, QFont.Weight.Bold))

        if self.game.get("is_live"):
            lbl_status.setStyleSheet("color: #34d399; background: #064e3b; padding: 2px 8px; border-radius: 6px;")
        elif is_final:
            lbl_status.setStyleSheet("color: #94a3b8; background: #1e293b; padding: 2px 8px; border-radius: 6px;")
        else:
            lbl_status.setStyleSheet("color: #64748b; background: #131a27; padding: 2px 8px; border-radius: 6px;")
        top_row.addWidget(lbl_status)
        top_row.addStretch()

        lbl_league = QLabel(self.league_name or "Hockey")
        lbl_league.setFont(QFont("Segoe UI", 7, QFont.Weight.Bold))
        lbl_league.setStyleSheet("color: #475569; letter-spacing: 0.5px;")
        top_row.addWidget(lbl_league)
        self.main_layout.addLayout(top_row)

        # 2. Team Badges & Centered Score
        match_row = QHBoxLayout()
        match_row.setSpacing(10)

        away_box = QVBoxLayout()
        away_box.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.away_logo = SafeAsyncLogoLabel(40)
        self.away_logo.load_image(self.game.get("away_logo"), fallback_text=self.game.get("away", "A")[:3].upper())
        lbl_away = QLabel(self.game.get("away", "Away"))
        lbl_away.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
        lbl_away.setStyleSheet("color: #f1f5f9; border: none;")
        lbl_away.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl_away.setWordWrap(True)
        away_box.addWidget(self.away_logo, alignment=Qt.AlignmentFlag.AlignCenter)
        away_box.addWidget(lbl_away)
        match_row.addLayout(away_box, stretch=1)

        center_box = QVBoxLayout()
        center_box.setAlignment(Qt.AlignmentFlag.AlignCenter)
        raw_a = str(self.game.get("away_score") or "0").strip()
        raw_h = str(self.game.get("home_score") or "0").strip()
        has_score = (raw_a != "0" or raw_h != "0" or self.game.get("is_live") or is_final)
        
        if has_score:
            lbl_score = QLabel(f"{raw_a} - {raw_h}")
            lbl_score.setFont(QFont("Segoe UI", 16, QFont.Weight.Bold))
            lbl_score.setStyleSheet("color: #10B981; border: none;")
            center_box.addWidget(lbl_score, alignment=Qt.AlignmentFlag.AlignCenter)
        else:
            lbl_vs = QLabel("VS")
            lbl_vs.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
            lbl_vs.setStyleSheet("color: #334155; border: none;")
            center_box.addWidget(lbl_vs, alignment=Qt.AlignmentFlag.AlignCenter)
        match_row.addLayout(center_box)

        home_box = QVBoxLayout()
        home_box.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.home_logo = SafeAsyncLogoLabel(40)
        self.home_logo.load_image(self.game.get("home_logo"), fallback_text=self.game.get("home", "H")[:3].upper())
        lbl_home = QLabel(self.game.get("home", "Home"))
        lbl_home.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
        lbl_home.setStyleSheet("color: #f1f5f9; border: none;")
        lbl_home.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl_home.setWordWrap(True)
        home_box.addWidget(self.home_logo, alignment=Qt.AlignmentFlag.AlignCenter)
        home_box.addWidget(lbl_home)
        match_row.addLayout(home_box, stretch=1)

        self.main_layout.addLayout(match_row)

        # 3. Action Shelf
        bottom_row = QHBoxLayout()
        
        if self.has_gamecast:
            self.btn_gamecast = QPushButton("📊 Gamecast", self)
            self.btn_gamecast.setStyleSheet("""
                QPushButton {
                    background: transparent; color: #64748b; font-size: 10px; font-weight: bold;
                    border: none; padding: 4px;
                }
                QPushButton:hover { color: #10B981; }
            """)
            self.btn_gamecast.clicked.connect(self.toggle_gamecast)
            bottom_row.addWidget(self.btn_gamecast)

        bottom_row.addStretch()

        is_live = self.game.get("is_live", False)
        kickoff_ts = self.game.get("kickoff_ts", 0)
        starts_soon = False
        if kickoff_ts > 0 and (kickoff_ts - datetime.now().timestamp() <= 900):
            starts_soon = True

        if not self.is_past_date and not is_final:
            if is_live or starts_soon:
                btn_watch = QPushButton("Watch ▾")
                btn_watch.setStyleSheet("""
                    QPushButton {
                        background-color: #10B981; color: #05070a;
                        font-weight: 800; font-size: 11px; padding: 5px 16px;
                        border-radius: 5px; border: none;
                    }
                    QPushButton:hover { background-color: #059669; color: #fff; }
                """)
                menu = QMenu(self)
                act_vlc = QAction("▶ VLC Player (Direct)", self)
                act_vlc.triggered.connect(lambda ch, u=self.game.get("embed_url"), t=f"{self.game.get('away')} vs {self.game.get('home')}": resolve_and_launch_vlc(u, t))
                menu.addAction(act_vlc)

                act_embed = QAction("🌐 Web Stream", self)
                act_embed.triggered.connect(lambda ch, u=self.game.get("embed_url"): open_url(u))
                menu.addAction(act_embed)

                act_onhockey = QAction("🏒 OnHockey Fallback", self)
                act_onhockey.triggered.connect(lambda ch: open_url("http://onhockey.tv/"))
                menu.addAction(act_onhockey)

                btn_watch.setMenu(menu)
                bottom_row.addWidget(btn_watch)
            else:
                btn_pre = QPushButton(f"Starts {self.game.get('status', 'Soon')}")
                btn_pre.setEnabled(False)
                btn_pre.setStyleSheet("background: #111724; color: #64748b; font-size: 10px; padding: 4px 10px; border-radius: 4px; border: 1px solid #1a2233;")
                bottom_row.addWidget(btn_pre)
        elif self.game.get("recap_url"):
            btn_recap = QPushButton("▶ Recap")
            btn_recap.setStyleSheet("background: #182234; color: #38bdf8; font-size: 10px; padding: 4px 10px; border-radius: 4px; border: 1px solid #0284c7;")
            btn_recap.clicked.connect(lambda ch, u=self.game.get("recap_url"): open_url(u))
            bottom_row.addWidget(btn_recap)

        self.main_layout.addLayout(bottom_row)

        if self.has_gamecast:
            self.drawer = InlineGamecastDrawer(self.game, self)
            self.drawer.setVisible(False)
            self.main_layout.addWidget(self.drawer)
        else:
            self.drawer = None

    def toggle_gamecast(self):
        if not self.drawer:
            return
        is_visible = self.drawer.isVisible()
        self.drawer.setVisible(not is_visible)
        self.btn_gamecast.setStyleSheet(
            "QPushButton { background: transparent; color: #10B981; font-size: 10px; font-weight: bold; border: none; padding: 4px; }"
            if not is_visible else
            "QPushButton { background: transparent; color: #64748b; font-size: 10px; font-weight: bold; border: none; padding: 4px; } QPushButton:hover { color: #10B981; }"
        )


class LeagueHeaderBanner(QFrame):
    def __init__(self, league_key, game_count, parent=None):
        super().__init__(parent)
        self.setObjectName("LeagueBanner")

        brand = LEAGUE_BRANDING.get(league_key, {
            "badge_text": league_key[:4].upper(),
            "color": "#10B981",
            "full_name": league_key.upper()
        })
        accent_color = brand.get("color", "#10B981")
        title_text = brand.get("full_name", league_key.upper())
        badge_txt = brand.get("badge_text", "HLH")

        self.setStyleSheet(f"""
            QFrame#LeagueBanner {{
                background-color: #0c1018;
                border: 1px solid #1a2233;
                border-left: 4px solid {accent_color};
                border-radius: 8px;
            }}
        """)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(14, 10, 16, 10)
        layout.setSpacing(12)

        self.badge = LeagueShieldBadge(badge_txt, accent_color)
        layout.addWidget(self.badge)

        lbl_title = QLabel(title_text)
        lbl_title.setFont(QFont("Impact" if sys.platform == "win32" else "Arial Black", 12))
        lbl_title.setStyleSheet("color: #F8FAFC; letter-spacing: 1.5px; border: none;")
        layout.addWidget(lbl_title)

        lbl_count = QLabel(f"{game_count} GAMES" if game_count != 1 else "1 GAME")
        lbl_count.setFont(QFont("Segoe UI", 8, QFont.Weight.Bold))
        lbl_count.setStyleSheet(f"""
            background-color: #151d2c;
            color: {accent_color};
            border: 1px solid {accent_color}55;
            padding: 3px 8px;
            border-radius: 5px;
        """)
        layout.addWidget(lbl_count)

        layout.addSpacing(6)
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setStyleSheet(f"border: none; background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 {accent_color}66, stop:1 transparent); height: 2px;")
        layout.addWidget(line, stretch=1)


class CheckUpdateThread(QThread):
    update_result = pyqtSignal(bool, str, str, str)

    def run(self):
        try:
            url = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"
            headers = {"User-Agent": "HockeyLiveHub-Desktop"}
            resp = requests.get(url, headers=headers, timeout=4)
            if resp.status_code == 200:
                data = resp.json()
                latest_tag = data.get("tag_name", "").strip()
                html_url = data.get("html_url", f"https://github.com/{GITHUB_REPO}/releases/latest")
                body = data.get("body", "No changelog provided.")

                clean_latest = latest_tag.lstrip("v")
                clean_curr = CURRENT_VERSION.lstrip("v")

                if clean_latest and clean_latest != clean_curr:
                    self.update_result.emit(True, latest_tag, html_url, body)
                    return
            self.update_result.emit(False, CURRENT_VERSION, "", "")
        except Exception:
            self.update_result.emit(False, CURRENT_VERSION, "", "")


class CalendarPopupDialog(QDialog):
    def __init__(self, current_date, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Select Date")
        self.setWindowFlags(Qt.WindowType.Popup | Qt.WindowType.FramelessWindowHint)
        self.setStyleSheet("""
            QDialog {
                background-color: #0b0f17;
                border: 1px solid #202b3d;
                border-radius: 8px;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)

        self.calendar = QCalendarWidget(self)
        self.calendar.setGridVisible(False)
        self.calendar.setSelectedDate(QDate(current_date.year, current_date.month, current_date.day))
        self.calendar.activated.connect(self.accept)
        layout.addWidget(self.calendar)

        btn_today = QPushButton("Jump to Today", self)
        btn_today.setStyleSheet("""
            QPushButton {
                background-color: #10B981; color: #05070a; font-weight: 800; font-size: 11px;
                padding: 6px; border-radius: 4px; border: none;
            }
            QPushButton:hover { background-color: #059669; color: #FFFFFF; }
        """)
        btn_today.clicked.connect(self.select_today)
        layout.addWidget(btn_today)

    def select_today(self):
        today = datetime.now().date()
        self.calendar.setSelectedDate(QDate(today.year, today.month, today.day))
        self.accept()

    def get_selected_date(self):
        qdate = self.calendar.selectedDate()
        return datetime(qdate.year(), qdate.month(), qdate.day()).date()


class TimezoneSelectionDialog(QDialog):
    def __init__(self, parent=None, initial_tz="Local System Time"):
        super().__init__(parent)
        self.setWindowTitle("Select Timezone")
        self.setFixedSize(360, 160)
        self.setStyleSheet("""
            QDialog { background-color: #0d121c; color: #fff; }
            QLabel { color: #f8fafc; font-size: 13px; font-weight: bold; }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(12)

        lbl = QLabel("Choose display timezone for game times:")
        layout.addWidget(lbl)

        self.tz_combo = QComboBox()
        self.tz_combo.addItems(list(TIMEZONE_OFFSETS.keys()))
        if initial_tz in TIMEZONE_OFFSETS:
            self.tz_combo.setCurrentText(initial_tz)
        layout.addWidget(self.tz_combo)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.setStyleSheet("""
            QPushButton {
                background-color: #10B981; color: #05070a; font-weight: bold;
                padding: 6px 14px; border-radius: 4px;
            }
        """)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def get_selected_timezone(self):
        return self.tz_combo.currentText()


def resolve_and_launch_vlc(embed_url, window_title="HLH Stream"):
    if not embed_url:
        return

    if "matchora.to/embed/match/" in embed_url:
        try:
            session = requests.Session()
            session.headers.update({
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "Referer": "https://matchora.to/",
            })
            resp = session.get(embed_url, timeout=4)
            if resp.status_code == 200:
                html = resp.text
                ch_match = re.search(r'var\s+CH\s*=\s*"([^"]+)"', html)
                fx_match = re.search(r'var\s+FX\s*=\s*"([^"]+)"', html)
                pp_match = re.search(r'var\s+PP\s*=\s*"([^"]+)"', html)

                if ch_match and pp_match:
                    ch = ch_match.group(1)
                    fx = fx_match.group(1) if fx_match else ""
                    pp = pp_match.group(1)

                    api_url = f"https://matchora.to/api/play/{ch}?fx={fx}&pp={pp}"
                    api_resp = session.get(api_url, timeout=4)
                    if api_resp.status_code == 200:
                        stream_m3u8 = api_resp.json().get("url")

                        if stream_m3u8 and ".m3u8" in stream_m3u8:
                            vlc = shutil.which("vlc")
                            if not vlc and sys.platform == "win32":
                                for default_path in [
                                    r"C:\Program Files\VideoLAN\VLC\vlc.exe",
                                    r"C:\Program Files (x86)\VideoLAN\VLC\vlc.exe"
                                ]:
                                    if os.path.exists(default_path):
                                        vlc = default_path
                                        break
                            elif not vlc and sys.platform == "darwin":
                                mac_vlc = "/Applications/VLC.app/Contents/MacOS/VLC"
                                if os.path.exists(mac_vlc):
                                    vlc = mac_vlc
                            elif not vlc and sys.platform.startswith("linux"):
                                for default_path in ["/usr/bin/vlc", "/usr/local/bin/vlc"]:
                                    if os.path.exists(default_path):
                                        vlc = default_path
                                        break

                            if vlc:
                                cmd = [
                                    vlc,
                                    stream_m3u8,
                                    ":http-referrer=https://matchora.to/",
                                    f"--meta-title={window_title}",
                                    "--qt-minimal-view"
                                ]
                                creation_flag = 0x08000000 if sys.platform == "win32" else 0
                                subprocess.Popen(cmd, creationflags=creation_flag)
                                return
        except Exception:
            pass

    open_url(embed_url)


def open_url(url):
    if not url:
        return
    webbrowser.open(url)


def parse_nhl_team(team_dict):
    if not isinstance(team_dict, dict):
        return "NHL Team", ""
    abbrev = str(team_dict.get("abbrev", "")).strip().lower()
    if abbrev in NHL_FRANCHISES:
        return NHL_FRANCHISES[abbrev], abbrev
    place = team_dict.get("placeName")
    nick = team_dict.get("commonName")
    if isinstance(place, dict):
        place = place.get("default", "")
    if isinstance(nick, dict):
        nick = nick.get("default", "")
    full = f"{str(place or '')} {str(nick or '')}".strip()
    if full and full != "None None":
        return full, abbrev
    return abbrev.upper() if abbrev else "NHL Team", abbrev


class MultiLeagueScheduleFetcher(QThread):
    games_loaded = pyqtSignal(list)
    fetch_error = pyqtSignal(str)

    def __init__(self, filter_key, target_date, tz_name):
        super().__init__()
        self.filter_key = filter_key
        self.target_date = target_date
        self.tz_name = tz_name
        self.is_aborted = False

    def get_event_local_date(self, kickoff_ts):
        if not kickoff_ts:
            return self.target_date
        offset_hours = TIMEZONE_OFFSETS.get(self.tz_name)
        if offset_hours is None:
            return datetime.fromtimestamp(kickoff_ts).date()
        else:
            tz = timezone(timedelta(hours=offset_hours))
            return datetime.fromtimestamp(kickoff_ts, tz=tz).date()

    def format_time(self, utc_dt):
        offset_hours = TIMEZONE_OFFSETS.get(self.tz_name)
        if offset_hours is None:
            return utc_dt.astimezone().strftime("%I:%M %p")
        else:
            tz = timezone(timedelta(hours=offset_hours))
            return utc_dt.astimezone(tz).strftime("%I:%M %p")

    def get_matchora_stream_map(self, session):
        matchora_streams = []
        try:
            url = f"{API_BASE}/schedule?watchable=1"
            resp = session.get(url, timeout=3.0)
            if resp.status_code == 200:
                for ev in resp.json().get("events", []):
                    home = str(ev.get("home") or "").lower()
                    away = str(ev.get("away") or "").lower()
                    embed = ev.get("embed_url") or f"https://matchora.to/embed/match/{ev.get('id')}"
                    matchora_streams.append({"home": home, "away": away, "embed": embed})
        except Exception:
            pass
        return matchora_streams

    def find_matchora_url(self, home_name, away_name, stream_map):
        h_words = [w.lower() for w in home_name.split() if len(w) > 3]
        a_words = [w.lower() for w in away_name.split() if len(w) > 3]
        for item in stream_map:
            h_match = any(w in item["home"] for w in h_words)
            a_match = any(w in item["away"] for w in a_words)
            if h_match or a_match:
                return item["embed"]
        return "http://onhockey.tv/"

    def fetch_nhl_official(self, session, stream_map):
        games = []
        try:
            date_str = self.target_date.strftime("%Y-%m-%d")
            url = f"https://api-web.nhle.com/v1/score/{date_str}"
            resp = session.get(url, timeout=2.5)
            if resp.status_code != 200:
                return []

            data = resp.json()
            for g in data.get("games", []):
                away_raw = g.get("awayTeam", {})
                home_raw = g.get("homeTeam", {})
                away_name, away_code = parse_nhl_team(away_raw)
                home_name, home_code = parse_nhl_team(home_raw)

                state = g.get("gameState", "SCHEDULED")
                is_live = (state in ["LIVE", "CRIT"])
                is_final = (state in ["FINAL", "OFF"])

                kickoff_ts = 0
                utc_start = g.get("startTimeUTC")
                if utc_start:
                    try:
                        dt = datetime.fromisoformat(utc_start.replace("Z", "+00:00"))
                        kickoff_ts = dt.timestamp()
                    except Exception:
                        pass

                if is_live:
                    clock = g.get("clock", {})
                    time_rem = clock.get("timeRemaining", "")
                    period = g.get("periodDescriptor", {}).get("number", "")
                    status = f"P{period} {time_rem}".strip()
                elif is_final:
                    status = "FINAL"
                else:
                    status = "Scheduled"
                    if utc_start:
                        try:
                            dt = datetime.fromisoformat(utc_start.replace("Z", "+00:00"))
                            status = self.format_time(dt)
                        except Exception:
                            pass

                away_code_espn = ESPN_LOGO_OVERRIDES.get(away_code, away_code)
                home_code_espn = ESPN_LOGO_OVERRIDES.get(home_code, home_code)
                away_logo = f"https://a.espncdn.com/i/teamlogos/nhl/500/{away_code_espn}.png"
                home_logo = f"https://a.espncdn.com/i/teamlogos/nhl/500/{home_code_espn}.png"

                date_query = self.target_date.strftime("%B %d %Y")
                recap_query = urllib.parse.quote(f"{away_name} vs {home_name} condensed game recap {date_query}")
                recap_url = f"https://www.youtube.com/results?search_query={recap_query}" if is_final else None
                watch_url = self.find_matchora_url(home_name, away_name, stream_map)

                games.append({
                    "id": str(g.get("id")),
                    "home": home_name,
                    "away": away_name,
                    "home_logo": home_logo,
                    "away_logo": away_logo,
                    "home_score": str(home_raw.get("score", "0")),
                    "away_score": str(away_raw.get("score", "0")),
                    "league": "NHL",
                    "status": status,
                    "is_live": is_live,
                    "is_final": is_final,
                    "embed_url": watch_url,
                    "recap_url": recap_url,
                    "channels": 1,
                    "kickoff_ts": kickoff_ts,
                    "is_ncaa": False
                })
        except Exception:
            pass
        return games

    def fetch_espn_ncaa(self, session, stream_map):
        games = []
        try:
            date_param = self.target_date.strftime("%Y%m%d")
            url = f"{ESPN_NCAA_API}?dates={date_param}"
            resp = session.get(url, timeout=2.5)
            if resp.status_code != 200:
                return []

            data = resp.json()
            for ev in data.get("events", []):
                comps = ev.get("competitions", [{}])[0]
                competitors = comps.get("competitors", [])
                if len(competitors) < 2:
                    continue

                home_data = competitors[0]
                away_data = competitors[1]
                home_team = home_data.get("team", {})
                away_team = away_data.get("team", {})

                status_type = ev.get("status", {}).get("type", {})
                state = status_type.get("state", "pre")
                short_detail = status_type.get("shortDetail", "Scheduled")

                is_live = (state == "in")
                is_final = (state == "post")

                kickoff_ts = 0
                date_iso = ev.get("date")
                if date_iso:
                    try:
                        dt = datetime.fromisoformat(date_iso.replace("Z", "+00:00"))
                        kickoff_ts = dt.timestamp()
                    except Exception:
                        pass

                if kickoff_ts:
                    ev_date = self.get_event_local_date(kickoff_ts)
                    if ev_date != self.target_date:
                        continue

                home_name = home_team.get("displayName", "Home")
                away_name = away_team.get("displayName", "Away")

                date_query = self.target_date.strftime("%B %d %Y")
                recap_query = urllib.parse.quote(f"{away_name} vs {home_name} hockey highlights {date_query}")
                recap_url = f"https://www.youtube.com/results?search_query={recap_query}" if is_final else None
                watch_url = self.find_matchora_url(home_name, away_name, stream_map)

                games.append({
                    "id": ev.get("id"),
                    "home": home_name,
                    "away": away_name,
                    "home_logo": home_team.get("logo"),
                    "away_logo": away_team.get("logo"),
                    "home_score": str(home_data.get("score", "0")),
                    "away_score": str(away_data.get("score", "0")),
                    "league": "NCAA Men's D1",
                    "status": short_detail,
                    "is_live": is_live,
                    "is_final": is_final,
                    "embed_url": watch_url,
                    "recap_url": recap_url,
                    "channels": 1,
                    "kickoff_ts": kickoff_ts,
                    "is_ncaa": True
                })
        except Exception:
            pass
        return games

    def fetch_matchora(self, session):
        games = []
        try:
            d_str = self.target_date.strftime("%Y-%m-%d")
            url = f"{API_BASE}/schedule?date={d_str}"
            resp = session.get(url, timeout=3.0)
            if resp.status_code != 200:
                return []

            now_ts = datetime.now().timestamp()
            seen_matchora = {}

            for ev in resp.json().get("events", []):
                league_raw = str(ev.get("league") or "").lower()
                home_raw = str(ev.get("home") or "").lower()
                away_raw = str(ev.get("away") or "").lower()
                sport_raw = str(ev.get("sport") or "").lower()

                if "nhl" in league_raw or any(t.lower() in home_raw for t in NHL_FRANCHISES.values()) or any(t.lower() in away_raw for t in NHL_FRANCHISES.values()):
                    continue
                if "ncaa" in league_raw or "college" in league_raw or "university" in league_raw:
                    continue

                non_hockey = ["tennis", "atp", "wta", "indoors", "basketball", "soccer", "football", "nfl", "nba", "baseball"]
                if any(bad in league_raw for bad in non_hockey) or any(bad in sport_raw for bad in non_hockey):
                    continue

                is_ahl = "ahl" in league_raw or "american hockey league" in league_raw
                is_echl = "echl" in league_raw
                is_sphl = "sphl" in league_raw or "southern professional" in league_raw
                is_qmjhl = "qmjhl" in league_raw or "quebec major" in league_raw or "lhjmq" in league_raw
                is_juniors = any(k in league_raw for k in ["ohl", "whl", "chl", "junior"])
                is_shl = ("shl" in league_raw or "swedish hockey league" in league_raw or "allsvenskan" in league_raw)
                is_liiga = "liiga" in league_raw or "mestis" in league_raw
                is_swiss = ("swiss national league" in league_raw or "national league" in league_raw or "nla" in league_raw) and ("swiss" in league_raw or "switzerland" in league_raw or "nl" in league_raw)

                is_hockey = (is_ahl or is_echl or is_sphl or is_qmjhl or is_juniors or is_shl or is_liiga or is_swiss or "hockey" in league_raw or "hockey" in sport_raw)
                if not is_hockey:
                    continue

                if self.filter_key == "AHL" and not is_ahl: continue
                elif self.filter_key == "ECHL" and not is_echl: continue
                elif self.filter_key == "SPHL" and not is_sphl: continue
                elif self.filter_key == "QMJHL" and not is_qmjhl: continue
                elif self.filter_key == "OHL / WHL Juniors" and not is_juniors: continue
                elif self.filter_key == "Swedish Hockey League (SHL)" and not is_shl: continue
                elif self.filter_key == "Finnish Liiga" and not is_liiga: continue
                elif self.filter_key == "Swiss National League (NL)" and not is_swiss: continue

                kickoff = ev.get("kickoff")
                kickoff_ts = float(kickoff) if kickoff else 0

                is_live = bool(ev.get("live"))
                time_str = "Scheduled"
                if kickoff:
                    try:
                        utc_dt = datetime.fromtimestamp(kickoff_ts, tz=timezone.utc)
                        time_str = self.format_time(utc_dt)
                    except Exception:
                        pass

                minute_val = str(ev.get("minute") or "").strip().upper()
                raw_status = str(ev.get("status") or "").strip().upper()

                if is_live and minute_val and minute_val not in ["FT", "ENDED"]:
                    status_label = f"{minute_val}m"
                elif is_live:
                    status_label = "LIVE"
                elif raw_status in ["FT", "FINAL", "ENDED", "POST", "FINISHED"]:
                    status_label = "FINAL"
                else:
                    status_label = time_str

                time_since_start = now_ts - kickoff_ts if kickoff_ts else 0
                is_overdue = (kickoff_ts > 0 and time_since_start > 12600 and not is_live)
                is_final = (status_label in ["FT", "FINAL", "ENDED", "FINISHED"]) or is_overdue
                if is_final:
                    status_label = "FINAL"

                score_str = ev.get("score") or "0-0"
                scores = score_str.split("-") if "-" in score_str else ["0", "0"]

                if is_echl: league_label = "ECHL"
                elif is_sphl: league_label = "SPHL"
                elif is_qmjhl: league_label = "QMJHL"
                elif is_juniors: league_label = "OHL / WHL Juniors"
                elif is_shl: league_label = "Swedish SHL"
                elif is_liiga: league_label = "Finnish Liiga"
                elif is_swiss: league_label = "Swiss NL"
                elif is_ahl: league_label = "AHL"
                else: league_label = "Other Hockey"

                h_name = ev.get("home", "Home")
                a_name = ev.get("away", "Away")

                dedup_key = (league_label, clean_team_name(a_name), clean_team_name(h_name))
                if dedup_key in seen_matchora:
                    existing = seen_matchora[dedup_key]
                    if not existing.get("is_live") and is_live:
                        existing["is_live"] = True
                        existing["status"] = status_label
                    if ev.get("embed_url") and "onhockey" not in str(ev.get("embed_url")):
                        existing["embed_url"] = ev.get("embed_url")
                    existing["channels"] = existing.get("channels", 1) + 1
                    continue

                date_query = self.target_date.strftime("%B %d %Y")
                recap_query = urllib.parse.quote(f"{a_name} vs {h_name} highlights {date_query}")
                recap_url = f"https://www.youtube.com/results?search_query={recap_query}" if is_final else None

                game_item = {
                    "id": str(ev.get("id")),
                    "home": h_name,
                    "away": a_name,
                    "home_logo": ev.get("home_badge") or ev.get("home_logo"),
                    "away_logo": ev.get("away_badge") or ev.get("away_logo"),
                    "home_score": scores[0].strip(),
                    "away_score": scores[1].strip(),
                    "league": league_label,
                    "status": status_label,
                    "is_live": is_live and not is_final,
                    "is_final": is_final,
                    "embed_url": ev.get("embed_url") or f"https://matchora.to/embed/match/{ev.get('id')}",
                    "recap_url": recap_url,
                    "channels": ev.get("channel_count", 1),
                    "kickoff_ts": kickoff_ts,
                    "is_ncaa": False
                }
                seen_matchora[dedup_key] = game_item
                games.append(game_item)
        except Exception:
            pass
        return games

    def run(self):
        try:
            session = requests.Session()
            session.headers.update({"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"})
            combined_games = []

            if self.is_aborted: return

            stream_map = self.get_matchora_stream_map(session)

            if self.filter_key == "All Hockey":
                combined_games.extend(self.fetch_nhl_official(session, stream_map))
                combined_games.extend(self.fetch_espn_ncaa(session, stream_map))
                combined_games.extend(self.fetch_matchora(session))
            elif self.filter_key == "NHL":
                combined_games.extend(self.fetch_nhl_official(session, stream_map))
            elif self.filter_key == "NCAA Men's D1 Hockey":
                combined_games.extend(self.fetch_espn_ncaa(session, stream_map))
            else:
                combined_games.extend(self.fetch_matchora(session))

            if self.is_aborted: return

            unique_games = []
            seen_keys = set()
            for g in combined_games:
                key = (g["league"], clean_team_name(g["away"]), clean_team_name(g["home"]))
                if key not in seen_keys:
                    seen_keys.add(key)
                    unique_games.append(g)

            unique_games.sort(
                key=lambda g: (
                    LEAGUE_PRIORITY.get(g["league"], 50),
                    not g["is_live"]
                )
            )
            self.games_loaded.emit(unique_games)
        except Exception as e:
            self.fetch_error.emit(str(e))


class HockeyHubBeta(QMainWindow):
    def __init__(self):
        super().__init__()
        pool = QThreadPool.globalInstance()
        if pool:
            pool.setMaxThreadCount(4)

        self.thread = None
        self.update_thread = None
        self.active_date = datetime.now().date()

        self.settings = QSettings("HLH", "HockeyLiveHub")
        self.init_timezone()

        self.setWindowTitle(f"Hockey Live Hub - {CURRENT_VERSION}")
        self.resize(1060, 750)
        self.setStyleSheet(STYLESHEET)
        self.init_icon()

        central = QWidget()
        central.setObjectName("CentralWidget")
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(20, 16, 20, 14)
        main_layout.setSpacing(12)

        header_bar = QHBoxLayout()
        header_bar.setSpacing(10)

        lbl_icon = QLabel("🏒")
        lbl_icon.setFont(QFont("Segoe UI", 15))
        header_bar.addWidget(lbl_icon)

        self.league_combo = QComboBox()
        self.league_combo.addItems(LEAGUE_CATEGORIES)
        self.league_combo.activated.connect(lambda: self.load_schedule())
        header_bar.addWidget(self.league_combo)

        btn_refresh = QPushButton("Refresh")
        btn_refresh.setObjectName("NavBtn")
        btn_refresh.clicked.connect(self.load_schedule)
        header_bar.addWidget(btn_refresh)

        self.btn_tz = QPushButton(f"⚙ {self.get_tz_short_label()}")
        self.btn_tz.setObjectName("NavBtn")
        self.btn_tz.setToolTip("Click to change timezone")
        self.btn_tz.clicked.connect(self.prompt_change_timezone)
        header_bar.addWidget(self.btn_tz)

        header_bar.addSpacing(10)

        btn_prev = QPushButton("◀")
        btn_prev.setObjectName("NavBtn")
        btn_prev.setToolTip("Previous Day")
        btn_prev.clicked.connect(self.go_to_yesterday)
        header_bar.addWidget(btn_prev)

        self.btn_date_picker = QPushButton(f"📅 {self.active_date.strftime('%a, %b %d')}")
        self.btn_date_picker.setObjectName("DateBtn")
        self.btn_date_picker.setToolTip("Click to open calendar")
        self.btn_date_picker.clicked.connect(self.open_calendar_popup)
        header_bar.addWidget(self.btn_date_picker)

        btn_next = QPushButton("▶")
        btn_next.setObjectName("NavBtn")
        btn_next.setToolTip("Next Day")
        btn_next.clicked.connect(self.go_to_tomorrow)
        header_bar.addWidget(btn_next)

        header_bar.addStretch()

        self.btn_check_update = QPushButton("Check for Updates")
        self.btn_check_update.setObjectName("NavBtn")
        self.btn_check_update.clicked.connect(self.check_for_updates)
        header_bar.addWidget(self.btn_check_update)

        main_layout.addLayout(header_bar)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)

        self.card_container = QWidget()
        self.card_container.setStyleSheet("background: transparent;")
        self.card_layout = QVBoxLayout(self.card_container)
        self.card_layout.setSpacing(8)
        self.card_layout.setContentsMargins(0, 4, 6, 4)
        self.scroll.setWidget(self.card_container)
        main_layout.addWidget(self.scroll)

        footer_bar = QHBoxLayout()
        self.lbl_footer_info = QLabel(f"HLH {CURRENT_VERSION} | FOSS Desktop Client")
        self.lbl_footer_info.setStyleSheet("color: #475569; font-size: 11px; font-weight: 600;")
        footer_bar.addWidget(self.lbl_footer_info)

        footer_bar.addStretch()

        self.lbl_game_count = QLabel("Games Found: 0")
        self.lbl_game_count.setStyleSheet("color: #10B981; font-size: 11px; font-weight: 700;")
        footer_bar.addWidget(self.lbl_game_count)
        main_layout.addLayout(footer_bar)

        self.refresh_timer = QTimer(self)
        self.refresh_timer.setInterval(30000)
        self.refresh_timer.timeout.connect(self.background_refresh)
        self.refresh_timer.start()

        self.update_date_button()
        self.load_schedule()

    def open_calendar_popup(self):
        dialog = CalendarPopupDialog(self.active_date, self)
        btn_pos = self.btn_date_picker.mapToGlobal(self.btn_date_picker.rect().bottomLeft())
        dialog.move(btn_pos)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.active_date = dialog.get_selected_date()
            self.update_date_button()
            self.load_schedule()

    def check_for_updates(self):
        self.btn_check_update.setEnabled(False)
        self.btn_check_update.setText("Checking...")
        self.update_thread = CheckUpdateThread()
        self.update_thread.update_result.connect(self.handle_update_result)
        self.update_thread.start()

    def handle_update_result(self, has_update, tag, release_url, changelog):
        self.btn_check_update.setEnabled(True)
        self.btn_check_update.setText("Check for Updates")

        if has_update:
            msg = QMessageBox(self)
            msg.setWindowTitle("Update Available")
            msg.setText(f"<h3>A newer release of Hockey Live Hub is available!</h3>"
                        f"<p>Current: <b>{CURRENT_VERSION}</b> → Latest: <b style='color:#10B981;'>{tag}</b></p>")
            msg.setInformativeText(f"<b>Changelog:</b><br>{changelog[:300]}...")
            btn_download = msg.addButton("Download Release", QMessageBox.ButtonRole.AcceptRole)
            msg.addButton("Later", QMessageBox.ButtonRole.RejectRole)
            msg.exec()

            if msg.clickedButton() == btn_download and release_url:
                open_url(release_url)
        else:
            QMessageBox.information(self, "Up to Date", f"You are running the latest version of Hockey Live Hub ({CURRENT_VERSION}).")

    def init_timezone(self):
        saved_tz = self.settings.value("timezone", None)
        if not saved_tz:
            dialog = TimezoneSelectionDialog(self)
            if dialog.exec() == QDialog.DialogCode.Accepted:
                saved_tz = dialog.get_selected_timezone()
            else:
                saved_tz = "Local System Time"
            self.settings.setValue("timezone", saved_tz)
        self.current_tz = saved_tz

    def get_tz_short_label(self):
        if "Eastern" in self.current_tz: return "ET"
        if "Central" in self.current_tz: return "CT"
        if "Mountain" in self.current_tz: return "MT"
        if "Pacific" in self.current_tz: return "PT"
        if "Alaska" in self.current_tz: return "AKT"
        if "Hawaii" in self.current_tz: return "HST"
        if "UTC" in self.current_tz: return "UTC"
        return "LOC"

    def prompt_change_timezone(self):
        dialog = TimezoneSelectionDialog(self, initial_tz=self.current_tz)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.current_tz = dialog.get_selected_timezone()
            self.settings.setValue("timezone", self.current_tz)
            self.btn_tz.setText(f"⚙ {self.get_tz_short_label()}")
            self.load_schedule()

    def init_icon(self):
        base_dir = getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(__file__)))
        icon_path = os.path.join(base_dir, "app_icon.ico")
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))

    def update_date_button(self):
        self.btn_date_picker.setText(f"📅 {self.active_date.strftime('%a, %b %d')}")

    def go_to_yesterday(self):
        self.active_date -= timedelta(days=1)
        self.update_date_button()
        self.load_schedule()

    def go_to_tomorrow(self):
        self.active_date += timedelta(days=1)
        self.update_date_button()
        self.load_schedule()

    def background_refresh(self):
        if self.active_date == datetime.now().date():
            self.load_schedule(silent=True)

    def clear_cards(self):
        while self.card_layout.count():
            item = self.card_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.hide()
                widget.deleteLater()

    def load_schedule(self, silent=False):
        if self.thread is not None and self.thread.isRunning():
            self.thread.is_aborted = True

        if not silent:
            self.clear_cards()
            lbl_loading = QLabel("Loading games...")
            lbl_loading.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
            lbl_loading.setStyleSheet("color: #10B981; padding: 20px;")
            self.card_layout.addWidget(lbl_loading)

        selected = self.league_combo.currentText()
        self.thread = MultiLeagueScheduleFetcher(selected, self.active_date, self.current_tz)
        self.thread.games_loaded.connect(self.populate_games)
        self.thread.fetch_error.connect(self.handle_error)
        self.thread.start()

    def handle_error(self, err_msg):
        QMessageBox.warning(self, "Fetch Error", f"Could not load schedule:\n{err_msg}")

    def populate_games(self, games):
        scroll_bar = self.scroll.verticalScrollBar()
        current_scroll = scroll_bar.value()

        self.clear_cards()
        self.lbl_game_count.setText(f"Games Found: {len(games)}")

        if not games:
            lbl = QLabel(f"No games found on {self.active_date.strftime('%B %d')} for {self.league_combo.currentText()}.")
            lbl.setFont(QFont("Segoe UI", 12, QFont.Weight.Medium))
            lbl.setStyleSheet("color: #64748B; padding: 40px;")
            self.card_layout.addWidget(lbl)
            return

        is_all_hockey = (self.league_combo.currentText() == "All Hockey")
        is_past = (self.active_date < datetime.now().date())
        columns = 2

        if is_all_hockey:
            grouped = {}
            for g in games:
                grouped.setdefault(g["league"], []).append(g)

            sorted_leagues = sorted(grouped.keys(), key=lambda l: LEAGUE_PRIORITY.get(l, 50))
            for league_name in sorted_leagues:
                league_games = grouped[league_name]
                self.card_layout.addWidget(LeagueHeaderBanner(league_name, len(league_games)))

                grid_widget = QWidget()
                grid = QGridLayout(grid_widget)
                grid.setContentsMargins(0, 4, 0, 8)
                grid.setSpacing(10)

                for idx, game in enumerate(league_games):
                    card = GridGameCard(game, is_past_date=is_past)
                    grid.addWidget(card, idx // columns, idx % columns, Qt.AlignmentFlag.AlignTop)

                self.card_layout.addWidget(grid_widget)
        else:
            grid_widget = QWidget()
            grid = QGridLayout(grid_widget)
            grid.setContentsMargins(0, 4, 0, 8)
            grid.setSpacing(10)

            for idx, game in enumerate(games):
                card = GridGameCard(game, is_past_date=is_past)
                grid.addWidget(card, idx // columns, idx % columns, Qt.AlignmentFlag.AlignTop)

            self.card_layout.addWidget(grid_widget)

        self.card_layout.addStretch()
        QTimer.singleShot(50, lambda: scroll_bar.setValue(current_scroll))


if __name__ == "__main__":
    app = QApplication(sys.argv)
    win = HockeyHubBeta()
    win.show()
    sys.exit(app.exec())