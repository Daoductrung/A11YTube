import re
import datetime
from .settings import config_get
from .paths import get_data_dir, COOKIES_FILE
import os

YT_LINK_PATTERN = re.compile(r"^((?:https?:)?\/\/)?((?:www|m)\.)?((?:youtube\.com|youtu.be))(\/(?:[\w\-]+\?v=|embed\/|v\/)?)([\w\-]+)(\S+)?$")

class Stream:
    def __init__(self, url, title, extension=None, resolution=None, http_headers=None, duration=0):
        self.url = url
        self.title = title
        self.extension = extension
        self.resolution = resolution
        self.http_headers = http_headers
        self.duration = duration

def get_cookie_opts():
    path = os.path.join(get_data_dir(), COOKIES_FILE)
    if os.path.exists(path):
        return {'cookiefile': path}
    return {}

def youtube_regexp(string):
    return YT_LINK_PATTERN.search(string)

def time_formatting(t):
    try:
        total_seconds = int(float(t))
    except (ValueError, TypeError):
        return t

    m, s = divmod(total_seconds, 60)
    h, m = divmod(m, 60)

    parts = []
    if h > 0: parts.append(f"{h}h")
    parts.append(f"{m}m")
    parts.append(f"{s}s")
    return " ".join(parts)

def format_relative_time(date_str):
    try:
        if not date_str or len(date_str) != 8:
            return ""

        year = int(date_str[0:4])
        month = int(date_str[4:6])
        day = int(date_str[6:8])

        uploaded = datetime.datetime(year, month, day)
        now = datetime.datetime.now()

        diff = now - uploaded
        days = diff.days

        if days == 0: return "Today"
        elif days == 1: return "Yesterday"
        elif days < 30: return f"{days} days ago"
        elif days < 365: return f"{int(days/30)} months ago"
        else: return f"{int(days/365)} years ago"
    except Exception:
        return ""

def check_bot_error(error_msg):
    error_msg = str(error_msg).lower()
    keywords = [
        "sign in to confirm your age",
        "verify your age",
        "sign in to confirm you're not a bot",
        "http error 403",
        "private video",
        "members-only"
    ]
    for k in keywords:
        if k in error_msg:
            return True
    return False

# Function to get video stream - Simplified for direct extraction without GUI dependencies
def get_video_info(url):
    import yt_dlp

    ydl_opts = {
        'format': 'best',
        'quiet': True,
        'no_warnings': True,
        'noplaylist': True
    }
    ydl_opts.update(get_cookie_opts())

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            stream_url = info.get('manifest_url') or info.get('url')

            s = Stream(
                stream_url,
                info.get('title', 'Unknown'),
                info.get('ext'),
                info.get('resolution'),
                info.get('http_headers'),
                info.get('duration', 0)
            )
            return s
    except Exception as e:
        print(f"Extraction error: {e}")
        return None
