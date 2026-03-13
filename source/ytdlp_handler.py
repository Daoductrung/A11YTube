import os
import sys
import subprocess
import urllib.request
import threading
from paths import settings_path

def get_ytdlp_path():
    if sys.platform.startswith('win'):
        return os.path.join(settings_path, 'yt-dlp.exe')
    else:
        return os.path.join(settings_path, 'yt-dlp')

def is_ytdlp_downloaded():
    path = get_ytdlp_path()
    return os.path.exists(path) and os.path.getsize(path) > 1000000

def download_ytdlp(progress_callback=None):
    path = get_ytdlp_path()
    if sys.platform.startswith('win'):
        url = "https://github.com/yt-dlp/yt-dlp/releases/latest/download/yt-dlp.exe"
    elif sys.platform.startswith('darwin'):
        url = "https://github.com/yt-dlp/yt-dlp/releases/latest/download/yt-dlp_macos"
    else:
        url = "https://github.com/yt-dlp/yt-dlp/releases/latest/download/yt-dlp"

    os.makedirs(os.path.dirname(path), exist_ok=True)

    def report_hook(count, block_size, total_size):
        if progress_callback and total_size > 0:
            percent = int(count * block_size * 100 / total_size)
            percent = min(percent, 100)
            progress_callback(percent)

    urllib.request.urlretrieve(url, path, reporthook=report_hook)

    if not sys.platform.startswith('win'):
        os.chmod(path, 0o755)

def update_ytdlp():
    path = get_ytdlp_path()
    if os.path.exists(path):
        try:
            subprocess.run([path, "-U"], check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except Exception:
            pass

def manual_update_ytdlp(parent_window):
    import wx
    path = get_ytdlp_path()
    if os.path.exists(path):
        try:
            kwargs = {}
            if os.name == 'nt':
                kwargs['creationflags'] = subprocess.CREATE_NO_WINDOW
            result = subprocess.run([path, "-U"], check=False, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, **kwargs)
            out = result.stdout.strip()
            wx.CallAfter(wx.MessageBox, out if out else _("yt-dlp updated successfully."), _("yt-dlp Update"), parent=parent_window)
        except Exception as e:
            wx.CallAfter(wx.MessageBox, _("Failed to update yt-dlp: {}").format(e), _("Error"), style=wx.ICON_ERROR, parent=parent_window)
    else:
        wx.CallAfter(wx.MessageBox, _("yt-dlp is not installed."), _("Error"), style=wx.ICON_ERROR, parent=parent_window)

def ensure_ytdlp_exists(splash=None):
    if not is_ytdlp_downloaded():
        if splash:
            import wx
            wx.CallAfter(splash.update_progress, 10, _("Downloading yt-dlp core..."))
        download_ytdlp()

def update_ytdlp_background():
    Thread = threading.Thread(target=update_ytdlp)
    Thread.daemon = True
    Thread.start()
