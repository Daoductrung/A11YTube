import re
import json
import subprocess
from threading import Thread
from settings_handler import config_get, config_set

import wx
import application
import os
from paths import settings_path

class BotDetectionError(RuntimeError):
	pass

def get_ffmpeg_path():
	import sys
	if getattr(sys, 'frozen', False):
		if hasattr(sys, '_MEIPASS'):
			base_path = sys._MEIPASS
		else:
			base_path = os.path.dirname(sys.executable)
	else:
		base_path = os.path.dirname(os.path.abspath(__file__))
	ffmpeg_path = os.path.join(base_path, 'ffmpeg.exe')
	if os.path.exists(ffmpeg_path):
		return ffmpeg_path
	return 'ffmpeg'

class Stream:
	def __init__(self, url, title, extension=None, resolution=None, http_headers=None, secondary_audios=None, audio_url=None):
		self.url = url
		self.title = title
		self.extension = extension
		self.resolution = resolution
		self.http_headers = http_headers
		self.secondary_audios = secondary_audios or []
		self.audio_url = audio_url
		self.duration = 0

def get_cookie_opts_args():
	path = os.path.join(settings_path, "cookies.txt")
	if os.path.exists(path):
		return ['--cookies', path]
	if os.path.exists("cookies.txt"):
		return ['--cookies', "cookies.txt"]
	return []

def run_ytdlp_json(url, format_str=None, extract_flat=False, cookies=False, extra_args=None):
	from ytdlp_handler import get_ytdlp_path
	exe = get_ytdlp_path()
	cmd = [exe, '-J', '--no-warnings', '--quiet']
	if format_str:
		cmd.extend(['-f', format_str])
	if extract_flat:
		cmd.append('--flat-playlist')
	if cookies:
		cmd.extend(get_cookie_opts_args())
	if extra_args:
		cmd.extend(extra_args)
	cmd.append(url)

	try:
		kwargs = {}
		if os.name == 'nt':
			kwargs['creationflags'] = subprocess.CREATE_NO_WINDOW
		result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=True, **kwargs)
		output = result.stdout.strip()
		if output:
			return json.loads(output)
		return {}
	except subprocess.CalledProcessError as e:
		err = e.stderr
		if check_bot_error(err):
			raise BotDetectionError(_("Authentication Error: ") + err)
		raise RuntimeError(_("yt-dlp error: ") + err)

def extract_secondary_audios(info):
	formats = info.get('formats', [])
	results = []
	for f in formats:
		if f.get('vcodec') == 'none' and f.get('acodec') != 'none':
			url = f.get('url')
			if not url: continue
			lang = f.get('language', '')
			note = f.get('format_note', '') or ''
			abr = f.get('abr', 0)
			
			label_parts = []
			if lang: label_parts.append(lang)
			if note: label_parts.append(note)
			if abr: label_parts.append(f"{int(abr)}k")
			
			display = "Audio" if not label_parts else " - ".join(label_parts)
			display += f" [{f.get('format_id')}]"

			track = {
				'url': url,
				'label': display,
				'language': lang,
				'abr': abr
			}
			results.append(track)
	return results

def fetch_audio_tracks(url):
	try:
		info = run_ytdlp_json(url, extra_args=['--audio-multistreams', '--no-playlist'])
		return extract_secondary_audios(info)
	except BotDetectionError:
		try:
			info = run_ytdlp_json(url, cookies=True, extra_args=['--audio-multistreams', '--no-playlist'])
			return extract_secondary_audios(info)
		except Exception:
			return []
	except Exception:
		return []

def get_audio_stream(url):
	format_str = 'bestaudio/best'
	try:
		info = run_ytdlp_json(url, format_str=format_str, extra_args=['--no-playlist'])
	except BotDetectionError as e:
		if not get_cookie_opts_args():
			raise BotDetectionError(_("This video is age restricted or requires a valid cookies.txt file to play."))
		try:
			info = run_ytdlp_json(url, format_str=format_str, cookies=True, extra_args=['--no-playlist'])
		except BotDetectionError:
			raise BotDetectionError(_("Authentication failed. Your cookies.txt might be expired or invalid. Please delete and re-import a fresh one."))

	stream_url = info.get('manifest_url') or info.get('url')
	s = Stream(stream_url, info.get('title', 'Unknown'), info.get('ext'), None, info.get('http_headers'))
	s.duration = info.get('duration', 0)
	return s

def get_video_stream(url):
	format_str = '22/18/best[ext=mp4]/best'
	try:
		info = run_ytdlp_json(url, format_str=format_str, extra_args=['--no-playlist'])
	except BotDetectionError as e:
		if not get_cookie_opts_args():
			raise BotDetectionError(_("This video is age restricted or requires a valid cookies.txt file to play."))
		try:
			info = run_ytdlp_json(url, format_str='best', cookies=True, extra_args=['--no-playlist'])
		except BotDetectionError:
			raise BotDetectionError(_("Authentication failed. Your cookies.txt might be expired or invalid. Please delete and re-import a fresh one."))

	stream_url = info.get('manifest_url') or info.get('url')
	s = Stream(stream_url, info.get('title', 'Unknown'), info.get('ext'), info.get('resolution'), info.get('http_headers'))
	s.duration = info.get('duration', 0)
	return s

def time_formatting(t):
	try:
		total_seconds = int(float(t))
	except (ValueError, TypeError):
		return t

	m, s = divmod(total_seconds, 60)
	h, m = divmod(m, 60)

	def minute(m):
		if m == 1: return _("one minute")
		elif m == 2: return _("two minutes")
		else: return _("{} minutes").format(m)
	def second(s):
		if s == 1: return _("one second")
		elif s == 2: return _("two seconds")
		else: return _("{} seconds").format(s)
	def hour(h):
		if h == 1: return _("one hour")
		elif h == 2: return _("two hours")
		else: return _("{} hours").format(h)

	parts = []
	if h > 0: parts.append(hour(h))
	if m > 0: parts.append(minute(m))
	if s > 0 or not parts: parts.append(second(s))

	if len(parts) == 1: return parts[0]
	elif len(parts) == 2: return _("{} and {}").format(parts[0], parts[1])
	elif len(parts) >= 3: return _("{} and {} and {}").format(parts[0], parts[1], parts[2])

def format_relative_time(date_str):
	import datetime
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
		
		if days < 0: return ""
		if days == 0: return _("Today")
		elif days == 1: return _("Yesterday")
		elif days < 30: return _("{} days ago").format(days)
		elif days < 365:
			months = int(days / 30)
			if months <= 1: return _("1 month ago")
			else: return _("{} months ago").format(months)
		else:
			years = int(days / 365)
			if years <= 1: return _("1 year ago")
			else: return _("{} years ago").format(years)
	except Exception:
		return ""

YT_LINK_PATTERN = re.compile(r"^((?:https?:)?\/\/)?((?:www|m)\.)?((?:youtube\.com|youtu.be))(\/(?:[\w\-]+\?v=|embed\/|v\/)?)([\w\-]+)(\S+)?$")

def youtube_regexp(string):
	return YT_LINK_PATTERN.search(string)

def direct_download(option, url, dlg, download_type="video", path=config_get("path")):
	from download_handler.downloader import downloadAction
	if option == 0:
		format = "bestvideo+bestaudio/best"
		convert = False
	else:
		format = "bestaudio/best"
		convert = True
		if option == 2:
			config_set("defaultaudio", "1")
		else:
			config_set("defaultaudio", "0")
	folder = False if download_type == "video" else True
	noplaylist = False if folder else True
	trd = Thread(target=downloadAction, args=[url, path, dlg, format, dlg.gaugeProgress, dlg.textProgress, convert, folder, noplaylist])
	trd.daemon = True
	trd.start()

def check_for_updates(quiet=False):
	url = "https://raw.githubusercontent.com/Daoductrung/A11YTube/master/update_info.json"
	try:
		import requests
		r = requests.get(url, timeout=5)
		if r.status_code != 200:
			if not quiet:
				wx.CallAfter(wx.MessageBox, _("An error occurred while connecting to the update service. Please check your internet connection and try again."), _("Error"), parent=wx.GetApp().GetTopWindow(), style=wx.ICON_ERROR)
			return
		info = r.json()
		if application.version != info["version"]:
			def ask_update():
				message = wx.MessageBox(_("A new update is available. Do you want to download it now?"), _("New Update"), parent=wx.GetApp().GetTopWindow(), style=wx.YES_NO)
				if message == wx.YES:
					from gui.update_dialog import UpdateDialog
					UpdateDialog(wx.GetApp().GetTopWindow(), info["url"])
			wx.CallAfter(ask_update)
			return
		if not quiet:
			wx.CallAfter(wx.MessageBox, _("You are running the latest version."), _("No Update"), parent=wx.GetApp().GetTopWindow())
	except Exception:
		if not quiet:
			wx.CallAfter(wx.MessageBox, _("An error occurred while connecting to the update service. Please check your internet connection and try again."), _("Error"), parent=wx.GetApp().GetTopWindow(), style=wx.ICON_ERROR)

def check_bot_error(error_msg):
	ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
	error_msg = ansi_escape.sub('', str(error_msg))
	error_msg = error_msg.replace("’", "'").replace("‘", "'").replace("“", '"').replace("”", '"').lower()
	keywords = ["sign in to confirm your age", "verify your age", "sign in to confirm you're not a bot", "http error 403", "private video", "members-only", "bot"]
	for k in keywords:
		if k in error_msg:
			return True
	return False

def force_taskbar_style(window):
	try:
		import ctypes
		hwnd = window.GetHandle()
		style = ctypes.windll.user32.GetWindowLongW(hwnd, -20)
		style |= 0x00040000
		ctypes.windll.user32.SetWindowLongW(hwnd, -20, style)
		ctypes.windll.user32.ShowWindow(hwnd, 5)
	except Exception:
		pass

def find_app_window(app_name_suffix):
	import ctypes
	best_hwnd = None
	fallback_hwnd = None
	def callback(hwnd, extra):
		nonlocal best_hwnd, fallback_hwnd
		length = ctypes.windll.user32.GetWindowTextLengthW(hwnd)
		if length == 0: return True
		buff = ctypes.create_unicode_buffer(length + 1)
		ctypes.windll.user32.GetWindowTextW(hwnd, buff, length + 1)
		title = buff.value
		if title.endswith(f" - {app_name_suffix}"):
			best_hwnd = hwnd
			return False
		if title == app_name_suffix:
			fallback_hwnd = hwnd
		return True
	WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)
	ctypes.windll.user32.EnumWindows(WNDENUMPROC(callback), 0)
	return best_hwnd if best_hwnd else fallback_hwnd

class SilentPanel(wx.Panel):
	def AcceptsFocus(self): return False
	def AcceptsFocusFromKeyboard(self): return False

def get_youtube_mix(video_id):
	mix_url = f"https://www.youtube.com/watch?v={video_id}&list=RD{video_id}"
	results = []
	try:
		info = run_ytdlp_json(mix_url, extract_flat=True, cookies=True, extra_args=['--playlist-end', '50'])
		entries = info.get('entries', [])
		for vid in entries:
			if vid.get('id') == video_id: continue
			item = {
				"title": vid.get('title', _('Unknown Title')),
				"display_title": vid.get('title', _('Unknown Title')),
				"url": vid.get('url') or f"https://www.youtube.com/watch?v={vid.get('id')}",
				"channel_name": vid.get('uploader') or vid.get('channel', _('Unknown Channel')),
				"channel_url": vid.get('uploader_url') or vid.get('channel_url', ''),
				"duration": vid.get('duration'),
				"live": 0
			}
			if item['url']:
				results.append(item)
	except Exception:
		pass
	return results

def get_related_videos(url):
	results = []
	current_id = None
	current_title = ""
	current_tags = []
	current_artist = ""
	
	try:
		info = run_ytdlp_json(url, cookies=True, extra_args=['--no-playlist'])
		current_id = info.get('id')
		current_title = info.get('title', '')
		current_tags = info.get('tags', [])
		current_artist = info.get('artist') or info.get('creator') or info.get('uploader')
		
		raw_related = info.get('related_videos') or info.get('recommendations') or info.get('suggested_videos') or []
		for vid in raw_related:
			v_id = vid.get('id')
			v_url = vid.get('url') or f"https://www.youtube.com/watch?v={v_id}"
			item = {
				"title": vid.get('title', _('Unknown Title')),
				"display_title": vid.get('title', _('Unknown Title')),
				"url": v_url,
				"channel_name": vid.get('uploader') or vid.get('channel', _('Unknown Channel')),
				"channel_url": vid.get('uploader_url') or vid.get('channel_url', ''),
				"duration": vid.get('duration'),
				"live": 0
			}
			results.append(item)
	except Exception:
		pass

	if not results and (current_id or "v=" in url or "youtu.be/" in url):
		if not current_id:
			try:
				if "v=" in url: current_id = url.split("v=")[1].split("&")[0]
				elif "youtu.be/" in url: current_id = url.split("youtu.be/")[1].split("?")[0]
			except: pass
		if current_id:
			mix_results = get_youtube_mix(current_id)
			if mix_results: results = mix_results

	if not results and current_title:
		query = current_title
		if current_artist and "topic" not in current_artist.lower(): query = f"{current_artist} mix"
		elif current_tags:
			valid_tags = [t for t in current_tags if len(t) > 3 and "video" not in t.lower()]
			if valid_tags: query = f"{valid_tags[0]} mix"
		elif " - " in current_title:
			parts = current_title.split(" - ", 1)
			if len(parts[0].strip()) < 30: query = f"{parts[0].strip()} mix"
		else: query = f"{current_title} mix"
		
		try:
			info = run_ytdlp_json(f"ytsearch50:{query}", extract_flat=True, cookies=True)
			entries = info.get('entries', [])
			for vid in entries:
				if current_id and vid.get('id') == current_id: continue
				if vid.get('url') == url: continue
				t = vid.get('title', '')
				if t and current_title and t.strip().lower() == current_title.strip().lower(): continue
				if any(r['url'] == vid.get('url') for r in results): continue
				item = {
					"title": vid.get('title', _('Unknown Title')),
					"display_title": vid.get('title', _('Unknown Title')),
					"url": vid.get('url') or f"https://www.youtube.com/watch?v={vid.get('id')}",
					"channel_name": vid.get('uploader', _('Unknown Channel')),
					"channel_url": vid.get('uploader_url', ''),
					"duration": vid.get('duration'),
					"live": 0
				}
				results.append(item)
		except Exception:
			pass
	return results
