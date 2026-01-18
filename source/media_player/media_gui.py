import webbrowser
import pyperclip
import wx
from gui.download_progress import DownloadProgress
from download_handler.downloader import downloadAction
from nvda_client.client import speak
from settings_handler import config_get, config_set
import application
from utiles import direct_download, get_audio_stream, get_video_stream, fetch_audio_tracks, BotDetectionError, get_related_videos

from gui.settings_dialog import SettingsDialog
from gui.description import DescriptionDialog
from gui.custom_controls import CustomButton
from youtube_browser.extras import Video
from threading import Thread, Event
import time
from database import Continue, History, Favorite
from .analysis import detect_silence
from .player import Player, State
import random




def has_player(method):
	def wrapper(self, *args):
		if self.player is not None:
			method(self, *args)
	return wrapper



class MediaGui(wx.Frame):

	def __init__(self, parent, title, stream, url, can_download=True, results=None, audio_mode=False, shuffle=False, on_close=None):

		wx.Frame.__init__(self, None, title=f'{title} - {application.name}')
		self.caller = parent # Store parent manually
		self.on_close = on_close
		self.title = title
		self.stream = not can_download
		self.video_stream = stream # Store Stream Object
		self.seek = int(config_get("seek"))
		self.results = results
		self.audio_mode = audio_mode
		self.shuffle = False # Default
		self.shuffle_indices = []
		self.shuffle_ptr = 0
		# Track Cache
		self.track_cache = {}
		self.is_preloading = False # Map index -> stream_obj
		
		# If caller requests shuffle (we need to pass this arg or set it)
		# NOTE: Method signature changed below? No, I will use a kwarg or just set it manually if passed.
		# `__init__` is complex. I'll add `shuffle=False` to init args in next chunk.
		self.path = config_get('path')
		self.Centre()
		self.SetSize(wx.DisplaySize())

		self.Maximize(True)
		self.SetBackgroundColour(wx.BLACK)
		self.player = None
		self.url = url
		self.target_url = url # Initialize target
		self.history = History()
		self.favorite = Favorite()
		self.history_saved = False
		self.video_data = None


		# Smart Navigation Init
		is_search = hasattr(self.caller, 'searchResults')
		is_history = hasattr(self.caller, 'historyList')
		self.smart_mode = (is_search or is_history)

		
		self.history_stack = []
		self.session_history = set() # Track ALL played URLs to prevent loops
		self.related_videos = []
		self.related_index = 0
		self.last_auto_next = 0 # Debounce timer
		self.fetching_related = False
		self.loading_track = False # Prevent spamming next/prev
		self.last_load_warn = 0 # Debounce timer for user feedback
		
		# Thread Safety Flags
		self.shutting_down = False
		
		# Prepare Video Data
		self.timer = None
		if self.results is not None:
			try:
				if hasattr(self.results, 'videos') and isinstance(self.results.videos, list):
					idx = 0
					for i, v in enumerate(self.results.videos):
						if v['url'] == self.url:
							idx = i
							break
					vid = self.results.videos[idx]
					self.video_data = {
						"title": vid.get('title', ''),
						"display_title": vid.get('title', ''),
						"url": vid.get('url', ''),
						"live": 0,
						"channel_name": vid.get('channel', {}).get('name', ''),
						"channel_url": vid.get('channel', {}).get('url', '')
					}
				elif hasattr(self.caller, 'searchResults'):
					idx = self.caller.searchResults.Selection
					self.video_data = {
						"title": self.results.get_title(idx),
						"display_title": self.results.get_title(idx), 
						"url": self.results.get_url(idx),
						"live": 1 if self.stream else 0,
						"channel_name": self.results.get_channel(idx)['name'],
						"channel_url": self.results.get_channel(idx)['url']
					}
				elif hasattr(self.caller, 'videosBox'): # Playlist
					idx = self.caller.videosBox.Selection
					vid = self.results.videos[idx]
					self.video_data = {
						"title": vid.get('title', ''),
						"display_title": vid.get('title', ''),
						"url": vid.get('url', ''),
						"live": 0,
						"channel_name": vid.get('channel', {}).get('name', ''),
						"channel_url": vid.get('channel', {}).get('url', '')
					}
				elif hasattr(self.caller, 'favList') or hasattr(self.caller, 'historyList'):
					idx = self.caller.favList.Selection if hasattr(self.caller, 'favList') else self.caller.historyList.Selection
					self.video_data = self.results[idx]
				elif hasattr(self.caller, 'videoList'): # CollectionView
					idx = self.caller.videoList.Selection
					# Collection items dict keys match video_data structure roughly but need verification
					# Collection items: id, title, url, channel_name, channel_url
					item = self.results[idx]
					self.video_data = {
						"title": item['title'],
						"display_title": item['title'],
						"url": item['url'],
						"live": 0, # Collections are offline/local usually, assume not live or don't care
						"channel_name": item.get('channel_name', ''),
						"channel_url": item.get('channel_url', '')
					}
			except Exception as e:
				print(f"Failed to prepare video data: {e}")
		
		# Shuffle Logic
		self.shuffle = shuffle
		if self.shuffle and self.results:
			# Determine count
			count = 0
			if hasattr(self.results, 'videos') and isinstance(self.results.videos, list):
				count = len(self.results.videos)
			elif hasattr(self.caller, 'searchResults'):
				count = self.caller.searchResults.GetCount()
			elif hasattr(self.caller, 'videosBox'):
				count = self.caller.videosBox.GetCount()
			elif hasattr(self.caller, 'favList'):
				count = self.caller.favList.GetCount()
			elif hasattr(self.caller, 'videoList'):
				count = self.caller.videoList.GetCount()
			
			if count > 0:
				self.shuffle_indices = list(range(count))
				random.shuffle(self.shuffle_indices)
				# Find current url index to set ptr
				# We need to find where the current PLAYING item is in our shuffled list
				# But wait, if we start shuffle playback, we might start at a specific item or random?
				# Usually start at passed `url`.
				# Find `idx` of `url` in results.
				# `self.video_data` logic above found the index `idx`.
				# We need `idx` here.
				# Re-acquiring `idx` safely.
				current_real_idx = -1
				
				if hasattr(self.results, 'videos') and isinstance(self.results.videos, list):
					for i, v in enumerate(self.results.videos):
						if v['url'] == self.url:
							current_real_idx = i
							break
				else:
					# Helper to get attributes safe
					def get_box():
						for attr in ['searchResults', 'videosBox', 'favList', 'historyList', 'videoList']:
							if hasattr(self.caller, attr): return getattr(self.caller, attr)
						return None
					
					box = get_box()
					if box:
						current_real_idx = box.Selection
				
				if current_real_idx != -1:
					# Find this index in shuffled list to set pointer
					# If not found (should be there), default 0
					if current_real_idx in self.shuffle_indices:
						self.shuffle_ptr = self.shuffle_indices.index(current_real_idx)
					else:
						# Should not happen if sync
						self.shuffle_ptr = 0

		# Main Panel (Everything is on this to ensure Tab Traversal functionality)
		# Removed wx.TAB_TRAVERSAL to let specific children handle focus
		from utiles import SilentPanel
		self.mainPanel = SilentPanel(self)
		
		# Main Sizer
		mainSizer = wx.BoxSizer(wx.VERTICAL)

		# Video Panel (Dedicated for VLC)
		self.videoPanel = SilentPanel(self.mainPanel, -1)
		self.videoPanel.SetBackgroundColour(wx.BLACK)
		
		# Player Controls Sizer (Grouped)
		self.controlsSizer = wx.StaticBoxSizer(wx.StaticBox(self.mainPanel, label=_("Player Controls")), wx.HORIZONTAL)
		
		# Use mainPanel as parent
		self.previousButton = CustomButton(self.mainPanel, -1, _("Previous Video"), name="controls")
		self.previousButton.Show() if self.results is not None else self.previousButton.Hide()
		self.beginningButton = CustomButton(self.mainPanel, -1, _("Beginning of Video"), name="controls")
		self.rewindButton = CustomButton(self.mainPanel, -1, _("Rewind <"), name="controls")
		self.playButton = CustomButton(self.mainPanel, -1, _("Play/Pause"), name="controls")
		self.forwardButton = CustomButton(self.mainPanel, -1, _("Forward >"), name="controls")
		self.nextButton = CustomButton(self.mainPanel, -1, _("Next Video"), name="controls")
		self.nextButton.Show() if self.results is not None else self.nextButton.Hide()
		
		self.speedButton = CustomButton(self.mainPanel, -1, _("Speed"), name="controls")
		self.audioTrackBtn = CustomButton(self.mainPanel, -1, _("Audio Track"), name="controls")

		# Toggles (Checkboxes)
		self.chkRepeat = wx.CheckBox(self.mainPanel, -1, _("Repeat"))
		self.chkAutoNext = wx.CheckBox(self.mainPanel, -1, _("Auto Next"))
		self.btnFullScreen = wx.Button(self.mainPanel, -1, _("Full Screen"))
		self.chkFavorite = wx.CheckBox(self.mainPanel, -1, _("Add to Favorites"))
		
		# Set initial state
		# Set initial state
		self.chkRepeat.SetValue(config_get("repeatetracks"))
		self.chkAutoNext.SetValue(config_get("autonext"))
		self.chkAutoNext.Show() if self.results is not None else self.chkAutoNext.Hide()
		

		fullscreen_setting = config_get("fullscreen")
		if not self.audio_mode:
			# If starting in fullscreen, toggle immediately (but button stays standard)
			if fullscreen_setting:
				wx.CallAfter(self.toggleFullScreen) # Use method to trigger full logic
		else:
			self.btnFullScreen.Hide()
			
		self.chkFavorite.SetValue(self.favorite.is_favorite(self.url))

		# Add explicitly to manage order visually
		if self.results: self.controlsSizer.Add(self.previousButton, 1, wx.EXPAND)
		self.controlsSizer.Add(self.beginningButton, 1, wx.EXPAND)
		self.controlsSizer.Add(self.rewindButton, 1, wx.EXPAND)
		self.controlsSizer.Add(self.playButton, 1, wx.EXPAND)
		self.controlsSizer.Add(self.forwardButton, 1, wx.EXPAND)
		if self.results: self.controlsSizer.Add(self.nextButton, 1, wx.EXPAND)
		self.controlsSizer.Add(self.speedButton, 1, wx.EXPAND)
		self.controlsSizer.Add(self.audioTrackBtn, 1, wx.EXPAND)
		
		self.controlsSizer.Add(self.chkRepeat, 0, wx.ALIGN_CENTER_VERTICAL | wx.ALL, 5)

		if self.results: self.controlsSizer.Add(self.chkAutoNext, 0, wx.ALIGN_CENTER_VERTICAL | wx.ALL, 5)
		self.controlsSizer.Add(self.btnFullScreen, 0, wx.ALIGN_CENTER_VERTICAL | wx.ALL, 5)
		
		self.btnAddToCol = CustomButton(self.mainPanel, -1, _("Add to Collection"), name="controls")
		self.controlsSizer.Add(self.btnAddToCol, 0, wx.ALIGN_CENTER_VERTICAL | wx.ALL, 5)
		self.btnAddToCol.Bind(wx.EVT_BUTTON, self.onAddToCollection)

		self.btnSuggested = CustomButton(self.mainPanel, -1, _("Suggested Videos"), name="controls")
		self.controlsSizer.Add(self.btnSuggested, 0, wx.ALIGN_CENTER_VERTICAL | wx.ALL, 5)
		self.btnSuggested.Bind(wx.EVT_BUTTON, self.onSuggested)
		self.btnSuggested.Hide() # Hide by default, show only if suggestions found
		
		self.controlsSizer.Add(self.chkFavorite, 0, wx.ALIGN_CENTER_VERTICAL | wx.ALL, 5)

		# Sliders Sizer (Grouped)
		self.slidersSizer = wx.StaticBoxSizer(wx.StaticBox(self.mainPanel, label=_("Seek & Volume")), wx.HORIZONTAL)
		
		self.lblSeek = wx.StaticText(self.mainPanel, -1, _("Time"))
		self.timeSlider = wx.Slider(self.mainPanel, -1, 0, 0, 100, name=_("Seek"))
		self.lblVol = wx.StaticText(self.mainPanel, -1, _("Volume"))
		self.volumeSlider = wx.Slider(self.mainPanel, -1, 100, 0, 100, name=_("Volume"))
		
		self.slidersSizer.Add(self.lblSeek, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 5)
		self.slidersSizer.Add(self.timeSlider, 3, wx.EXPAND | wx.ALL, 5)
		self.slidersSizer.Add(self.lblVol, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT | wx.LEFT, 10)
		self.slidersSizer.Add(self.volumeSlider, 1, wx.EXPAND | wx.ALL, 5)

		# Actions Sizer (Grouped)
		actions_box = wx.StaticBox(self.mainPanel, label=_("Options"))
		self.actionsSizer = wx.StaticBoxSizer(actions_box, wx.VERTICAL)
		actionsGrid = wx.GridSizer(2, 4, 5, 5) # 2 rows, 4 cols
		
		self.downloadVideoBtn = wx.Button(self.mainPanel, -1, _("Download Video"))
		self.downloadM4aBtn = wx.Button(self.mainPanel, -1, _("Download m4a"))
		self.downloadMp3Btn = wx.Button(self.mainPanel, -1, _("Download mp3"))
		self.directDownloadBtn = wx.Button(self.mainPanel, -1, _("Direct Download (Ctrl+D)"))
		self.descBtn = wx.Button(self.mainPanel, -1, _("Description (Ctrl+Shift+D)"))
		self.copyBtn = wx.Button(self.mainPanel, -1, _("Copy Link (Ctrl+K)"))
		self.browserBtn = wx.Button(self.mainPanel, -1, _("Open in Browser (Ctrl+B)"))

		self.settingsBtn = wx.Button(self.mainPanel, -1, _("Settings (Ctrl+Shift+S)"))
		
		if not can_download:
			self.downloadVideoBtn.Disable()
			self.downloadM4aBtn.Disable()
			self.downloadMp3Btn.Disable()
			self.directDownloadBtn.Disable()

		actionsGrid.Add(self.downloadVideoBtn, 1, wx.EXPAND)
		actionsGrid.Add(self.downloadM4aBtn, 1, wx.EXPAND)
		actionsGrid.Add(self.downloadMp3Btn, 1, wx.EXPAND)
		actionsGrid.Add(self.directDownloadBtn, 1, wx.EXPAND)
		actionsGrid.Add(self.descBtn, 1, wx.EXPAND)
		actionsGrid.Add(self.copyBtn, 1, wx.EXPAND)
		actionsGrid.Add(self.browserBtn, 1, wx.EXPAND)
		actionsGrid.Add(self.settingsBtn, 1, wx.EXPAND)
		
		self.actionsSizer.Add(actionsGrid, 1, wx.EXPAND)
		
		# Compose Main Sizer
		mainSizer.Add(self.videoPanel, 1, wx.EXPAND | wx.ALL, 0)
		
		# Exit Full Screen Button (Hidden by default)
		self.exitFullScreenBtn = wx.Button(self.mainPanel, -1, _("Exit Full Screen"))
		self.exitFullScreenBtn.Hide()
		self.exitFullScreenBtn.Bind(wx.EVT_BUTTON, lambda e: self.toggleFullScreen())
		mainSizer.Add(self.exitFullScreenBtn, 0, wx.ALL | wx.ALIGN_CENTER, 5)

		mainSizer.Add(self.controlsSizer, 0, wx.EXPAND | wx.ALL, 5)
		mainSizer.Add(self.slidersSizer, 0, wx.EXPAND | wx.ALL, 5)
		mainSizer.Add(self.actionsSizer, 0, wx.EXPAND | wx.ALL, 5)
		
		self.mainPanel.SetSizer(mainSizer)

		# Frame Sizer to hold the Main Panel
		frameSizer = wx.BoxSizer(wx.VERTICAL)
		frameSizer.Add(self.mainPanel, 1, wx.EXPAND)
		self.SetSizer(frameSizer)

		# Initial Focus
		wx.CallAfter(self.playButton.SetFocus)

		# Bindings
		self.downloadVideoBtn.Bind(wx.EVT_BUTTON, self.onVideoDownload)
		self.downloadM4aBtn.Bind(wx.EVT_BUTTON, self.onM4aDownload)
		self.downloadMp3Btn.Bind(wx.EVT_BUTTON, self.onMp3Download)
		self.directDownloadBtn.Bind(wx.EVT_BUTTON, self.onDirect)
		self.descBtn.Bind(wx.EVT_BUTTON, self.onDescription)
		self.copyBtn.Bind(wx.EVT_BUTTON, self.onCopy)
		self.browserBtn.Bind(wx.EVT_BUTTON, self.onBrowser)

		self.audioTrackBtn.Bind(wx.EVT_BUTTON, self.onAudioTrack)
		self.settingsBtn.Bind(wx.EVT_BUTTON, lambda event: SettingsDialog(self))
		
		# Player Controls Bindings
		self.previousButton.Bind(wx.EVT_BUTTON, lambda event: self.previous())
		self.beginningButton.Bind(wx.EVT_BUTTON, lambda event: self.beginningAction())
		self.rewindButton.Bind(wx.EVT_BUTTON, lambda event: self.rewindAction())
		self.playButton.Bind(wx.EVT_BUTTON, lambda event: self.playAction())
		self.forwardButton.Bind(wx.EVT_BUTTON, lambda event: self.forwardAction())
		self.nextButton.Bind(wx.EVT_BUTTON, lambda event: self.next())
		self.speedButton.Bind(wx.EVT_BUTTON, self.onSpeedButton)

		# Toggle Bindings
		self.chkRepeat.Bind(wx.EVT_CHECKBOX, self.onRepeatToggle)
		self.chkAutoNext.Bind(wx.EVT_CHECKBOX, self.onAutoNextToggle)
		self.btnFullScreen.Bind(wx.EVT_BUTTON, lambda e: self.toggleFullScreen())
		self.chkFavorite.Bind(wx.EVT_CHECKBOX, self.onFavoriteToggle)

		# Slider Bindings
		self.timeSlider.Bind(wx.EVT_SCROLL, self.onTimeScroll)
		self.volumeSlider.Bind(wx.EVT_SCROLL, self.onVolumeScroll)

		# Key Bindings - Hook on Frame
		self.Bind(wx.EVT_CHAR_HOOK, self.onHook)
		
		# Accelerators
		self.ID_DIRECT = wx.NewIdRef()
		self.ID_DESC = wx.NewIdRef()
		self.ID_COPY = wx.NewIdRef()
		self.ID_BROWSER = wx.NewIdRef()
		self.ID_SETTINGS = wx.NewIdRef()
		self.ID_AUDIO_TRACK = wx.NewIdRef()
		
		hotKeys = wx.AcceleratorTable([
			(wx.ACCEL_CTRL, ord("D"), self.ID_DIRECT),
			(wx.ACCEL_CTRL|wx.ACCEL_SHIFT, ord("D"), self.ID_DESC),
			# (wx.ACCEL_CTRL, ord("L"), self.ID_COPY), # Removed to free Ctrl+L for Collections
			(wx.ACCEL_CTRL, ord("K"), self.ID_COPY), # Ctrl+K
			(wx.ACCEL_CTRL, ord("B"), self.ID_BROWSER),
			(wx.ACCEL_CTRL|wx.ACCEL_SHIFT, ord("S"), self.ID_SETTINGS),
		])
		self.SetAcceleratorTable(hotKeys)
		
		self.Bind(wx.EVT_MENU, self.onDirect, id=self.ID_DIRECT)
		self.Bind(wx.EVT_MENU, self.onDescription, id=self.ID_DESC)
		self.Bind(wx.EVT_MENU, self.onCopy, id=self.ID_COPY)

		self.Bind(wx.EVT_MENU, self.onBrowser, id=self.ID_BROWSER)
		
		self.Bind(wx.EVT_MENU, lambda event: SettingsDialog(self), id=self.ID_SETTINGS)

		# Media Keys
		self.prev_id = 100
		self.play_pause_id = 150
		self.next_id = 200
		self.registerHotKey()
		for hot_id in [self.prev_id, self.play_pause_id, self.next_id]:
			self.Bind(wx.EVT_HOTKEY, self.onHot, id=hot_id)

		self.Bind(wx.EVT_CLOSE, lambda event: self.closeAction())
		
		self.Show()
		# Pass VIDEO PANEL Handle, NOT Frame Handle!
		try:
			# Analyze Silence for Initial Track
			# Analyze Silence for Initial Track (Threaded)
			start_time = 0.0
			stop_time = None
			self.soft_stop_time = None # Initialize
			if config_get("skip_silence"):
				def analyze_initial():
					try:
						# Wait for player to start first
						time.sleep(2) 
						if not self or not self.check_window_valid(): return
						
						s_start, s_stop = detect_silence(stream.url, headers=stream.http_headers, duration=getattr(stream, 'duration', 0))
						print(f"Initial Analysis Result: Start={s_start}, Stop={s_stop}")
						
						# Apply Start Time
						if s_start > 0:
							def safe_seek():
								# Only seek if we haven't passed the silence yet!
								# And current time is significantly less (e.g. not just 0 vs 0.1)
								ct = self.player.media.get_time() / 1000.0
								# Tolerance: If we are at 2s and silence ends at 3s, skipping 1s is worth it.
								# If we are at 5s and silence was 3s, skipping brings us BACK 2s (BAD).
								if ct < s_start:
									self.player.media.set_time(int(s_start * 1000))
							wx.CallAfter(safe_seek)
							
							wx.CallAfter(safe_seek)
							
						# Apply Stop Time
						if s_stop:
							self.soft_stop_time = s_stop
						
					except Exception as e:
						print(f"Initial Silence analysis failed: {e}")
						
				t = Thread(target=analyze_initial)
				t.daemon = True
				t.start()
			
			audio_url = getattr(stream, 'audio_url', None)

			self.player = Player(stream.url, self.videoPanel.GetHandle(), self, stream.http_headers,
								audio_slave=audio_url, start_time=start_time, stop_time=stop_time)
			
			# Restore Playback State (Threaded for robustness)
			
			# Trigger Smart Navigation for Initial Track
			if self.smart_mode:
				Thread(target=self.fetch_related, args=(self.url,)).start()
			t_resume = Thread(target=self.restore_playback_state)
			t_resume.daemon = True
			t_resume.start()
			
			# Set Initial Volume
			self.player.volume = int(config_get("volume")) # Ensure volume is loaded
			self.volumeSlider.SetValue(self.player.volume)
			
			# Trigger Smart Preload for neighbors
			def delayed_preload_init():
				time.sleep(5)
				if not self.check_window_valid(): return
				if self.is_preloading: return # Already running
				self.preload_nearby_tracks()
			t_preload = Thread(target=delayed_preload_init)
			t_preload.daemon = True
			t_preload.start()
		except Exception as e:
			print(f"Player init failed: {e}")
			self.player = None
			if not self.shutting_down: # Only complain if unexpected
				wx.MessageBox(_("Failed to initialize media player. Please check your settings or installation."), _("Error"), parent=self)
				self.Close()
			return
		
		# Timer for Slider
		self.timer = wx.Timer(self)
		self.Bind(wx.EVT_TIMER, self.onTimer, self.timer)
		self.timer.Start(1000)


		# Save History logic
		if self.video_data and config_get("continue"):
			try:
				self.history.add_history(self.video_data)
				self.history_saved = True
			except Exception as e:
				print(f"Failed to save history in init: {e}")

		t = Thread(target=self.extract_description)
		t.daemon = True
		t.start()

	def speak_status(self, msg):
		if config_get("player_notifications"):
			speak(msg)

	def onTimer(self, event):
		if not self.check_window_valid(): return
		if self.player is not None:
			length = self.player.media.get_length()
			cur = self.player.media.get_time()
			
			# Check Dynamic Stop Time (for Initial Track or Silence Skip)
			if hasattr(self, 'soft_stop_time') and self.soft_stop_time:
				if cur >= self.soft_stop_time * 1000:
					self.soft_stop_time = None # Trigger once
					if config_get("autonext"):
						wx.CallAfter(self.next, auto=True)
					else:
						# If auto-next is OFF, we just stop the player here
						# mimicking natural end of track (but earlier)
						self.player.media.stop()
					return

			if length > 0:
				self.timeSlider.SetRange(0, length)
				self.timeSlider.SetValue(cur)
		else:
			# Player is None (Loading or Stopped)
			# Ensure slider is reset to "Nothing" state (0-100 placeholder or 0-0)
			# User request: "hien thi dong thoi gian la khong co gi" -> Meaning empty/zero
			self.timeSlider.SetRange(0, 100)
			self.timeSlider.SetValue(0)

		# Sync Play/Pause Button Label
		if self.player:
			state = self.player.media.get_state()
			if state == State.Playing:
				if self.playButton.GetLabel() != _("Pause"):
					self.playButton.SetLabel(_("Pause"))
			else:
				if self.playButton.GetLabel() != _("Play"):
					self.playButton.SetLabel(_("Play"))

		from utiles import force_taskbar_style
		force_taskbar_style(self)

		self.Bind(wx.EVT_SHOW, self.onShow)
		self.Bind(wx.EVT_ACTIVATE, self.onActivate)
		self.Bind(wx.EVT_ICONIZE, self.onIconize)

	def onShow(self, event):
		from utiles import force_taskbar_style
		force_taskbar_style(self)
		event.Skip()

	def onActivate(self, event):
		if event.GetActive():
			from utiles import force_taskbar_style
			force_taskbar_style(self)
			# Re-apply fullscreen if needed
			if self.IsFullScreen():
				self.ShowFullScreen(True)
		event.Skip()

	def onIconize(self, event):
		if not event.IsIconized():
			from utiles import force_taskbar_style
			force_taskbar_style(self)
			if self.IsFullScreen():
				self.ShowFullScreen(True)
		event.Skip()

	def onTimeScroll(self, event):
		if self.player is not None:
			val = self.timeSlider.GetValue()
			# Slider value is in ms? No, set_position takes 0.0-1.0 float? 
			# Let's check onTimer: self.timeSlider.SetRange(0, length) (length is ms)
			# self.timeSlider.SetValue(cur) (cur is ms)
			# So val is ms.
			# set_position expects 0.0-1.0? 
			# VLC bindings: set_time(ms) or set_position(float).
			# Original code: self.player.media.set_time(val)
			
			# We want to use _safe_seek which takes percent 0-1.
			length = self.player.media.get_length()
			if length > 0:
				percent = val / length
				self._safe_seek(percent)
			else:
				# Fallback if length unknown
				self.player.media.set_time(val)

	def onVolumeScroll(self, event):
		val = self.volumeSlider.GetValue()
		if self.player is not None:
			self.player.media.audio_set_volume(val)
			self.player.volume = val
		config_set("volume", val)

	def onRepeatToggle(self, event):
		v = self.chkRepeat.GetValue()
		config_set("repeatetracks", v)
		if v: 
			config_set("autonext", False)
			self.chkAutoNext.SetValue(False)
			self.chkAutoNext.SetValue(False)
		speak(_("Repeat on") if v else _("Repeat off"))

	def onAutoNextToggle(self, event):
		v = self.chkAutoNext.GetValue()
		config_set("autonext", v)
		if v:
			config_set("repeatetracks", False)
			self.chkRepeat.SetValue(False)
		speak(_("Auto play next on") if v else _("Auto play next off"))

	def onFavoriteToggle(self, event):
		v = self.chkFavorite.GetValue()
		if not self.video_data:
			speak(_("Unable to add to favorites"))
			self.chkFavorite.SetValue(False)
			return
			
		if v:
			self.favorite.add_favorite(self.video_data)
			speak(_("Added to favorites"))
		else:
			self.favorite.remove_favorite(self.url)
			speak(_("Removed from favorites"))
			
	def onAddToCollection(self, event):
		if not self.video_data:
			speak(_("No video data"))
			return
		
		from gui.collections import AddToCollectionDialog
		dlg = AddToCollectionDialog(self, self.video_data)
		dlg.ShowModal()
		dlg.Destroy()
			
	def onSuggested(self, event):
		if not self.related_videos:
			speak(_("No suggested videos available yet."))
			return
			
		titles = [v.get('title', 'Unknown') for v in self.related_videos]
		dlg = wx.SingleChoiceDialog(self, _("Select a video to play"), _("Suggested Videos"), titles)
		if dlg.ShowModal() == wx.ID_OK:
			idx = dlg.GetSelection()
			item = self.related_videos[idx]
			self.changeTrack(item)
		dlg.Destroy()
			
	def onSpeedButton(self, event):
		# Open Dialog to select speed
		choices = [_("Slow"), _("Normal"), _("Fast")]
		# Map to rates: 0.6, 1.0, 1.4
		rates = [0.6, 1.0, 1.4]
		
		dlg = wx.SingleChoiceDialog(self, _("Select Playback Speed"), _("Speed"), choices)
		if dlg.ShowModal() == wx.ID_OK:
			idx = dlg.GetSelection()
			rate = rates[idx]
			self.player.media.set_rate(rate)
			speak(choices[idx])
		dlg.Destroy()

	@has_player
	def playAction(self):
		state = self.player.media.get_state()
		if state in (State.NothingSpecial, State.Stopped):
			self.player.media.play()
			self.speak_status(_("Played"))
			self.playButton.SetLabel(_("Pause")) # Immediate feedback
		elif state == State.Paused:
			self.player.media.play() # Resume
			self.speak_status(_("Played"))
			self.playButton.SetLabel(_("Pause"))
		elif state == State.Playing:
			self.player.media.pause()
			self.speak_status(_("Paused"))
			self.playButton.SetLabel(_("Play"))

	@has_player
	def forwardAction(self):
		position = self.player.media.get_position()
		target = position + self.player.seek(self.seek)
		self._safe_seek(target)

	@has_player
	def rewindAction(self):
		position = self.player.media.get_position()
		target = position - self.player.seek(self.seek)
		self._safe_seek(target)

	def set_position(self, key):
		step = int(chr(key))/10
		self._safe_seek(step)
		
	def _safe_seek(self, target_pos_percent):
		# Centralized Safe Seek Logic
		# 1. Handles strict restart if Ended
		# 2. Guards against spurious EndReached events during seek (Safe Guard)
		
		if not self.player: return
		state = self.player.media.get_state()
		
		# Ensure target is within bounds 0.0 - 1.0 (VLC requirement roughly, though it handles overflow)
		if target_pos_percent < 0: target_pos_percent = 0.0
		if target_pos_percent > 1: target_pos_percent = 0.99 # Prevent seeking to absolute end which triggers end event immediately
		
		if state in (State.Ended, State.Stopped, State.NothingSpecial):
			self.speak_status(_("Resuming to seek..."))
			self.player.media.play()
			
			def strict_restart_seek():
				# Poll until playing, then seek
				for attempt in range(20): # Wait up to 2s
					if self.player.media.get_state() == State.Playing:
						time.sleep(0.05)
						wx.CallAfter(self._perform_guarded_seek, target_pos_percent)
						break
					time.sleep(0.1)
			Thread(target=strict_restart_seek, daemon=True).start()
		else:
			# Already playing/paused, just seek with guard
			self._perform_guarded_seek(target_pos_percent)

	def _perform_guarded_seek(self, percent):
		# Enable Guard
		if self.player: self.player.ignore_end = True
		
		# Seek
		if self.player: self.player.media.set_position(percent)
		
		# Feedback
		self.speak_status(_("Elapsed: {}").format(self.player.get_elapsed()))
		self.onTimer(None)
		
		# Disable Guard after delay
		def reset_guard():
			import time
			time.sleep(0.7) # Wait for buffers to settle
			if self.player: self.player.ignore_end = False
			
		Thread(target=reset_guard, daemon=True).start()

	@has_player
	def beginningAction(self):
		self.player.media.set_position(0.0)
		self.speak_status(_("Beginning of video"))
		if self.player.media.get_state() in (State.NothingSpecial, State.Stopped):
			self.player.media.play()
		self.onTimer(None)

	def restore_playback_state(self):
		if not (self.url in Continue.get_all() and config_get("continue")):
			return
		
		try:
			data = Continue.get_all()[self.url]
			position = data.get("position", 0.0)
			audio_track = data.get("audio_track", -1)
			
			# Wait for Player Ready
			ready = False
			for _ in range(20):
				if self.player and self.player.media.get_state() in [State.Playing, State.Paused]:
					ready = True
					break
				time.sleep(0.5)
				
			if not ready: return
			
			# Restore Position
			if position > 0:
				wx.CallAfter(self.player.media.set_position, position)
				
			# Restore Audio Track
			if isinstance(audio_track, str) and audio_track != "Default":
				wx.CallAfter(self.restore_audio_preference, audio_track)
		except Exception as e:
			print(f"Error restoring playback state: {e}")

	def closeAction(self):
		self.shutting_down = True
		if self.player is not None:
			cur_pos = self.player.media.get_position()
			# Save current Audio Track preference
			# We need to know the current label? 
			# Actually closeAction updates DB, but we already updated it on Switch.
			# But position updates on Close.
			# We need to PRESERVE the existing 'audio_track' value from DB if we don't track it locally?
			# Or better: `MediaGui` should store `current_audio_label`.
			# I'll initializing it to "Default" or -1.
			
			track_val = -1
			if self.url in Continue.get_all():
				# Keep existing preference if we didn't change it?
				# The issue: closeAction overwrites.
				# So we scan `Continue` to get old value?
				old_data = Continue.get_all()[self.url]
				if "audio_track" in old_data:
					track_val = old_data["audio_track"]

			if cur_pos in (0.0, -1) and self.url in Continue.get_all():
				Continue.remove_continue(self.url)
			elif self.url in Continue.get_all():
				Continue.update(self.url, cur_pos, track_val)
			else:
				Continue.new_continue(self.url, cur_pos, track_val)
			self.player.media.stop()
			self.player = None # Kill reference to prevent ghost threads usage
		if self.timer:
			self.timer.Stop()
			
		if self.on_close:
			self.on_close()
		else:
			self.caller.Show()
		self.Destroy()

	def registerHotKey(self):
		self.RegisterHotKey(
			self.prev_id,
			0, wx.WXK_MEDIA_PREV_TRACK)
		self.RegisterHotKey(
			self.play_pause_id,
			0, wx.WXK_MEDIA_PLAY_PAUSE)
		self.RegisterHotKey(
			self.next_id,
			0, wx.WXK_MEDIA_NEXT_TRACK)
			
	def onHot(self, event):
		if event.Id == self.prev_id:
			self.previous()
		elif event.Id == self.play_pause_id:
			self.playAction()
		elif event.Id == self.next_id:
			self.next()

	def onHook(self, event):
		key = event.GetKeyCode()

		# Escape always closes
		if key == wx.WXK_ESCAPE:
			self.closeAction()
			return # Event consumed

		# Full Screen Toggle (Ctrl+Shift+E)
		if key == ord("E") and event.ControlDown() and event.ShiftDown():
			self.toggleFullScreen()
			return

		# Full Screen Override Logic
		if self.IsFullScreen():
			# Trapping Navigation Keys for Player Control (Prevents Focus Loss)
			if key == wx.WXK_RIGHT and not event.HasAnyModifiers():
				self.forwardAction()
				return
			elif key == wx.WXK_LEFT and not event.HasAnyModifiers():
				self.rewindAction()
				return
			elif key == wx.WXK_UP and not event.HasAnyModifiers():
				self.increase_volume()
				return
			elif key == wx.WXK_DOWN and not event.HasAnyModifiers():
				self.decrease_volume()
				return
			
			# Shift+Space = Play/Pause
			elif key == wx.WXK_SPACE and event.ShiftDown():
				self.playAction()
				return
			
			# Block classic Fullscreen toggle keys if user unwanted them?
			# User asked to "Change to better shortcut". 
			# I will disable Alt and Enter for fullscreen here implicitly by not handling them for that purpose.
			
		# Check if we should trap navigation keys (Arrows)
		obj = self.FindFocus()
		# Allow arrows to seek ONLY if focused on CustomButton (Player Controls)
		allow_seek = isinstance(obj, CustomButton)

		if key in (wx.WXK_LEFT, wx.WXK_RIGHT, wx.WXK_UP, wx.WXK_DOWN):
			if allow_seek:
				# We are in controls area, hijack arrows for seek/volume
				if key == wx.WXK_RIGHT and not event.HasAnyModifiers():
					self.forwardAction()
				elif key == wx.WXK_LEFT and not event.HasAnyModifiers():
					self.rewindAction()
				elif key == wx.WXK_UP:
					self.increase_volume()
				elif key == wx.WXK_DOWN:
					self.decrease_volume()
				# Consume event so it doesn't navigate focus
				return 
			else:
				# We are in Sliders or Action Buttons, let default nav happen
				event.Skip()
				return

		# Space / Pause
		if key == wx.WXK_PAUSE:
			self.playAction()
			return

		if key == wx.WXK_SPACE:
			if event.ShiftDown():
				self.playAction()
				return
			else:
				# Space alone triggers the focused control (standard behavior)
				event.Skip()
				return

		# New Navigation (Shift+N / Shift+B)
		if event.ShiftDown() and not event.ControlDown() and not event.AltDown():
			if key == ord("N"):
				if self.results: self.next()
				return
			elif key == ord("B"):
				if self.results: self.previous()
				return

		# Letter Hotkeys (Speed, Seek step, Repeat, etc.)
		# Ensure NO modifiers are pressed for these single-key shortcuts
		if not event.HasAnyModifiers():
			if key == wx.WXK_HOME:
				self.beginningAction()
				return
			elif key in range(49, 58): # 1-9
				self.set_position(key)
				return
			elif key == ord("S"):
				self.player.media.set_rate(1.4)
				speak(_("Fast"))
				return
			elif key == ord("D"):
				self.player.media.set_rate(1.0)
				speak(_("Normal"))
				return
			elif key == ord("F"):
				self.player.media.set_rate(0.6)
				speak(_("Slow"))
				return
			elif key in (ord("-"), wx.WXK_NUMPAD_SUBTRACT):
				self.seek -= 1
				config_set("seek", max(1, self.seek))
				speak(f"{_('Seek')} {self.seek} {_('seconds')}")
				return
			elif key in (ord("="), wx.WXK_NUMPAD_ADD):
				self.seek += 1
				config_set("seek", min(10, self.seek))
				speak(f"{_('Seek')} {self.seek} {_('seconds')}")
				return
			
			# Toggles via Hotkeys
			elif key == ord("R"):
				v = not config_get("repeatetracks")
				self.chkRepeat.SetValue(v)
				self.onRepeatToggle(None) 
				return
			elif key == ord("N"): # Auto Next Toggle
				if self.results:
					v = not config_get("autonext")
					self.chkAutoNext.SetValue(v)
					self.onAutoNextToggle(None)
				return
				
			# New Added Favorites / Collections
			elif key == ord("L"): # Like / Favorite
				v = not self.chkFavorite.GetValue()
				self.chkFavorite.SetValue(v) # Visual update
				self.onFavoriteToggle(None) # Logic
				return
			elif key == ord("C"): # Collection
				self.onAddToCollection(None)
				return
		
		# Global Ctrl+Shift+T (Total) / Ctrl+T (Elapsed)
		if event.controlDown and event.shiftDown and key == ord("T"):
			self.get_duration()
			return
		elif event.controlDown and not event.shiftDown and key == ord("T") and self.player:
			speak(_("Elapsed: {}").format(self.player.get_elapsed()))
			return
		
		# Ensure Tab and other unhandled keys propagate
		event.Skip()

	@has_player
	def get_duration(self):
			speak(_("Duration: {}").format(self.player.get_duration()))

	def increase_volume(self):
		if self.player:
			vol = self.player.media.audio_get_volume()
		else:
			vol = int(config_get("volume"))

		vol = vol+5 if vol < 100 else 100
		if vol > 100: vol = 100
		
		if self.player:
			self.player.media.audio_set_volume(vol)
			self.player.volume = vol
			
		self.volumeSlider.SetValue(vol)
		self.speak_status(f"{vol}%")
		config_set("volume", vol)
		
	def decrease_volume(self):
		if self.player:
			vol = self.player.media.audio_get_volume()
		else:
			vol = int(config_get("volume"))
			
		vol = vol-5 if vol > 0 else 0
		
		if self.player:
			self.player.media.audio_set_volume(vol)
			self.player.volume = vol
			
		self.volumeSlider.SetValue(vol)
		self.speak_status(f"{vol}%")
		config_set("volume", vol)

	def toggleFullScreen(self):
		# Toggle based on current state
		is_full = self.IsFullScreen()
		val = not is_full 
		
		# Update internal button state if needed? Button is stateless.
		self.exitFullScreenBtn.Hide() if not val else None # Logic handled below

		config_set("fullscreen", val)
		
		# Cinema Mode Logic
		if val:
			# Hide Controls
			self.mainPanel.GetSizer().Hide(self.controlsSizer)
			self.mainPanel.GetSizer().Hide(self.slidersSizer)
			self.mainPanel.GetSizer().Hide(self.actionsSizer)
			self.exitFullScreenBtn.Show()
			self.exitFullScreenBtn.SetFocus()
			speak(_("Full screen on"))
		else:
			# Show Controls
			self.mainPanel.GetSizer().Show(self.controlsSizer)
			self.mainPanel.GetSizer().Show(self.slidersSizer)
			self.mainPanel.GetSizer().Show(self.actionsSizer)
			self.exitFullScreenBtn.Hide()
			self.playButton.SetFocus()
			speak(_("Full screen off"))
			
		self.mainPanel.Layout()
		self.ShowFullScreen(val)
		
		# Force style AFTER setting fullscreen to ensure taskbar button remains
		from utiles import force_taskbar_style
		force_taskbar_style(self)

	def get_videos_box(self):
		if hasattr(self.caller, 'searchResults'): return self.caller.searchResults
		elif hasattr(self.caller, 'videosBox'): return self.caller.videosBox
		elif hasattr(self.caller, 'favList'): return self.caller.favList
		elif hasattr(self.caller, 'historyList'): return self.caller.historyList
		elif hasattr(self.caller, 'videoList'): return self.caller.videoList
		return None

	def sync_shuffle_ptr(self, index):
		if not self.shuffle or not self.shuffle_indices: return
		try:
			self.shuffle_ptr = self.shuffle_indices.index(index)
		except ValueError:
			# Index not in shuffle list? Should reset or append?
			# Regenerate to be safe
			count = self.get_videos_box().GetCount() if self.get_videos_box() else 0
			if count > 0:
				self.shuffle_indices = list(range(count))
				random.shuffle(self.shuffle_indices)
				# Try to put current index at 0 or find it? 
				# If we re-shuffle, we disrupt 'history'.
				# Just find it again or reset ptr
				if index in self.shuffle_indices:
					self.shuffle_ptr = self.shuffle_indices.index(index)

	def changeTrack(self, track):
		# Guard against spamming
		if self.loading_track:
			import time
			curr = time.time()
			if curr - self.last_load_warn > 1.5:
				self.speak_status(_("Please wait, video is loading..."))
				self.last_load_warn = curr
			return
		self.loading_track = True

		# Smart Mode / Direct Object handling
		if isinstance(track, dict):
			self.video_data = track
			url = track.get('url')
			title = track.get('title')
			
			if config_get("continue"):
				try:
					self.history.add_history(track)
				except Exception: pass
			
			# Check Cache (URL-based)
			if url in self.track_cache:
				cache_data = self.track_cache.pop(url)
				if isinstance(cache_data, tuple) and len(cache_data) == 3:
					stream, start_time, stop_time = cache_data
				else:
					stream = cache_data
					start_time = 0.0
					stop_time = None
				self.track_cache.clear()
				self.speak_status(_("Loading..."))
				self._finish_track_loading(stream, url, title, start_time, stop_time)
				return

			self.target_url = url
			t = Thread(target=self._load_and_play_track, args=(url, title))
			t.daemon = True
			t.start()
			return

		# Existing Index Logic
		index = track
		# Cache cleanup is less critical now as we overwrite or use specific keys.
		# But if we jump far, we should probably clear old cache to save RAM?
		# For now, dictionary is small (2 items max).

		# Sync UI and Shuffle Pointer
		box = self.get_videos_box()
		if box and box.GetSelection() != index:
			box.SetSelection(index)
			
		self.sync_shuffle_ptr(index)

		if not isinstance(self.results, list):
			url = self.results.get_url(index)
			title = self.results.get_title(index)
			# Save History (Search/Playlist)
			try:
				if hasattr(self.caller, 'searchResults'): # Search
					data = {
						"title": title,
						"display_title": title,
						"url": url,
						"live": 0,
						"channel_name": self.results.get_channel(index)['name'],
						"channel_url": self.results.get_channel(index)['url']
					}
					if config_get("continue"):
						self.history.add_history(data)
				elif hasattr(self.caller, 'videosBox'): # Playlist
					vid = self.results.videos[index]
					data = {
						"title": vid.get('title', ''),
						"display_title": vid.get('title', ''),
						"url": vid.get('url', ''),
						"live": 0,
						"channel_name": vid.get('channel', {}).get('name', ''),
						"channel_url": vid.get('channel', {}).get('url', '')
					}
					if config_get("continue"):
						self.history.add_history(data)
				elif hasattr(self.caller, 'videoList'): # Collection
					item = self.results[index]
					data = {
						"title": item['title'],
						"display_title": item['title'],
						"url": item['url'],
						"live": 0,
						"channel_name": item.get('channel_name', '') or item.get('channel', {}).get('name', ''),
						"channel_url": item.get('channel_url', '') or item.get('channel', {}).get('url', '')
					}
					if config_get("continue"):
						self.history.add_history(data)
			except Exception as e:
				print(f"Error saving history in changeTrack: {e}")

		else:
			url = self.results[index]["url"]
			title = self.results[index]["title"]
			# Save History (List/Favorites)
			try:
				if config_get("continue"):
					try:
						self.history.add_history(self.results[index])
					except Exception: pass
			except Exception as e:
				print(f"Error saving history in changeTrack list: {e}")

		# Seamless Transition: DO NOT STOP PLAYER HERE
		# We let the current track play until _finish_track_loading calls stop/set_media

		if hasattr(self, "description"):
			del self.description 
		
		# Check cache for THIS index
		if index in self.track_cache:

			# Cache now stores tuple: (stream, start, stop)
			cache_data = self.track_cache.pop(index) 
			
			if isinstance(cache_data, tuple) and len(cache_data) == 3:
				stream, start_time, stop_time = cache_data
			else:
				# Backward compatibility or fallback if logic changes
				stream = cache_data
				start_time = 0.0
				stop_time = None
				
			# Trigger logic to clear others? Or just let them be replaced by next preload cycle.
			self.track_cache.clear() # Clear others to ensure fresh preload based on NEW position
			
			self.speak_status(_("Loading..."))
			self._finish_track_loading(stream, url, title, start_time, stop_time)
		else:
			# Offload heavy network streaming to thread
			self.speak_status(_("Loading..."))
			
			# Cancel previous preload if running?
			# We can't easily kill thread, but we can set Flag?
			# self.is_preloading is a mutex, unfortunately.
			# We rely on check_window_valid or logic check.
			
			self.target_url = url
			t = Thread(target=self._load_and_play_track, args=(url, title))
			t.daemon = True
			t.start()

	def fetch_related(self, url):
		if not self.smart_mode: return
		self.fetching_related = True
		self.last_related_error = None # Reset error
		try:
			# Not blocking main thread
			related = get_related_videos(url)
			if related:
				self.related_videos = related
				self.related_index = 0
				# Show Suggested Button
				self.safe_call_after(self.btnSuggested.Show)
				self.safe_call_after(self.mainPanel.Layout) # Refresh UI
				
				# Trigger Preload of the FIRST related video immediately
				# Update UI (Optional - maybe show "Related: X" in status?)
			# self.safe_call_after(self.SetStatusText, _("Found {} related videos").format(len(self.related_videos)))
			
			# Trigger Preload for the new related videos
			self.preload_nearby_tracks(force_smart=True)
			
		except Exception as e:
			print(f"Error fetching related: {e}")
			self.last_related_error = str(e)
		finally:
			self.fetching_related = False

	def _load_and_play_track(self, url, title):
		try:
			# Check race condition
			if hasattr(self, 'target_url') and self.target_url != url:
				self.loading_track = False
				return
				
			# Check Cache First (Safety)
			# ... (Logic usually handled in changeTrack but check here too?)
			
			# 1. Get Stream
			stream = get_video_stream(url) if not self.audio_mode else get_audio_stream(url)
			
			# 2. Silence Analysis
			start_time = 0.0
			stop_time = None
			if config_get("skip_silence"):
				try:
					s_start, s_stop = detect_silence(stream.url, headers=stream.http_headers, duration=getattr(stream, 'duration', 0))
					start_time = s_start
					if s_stop:
						stop_time = s_stop
				except Exception as e:
					print(f"Silence analysis failed: {e}")

			self._finish_track_loading(stream, url, title, start_time, stop_time)
			
			if self.smart_mode:
				# Add to session history
				self.session_history.add(url)
				t = Thread(target=self.fetch_related, args=(url,))
				t.daemon = True
				t.start()
			
		except Exception as e:
			print(f"Error loading track: {e}")
			
			# If stopped load manually?
			# Check race condition
			# If stopped load manually?
			# Check race condition
			if hasattr(self, 'target_url') and self.target_url != url:
				self.loading_track = False
				return

			# Determine Error Message
			emsg = str(e).lower()
			display_msg = str(e)
			if "sign in" in emsg or "bot" in emsg or "cookie" in emsg:
				display_msg = _("Playback blocked by YouTube anti-bot. Please check your cookies.")
			elif "private" in emsg:
				display_msg = _("This video is private.")
			elif "members-only" in emsg:
				display_msg = _("This video is for members only.")
				
			# Logic:
			# 1. Speak Error always? (Maybe just "Error" if skipping quickly)
			# 2. Check AutoNext
			# 3. If AutoNext: Skip
			# 4. If No AutoNext: Show Dialog
			
			# Auto-skip if in playlist/list mode AND AutoNext is enabled
			if self.results and config_get("autonext"):
				speak(f"{display_msg}. " + _("Skipping..."))
				
				# Wait and Check Interruption
				# We wait 1 second to accept user input (e.g. stop autonext)
				for i in range(10): # 1.0s total
					time.sleep(0.1)
					if not self.check_window_valid(): 
						self.loading_track = False
						return
					if not config_get("autonext"): # Check if user toggled off!
						break
				
				# Final Check before Skipping
				if config_get("autonext"):
					self.loading_track = False # Reset before recursive call!
					wx.CallAfter(self.next)
					return
			
			# Fallback: Show Dialog for Single Play OR if AutoNext was disabled
			self.loading_track = False
			speak(display_msg)
			wx.CallAfter(wx.MessageBox, display_msg, _("Error"), parent=self, style=wx.ICON_ERROR)

	def _finish_track_loading(self, stream_obj, url, title, start_time=None, stop_time=None):
		self.stream = stream_obj
		self.url = url
		self.title = title
		
		# Update UI
		self.safe_call_after(self.SetTitle, f"{title} - {application.name}")
		
		# Start Player
		try:
			# Ensure Player instance exists (Lazy Loading)
			if self.player is None:
				from .player import Player
				# Player init: (filename, hwnd, window=None, headers=None, **kwargs)
				# We need a handle.
				try:
					if not self.check_window_valid(): return
					hwnd = self.videoPanel.GetHandle()
				except (RuntimeError, Exception): return
				
				self.player = Player(url, hwnd, window=self.videoPanel, headers=stream_obj.http_headers)
			
			# Pass start/stop time to Player
			# Check audio_url safely
			audio_url = getattr(self.stream, 'audio_url', None)

			# CRITICAL: Ignore End Event from OLD media ending during swap
			self.player.ignore_end = True
			
			self.safe_call_after(self.player.set_media, self.stream.url, self.stream.http_headers, audio_slave=audio_url, start_time=start_time, stop_time=stop_time)
			
			# Start Playback! (Missing in previous patch)
			self.safe_call_after(self.player.media.play)
			self.safe_call_after(self.player.media.audio_set_volume, self.player.volume)
			
			self.loading_track = False # Loading complete, playback started
			
				
		except Exception as e:
			print(f"Error setting media: {e}")
			
		# Apply soft_stop_time logic to ANY loaded track
		self.soft_stop_time = stop_time if stop_time else None
		
		# Reset flag delayed? No, we reset it AFTER we are sure the new media is set.
		# But set_media is async in CallAfter... 
		# If we reset it immediately here, it might be too early if CallAfter is pending.
		
		# We need to reset ignore_end ONLY when the NEW media starts playing.
		# OR, we reset it in a delayed manner.
		
		def enable_end_check():
			import time
			time.sleep(1.5) # Wait for transition to settle
			if self.player: self.player.ignore_end = False
			
		Thread(target=enable_end_check, daemon=True).start()
		
		# Enable Controls
		self.safe_call_after(self.enable_controls)
		
		# On Finish Load actions
		self.onTimer(None)

		# Trigger Smart Preload (Loop/Next)
		def delayed_preload():
			# No delay - Instant preload as requested
			if not self or not self.check_window_valid(): return # Safety
			self.preload_nearby_tracks()
			
		t_pl = Thread(target=delayed_preload)
		t_pl.daemon = True
		t_pl.start()

	def enable_controls(self):
		# Helper to re-enable controls if they were disabled (placeholder if not used logic)
		# For now, just focus play button if needed or ensure UI is responsive
		if self.playButton: self.playButton.Enable()
		pass

	def preload_nearby_tracks(self, force_smart=False):
		if self.is_preloading: return # Prevent concurrent threads
		self.is_preloading = True
		try:
			# Check cancellation periodically
			if not self.check_window_valid(): return
			
			metrics = [] # List of items to preload (Int index OR Dict item)
			
			# SMART MODE LOGIC
			if self.smart_mode or force_smart:
				# Next: First related video (if available)
				if self.related_videos and self.related_index < len(self.related_videos):
					metrics.append(self.related_videos[self.related_index])
				
				# Prev: Last history item
				if self.history_stack and not force_smart:
					metrics.append(self.history_stack[-1])
					
			# NORMAL MODE LOGIC
			elif self.results is not None:
				videosBox = self.get_videos_box()
				if videosBox:
					count = videosBox.GetCount()
					current = videosBox.Selection
					
					# Next Index
					next_idx = -1
					if self.shuffle:
						next_ptr = self.shuffle_ptr + 1
						if next_ptr < len(self.shuffle_indices):
							next_idx = self.shuffle_indices[next_ptr]
					else:
						if current < count - 1:
							next_idx = current + 1
					if next_idx != -1: metrics.append(next_idx)

					# Prev Index
					prev_idx = -1
					if self.shuffle:
						prev_ptr = self.shuffle_ptr - 1
						if prev_ptr >= 0:
							prev_idx = self.shuffle_indices[prev_ptr]
					else:
						if current > 0:
							prev_idx = current - 1
					if prev_idx != -1: metrics.append(prev_idx)

			if not metrics: return
			
			# Check silence optimization dependency
			skip_silence = config_get("skip_silence")
			if not skip_silence: return

			for item in metrics:
				if not self.check_window_valid(): return
				try:
					# RESOLVE DATA
					cache_key = None
					url = ""
					title = "Unknown"
					
					if isinstance(item, int): # Index
						idx = item
						cache_key = idx
						if cache_key in self.track_cache: continue
						
						if not isinstance(self.results, list):
							url = self.results.get_url(idx)
							title = self.results.get_title(idx)
						else:
							url = self.results[idx]['url']
							title = self.results[idx]['title']
					elif isinstance(item, dict): # Smart Item
						cache_key = item['url']
						if cache_key in self.track_cache: continue
						url = item['url']
						title = item.get('title', 'Unknown')
					
					if not url: continue
					
					# Fetch Stream FIRST
					stream = get_video_stream(url) if not self.audio_mode else get_audio_stream(url)
					
					# Silence Analysis (Background)
					start_time = 0.0
					stop_time = None
					
					if config_get("skip_silence"):
						try:
							s_start, s_stop = detect_silence(stream.url, headers=stream.http_headers, duration=getattr(stream, 'duration', 0))
							start_time = s_start
							if s_stop:
								stop_time = s_stop
						except Exception as e:
							print(f"Silence analysis failed: {e}")

					# Cache: (stream, start, stop)
					self.track_cache[cache_key] = (stream, start_time, stop_time)
				except BotDetectionError as be:
					print(f"Bot detection preloading: {be}")
					break 
				except Exception as loop_e:
					print(f"Failed to preload item: {loop_e}")
				
		except Exception as e:
			wx.CallAfter(speak, _("Error loading playlist"))
		finally:
			self.is_preloading = False
			
	def check_window_valid(self):
		# Helper to check if window is still valid
		try:
			if self.shutting_down: return False
			if not self: return False
			if not self.player: return False # Player killed means we are dead
			return True
		except (RuntimeError, Exception):
			return False



	def safe_call_after(self, func, *args, **kwargs):
		# Wrapper to ensure CallAfter only executes if window is valid
		def wrapper():
			try:
				if self.check_window_valid():
					func(*args, **kwargs)
			except (RuntimeError, Exception):
				pass # Ignore errors if window died
		wx.CallAfter(wrapper)


	def next(self, auto=False):
		if not self.check_window_valid(): return

		# Auto-Next Debounce to prevent Double Skips (Race Condition)
		if auto:
			import time
			curr_time = time.time()
			if hasattr(self, 'last_auto_next') and (curr_time - self.last_auto_next < 2.0):
				print("Debounced double auto-next event.")
				return
			self.last_auto_next = curr_time

		# SMART NAVIGATION
		if self.smart_mode:
			if self.fetching_related:
				speak(_("Fetching suggested videos, please wait..."))
				return
				
			if not self.related_videos:
				# Smart Mode Failed (Empty or Error)
				msg = self.last_related_error or _("No suggested videos available.")
				
				# Config check
				if config_get("autonext"):
					# AutoNext ON: Try to alert user but stop? 
					# User asked to "Find Next" if possible.
					# But we are stuck. So we just speak error to not disrupt flow completely?
					# Or stop? 
					# Actually, best behavior for AutoNext failure is: Speak Error, Stop.
					speak(_("Unable to play next: {}").format(msg))
				else:
					# AutoNext OFF: Show Dialog
					wx.MessageBox(msg, _("Error"), parent=self, style=wx.ICON_ERROR)
				return
			
			# Iterate through suggestions to find one that hasn't been played recently
			scan_index = self.related_index
			found_new = False
			
			while scan_index < len(self.related_videos):
				item = self.related_videos[scan_index]
				
				# Check if in history stack (Back navigation)
				is_in_history = any(h.get('url') == item.get('url') for h in self.history_stack)
				
				# Check strict title match if URL differs? 
				# Sometimes URL changes but title is same "Faded".
				# Let's rely on URL first.
				is_in_session = item.get('url') in self.session_history
				
				if is_in_history or is_in_session or item.get('url') == self.url:
					# Skip this one
					scan_index += 1
					continue
				else:
					found_new = True
					self.related_index = scan_index # Update real index
					break
			
			if found_new:
				# Push current to history
				if self.video_data:
					self.history_stack.append(self.video_data)
					
				item = self.related_videos[self.related_index]
				self.related_index += 1
				
				self.speak_status(_("Playing suggested video") + ": " + item['title'])
				self.changeTrack(item)
			else:
				self.speak_status(_("End of suggestions."))
			return

		if self.results is None:
			return
		
		videosBox = None
		if hasattr(self.caller, 'searchResults'):
			videosBox = self.caller.searchResults
		elif hasattr(self.caller, 'videosBox'):
			videosBox = self.caller.videosBox
		elif hasattr(self.caller, 'favList'):
			videosBox = self.caller.favList
		elif hasattr(self.caller, 'historyList'):
			videosBox = self.caller.historyList
		elif hasattr(self.caller, 'videoList'):
			videosBox = self.caller.videoList
		else:
			return

		if not videosBox or not isinstance(videosBox, wx.ListBox): return
		try:
			if not videosBox.IsShownOnScreen() and not self.IsShown(): return # Basic visibility check
		except Exception: pass # Window might be destroyed
		
		try:
			current = videosBox.Selection
		except (RuntimeError, Exception): return # Handle "wrapped C/C++ object... deleted"
		count = videosBox.GetCount()

		if not self.shuffle:
			if current < count - 1:
				videosBox.Selection += 1
				index = videosBox.Selection
				self.changeTrack(index)
				
				# Load more logic
				if index >= count - 2:
					def load_more():
						if hasattr(self.caller, 'searchResults'):
							if self.results.load_more():
								self.safe_call_after(self.caller.searchResults.Append, self.results.get_last_titles())
						elif hasattr(self.caller, 'videosBox'): # Only playlist supports loading more
							if self.results.next():
								self.safe_call_after(self.caller.videosBox.Append, self.results.get_new_titles())
					t = Thread(target=load_more)
					t.daemon = True
					t.start()
			else:
				self.speak_status(_("No more videos"))
		else:
			# Shuffle Next
			if count == 0: return
			self.shuffle_ptr += 1
			
			# Wrap around logic (Infinite Loop)
			# Wrap around logic (Infinite Loop)
			if self.shuffle_ptr >= len(self.shuffle_indices):
				self.speak_status(_("Reshuffling..."))
				last_index = self.shuffle_indices[-1]
				random.shuffle(self.shuffle_indices)
				# Prevent immediate repeat of same song
				if len(self.shuffle_indices) > 1 and self.shuffle_indices[0] == last_index:
					# Swap first with second
					self.shuffle_indices[0], self.shuffle_indices[1] = self.shuffle_indices[1], self.shuffle_indices[0]
					
				self.shuffle_ptr = 0
			
			next_idx = self.shuffle_indices[self.shuffle_ptr]
			
			# Check valid range
			if 0 <= next_idx < count:
				# Update UI selection
				videosBox.Selection = next_idx
				self.changeTrack(next_idx)
			else:
				# Should not happen, but safety net
				self.shuffle_ptr = 0
				videosBox.Selection = self.shuffle_indices[0]
				self.changeTrack(self.shuffle_indices[0])


	def previous(self):
		if not self.check_window_valid(): return

		# SMART NAVIGATION
		if self.smart_mode:
			if self.history_stack:
				item = self.history_stack.pop()
				# When going back, we treat it as playing that item. 
				# _load_and_play_track will trigger fetch_related for IT.
				# This effectively resets the "Forward" path to be relative to the popped item.
				self.speak_status(_("Going back to") + ": " + item['title'])
				self.changeTrack(item)
			else:
				self.speak_status(_("No previous video."))
			return

		if self.results is None:
			return
		if hasattr(self.caller, 'searchResults'):
			videosBox = self.caller.searchResults
		elif hasattr(self.caller, 'videosBox'):
			videosBox = self.caller.videosBox
		elif hasattr(self.caller, 'favList'):
			videosBox = self.caller.favList
		elif hasattr(self.caller, 'historyList'):
			videosBox = self.caller.historyList
		elif hasattr(self.caller, 'videoList'):
			videosBox = self.caller.videoList
		else:
			return

		if not self.shuffle:
			if videosBox.Selection > 0:
				videosBox.Selection -= 1
				index = videosBox.Selection
				self.changeTrack(index)
			else:
				self.speak_status(_("No previous video"))
		else:
			# Shuffle Previous
			if self.shuffle_ptr > 0:
				self.shuffle_ptr -= 1
				prev_idx = self.shuffle_indices[self.shuffle_ptr]
				videosBox.Selection = prev_idx
				self.changeTrack(prev_idx)
			else:
				self.speak_status(_("Beginning of shuffle list"))

	def onCopy(self, event):
		pyperclip.copy(self.url)
		wx.MessageBox(_("Link copied successfully"), _("Done"), parent=self)

	def onBrowser(self, event):
		speak(_("Opening"))
		webbrowser.open(self.url)

	def onM4aDownload(self, event):
		dlg = DownloadProgress(wx.GetApp().GetTopWindow(), self.title)
		direct_download(1, self.url, dlg, path=config_get("path"))

	def onMp3Download(self, event):
		dlg = DownloadProgress(wx.GetApp().GetTopWindow(), self.title)
		direct_download(2, self.url, dlg, path=config_get("path"))

	def onAudioTrack(self, event):
		if not self.player: return
		speak(_("Fetching audio tracks, please wait..."))
		Thread(target=self.bg_fetch_audio).start()
		
	def bg_fetch_audio(self):
		tracks = fetch_audio_tracks(self.url)
		wx.CallAfter(self.show_audio_track_dialog, tracks)

	def show_audio_track_dialog(self, tracks):
		if not tracks:
			wx.MessageBox(_("No other audio tracks available."), _("Info"), parent=self)
			return

		# Prepare choices: Default + New Tracks
		# Use a list of dicts to map index to data
		self.audio_choices_data = [{'label': _("Default"), 'url': None, 'language': None}] + tracks
		choices = [item['label'] for item in self.audio_choices_data]
		
		dlg = wx.SingleChoiceDialog(self, _("Select Audio Track"), _("Audio Tracks"), choices)
		if dlg.ShowModal() == wx.ID_OK:
			idx = dlg.GetSelection()
			item = self.audio_choices_data[idx]
			if item['url']:
				# Restart with new audio
				self.restart_with_audio_track(item['url'], item['label'], item.get('language'))
			else:
				# Revert to default
				self.restart_with_audio_track(None, "Default")
				
		dlg.Destroy()

	def restart_with_audio_track(self, audio_url, label, lang_code=None):
		if not self.player: return
		
		# Save current position (Percentage for DB, Time for Resume)
		pos_pct = self.player.media.get_position()
		pos_time = self.player.media.get_time()
		if pos_time == -1: pos_time = 0
		
		was_playing = self.player.media.get_state() == State.Playing
		
		# Save preference
		val = label if label != "Default" else -1
		if self.url in Continue.get_all():
			Continue.update(self.url, pos_pct, val)
		else:
			Continue.new_continue(self.url, pos_pct, val)

		# Restart Player
		self.speak_status(_("Switched to") + f" {label}")
		
		# Stop current
		self.player.media.stop()
		
		# Re-init media with slave (remove start keys)
		# Pass start_time explicitly to Resume immediately without relying on "Continue" logic
		
		# Calculate seconds from pos_pct? No, pos_time is ms.
		start_seconds = pos_time / 1000.0
		
		self.player.set_media(
			self.video_stream.url, 
			self.video_stream.http_headers, 
			audio_slave=audio_url,
			start_time=start_seconds
		)
		
		self.player.media.play()
		self.player.media.audio_set_volume(self.player.volume)
		# Restore rate?
		# self.player.media.set_rate(saved_rate)
		# Launch robust switcher thread
		Thread(target=self.post_audio_switch, args=(pos_time, label, lang_code)).start()

	def onShow(self, event):
		if event.IsShown():
			self.playButton.SetFocus()
		event.Skip()

	def onActivate(self, event):
		if event.GetActive():
			# Check where focus is. If focus is lost (None) or on the Frame/Panel itself,
			# restoration is needed to ensure keyboard traps work.
			focused = self.FindFocus()
			if focused in (self, self.mainPanel, None):
				# Prefer playButton as anchor
				if self.playButton:
					self.playButton.SetFocus()
		event.Skip()
		
	def post_audio_switch(self, position, label, lang_code):
		# Wait for Play parameters to initialize
		# Retry loop for 10 seconds
		ready = False
		for _ in range(20):
			if self.player.media.get_state() in [State.Playing, State.Paused]:
				ready = True
				break
			time.sleep(0.5)
			
		if not ready: return
		
		# 1. Restore Position
		if position > 0:
			self.player.media.set_time(int(position))
			
		# 2. Force Audio Selection
		# Wait for tracks to populate (Metadata parsing)
		selected_id = -1
		
		# Try to find the track that matches our label/lang
		# We expect the new track to appear.
		# Retry looking for track
		for _ in range(10):
			tracks = self.player.get_audio_tracks()
			# tracks format: [(id, bytes_desc), ...]
			
			# Logic:
			# If we added a slave, it likely has a different ID or is new.
			# Filter out -1.
			valid = [t for t in tracks if t[0] != -1]
			
			if not valid:
				time.sleep(0.5)
				continue
				
			# Search for match
			# If lang_code provided, look for it in description
			# Or match label
			found = False
			for tid, desc in valid:
				d = desc.decode('utf-8') if isinstance(desc, bytes) else str(desc)
				
				# Criteria 1: Lang Code in description (e.g. "vi" in "vi (Vietnamese)")
				if lang_code and lang_code.lower() in d.lower():
					selected_id = tid
					found = True
					break
					
				# Criteria 2: Label fuzzy match
				# Our label: "vi" or "Vietnamese".
				if label.lower() in d.lower():
					selected_id = tid
					found = True
					break
			
			if found:
				break
				
			# If not found, maybe it's the LAST track added?
			# If valid tracks > 1, pick the last one (usually slave)
			if len(valid) > 1:
				selected_id = valid[-1][0]
				found = True
				break
				
			time.sleep(0.5)
			
		if selected_id != -1:
			self.safe_call_after(self.player.set_audio_track, selected_id)
			# wx.CallAfter(speak, _("Audio restored and synchronized."))


	def restore_audio_preference(self, label):
		# Background fetch to find URL for label
		Thread(target=self.bg_restore_audio, args=(label,)).start()

	def bg_restore_audio(self, label):
		tracks = fetch_audio_tracks(self.url)
		# Find match
		url = None
		lang = None
		for t in tracks:
			# Match label exactly or loosely?
			# Label in DB might be "vi (Vietnamese...)"
			# New label might be "vi (Vietnamese...)"
			if t['label'] == label:
				url = t['url']
				lang = t.get('language')
				break
		
		if url:
			self.safe_call_after(self.restart_with_audio_track, url, label, lang)
		else:
			# Only warn if it was a persistent pref that is now gone?
			# Or just fail silently to default
			pass

	def onVideoDownload(self, event):
		dlg = DownloadProgress(wx.GetApp().GetTopWindow(), self.title)
		direct_download(0, self.url, dlg, path=config_get("path"))


	def onDirect(self, event):
		dlg = DownloadProgress(wx.GetApp().GetTopWindow(), self.title)
		direct_download(int(config_get('defaultformat')), self.url, dlg, path=config_get("path"))

	def onDescription(self, event):
		if hasattr(self, "description"):
			DescriptionDialog(self, self.description)
			return
		def extract_description():
			try:
				speak(_("Fetching video description"))
				info = Video.getInfo(self.url)
			except Exception as e:
				print(e)
				speak(_("An error occurred while fetching video description"))
				return
			self.description = info['description']
			self.safe_call_after(DescriptionDialog, self, self.description)
		t = Thread(target=extract_description)
		t.daemon = True
		t.start()

	def extract_description(self):
		try:
			info = Video.get(self.url)
		except Exception:
			return
		self.description = info['description']
		
		# Construct metadata for usage
		data = {
			"title": info.get('title', self.title),
			"display_title": info.get('title', self.title),
			"url": self.url,
			"live": 0,
			"channel_name": info.get('channel_name', _("Unknown")),
			"channel_url": info.get('channel_url', "")
		}
		
		# Update self.video_data for Favorite/History
		# If we already have video_data (from search list), prefer it over potential "Unknown" from simple extraction
		if self.video_data and self.video_data.get("channel_name") and self.video_data["channel_name"] != _("Unknown"):
			# Update only if we have better info, or keep existing.
			# For now, trust the list data if it exists.
			pass
		else:
			self.video_data = data

		# Save History if not saved yet (e.g. Play from Link)
		if not self.history_saved and config_get("continue"):
			try:
				self.history.add_history(data)
				self.history_saved = True
			except Exception as e:
				print(f"Error saving history in extract_description: {e}")

