import re
from threading import Thread
from settings_handler import config_get
from download_handler.downloader import downloadAction
import json

import wx
import application
import os
from paths import settings_path
# import yt_dlp moved to local scopes

class BotDetectionError(RuntimeError):
	pass

def get_ffmpeg_path():
	import sys
	# Logic to find ffmpeg.exe in frozen environments
	if getattr(sys, 'frozen', False):
		# If OneFile (less likely now, but for robustness)
		if hasattr(sys, '_MEIPASS'):
			base_path = sys._MEIPASS
		else:
			# OneDir (Typical for us)
			base_path = os.path.dirname(sys.executable)
	else:
		# Development mode (Source root)
		base_path = os.path.dirname(os.path.abspath(__file__))
		# In dev, utiles is in source/, ffmpeg is in source/ or root?
		# Spec says ffmpeg is in source/ffmpeg.exe
		# If __file__ is source/utiles.py, dirname is source/
		# So path is source/ffmpeg.exe
		
	# Build path
	ffmpeg_path = os.path.join(base_path, 'ffmpeg.exe')
	
	# Fallback if not found (e.g. system path)
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
		self.duration = 0 # Default

def get_cookie_opts():
	path = os.path.join(settings_path, "cookies.txt")
	if os.path.exists(path):
		return {'cookiefile': path}
	
	if os.path.exists("cookies.txt"):
		return {'cookiefile': "cookies.txt"}
	return {}



def extract_secondary_audios(info):
	formats = info.get('formats', [])
	# Dictionary to store best track per language/label
	# Key: Language Code (or Label if no code), Value: Track Dict
	unique_tracks = {}
	
	for f in formats:
		# Check for audio-only
		if f.get('vcodec') == 'none' and f.get('acodec') != 'none':
			url = f.get('url')
			if not url: continue
				
			lang = f.get('language')
			note = f.get('format_note', '')
			abr = f.get('abr', 0) or 0 # Audio Bitrate
			
			# Construct cleaner label
			# If lang is present, use it as primary key
			if lang:
				key = lang
				# Try to get full language name if possible, or just code
				# yt-dlp usually provides code 'vi', 'en'. 
				# We can beautify in GUI or just use as is. 
				label = f"{lang}"
			else:
				# No language code. Use Note or Label as key.
				key = f"unknown_{note}"
				label = note if note else "Unknown Audio"

			# Create track object
			track = {
				'url': url,
				'label': label, # This will be updated if we find better one?
				'language': lang,
				'abr': abr,
				'note': note
			}
			
			if key in unique_tracks:
				# Compare Bitrate
				if abr > unique_tracks[key]['abr']:
					unique_tracks[key] = track
			else:
				unique_tracks[key] = track

	# Convert back to list and Sort
	# Sort by Language code?
	results = list(unique_tracks.values())
	
	# Refine Labels separate from Key comparison
	for t in results:
		# Improve Label: "Language (Bitrate?)" or just "Language"
		# User saw: "vi (Vietnamese, low)". 
		# We want: "Vietnamese" or "vi".
		# t['note'] might be "Vietnamese, low".
		# Let's split note by comma?
		
		# Simple approach: Use Language Code + Note (but clean).
		# Or rely on `t['language']` being the code.
		# Let's formatting: "Lang: vi - [Original Note]"?
		# User complains about duplicates. We fixed that by Unique Key.
		# Now just clean label.
		
		l = t.get('language')
		n = t.get('note', '')
		
		display = l if l else "Audio"
		if n:
			# If n contains l?
			display += f" ({n})"
		
		t['label'] = display

	return results

def fetch_audio_tracks(url):
	import yt_dlp
	ydl_opts = {
		'quiet': True,
		'no_warnings': True,
		'noplaylist': True
	}
	# Try without cookies first
	try:
		opts = ydl_opts.copy()
		with yt_dlp.YoutubeDL(opts) as ydl:
			info = ydl.extract_info(url, download=False)
			return extract_secondary_audios(info)
	except yt_dlp.utils.DownloadError as e:
		if check_bot_error(str(e)):
			# Retry with cookies
			opts = ydl_opts.copy()
			opts.update(get_cookie_opts())
			try:
				with yt_dlp.YoutubeDL(opts) as ydl:
					info = ydl.extract_info(url, download=False)
					return extract_secondary_audios(info)
			except Exception:
				return []
	except Exception:
		return []



def get_audio_stream(url):
	import yt_dlp
	ydl_opts = {
		'format': 'bestaudio/best',
		'quiet': True,
		'no_warnings': True,
		'noplaylist': True
	}
	# First attempt: No cookies
	try:
		# Copy default opts
		opts = ydl_opts.copy()
		with yt_dlp.YoutubeDL(opts) as ydl:
			info = ydl.extract_info(url, download=False)
			stream_url = info.get('manifest_url') if info.get('manifest_url') else info['url']
			s = Stream(stream_url, info.get('title', 'Unknown'), info.get('ext'), None, info.get('http_headers'))
			s.duration = info.get('duration', 0)
			return s
	except yt_dlp.utils.DownloadError as e:
		# Check if error suggests authentication/cookie need
		if check_bot_error(str(e)):
			print(f"Auth needed for audio: {e}")
			# Retry with cookies
			opts = ydl_opts.copy()
			opts.update(get_cookie_opts())
			if 'cookiefile' not in opts:
				# No cookies found, but we need them
				raise BotDetectionError(_("This video is age restricted or requires a valid cookies.txt file to play."))
			
			try:
				with yt_dlp.YoutubeDL(opts) as ydl:
					info = ydl.extract_info(url, download=False)
					stream_url = info.get('manifest_url') if info.get('manifest_url') else info['url']

					s = Stream(stream_url, info.get('title', 'Unknown'), info.get('ext'), None, info.get('http_headers'))
					s.duration = info.get('duration', 0)
					return s
			except Exception as e2:
				# If it still fails, it might be expired cookies or other issue
				if check_bot_error(str(e2)):
					raise BotDetectionError(_("Authentication failed. Your cookies.txt might be expired or invalid. Please delete and re-import a fresh one."))
				raise e2
		# If not auth error, raise original
		raise e

def get_video_stream(url):
	import yt_dlp
	# Prioritize 720p (22) and 360p (18) progressive mp4 for compatibility
	ydl_opts = {
		'format': '22/18/best[ext=mp4]/best', 
		'quiet': True,
		'no_warnings': True,
		'noplaylist': True
	}
	# First attempt: No cookies
	try:
		opts = ydl_opts.copy()
		with yt_dlp.YoutubeDL(opts) as ydl:
			info = ydl.extract_info(url, download=False)
			stream_url = info.get('manifest_url') if info.get('manifest_url') else info['url']
			s = Stream(stream_url, info.get('title', 'Unknown'), info.get('ext'), info.get('resolution'), info.get('http_headers'))
			s.duration = info.get('duration', 0)
			return s
	except yt_dlp.utils.DownloadError as e:
		if check_bot_error(str(e)):
			print(f"Auth needed for video: {e}")
			opts = ydl_opts.copy()
			opts.update(get_cookie_opts())
			if 'cookiefile' not in opts:
				raise BotDetectionError(_("This video is age restricted or requires a valid cookies.txt file to play."))
				
			try:
				with yt_dlp.YoutubeDL(opts) as ydl:
					info = ydl.extract_info(url, download=False)
					stream_url = info.get('manifest_url') if info.get('manifest_url') else info['url']
					s = Stream(stream_url, info.get('title', 'Unknown'), info.get('ext'), info.get('resolution'), info.get('http_headers'))
					s.duration = info.get('duration', 0)
					return s
			except Exception as e2:
				print(f"Retry video failed: {e2}")
				if check_bot_error(str(e2)):
					raise BotDetectionError(_("Authentication failed. Your cookies.txt might be expired or invalid. Please delete and re-import a fresh one."))
				raise e2
		raise e

def time_formatting( t):
	try:
		total_seconds = int(float(t)) # Handle string "213" or float 213.5
	except (ValueError, TypeError):
		return t

	m, s = divmod(total_seconds, 60)
	h, m = divmod(m, 60)

	def minute(m):
		if m == 1:
			return _("one minute")
		elif m == 2:
			return _("two minutes")
		else:
			return _("{} minutes").format(m)
	def second(s):
		if s == 1:
			return _("one second")
		elif s == 2:
			return _("two seconds")
		else:
			return _("{} seconds").format(s)
	def hour(h):
		if h == 1:
			return _("one hour")
		elif h == 2:
			return _("two hours")
		else:
			return _("{} hours").format(h)

	parts = []
	if h > 0:
		parts.append(hour(h))
	if m > 0:
		parts.append(minute(m))
	if s > 0 or not parts: # Show seconds if they exist or if time is 0
		parts.append(second(s))

	if len(parts) == 1:
		return parts[0]
	elif len(parts) == 2:
		return _("{} and {}").format(parts[0], parts[1])
	elif len(parts) >= 3:
		return _("{} and {} and {}").format(parts[0], parts[1], parts[2])

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
		
		if days < 0: return "" # Future date?
		
		if days == 0:
			return _("Today")
		elif days == 1:
			return _("Yesterday")
		elif days < 30:
			return _("{} days ago").format(days)
		elif days < 365:
			months = int(days / 30)
			if months <= 1:
				return _("1 month ago")
			else:
				return _("{} months ago").format(months)
		else:
			years = int(days / 365)
			if years <= 1:
				return _("1 year ago")
			else:
				return _("{} years ago").format(years)
	except Exception:
		return ""

YT_LINK_PATTERN = re.compile(r"^((?:https?:)?\/\/)?((?:www|m)\.)?((?:youtube\.com|youtu.be))(\/(?:[\w\-]+\?v=|embed\/|v\/)?)([\w\-]+)(\S+)?$")

def youtube_regexp(string):
	return YT_LINK_PATTERN.search(string)

def direct_download(option, url, dlg, download_type="video", path=config_get("path")):
	if option == 0:
		format = "bestvideo[ext=mp4]+bestaudio[ext=m4a]/mp4"
	else:
		format = "bestaudio[ext=m4a]"
	convert = True if option == 2 else False
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
				wx.CallAfter(wx.MessageBox,
					_("An error occurred while connecting to the update service. Please check your internet connection and try again."), 
					_("Error"), 
					parent=wx.GetApp().GetTopWindow(), style=wx.ICON_ERROR
				)
			return
		info = r.json()
		if application.version != info["version"]:
			print(info)
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
			wx.CallAfter(wx.MessageBox,
				_("An error occurred while connecting to the update service. Please check your internet connection and try again."), 
				_("Error"), 
				parent=wx.GetApp().GetTopWindow(), style=wx.ICON_ERROR
			)

def check_bot_error(error_msg):
	# Strip ANSI codes
	ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
	error_msg = ansi_escape.sub('', str(error_msg))
	
	# Normalize smart quotes to straight quotes
	error_msg = error_msg.replace("’", "'").replace("‘", "'").replace("“", '"').replace("”", '"')
	error_msg = error_msg.lower()

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

def force_taskbar_style(window):
	try:
		import ctypes
		hwnd = window.GetHandle()
		# GWL_EXSTYLE = -20
		# WS_EX_APPWINDOW = 0x00040000
		style = ctypes.windll.user32.GetWindowLongW(hwnd, -20)
		style |= 0x00040000
		ctypes.windll.user32.SetWindowLongW(hwnd, -20, style)
		
		# Aggressively show window to fix "lost" state (Healing)
		ctypes.windll.user32.ShowWindow(hwnd, 5) # SW_SHOW
	except Exception as e:
		print(f"Failed to force taskbar style: {e}")

def find_app_window(app_name_suffix):
	import ctypes
	best_hwnd = None
	fallback_hwnd = None
	
	def callback(hwnd, extra):
		nonlocal best_hwnd, fallback_hwnd
		
		# We DO NOT check IsWindowVisible here because we want to rescue "lost" (hidden) windows
		
		length = ctypes.windll.user32.GetWindowTextLengthW(hwnd)
		if length == 0:
			return True
			
		buff = ctypes.create_unicode_buffer(length + 1)
		ctypes.windll.user32.GetWindowTextW(hwnd, buff, length + 1)
		title = buff.value
		
		# Prioritize " - A11YTube" windows (Player, Browser, etc.)
		if title.endswith(f" - {app_name_suffix}"):
			best_hwnd = hwnd
			return False # Found a specific window, stop looking
			
		# Fallback: exact "A11YTube"
		if title == app_name_suffix:
			fallback_hwnd = hwnd
		
		return True

	WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)
	ctypes.windll.user32.EnumWindows(WNDENUMPROC(callback), 0)
	
	return best_hwnd if best_hwnd else fallback_hwnd

class SilentPanel(wx.Panel):
	"""
	A wx.Panel that overrides AcceptsFocus to return False.
	This prevents the panel itself from receiving focus during Tab traversal,
	solving the issue where screen readers announce 'Panel' unexpectedly.
	"""
	def AcceptsFocus(self):
		return False
	
	def AcceptsFocusFromKeyboard(self):
		return False

def get_youtube_mix(video_id):
	"""
	Attempts to fetch the standard YouTube Mix (Radio) for a given video ID.
	Mix URL format: https://www.youtube.com/watch?v={id}&list=RD{id}
	"""
	import yt_dlp
	mix_url = f"https://www.youtube.com/watch?v={video_id}&list=RD{video_id}"
	print(f"Attempting to fetch YouTube Mix: {mix_url}")
	
	results = []
	try:
		# We use extract_flat=True to get the list quickly. 
		# YouTube Mixes are technically playlists.
		opts = {
			'quiet': True,
			'ignoreerrors': True,
			'extract_flat': True,
			'no_warnings': True,
			'playlistend': 20, # Fetch top 20 items from the mix
		}
		opts.update(get_cookie_opts())
		
		with yt_dlp.YoutubeDL(opts) as ydl:
			info = ydl.extract_info(mix_url, download=False)
			if info and 'entries' in info:
				for vid in info['entries']:
					if not vid: continue
					
					# Filter out the seed video itself if present?
					# Usually Mix starts with the current video.
					if vid.get('id') == video_id: continue
					
					item = {
						"title": vid.get('title', _('Unknown Title')),
						"display_title": vid.get('title', _('Unknown Title')),
						"url": vid.get('url'), # Flat extraction might just give URL
						"channel_name": vid.get('uploader') or vid.get('channel', _('Unknown Channel')),
						"channel_url": vid.get('uploader_url') or vid.get('channel_url', ''),
						"duration": vid.get('duration'),
						"live": 0
					}
					
					# yt-dlp flat extraction often only gives 'url' or 'id'.
					# If 'url' is missing but 'id' exists:
					if not item['url'] and vid.get('id'):
						item['url'] = f"https://www.youtube.com/watch?v={vid.get('id')}"
					
					if item['url']:
						results.append(item)
						
	except Exception as e:
		print(f"Mix extraction failed: {e}")
		if check_bot_error(str(e)):
			# We don't raise here, we just return empty list to trigger fallback
			print("Bot/Auth detected during Mix extraction.")
			
	return results


def get_related_videos(url):
	import yt_dlp
	
	results = []
	current_id = None
	current_title = ""
	current_tags = []
	current_artist = ""
	
	# Attempt 1: Direct Extraction (noplaylist=True might help specific versions)
	# PRIORITY 1: Official Related Videos (Metadata) - The absolute truth
	try:
		opts = {
			'quiet': True,
			'ignoreerrors': True,
			'noplaylist': True, # Try forcing single video mode
			'extract_flat': False,
			'no_warnings': True,
		}
		opts.update(get_cookie_opts())
		
		with yt_dlp.YoutubeDL(opts) as ydl:
			info = ydl.extract_info(url, download=False)
		if info:
			current_id = info.get('id')
			current_title = info.get('title', '')
			current_tags = info.get('tags', [])
			current_artist = info.get('artist') or info.get('creator') or info.get('uploader')
			
			# Capture Channel URL for Fallback
			current_channel_url = info.get('uploader_url') or info.get('channel_url')
			
			# Check standard keys
			raw_related = info.get('related_videos') or \
						  info.get('recommendations') or \
						  info.get('suggested_videos') or []
			
			for vid in raw_related:
				if not isinstance(vid, dict): continue
				v_id = vid.get('id')
				v_url = vid.get('url')
				if not v_id and not v_url: continue
				if not v_url: v_url = f"https://www.youtube.com/watch?v={v_id}"
				
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
	except Exception as e:
		print(f"Direct extraction failed: {e}")
		if check_bot_error(str(e)):
			print("Bot/Auth detected during direct extraction.")

	# Attempt 2: Native YouTube Mix (Radio) - Priority 2
	# Used if Official Extraction yielded nothing (or failed), but we have ID
	if not results and (current_id or "v=" in url or "youtu.be/" in url):
		# If we don't have current_id from Attempt 1, try extracting from URL
		if not current_id:
			try:
				if "v=" in url:
					current_id = url.split("v=")[1].split("&")[0]
				elif "youtu.be/" in url:
					current_id = url.split("youtu.be/")[1].split("?")[0]
			except: pass
			
		if current_id:
			mix_results = get_youtube_mix(current_id)
			if mix_results:
				print(f"Successfully fetched YouTube Mix with {len(mix_results)} items.")
				results = mix_results

	# Attempt 3: Channel Fallback (Popular) - Priority 3
	# Used if Official AND Mix failed, but we have Channel URL
	if not results and current_channel_url:
		print(f"No direct related videos, attempting Channel Fallback: {current_channel_url}")
		try:
			# Fetch recent videos from channel
			# We use 'playlistend' to limit to 10
			chan_opts = {
				'quiet': True,
				'ignoreerrors': True,
				'extract_flat': True,
				'no_warnings': True,
				'playlistend': 10,
			}
			chan_opts.update(get_cookie_opts())
			
			with yt_dlp.YoutubeDL(chan_opts) as ydl:
				# Channel URL is treated as playlist
				info = ydl.extract_info(current_channel_url, download=False)
				if info and 'entries' in info:
					for vid in info['entries']:
						if not vid: continue
						# Skip current video
						if current_id and vid.get('id') == current_id: continue
						
						item = {
							"title": vid.get('title', _('Unknown Title')),
							"display_title": vid.get('title', _('Unknown Title')),
							"url": vid.get('url', ''),
							"channel_name": vid.get('uploader') or vid.get('channel', _('Unknown Channel')),
							"channel_url": vid.get('uploader_url') or vid.get('channel_url', ''),
							"duration": vid.get('duration'),
							"live": 0
						}
						
						# Fix URL if missing
						if not item['url'] and vid.get('id'):
							item['url'] = f"https://www.youtube.com/watch?v={vid.get('id')}"
							
						if item['url']:
							results.append(item)
							
			if results:
				print(f"Channel Fallback success: {len(results)} videos.")
				
		except Exception as e:
			print(f"Channel fallback failed: {e}")
			if check_bot_error(str(e)): pass

	# Attempt 2: Fallback Search (If extraction yielded no related items)
	if not results and current_title:
		print("No related videos found, falling back to Search...")
		
		# Construct Smart Query
		# Priority: 
		# 1. "Artist - Title" (if available) -> standard
		# 2. "Artist Mix" (if artist known)
		# 3. "Tag Mix" (if tags known)
		# 4. "Title" (standard fallback)
		
		# Extract metadata from info if available?
		# We need to pass 'info' out or extract earlier.
		# Let's assume we didn't save 'info' from Attempt 1 unless we refactor.
		# Refactoring slightly to keep 'info' if possible, but 'info' is local to with block.
		# Actually, current_title is saved. 
		# We should probably capture more metadata in Attempt 1.
		
		# Wait, we can't easily access 'info' from Attempt 1 here because it's out of scope.
		# But we can try to re-extract or just rely on what we have.
		# To do this properly, we should move the search logic inside the try/except block OR 
		# extract metadata to variables before the block ends.
		
		# Minimal change: We rely on current_title. 
		# But user wants "Smart". 
		# Let's assume we can get artist/tags if we parse title or had access to info.
		# Since we can't easily change the structure without re-extracting (expensive),
		# let's try to parse the Title for "Artist - Song" pattern as a heuristic?
		# "Alan Walker - Faded" -> Artist="Alan Walker".
		
		# Construct Smart Query
		# Priority: 
		# 1. "Artist Mix" (if specific artist found in metadata)
		# 2. "Tag Mix" (if useful tags found)
		# 3. "Title Mix" (if Artist - Title pattern)
		# 4. "Title" (standard fallback)
		
		query = current_title or "" # Default safe
		
		# If query is empty, we can't fall back.
		if not query.strip():
			return results
		
		if current_artist and "topic" not in current_artist.lower():
			# "Alan Walker Mix"
			query = f"{current_artist} mix"
		elif current_tags:
			# Use first relevant tag? "EDM mix"
			# Filter out generic tags like "video", "youtube"?
			# Take the first one that is likely a genre?
			valid_tags = [t for t in current_tags if len(t) > 3 and "video" not in t.lower()]
			if valid_tags:
				query = f"{valid_tags[0]} mix"
		elif " - " in current_title:
			# "Alan Walker - Faded" -> "Alan Walker mix"
			parts = current_title.split(" - ", 1)
			possible_artist = parts[0].strip()
			if len(possible_artist) < 30: # Santity check
				query = f"{possible_artist} mix"
		else:
			# "Faded mix"
			query = f"{current_title} mix"
		
		print(f"Using Smart Query: {query}")
		
		try:
			# Search for title, get 20 results (flat=True for speed)
			search_opts = {
				'quiet': True,
				'ignoreerrors': True,
				'extract_flat': True,
				'no_warnings': True,
			}
			search_opts.update(get_cookie_opts())
			
			with yt_dlp.YoutubeDL(search_opts) as ydl:
				# ytsearch20: more candidates to filter
				info = ydl.extract_info(f"ytsearch20:{query}", download=False)
				if info and 'entries' in info:
					for vid in info['entries']:
						if not vid: continue
						# Skip the CURRENT video (ID match)
						if current_id and vid.get('id') == current_id: continue
						if vid.get('url') == url: continue
						
						# Skip if title is identical (sometimes ID differs for same video upload)
						t = vid.get('title', '')
						if t and current_title and t.strip().lower() == current_title.strip().lower():
							continue
						
						# Check against already added results
						if any(r['url'] == vid.get('url') for r in results): continue
						
						item = {
							"title": vid.get('title', _('Unknown Title')),
							"display_title": vid.get('title', _('Unknown Title')),
							"url": vid.get('url', ''),
							"channel_name": vid.get('uploader', _('Unknown Channel')),
							"channel_url": vid.get('uploader_url', ''),
							"duration": vid.get('duration'),
							"live": 0
						}
						results.append(item)
		except Exception as e:
			print(f"Fallback search failed: {e}")
			if check_bot_error(str(e)):
				print("Bot/Auth detected during fallback search.")
				pass

	return results
