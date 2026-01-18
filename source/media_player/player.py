
import vlc
State = vlc.State
from datetime import timedelta
from utiles import time_formatting
from threading import Thread
from settings_handler import config_get
import os
from paths import settings_path

def get_vlc_options():
	options = ["--avcodec-hw=none", "--network-caching=1000", "--quiet"]
	return options

# Lazy VLC Instance Initialization
_instance = None
_instance_lock = Thread()  # This was a dummy in the previous file view? No, I need a real lock.
from threading import Lock
_vlc_lock = Lock()

def get_vlc_instance():
	"""
	Lazy initialization of VLC instance.
	Only creates the instance when first needed, not at module import time.
	Thread-safe implementation.
	"""
	global _instance
	with _vlc_lock:
		if _instance is None:
			_instance = vlc.Instance(get_vlc_options())
	return _instance

class Player:
	def __init__(self,filename, hwnd, window=None, headers=None, **kwargs):
		self.do_reset = False
		self.window = window
		self.filename = filename
		self.hwnd = hwnd
		self.headers = headers
		instance = get_vlc_instance()  # Lazy init here!
		if instance:
			self.media = instance.media_player_new()
			self.set_media(self.filename, self.headers, **kwargs)
			self.media.set_hwnd(self.hwnd)
			self.manager = self.media.event_manager()
			self.manager.event_attach(vlc.EventType.MediaPlayerEndReached,self.onEnd)
			self.media.play()
			
			# Apply deferred start_time (Fixes silence issue on network streams)
			if hasattr(self, 'pending_start_time') and self.pending_start_time:
				self._apply_deferred_seek()
				
			self.volume = int(config_get("volume"))
			self.media.audio_set_volume(self.volume)
			self.ignore_end = False
		else:
			print("Error: VLC Instance failed to initialize")
			self.media = None
			raise RuntimeError("VLC Instance failed to initialize")
	def onEnd(self,event):
		if self.ignore_end:
			self.ignore_end = False
			return
		if event.type == vlc.EventType.MediaPlayerEndReached:
			self.do_reset = True
			t = Thread(target=self.reset)
			t.daemon = True
			t.start()
	def seek(self, seconds):
		length = self.media.get_length()
		if length == -1:
			return 0.03
		try:
			return seconds/(self.media.get_length()/1000)
		except ZeroDivisionError:
			return 0.03
	def get_duration(self):
		duration = self.media.get_length()
		if duration == -1 or not isinstance(duration, int):
			return ""
		return time_formatting(str(timedelta(seconds=duration//1000)))
	def get_elapsed(self):
		elapsed = self.media.get_time()
		if elapsed == -1 or not isinstance(elapsed, int):
			return ""
		return time_formatting(str(timedelta(seconds=elapsed//1000)))

	def get_audio_tracks(self):
		# Returns list of (id, title)
		return self.media.audio_get_track_description()

	def set_audio_track(self, track_id):
		self.media.audio_set_track(track_id)

	def get_current_audio_track(self):
		return self.media.audio_get_track()

	def add_slave(self, type, uri, select=False):
		return self.media.add_slave(type, uri, select)

	def reset(self):
		self.do_reset = False
		self.media.set_media(self.media.get_media())
		if config_get("repeatetracks") and not config_get('autonext'):
			self.media.play()
		elif config_get('autonext') and not config_get('repeatetracks'):
			import wx
			wx.CallAfter(self.window.next, auto=True)


	def set_media(self, m, headers=None, audio_slave=None, start_time=None, stop_time=None, audio_lang=None):
		instance = get_vlc_instance()  # Lazy init
		if instance:
			options = []
			if headers:
				# Forward authentication headers from yt-dlp to VLC
				if 'Cookie' in headers:
					options.append(f':http-header=Cookie: {headers["Cookie"]}')
				if 'User-Agent' in headers:
					options.append(f':http-user-agent={headers["User-Agent"]}')
			else:
				# Fallback default
				options.append(":http-user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
			
			if audio_slave:
				options.append(f':input-slave={audio_slave}')
				
			# NOTE: Applying start-time via options can cause silence/buffering issues on some network streams.
			# We will handle seeking manually in MediaGui or Player init.
			# However, stop-time is reliable in options? 
			# User reported "Silence and no duration". 
			# We will NOT add start-time to options.
            # stop-time is useful for silence skipping end.
			if stop_time:
				options.append(f':stop-time={stop_time}')
				
			if audio_lang:
				options.append(f':audio-language={audio_lang}')

			# Construct media with options
			if options:
				media = instance.media_new(m, *options)
			else:
				media = instance.media_new(m)
				
			self.media.set_media(media)
            
            # If start_time is provided, we need to seek AFTER play. 
            # But set_media doesn't play. __init__ calls play.
            # We'll store it to apply later or caller handles it.
			if start_time:
				self.pending_start_time = start_time
				self._apply_deferred_seek()
			else:
				self.pending_start_time = None

	def _apply_deferred_seek(self):
		if hasattr(self, 'pending_start_time') and self.pending_start_time:
			def deferred_seek():
				# Wait for state to change to Playing
				import time
				for _ in range(30): # 30 attempts (upto 3s)
					state = self.media.get_state()
					if state == vlc.State.Playing:
						# Extra small delay to ensure buffer is ready
						time.sleep(0.05)
						self.media.set_time(int(self.pending_start_time * 1000))
						break
					time.sleep(0.1)
			t = Thread(target=deferred_seek)
			t.daemon = True
			t.start()
