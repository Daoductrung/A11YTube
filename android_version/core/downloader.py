import yt_dlp
import os
from .settings import config_get
from .utils import get_cookie_opts, check_bot_error

class Downloader:
    def __init__(self, url, path, format_option, progress_callback=None, completion_callback=None):
        self.url = url
        self.path = path
        self.format_option = format_option # 0=Video, 1=M4A, 2=MP3
        self.progress_callback = progress_callback
        self.completion_callback = completion_callback
        self.errors = []

    def get_format_string(self):
        if self.format_option == 0: # Video
            return "bestvideo+bestaudio/best"
        else: # Audio
            return "bestaudio/best"

    def progress_hook(self, d):
        if d['status'] == 'downloading':
            total = d.get('total_bytes') or d.get('total_bytes_estimate') or 0
            downloaded = d.get('downloaded_bytes', 0)
            if total > 0:
                percent = (downloaded / total)
                if self.progress_callback:
                    self.progress_callback(percent, d.get('speed', 0))
        elif d['status'] == 'finished':
            if self.progress_callback:
                self.progress_callback(1.0, 0)

    def download(self):
        try:
            if not os.path.exists(self.path):
                os.makedirs(self.path)

            opts = {
                'outtmpl': os.path.join(self.path, '%(title)s.%(ext)s'),
                'quiet': True,
                'format': self.get_format_string(),
                'progress_hooks': [self.progress_hook],
                'ignoreerrors': True,
                'nooverwrites': True,
                # On Android, ffmpeg might not be available or needs specific path.
                # Flet/Python-for-Android usually bundles ffmpeg or we might need to rely on static build.
                # For now, we assume it's in path or we don't use post-processing if missing.
            }
            opts.update(get_cookie_opts())

            # Post-processors for Audio
            if self.format_option in [1, 2]:
                codec = 'mp3' if self.format_option == 2 else 'm4a'
                # Check if ffmpeg is available?
                # If not, this will fail.
                # We can try to rely on Android ffmpeg wrapper if needed, but standard python uses subprocess.
                opts['postprocessors'] = [{
                    'key': 'FFmpegExtractAudio',
                    'preferredcodec': codec,
                }]

            with yt_dlp.YoutubeDL(opts) as ydl:
                ydl.download([self.url])

            if self.completion_callback:
                self.completion_callback(True, None)

        except Exception as e:
            if self.completion_callback:
                self.completion_callback(False, str(e))

def start_download(url, path, format_option, on_progress=None, on_complete=None):
    # Wrapper to run in thread ideally, but caller handles threading in Flet
    dl = Downloader(url, path, format_option, on_progress, on_complete)
    dl.download()
