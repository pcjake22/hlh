import sys
import os
import re
import shutil
import subprocess
import webbrowser
import requests
import math
import urllib.parse
from datetime import datetime, timedelta, timezone

from PyQt6 import sip
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QUrl, QPointF, QSettings, QTimer
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
    QLabel, QPushButton, QScrollArea, QFrame, QMessageBox, QComboBox,
    QMenu, QDialog, QDialogButtonBox
)
from PyQt6.QtGui import (
    QFont, QPixmap, QCursor, QPainter, QColor, QPen, QBrush, 
    QPainterPath, QLinearGradient, QIcon, QAction
)
from PyQt6.QtNetwork import QNetworkAccessManager, QNetworkRequest, QNetworkReply

# Windows taskbar grouping
if sys.platform == "win32":
    import ctypes
    try:
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("pcjake22.hlh.desktop.main")
    except Exception:
        pass

API_BASE = "https://matchora.to/api/v1"
ESPN_NCAA_API = "https://site.api.espn.com/apis/site/v2/sports/hockey/mens-college-hockey/scoreboard"

NETWORK_MANAGER = None
IMAGE_CACHE = {}

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
    "uta": "utah",
    "mtl": "mon",
    "cbj": "clb",
    "njd": "nj",
    "nj": "nj",
    "tbl": "tb",
    "tb": "tb",
    "la": "la",
    "lak": "la",
    "sjs": "sj",
    "sj": "sj",
    "wsh": "was",
    "cgy": "cal",
    "vgk": "vgs",
    "wpg": "wpg"
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
    background-color: #0d121c; color: #F1F5F9; padding: 8px 16px;
    border: 1px solid #1a2336; border-radius: 6px; font-weight: 700; font-size: 13px;
}
QComboBox:hover { border: 1px solid #10B981; }
QComboBox QAbstractItemView {
    background-color: #0d121c; color: #F1F5F9; selection-background-color: #10B981;
    selection-color: #05070a; border: 1px solid #1a2336; padding: 4px; outline: 0px;
}

QPushButton#NavBtn {
    background-color: #0f1624; color: #E2E8F0; font-weight: 700; font-size: 11px;
    padding: 6px 14px; border-radius: 6px; border: 1px solid #1d2b42;
}
QPushButton#NavBtn:hover { background-color: #172338; border-color: #10B981; color: #10B981; }

QPushButton#TodayBtn {
    background-color: #10B981; color: #05070a; font-weight: 700; font-size: 11px;
    padding: 6px 14px; border-radius: 6px; border: none;
}
QPushButton#TodayBtn:hover { background-color: #059669; color: #FFFFFF; }

QMenu {
    background-color: #0d121c;
    color: #F1F5F9;
    border: 1px solid #232d42;
    border-radius: 6px;
    padding: 4px;
}
QMenu::item {
    padding: 8px 20px;
    border-radius: 4px;
    font-size: 12px;
    font-weight: 600;
}
QMenu::item:selected {
    background-color: #10B981;
    color: #05070a;
}
"""


def clean_team_name(name):
    return re.sub(r'[^a-zA-Z0-9]', '', str(name or "")).lower()


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
    """Extracts session token from Matchora and opens the master .m3u8 in VLC."""
    if not embed_url:
        return

    if "matchora.to/embed/match/" in embed_url:
        try:
            session = requests.Session()
            session.headers.update({
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "Referer": "https://matchora.to/",
            })
            resp = session.get(embed_url, timeout=5)
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
                    api_resp = session.get(api_url, timeout=5)
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
    """Reliably opens links in default system browser."""
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

    def get_event_local_date(self, kickoff_ts):
        """Converts UTC kickoff timestamp to the selected timezone calendar date."""
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

    def get_matchora_stream_map(self, headers):
        matchora_streams = []
        try:
            url = f"{API_BASE}/schedule?watchable=1"
            resp = requests.get(url, headers=headers, timeout=5)
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
        h_clean = home_name.lower()
        a_clean = away_name.lower()
        for item in stream_map:
            if (any(word in item["home"] for word in h_clean.split() if len(word) > 3) or
                any(word in item["away"] for word in a_clean.split() if len(word) > 3)):
                return item["embed"]
        return "http://onhockey.tv/"

    def fetch_nhl_official(self, headers, stream_map):
        games = []
        try:
            date_str = self.target_date.strftime("%Y-%m-%d")
            url = f"https://api-web.nhle.com/v1/score/{date_str}"
            resp = requests.get(url, headers=headers, timeout=6)
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
                away_logo = f"https://a.espncdn.com/i/teamlogos/nhl/500/{away_code_espn}.png" if away_code else None
                home_logo = f"https://a.espncdn.com/i/teamlogos/nhl/500/{home_code_espn}.png" if home_code else None

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

    def fetch_espn_ncaa(self, headers, stream_map):
        games = []
        try:
            date_param = self.target_date.strftime("%Y%m%d")
            url = f"{ESPN_NCAA_API}?dates={date_param}"
            resp = requests.get(url, headers=headers, timeout=6)
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

                # Filter out games that don't match the selected local date
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
                    "channels": 1 if "matchora.to" in watch_url else 0,
                    "kickoff_ts": kickoff_ts,
                    "is_ncaa": True
                })
        except Exception:
            pass
        return games

    def fetch_matchora(self, headers):
        games = []
        try:
            # Query target date and the following UTC day to bridge late evening North American matches
            dates_to_query = [self.target_date.strftime("%Y-%m-%d")]
            offset_hours = TIMEZONE_OFFSETS.get(self.tz_name)
            if offset_hours is None or offset_hours <= 0:
                dates_to_query.append((self.target_date + timedelta(days=1)).strftime("%Y-%m-%d"))
            if offset_hours is not None and offset_hours > 0:
                dates_to_query.append((self.target_date - timedelta(days=1)).strftime("%Y-%m-%d"))

            dates_to_query = list(dict.fromkeys(dates_to_query))
            now_ts = datetime.now().timestamp()
            seen_matchora = {}

            for d_str in dates_to_query:
                url = f"{API_BASE}/schedule?date={d_str}"
                resp = requests.get(url, headers=headers, timeout=8)
                if resp.status_code != 200:
                    continue

                for ev in resp.json().get("events", []):
                    league_raw = str(ev.get("league") or "").lower()
                    home_raw = str(ev.get("home") or "").lower()
                    away_raw = str(ev.get("away") or "").lower()
                    sport_raw = str(ev.get("sport") or "").lower()

                    # Ignore NHL (official API handles it)
                    if "nhl" in league_raw or any(t.lower() in home_raw for t in NHL_FRANCHISES.values()) or any(t.lower() in away_raw for t in NHL_FRANCHISES.values()):
                        continue

                    # Ignore NCAA/college matches (clean ESPN NCAA API handles it)
                    if "ncaa" in league_raw or "college" in league_raw or "university" in league_raw:
                        continue

                    # Exclude non-hockey sports
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

                    # Strictly enforce local calendar day match
                    if kickoff_ts:
                        ev_local_date = self.get_event_local_date(kickoff_ts)
                        if ev_local_date != self.target_date:
                            continue

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

                    # Deduplication key to prevent repeated feeds
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
            headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
            combined_games = []
            stream_map = self.get_matchora_stream_map(headers)

            if self.filter_key == "All Hockey":
                combined_games.extend(self.fetch_nhl_official(headers, stream_map))
                combined_games.extend(self.fetch_espn_ncaa(headers, stream_map))
                combined_games.extend(self.fetch_matchora(headers))
            elif self.filter_key == "NHL":
                combined_games.extend(self.fetch_nhl_official(headers, stream_map))
            elif self.filter_key == "NCAA Men's D1 Hockey":
                combined_games.extend(self.fetch_espn_ncaa(headers, stream_map))
            else:
                combined_games.extend(self.fetch_matchora(headers))

            # Global deduplication across all sources
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


class AsyncLogoLabel(QLabel):
    def __init__(self, size=34, parent=None):
        super().__init__(parent)
        self.size = size
        self.setFixedSize(size, size)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setStyleSheet("background: transparent; border: none;")
        self.reply = None

    def load_image(self, url):
        if not url:
            self.setText("🏒")
            return
        if url in IMAGE_CACHE:
            self.setPixmap(IMAGE_CACHE[url])
            return

        request = QNetworkRequest(QUrl(url))
        self.reply = NETWORK_MANAGER.get(request)
        self.reply.finished.connect(lambda r=self.reply, u=url: self._on_finished(r, u))

    def _on_finished(self, reply, url):
        if sip.isdeleted(self):
            reply.deleteLater()
            return

        if reply.error() == QNetworkReply.NetworkError.NoError:
            pixmap = QPixmap()
            if pixmap.loadFromData(reply.readAll()):
                scaled = pixmap.scaled(
                    self.size, self.size,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation
                )
                IMAGE_CACHE[url] = scaled
                self.setPixmap(scaled)
            else:
                self.setText("🏒")
        else:
            self.setText("🏒")

        reply.deleteLater()
        self.reply = None


class MomentumWaveWidget(QWidget):
    def __init__(self, game, parent=None):
        super().__init__(parent)
        self.game = game
        self.setFixedHeight(140)
        self.away_logo_pixmap = None
        self.home_logo_pixmap = None

        if game.get("away_logo") in IMAGE_CACHE:
            self.away_logo_pixmap = IMAGE_CACHE[game["away_logo"]]
        if game.get("home_logo") in IMAGE_CACHE:
            self.home_logo_pixmap = IMAGE_CACHE[game["home_logo"]]

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        w = self.width()
        h = self.height()
        mid_y = h / 2.0
        left_m = 50.0
        right_m = 20.0
        chart_w = w - left_m - right_m

        if self.away_logo_pixmap:
            painter.drawPixmap(12, int(mid_y - 48), self.away_logo_pixmap.scaled(28, 28, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
        else:
            painter.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
            painter.setPen(QColor("#94A3B8"))
            painter.drawText(12, int(mid_y - 30), self.game["away"][:3].upper())

        if self.home_logo_pixmap:
            painter.drawPixmap(12, int(mid_y + 18), self.home_logo_pixmap.scaled(28, 28, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
        else:
            painter.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
            painter.setPen(QColor("#94A3B8"))
            painter.drawText(12, int(mid_y + 36), self.game["home"][:3].upper())

        pen_base = QPen(QColor("#242d3d"), 1)
        painter.setPen(pen_base)
        painter.drawLine(int(left_m), int(mid_y), int(w - right_m), int(mid_y))

        p1_x = left_m + chart_w * 0.33
        p2_x = left_m + chart_w * 0.66

        pen_dash = QPen(QColor("#1f2838"), 1, Qt.PenStyle.DashLine)
        painter.setPen(pen_dash)
        painter.drawLine(int(p1_x), 15, int(p1_x), int(h - 25))
        painter.drawLine(int(p2_x), 15, int(p2_x), int(h - 25))

        painter.setFont(QFont("Segoe UI", 8, QFont.Weight.Bold))
        painter.setPen(QColor("#64748B"))
        painter.drawText(int(left_m + 4), h - 8, "P1")
        painter.drawText(int(p1_x + 4), h - 8, "P2")
        painter.drawText(int(p2_x + 4), h - 8, "P3")

        try:
            a_s = int(self.game.get("away_score", 0))
            h_s = int(self.game.get("home_score", 0))
        except ValueError:
            a_s, h_s = 0, 0

        is_live = self.game.get("is_live", False)
        is_final = self.game.get("is_final", False)
        has_score = (a_s > 0 or h_s > 0 or is_live or is_final)

        if not has_score:
            pen_flat = QPen(QColor("#334155"), 1.5)
            painter.setPen(pen_flat)
            painter.drawLine(int(left_m), int(mid_y), int(w - right_m), int(mid_y))
            painter.setFont(QFont("Segoe UI", 8, QFont.Weight.Medium))
            painter.setPen(QColor("#64748B"))
            painter.drawText(int(left_m + chart_w * 0.4), int(mid_y - 12), "Match Scheduled")
            return

        game_progress = 0.65 if is_live else 1.0
        active_w = chart_w * game_progress
        points = []
        step_x = 14.0
        curr_x = left_m
        t = 0.0

        seed = abs(hash(self.game.get("id", "hockey"))) % 100
        bias = (a_s - h_s) * 8.0

        while curr_x <= left_m + active_w:
            wave1 = math.sin(t * 0.5 + seed) * 22.0
            wave2 = math.cos(t * 0.9 + seed) * 12.0
            wave3 = math.sin(t * 1.8) * 8.0
            y_offset = (wave1 + wave2 + wave3) + bias
            y_clamped = max(-42.0, min(42.0, y_offset))
            points.append(QPointF(curr_x, mid_y - y_clamped))
            t += 0.8
            curr_x += step_x

        if not points:
            return

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
        grad.setColorAt(0.0, QColor(185, 28, 28, 170))
        grad.setColorAt(0.5, QColor(90, 18, 18, 90))
        grad.setColorAt(1.0, QColor(185, 28, 28, 170))
        painter.fillPath(fill_path, QBrush(grad))

        pen_wave = QPen(QColor("#E2E8F0"), 1.6)
        painter.setPen(pen_wave)
        painter.drawPath(curve_path)

        if game_progress < 1.0:
            pen_remain = QPen(QColor("#2c384c"), 1)
            painter.setPen(pen_remain)
            painter.drawLine(int(points[-1].x()), int(mid_y), int(w - right_m), int(mid_y))

        painter.setFont(QFont("Segoe UI Emoji", 10))
        if a_s > 0: painter.drawText(int(left_m + (active_w * 0.32) - 7), int(mid_y - 44), "🚨")
        if a_s > 1: painter.drawText(int(left_m + (active_w * 0.54) - 7), int(mid_y - 44), "🚨")
        if h_s > 0: painter.drawText(int(left_m + (active_w * 0.16) - 7), int(mid_y + 54), "🚨")
        if h_s > 1: painter.drawText(int(left_m + (active_w * 0.78) - 7), int(mid_y + 54), "🚨")


class GameCard(QFrame):
    def __init__(self, game, is_past_date=False, parent=None):
        super().__init__(parent)
        self.game = game
        self.is_past_date = is_past_date
        self.setObjectName("GameCard")
        self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))

        self.setStyleSheet("""
            QFrame#GameCard {
                background-color: #0e121a;
                border: 1px solid #18202e;
                border-left: 3px solid #10B981;
                border-radius: 8px;
            }
            QFrame#GameCard:hover {
                border-color: #26334a;
                border-left: 3px solid #34D399;
                background-color: #121722;
            }
        """)

        self.root_layout = QVBoxLayout(self)
        self.root_layout.setContentsMargins(16, 12, 16, 12)
        self.root_layout.setSpacing(8)

        main_row = QHBoxLayout()
        main_row.setSpacing(16)

        status_box = QVBoxLayout()
        status_box.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl_status = QLabel(f"● {game['status']}" if game["is_live"] else game["status"])
        lbl_status.setFont(QFont("Segoe UI", 8, QFont.Weight.Bold))
        
        is_final = game.get("is_final", False) or (game.get("status") == "FINAL")

        if game["is_live"]:
            lbl_status.setStyleSheet("""
                background-color: #064e3b; color: #34d399; 
                padding: 4px 10px; border-radius: 10px; border: 1px solid #059669;
            """)
        elif is_final:
            lbl_status.setStyleSheet("""
                background-color: #27272a; color: #A1A1AA; 
                padding: 4px 10px; border-radius: 10px;
            """)
        else:
            lbl_status.setStyleSheet("""
                background-color: #161e2b; color: #94a3b8; 
                padding: 4px 10px; border-radius: 10px;
            """)
        status_box.addWidget(lbl_status)
        main_row.addLayout(status_box)

        teams_layout = QHBoxLayout()
        teams_layout.setSpacing(12)

        away_badge = AsyncLogoLabel(32)
        away_badge.load_image(game.get("away_logo"))
        teams_layout.addWidget(away_badge)

        lbl_away = QLabel(game["away"])
        lbl_away.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
        lbl_away.setStyleSheet("color: #F8FAFC; border: none;")
        teams_layout.addWidget(lbl_away)

        lbl_vs = QLabel("vs")
        lbl_vs.setFont(QFont("Segoe UI", 10, QFont.Weight.Medium))
        lbl_vs.setStyleSheet("color: #475569; border: none; padding: 0 4px;")
        teams_layout.addWidget(lbl_vs)

        home_badge = AsyncLogoLabel(32)
        home_badge.load_image(game.get("home_logo"))
        teams_layout.addWidget(home_badge)

        lbl_home = QLabel(game["home"])
        lbl_home.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
        lbl_home.setStyleSheet("color: #F8FAFC; border: none;")
        teams_layout.addWidget(lbl_home)

        has_score = (game["away_score"] != "0" or game["home_score"] != "0" or game["is_live"] or is_final)
        if has_score:
            score_text = f"{game['away_score']} - {game['home_score']}"
            lbl_score = QLabel(score_text)
            lbl_score.setFont(QFont("Segoe UI", 13, QFont.Weight.Bold))
            lbl_score.setStyleSheet("color: #10B981; border: none; margin-left: 12px;")
            teams_layout.addWidget(lbl_score)

        teams_layout.addStretch()
        main_row.addLayout(teams_layout, stretch=1)

        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(8)

        is_live = game.get("is_live", False)
        kickoff_ts = game.get("kickoff_ts", 0)

        starts_soon = False
        if kickoff_ts > 0:
            time_until_start = kickoff_ts - datetime.now().timestamp()
            if time_until_start <= 900:
                starts_soon = True

        if not self.is_past_date and not is_final:
            if is_live or starts_soon:
                self.btn_watch = QPushButton("Watch ▾")
                self.btn_watch.setStyleSheet("""
                    QPushButton {
                        background-color: #10B981; color: #05070a;
                        font-weight: 800; font-size: 11px; padding: 7px 18px;
                        border-radius: 6px; border: none;
                    }
                    QPushButton:hover { background-color: #059669; color: #FFFFFF; }
                """)

                stream_menu = QMenu(self)
                act_vlc = QAction("▶ VLC Player (Direct HLS)", self)
                match_title = f"{game['away']} vs {game['home']}"
                act_vlc.triggered.connect(lambda checked, u=game["embed_url"], t=match_title: resolve_and_launch_vlc(u, t))
                stream_menu.addAction(act_vlc)

                act_embed = QAction("🌐 Matchora Web Embed", self)
                act_embed.triggered.connect(lambda checked, u=game["embed_url"]: open_url(u))
                stream_menu.addAction(act_embed)

                act_onhockey = QAction("🏒 OnHockey Match Stream", self)
                act_onhockey.triggered.connect(lambda checked: open_url("http://onhockey.tv/"))
                stream_menu.addAction(act_onhockey)

                self.btn_watch.setMenu(stream_menu)
                btn_layout.addWidget(self.btn_watch)
            else:
                btn_pre = QPushButton(f"Starts {game['status']}")
                btn_pre.setEnabled(False)
                btn_pre.setStyleSheet("""
                    QPushButton {
                        background-color: #121824; color: #64748B;
                        font-weight: 700; font-size: 11px; padding: 7px 14px;
                        border-radius: 6px; border: 1px solid #1c2638;
                    }
                """)
                btn_layout.addWidget(btn_pre)
        else:
            if game.get("recap_url"):
                btn_recap = QPushButton("▶ Recap")
                btn_recap.setStyleSheet("""
                    QPushButton {
                        background-color: #182234; color: #38BDF8; font-weight: 700;
                        font-size: 11px; padding: 6px 14px; border-radius: 6px; border: 1px solid #0284C7;
                    }
                    QPushButton:hover { background-color: #0284C7; color: #FFFFFF; }
                """)
                btn_recap.clicked.connect(lambda checked, u=game["recap_url"]: open_url(u))
                btn_layout.addWidget(btn_recap)

        main_row.addLayout(btn_layout)

        self.lbl_chevron = QLabel("▼")
        self.lbl_chevron.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
        self.lbl_chevron.setStyleSheet("color: #475569; border: none; padding-left: 4px;")
        main_row.addWidget(self.lbl_chevron)

        self.root_layout.addLayout(main_row)

        self.momentum_drawer = QFrame()
        self.momentum_drawer.setStyleSheet("""
            QFrame { background-color: #06080d; border: 1px solid #131924; border-radius: 6px; }
        """)
        drawer_layout = QVBoxLayout(self.momentum_drawer)
        drawer_layout.setContentsMargins(12, 10, 12, 8)
        drawer_layout.setSpacing(6)

        lbl_head = QLabel("MOMENTUM")
        lbl_head.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
        lbl_head.setStyleSheet("color: #94A3B8; letter-spacing: 0.5px; border: none;")
        drawer_layout.addWidget(lbl_head)

        canvas = MomentumWaveWidget(game)
        drawer_layout.addWidget(canvas)

        self.momentum_drawer.setVisible(False)
        self.root_layout.addWidget(self.momentum_drawer)

    def mousePressEvent(self, event):
        is_visible = self.momentum_drawer.isVisible()
        self.momentum_drawer.setVisible(not is_visible)
        self.lbl_chevron.setText("▲" if not is_visible else "▼")
        self.lbl_chevron.setStyleSheet("color: #10B981;" if not is_visible else "color: #475569;")
        super().mousePressEvent(event)


class LeagueHeaderBanner(QWidget):
    def __init__(self, title, parent=None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(4, 16, 4, 6)
        layout.setSpacing(10)
        lbl = QLabel(title.upper())
        lbl.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        lbl.setStyleSheet("color: #10B981; letter-spacing: 1px;")
        layout.addWidget(lbl)
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setStyleSheet("border: none; background-color: #161e2b; height: 1px;")
        layout.addWidget(line, stretch=1)


class HockeyHubBeta(QMainWindow):
    def __init__(self):
        super().__init__()
        global NETWORK_MANAGER
        NETWORK_MANAGER = QNetworkAccessManager(self)
        self.thread = None
        self.active_date = datetime.now().date()

        self.settings = QSettings("HLH", "HockeyLiveHub")
        self.init_timezone()

        self.setWindowTitle("Hockey Live Hub")
        self.resize(980, 720)
        self.setStyleSheet(STYLESHEET)
        self.init_icon()

        central = QWidget()
        central.setObjectName("CentralWidget")
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(24, 20, 24, 20)
        main_layout.setSpacing(16)

        header_bar = QHBoxLayout()
        header_bar.setSpacing(12)

        lbl_icon = QLabel("🏒")
        lbl_icon.setFont(QFont("Segoe UI", 15))
        header_bar.addWidget(lbl_icon)

        self.league_combo = QComboBox()
        self.league_combo.addItems(LEAGUE_CATEGORIES)
        self.league_combo.currentTextChanged.connect(self.load_schedule)
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

        header_bar.addSpacing(16)

        btn_prev = QPushButton("← Yesterday")
        btn_prev.setObjectName("NavBtn")
        btn_prev.clicked.connect(self.go_to_yesterday)
        header_bar.addWidget(btn_prev)

        self.btn_today = QPushButton("📅 Today")
        self.btn_today.setObjectName("TodayBtn")
        self.btn_today.clicked.connect(self.go_to_today)
        header_bar.addWidget(self.btn_today)

        btn_next = QPushButton("Tomorrow →")
        btn_next.setObjectName("NavBtn")
        btn_next.clicked.connect(self.go_to_tomorrow)
        header_bar.addWidget(btn_next)

        self.lbl_date_status = QLabel("")
        self.lbl_date_status.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        self.lbl_date_status.setStyleSheet("color: #10B981; margin-left: 12px;")
        header_bar.addWidget(self.lbl_date_status)

        header_bar.addStretch()
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

        self.refresh_timer = QTimer(self)
        self.refresh_timer.setInterval(30000)
        self.refresh_timer.timeout.connect(self.background_refresh)
        self.refresh_timer.start()

        self.update_date_label()
        self.load_schedule()

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

    def update_date_label(self):
        today = datetime.now().date()
        self.lbl_date_status.setText(self.active_date.strftime("%A, %b %d"))
        if self.active_date == today:
            self.btn_today.setObjectName("TodayBtn")
            self.btn_today.setStyleSheet("background-color: #10B981; color: #05070a; font-weight: 700;")
        else:
            self.btn_today.setObjectName("NavBtn")
            self.btn_today.setStyleSheet("background-color: #0f1624; color: #E2E8F0; border: 1px solid #1d2b42;")

    def go_to_yesterday(self):
        self.active_date -= timedelta(days=1)
        self.update_date_label()
        self.load_schedule()

    def go_to_today(self):
        self.active_date = datetime.now().date()
        self.update_date_label()
        self.load_schedule()

    def go_to_tomorrow(self):
        self.active_date += timedelta(days=1)
        self.update_date_label()
        self.load_schedule()

    def background_refresh(self):
        if self.active_date == datetime.now().date():
            self.load_schedule(silent=True)

    def clear_cards(self):
        while self.card_layout.count():
            item = self.card_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.setParent(None)
                widget.deleteLater()

    def load_schedule(self, silent=False):
        if self.thread is not None and self.thread.isRunning():
            return

        if not silent:
            self.clear_cards()

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

        if not games:
            lbl = QLabel(f"No games found on {self.active_date.strftime('%B %d')} for {self.league_combo.currentText()}.")
            lbl.setFont(QFont("Segoe UI", 12, QFont.Weight.Medium))
            lbl.setStyleSheet("color: #64748B; padding: 40px;")
            self.card_layout.addWidget(lbl)
            return

        is_all_hockey = (self.league_combo.currentText() == "All Hockey")
        is_past = (self.active_date < datetime.now().date())

        if is_all_hockey:
            grouped = {}
            for g in games:
                grouped.setdefault(g["league"], []).append(g)

            sorted_leagues = sorted(grouped.keys(), key=lambda l: LEAGUE_PRIORITY.get(l, 50))
            for league_name in sorted_leagues:
                league_games = grouped[league_name]
                self.card_layout.addWidget(LeagueHeaderBanner(f"{league_name} ({len(league_games)})"))
                for game in league_games:
                    self.card_layout.addWidget(GameCard(game, is_past_date=is_past))
        else:
            for game in games:
                self.card_layout.addWidget(GameCard(game, is_past_date=is_past))

        self.card_layout.addStretch()
        QTimer.singleShot(50, lambda: scroll_bar.setValue(current_scroll))


if __name__ == "__main__":
    app = QApplication(sys.argv)
    win = HockeyHubBeta()
    win.show()
    sys.exit(app.exec())