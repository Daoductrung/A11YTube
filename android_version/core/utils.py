import re
import datetime
from .settings import config_get
from .paths import get_data_dir, COOKIES_FILE
import os
import subprocess

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

def detect_silence(url, headers=None, duration=0):
    """
    Analyzes audio URL for silence.
    Returns (start_time, stop_time) in seconds.
    start_time: Time when first non-silence audio begins.
    stop_time: Time when last non-silence audio ends (or None if no trailing silence).
    """
    try:
        # Check ffmpeg availability
        # On Android, ffmpeg path might be specific or bundled.
        # We assume 'ffmpeg' is in PATH or wrapped by Python-for-Android recipe.
        ffmpeg = 'ffmpeg'

        # Probing Function
        def probe_duration(url, headers):
            try:
                cmd = [ffmpeg]
                if headers:
                    header_args = ""
                    if 'Cookie' in headers:
                        header_args += f"Cookie: {headers['Cookie']}\r\n"
                    if 'User-Agent' in headers:
                        header_args += f"User-Agent: {headers['User-Agent']}\r\n"
                    if header_args:
                        cmd.extend(['-headers', header_args])

                cmd.extend(['-i', url, '-f', 'null', '-'])

                # Use standard Popen, no startupinfo needed for Linux/Android base usually
                process = subprocess.Popen(
                    cmd,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.PIPE,
                    universal_newlines=True,
                    encoding='utf-8',
                    errors='ignore'
                )
                _, stderr = process.communicate(timeout=10)
                match = re.search(r'Duration: (\d{2}):(\d{2}):(\d{2}\.\d+)', stderr)
                if match:
                    h, m, s = match.groups()
                    dur = int(h)*3600 + int(m)*60 + float(s)
                    return dur
                return 0
            except Exception:
                return 0

        # If Duration is missing or 0, PROBE IT
        if not duration or duration <= 0:
            duration = probe_duration(url, headers)

        # Helper parser
        def parse_silence(stderr_output, offset=0, segment_duration=60):
            start_time = 0.0
            stop_time = None

            silence_starts = []
            silence_ends = []

            for line in stderr_output.splitlines():
                if "silencedetect" in line:
                    if "silence_end" in line:
                        match = re.search(r'silence_end: ([\d\.]+)', line)
                        if match:
                            silence_ends.append(float(match.group(1)))
                    elif "silence_start" in line:
                        match = re.search(r'silence_start: ([\d\.]+)', line)
                        if match:
                            silence_starts.append(float(match.group(1)))

            # Logic:
            if silence_ends and silence_ends[0] < 15:
                start_time = silence_ends[0]

            if silence_starts:
                last_silence_start = silence_starts[-1]
                is_final = True
                for end in silence_ends:
                    if end > last_silence_start:
                        # If end is near segment end, ignore it (it's end of clip)
                        if end >= (segment_duration - 1.0):
                            continue
                        is_final = False
                        break
                if is_final:
                    stop_time = last_silence_start + offset

            return (start_time, stop_time)

        # Define Helper to run scan
        def scan_segment(start_offset, scan_duration):
            cmd = [ffmpeg]
            if headers:
                header_args = ""
                if 'Cookie' in headers:
                    header_args += f"Cookie: {headers['Cookie']}\r\n"
                if 'User-Agent' in headers:
                    header_args += f"User-Agent: {headers['User-Agent']}\r\n"
                if header_args:
                    cmd.extend(['-headers', header_args])

            # seek to offset
            if start_offset > 0:
                cmd.extend(['-ss', str(start_offset)])

            cmd.extend([
                '-i', url,
                '-t', str(scan_duration),
                '-af', 'silencedetect=noise=-45dB:d=0.2',
                '-f', 'null',
                '-'
            ])

            process = subprocess.Popen(
                cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
                universal_newlines=True,
                encoding='utf-8',
                errors='ignore'
            )
            try:
                _, stderr = process.communicate(timeout=30)
                return stderr
            except subprocess.TimeoutExpired:
                process.kill()
                return ""

        # Default values
        final_start = 0.0
        final_stop = None

        # Strategy: Always use dual-pass scan for efficiency.
        # 1. Check Start: 0-60s (or less if duration < 60)
        # 2. Check End: (Duration-60s)-Duration (if applicable)

        # Check Start
        scan_len = 60
        if duration and duration < 60:
            scan_len = duration

        out_start = scan_segment(0, scan_len)
        final_start, _ = parse_silence(out_start, 0, scan_len)

        # Check End (Only if duration is long enough to have a distinct end segment)
        if duration and duration > 60:
            offset = duration - 60
            # Ensure offset doesn't overlap weirdly
            out_end = scan_segment(offset, 60)
            _, final_stop = parse_silence(out_end, offset, 60)
        elif duration:
            # Short video < 60s
            _, final_stop = parse_silence(out_start, 0, scan_len)

        return final_start, final_stop

    except Exception as e:
        print(f"Error detecting silence: {e}")
        return 0.0, None

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
