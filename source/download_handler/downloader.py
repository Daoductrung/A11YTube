import wx
import os
import subprocess
import re
from settings_handler import config_get
from utiles import run_ytdlp_json, get_cookie_opts_args, get_ffmpeg_path

class Downloader:
	def __init__(self, url, path, downloading_format, monitor, monitor1, convert=False, folder=False, use_cookies=False, noplaylist=True):
		self.url = url
		self.path = path
		self.downloading_format = downloading_format
		self.monitor = monitor 
		self.monitor1 = monitor1
		self.convert = convert
		self.folder = folder
		self.use_cookies = use_cookies
		self.noplaylist = noplaylist
		self.errors = []
		self.process = None

	def get_quality(self):
		qualities = {0: '96', 1: '128', 2: '192', 3: '256', 4: '320'}
		return qualities[int(config_get("conversion"))]

	def get_title(self):
		if not self.folder: return None
		try:
			info = run_ytdlp_json(self.url, extract_flat=True, cookies=self.use_cookies)
			return info.get('title')
		except Exception:
			return None

	def download(self):
		from ytdlp_handler import get_ytdlp_path
		exe = get_ytdlp_path()
		
		tmpl = os.path.join(self.path, "%(title)s.%(ext)s")
		title = self.get_title()
		if title: tmpl = os.path.join(self.path, title, "%(title)s.%(ext)s")

		cmd = [
			exe,
			'--newline',
			'--quiet',
			'--no-warnings',
			'--ignore-errors',
			'--no-overwrites',
			'-f', self.downloading_format,
			'-o', tmpl,
			'--ffmpeg-location', get_ffmpeg_path()
		]

		if self.noplaylist: cmd.append('--no-playlist')
		if self.use_cookies: cmd.extend(get_cookie_opts_args())
		
		if self.convert:
			codec_idx = config_get("defaultaudio")
			codec = 'mp3' if str(codec_idx) == '1' else 'm4a'
			cmd.extend(['--extract-audio', '--audio-format', codec, '--audio-quality', self.get_quality()])
		else:
			cmd.extend(['--merge-output-format', 'mp4'])

		if isinstance(self.url, list): cmd.extend(self.url)
		else: cmd.append(self.url)

		kwargs = {}
		if os.name == 'nt':
			kwargs['creationflags'] = subprocess.CREATE_NO_WINDOW
			kwargs['startupinfo'] = subprocess.STARTUPINFO()
			kwargs['startupinfo'].dwFlags |= subprocess.STARTF_USESHOWWINDOW

		self.process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1, **kwargs)

		prog_regex = re.compile(r'\[download\]\s+([0-9\.]+)\%\s+of\s+([~0-9\.\w]+)\s+at\s+([0-9\.\w]+)\/s\s+ETA\s+([0-9:]+)')
		err_regex = re.compile(r'ERROR:\s+(.*)')

		for line in iter(self.process.stdout.readline, ''):
			line = line.strip()
			if not line: continue

			m = prog_regex.search(line)
			if m:
				pct = float(m.group(1))
				total = m.group(2)
				speed = m.group(3)
				eta = m.group(4)

				info = [
					_("Percentage: {}%").format(int(pct)),
					_("Total Size: {}").format(total),
					_("Downloaded: {}").format("N/A"),
					_("ETA: {}").format(eta),
					_("Speed: {}").format(speed)
				]

				def safe_update(p, i):
					try:
						self.monitor.SetValue(p)
						for index, value in zip(range(0, len(self.monitor1.Strings)), i):
							self.monitor1.SetString(index, value)
					except RuntimeError:
						pass
				wx.CallAfter(safe_update, int(pct), info)

			e = err_regex.search(line)
			if e:
				self.errors.append(e.group(1))

		self.process.wait()

def downloadAction(url, path, dlg, downloading_format, monitor, monitor1, convert=False, folder=False, noplaylist=True, silent=False):
	def run_downloader(use_cookies):
		downloader = Downloader(url, path, downloading_format, monitor, monitor1, convert=convert, folder=folder, use_cookies=use_cookies, noplaylist=noplaylist)
		downloader.download()
		return downloader

	wx.CallAfter(dlg.Show)
	
	def attempt(at, use_cookies=False):
		downloader = run_downloader(use_cookies)

		if len(downloader.errors) > 0:
			from utiles import check_bot_error, get_cookie_opts_args
			for err in downloader.errors:
				if check_bot_error(err):
					if not use_cookies:
						print("Auth error detected in download, retrying with cookies...")
						return attempt(at, use_cookies=True)
					else:
						if not get_cookie_opts_args():
							msg = _("This video is age restricted or requires a valid cookies.txt file to play.")
						else:
							msg = _("Authentication failed. Your cookies.txt might be expired or invalid. Please delete and re-import a fresh one.")
						wx.CallAfter(wx.MessageBox, msg, _("Authentication Error"), style=wx.ICON_ERROR, parent=dlg)
						wx.CallAfter(dlg.Destroy)
						return False

			wx.CallAfter(wx.MessageBox, _("Download completed, but {} videos failed to download.").format(len(downloader.errors)), _("Completed with Errors"), parent=dlg, style=wx.ICON_WARNING)
			wx.CallAfter(dlg.Destroy)
			return False

		if not silent:
			wx.CallAfter(wx.MessageBox, _("Download completed successfully"), _("Success"), parent=dlg)
		wx.CallAfter(dlg.Destroy)
		return True
	
	attempt(0, False)
