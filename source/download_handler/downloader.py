
# import yt_dlp as youtube_dl moved to local scopes

import wx
from settings_handler import config_get



class MyLogger:
	def __init__(self):
		self.errors = []
	def debug(self, msg):
		pass
	def warning(self, msg):
		pass
	def error(self, msg):
		self.errors.append(msg)
		print(msg)

class Downloader:
	def __init__(self, url, path, downloading_format, monitor, monitor1, convert=False, folder=False, use_cookies=False, noplaylist=True):
		# initializing class properties
		self.url = url
		self.path = path
		self.downloading_format = downloading_format
		self.monitor = monitor 
		self.monitor1 = monitor1
		self.convert = convert
		self.folder = folder
		self.use_cookies = use_cookies
		self.noplaylist = noplaylist
		self.logger = MyLogger()

	# progress bar updator
	def get_proper_count(self, number):
		length = len(str(int(number)))
		if length <= 3:
			return (number, _("Bytes"))
		elif length >=4 and length <7:
			return (round(number/1024, 2), _("KB"))
		elif length >=7 and length <10:
			return (round(number/1024**2, 2), _("MB"))
		elif length >= 10 and length < 13:
			return (round(number/1024**3, 2), _("GB"))
		elif length >= 13:
			return (round(number/1024**4, 2), _("TB"))
	def get_quality(self):
		qualities = {
			0: '96',
			1: '128',
			2: '192',
			3: '256',
			4: '320'
		}
		return qualities[int(config_get("conversion"))]
	def my_hook(self, data):
		if data['status'] == 'finished':
			return
		total = data.get("total_bytes", data.get("total_bytes_estimate", 0))
		if total == 0 or total is None:
			percent = 0
		else:
			percent = (data["downloaded_bytes"] / total) * 100
		try:
			percent = int(percent) # converted to integer
		except ValueError:
			percent = 0
		total = self.get_proper_count(total)
		downloaded = self.get_proper_count(data["downloaded_bytes"])
		remaining = self.get_proper_count(data.get("total_bytes", data.get("total_bytes_estimate"))-data["downloaded_bytes"])
		speed = data['speed'] if data['speed'] else 0
		speed = self.get_proper_count(int(speed))
		info = [_("Percentage: {}%").format(percent), _("Total Size: {} {}").format(total[0], total[1]), _("Downloaded: {} {}").format(downloaded[0], downloaded[1]), _("Remaining: {} {}").format(remaining[0], remaining[1]), _("Speed: {} {}").format(speed[0], speed[1])]
		# updating controls 
		def safe_update(p, i):
			try:
				self.monitor.SetValue(p)
				for index, value in zip(range(0, len(self.monitor1.Strings)), i):
					self.monitor1.SetString(index, value)
			except RuntimeError:
				# Window likely destroyed
				pass
		wx.CallAfter(safe_update, percent, info)
	def get_title(self):
		if not self.folder:
			return None
		import yt_dlp as youtube_dl
		try:
			ydl_opts = {
				'quiet': True,
				'extract_flat': 'in_playlist', # fast extraction
				'ignoreerrors': True,
			}
			from utiles import get_cookie_opts, get_ffmpeg_path
			ydl_opts.update(get_cookie_opts())
			ydl_opts['ffmpeg_location'] = get_ffmpeg_path()
			with youtube_dl.YoutubeDL(ydl_opts) as ydl:
				info = ydl.extract_info(self.url, download=False)
				return info.get('title')
		except Exception:
			return None

	def download(self):
		import yt_dlp as youtube_dl
		# Use os.path.join for cross-platform compatibility
		import os
		tmpl = os.path.join(self.path, "%(title)s.%(ext)s")
		
		# If it's a playlist/folder, we try to put it in a subfolder
		title = self.get_title()
		if title:
			tmpl = os.path.join(self.path, title, "%(title)s.%(ext)s")

		download_options = {
			'outtmpl': tmpl,
			'quiet': True,
			'format': self.downloading_format,
			"continuedl": True,
			"noplaylist": self.noplaylist,
			"youtube_include_dash_manifest": False,
			'progress_hooks': [self.my_hook],
			'ignoreerrors': True,
			'nooverwrites': True,
			'logger': self.logger
		}
		
		from utiles import get_ffmpeg_path
		if self.use_cookies:
			from utiles import get_cookie_opts
			download_options.update(get_cookie_opts())
			
		download_options['ffmpeg_location'] = get_ffmpeg_path()
			
		if self.convert:
			download_options['postprocessors'] = [{
				"key": "FFmpegExtractAudio",
				'preferredcodec': 'mp3',
				'preferredquality': self.get_quality(),
			}]

		with youtube_dl.YoutubeDL(download_options) as youtubeDownloader:
			if isinstance(self.url, list):
				youtubeDownloader.download(self.url)
			else:
				youtubeDownloader.download([self.url])

def downloadAction(url, path, dlg, downloading_format, monitor, monitor1, convert=False, folder=False, noplaylist=True, silent=False):
	# We start with use_cookies=False
	def run_downloader(use_cookies):
		downloader = Downloader(url, path, downloading_format, monitor, monitor1, convert=convert, folder=folder, use_cookies=use_cookies, noplaylist=noplaylist)
		downloader.download()
		return downloader

	wx.CallAfter(dlg.Show)
	
	def attempt(at, use_cookies=False):
		try:
			downloader = run_downloader(use_cookies)
			# Check for internal errors caught by logger
			if len(downloader.logger.errors) > 0:
				# Analyze errors
				from utiles import check_bot_error
				for err in downloader.logger.errors:
					if check_bot_error(err):
						# If we haven't tried cookies yet, try now
						if not use_cookies:
							print("Auth error detected in download, retrying with cookies...")
							return attempt(at, use_cookies=True)
						else:
							# Already tried with cookies, fatal error
							from utiles import get_cookie_opts
							if not get_cookie_opts():
								msg = _("This video is age restricted or requires a valid cookies.txt file to play.")
							else:
								msg = _("Authentication failed. Your cookies.txt might be expired or invalid. Please delete and re-import a fresh one.")
							wx.CallAfter(wx.MessageBox, msg, _("Authentication Error"), style=wx.ICON_ERROR, parent=dlg)
							wx.CallAfter(dlg.Destroy)
							return False
				
				# Generic errors
				wx.CallAfter(wx.MessageBox, _("Download completed, but {} videos failed to download.").format(len(downloader.logger.errors)), _("Completed with Errors"), parent=dlg, style=wx.ICON_WARNING)
				wx.CallAfter(dlg.Destroy)
				return False

			if not silent:
				wx.CallAfter(wx.MessageBox, _("Download completed successfully"), _("Success"), parent=dlg)
			wx.CallAfter(dlg.Destroy)
			return True

		except Exception as e:
			import yt_dlp
			# If yt-dlp raised an exception directly (not caught exclusively by logger)
			if isinstance(e, yt_dlp.utils.DownloadError):
				from utiles import check_bot_error
				if check_bot_error(str(e)):
					if not use_cookies:
						print("Auth exception detected, retrying with cookies...")
						return attempt(at, use_cookies=True)
					else:
						from utiles import get_cookie_opts
						if not get_cookie_opts():
							msg = _("This video is age restricted or requires a valid cookies.txt file to play.")
						else:
							msg = _("Authentication failed. Your cookies.txt might be expired or invalid. Please delete and re-import a fresh one.")
						wx.CallAfter(wx.MessageBox, msg, _("Authentication Error"), style=wx.ICON_ERROR, parent=dlg)
						wx.CallAfter(dlg.Destroy)
						return False

				if at < 3:
					return attempt(at+1, use_cookies)
				else:
					wx.CallAfter(wx.MessageBox, _("Invalid link. Please try another link, or check your internet connection."), _("Error"), style=wx.ICON_ERROR, parent=dlg)
					wx.CallAfter(dlg.Destroy)
					return False
			else:
				if at < 3: return attempt(at+1, use_cookies)
				else: 
					wx.CallAfter(wx.MessageBox, str(e), _("Error"), parent=dlg)
					wx.CallAfter(dlg.Destroy)
					return False
	
	attempt(0, False)
