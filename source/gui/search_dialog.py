import wx



class SearchDialog(wx.Dialog):
	def __init__(self, parent, value=""):
		wx.Dialog.__init__(self, parent=parent, title=_("Search"))
		self.Centre()
		panel = wx.Panel(self)
		sizer = wx.BoxSizer(wx.VERTICAL)
		
		# 1. Search Field
		lbl = wx.StaticText(panel, -1, _("Search YouTube: "))
		self.searchField = wx.TextCtrl(panel, -1, value=value)
		
		# 2. Voice Search Button (Created here for Correct Tab Order)
		from .voice_handler import VoiceHandler
		self.voice_handler = VoiceHandler()
		self.voiceParams = {"recording": False} 

		self.btnVoice = wx.Button(panel, -1, _("Voice Search (Hold Space)"))
		
		# 3. Filter
		lbl1 = wx.StaticText(panel, -1, _("Filter: "))
		self.filterBox = wx.Choice(panel, -1, choices=
							 [_("No Filter"), 
						_("Playlist")])
		self.filterBox.Selection = 0

		# 4. Buttons
		self.searchButton = wx.Button(panel, wx.ID_OK, _("Search"))
		self.searchButton.SetDefault()
		self.searchButton.Enabled = False if value == "" else True
		closeButton = wx.Button(panel, wx.ID_CANCEL, _("Close"))

		# Layout
		sizer1 = wx.BoxSizer(wx.HORIZONTAL)
		sizer1.Add(lbl, 1)
		sizer1.Add(self.searchField, 1)
		# Voice button in its own row/sizer? Or appended to sizer1?
		# User wanted ordering. Visual layout wasn't strictly defined but "After search box".
		# Let's keep the layout we had but with correct tab order.
		# We can just Add them to sizers in any order if we set Tab traversal, 
		# OR we rely on creation order. WxPython relies on creation order.
		
		sizer1.Add(self.btnVoice, 0, wx.ALL, 2)
		
		sizer2 = wx.BoxSizer(wx.HORIZONTAL)
		sizer2.Add(lbl1, 1)
		sizer2.Add(self.filterBox, 1)

		sizer3 = wx.BoxSizer(wx.HORIZONTAL)
		sizer3.Add(self.searchButton, 1)
		sizer3.Add(closeButton, 1)
		
		sizer.Add(sizer1, 1, wx.EXPAND)
		sizer.Add(sizer2, 1, wx.EXPAND)
		sizer.Add(sizer3, 1, wx.EXPAND)
		panel.SetSizer(sizer)
		
		self.searchField.Bind(wx.EVT_TEXT, lambda event: self.searchButton.Disable() if self.searchField.Value == "" else self.searchButton.Enable())
		self.searchButton.Bind(wx.EVT_BUTTON, self.onSearch)
		closeButton.Bind(wx.EVT_BUTTON, self.onClose)
		
		# Voice Events
		self.btnVoice.Bind(wx.EVT_LEFT_DOWN, self.onVoiceDown)
		self.btnVoice.Bind(wx.EVT_LEFT_UP, self.onVoiceUp)
		# CustomButton handles Enter/Space by mapping to Click?
		# CustomButton triggers EVT_BUTTON.
		# But we want "Hold" functionality.
		# EVT_BUTTON is "Click" (Down+Up).
		# We need Down and Up events.
		# CustomButton binds EVT_KEY_DOWN.
		# We should bind EVT_KEY_DOWN on the button instance too, which overrides or chains?
		self.btnVoice.Bind(wx.EVT_KEY_DOWN, self.onVoiceKey)
		self.btnVoice.Bind(wx.EVT_KEY_UP, self.onVoiceKeyUp)
		
		# Focus Management to allow Enter Key Hold - REMOVED (Replaced by Hook)
		# self.btnVoice.Bind(wx.EVT_SET_FOCUS, self.onVoiceFocus)
		# self.btnVoice.Bind(wx.EVT_KILL_FOCUS, self.onVoiceBlur)
		
		
		self.ShowModal()

	def onVoiceDown(self, event):
		if not self.voiceParams['recording']:
			self.voiceParams['recording'] = True
			self.voice_handler.start_recording_direct()
		if event: event.Skip()

	def onVoiceUp(self, event):
		if self.voiceParams['recording']:
			self.voiceParams['recording'] = False
			audio = self.voice_handler.stop_recording()
			if audio:
				# Process in thread to avoid UI freeze? 
				# Recognize is blocking (network).
				# Show a "Processing..." status or beep?
				# Helper to process
				from threading import Thread
				Thread(target=self._process_voice, args=(audio,)).start()
		if event: event.Skip()

	def _process_voice(self, audio):
		text = self.voice_handler.recognize(audio)
		if text:
			def update_and_search():
				self.searchField.SetValue(text)
				self.onSearch(None)
			wx.CallAfter(update_and_search)

	def onVoiceKey(self, event):
		if event.KeyCode in [wx.WXK_SPACE]:
			if not self.voiceParams['recording']:
				self.onVoiceDown(None)
			return 
		event.Skip()

	def onVoiceKeyUp(self, event):
		if event.KeyCode in [wx.WXK_SPACE]:
			if self.voiceParams['recording']:
				self.onVoiceUp(None)
			return
		event.Skip()
	def onSearch(self, event):
		self.query = self.searchField.Value if self.searchField.Value != "" else None
		self.filter = self.filterBox.Selection
		self.Destroy()
	def onClose(self, event):
		self.query = None
		self.filter = None
		self.Destroy()