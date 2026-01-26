import os
import sys

import wx
import shutil
from paths import settings_path
from settings_handler import config_get, config_set
from language_handler import supported_languages
from backup_handler import backup_data, restore_data


languages = {index:language for language, index in enumerate(supported_languages.values())}

class SettingsDialog(wx.Dialog):
	def __init__(self, parent):
		wx.Dialog.__init__(self, parent, title=_("Settings"))
		self.SetSize(600, 450)
		self.Centre()
		self.preferences = {}
		
		# --- Main Container ---
		mainSizer = wx.BoxSizer(wx.VERTICAL)
		
		# --- Navigation ---
		nav_choices = [
			_("Preferences"), 
			_("Download"), 
			_("Player"), 
			_("Cookies"), 
			_("Data")
		]
		self.navBox = wx.RadioBox(self, label=_("Category"), choices=nav_choices, majorDimension=1, style=wx.RA_SPECIFY_ROWS)
		self.navBox.Bind(wx.EVT_RADIOBOX, self.onNavChange)
		
		# --- Content Container ---
		self.contentSizer = wx.BoxSizer(wx.VERTICAL)
		
		# Create Pages (Panels) hidden by default
		self.page_prefs = self.setup_prefs_page()
		self.page_download = self.setup_download_page()
		self.page_player = self.setup_player_page()
		self.page_cookies = self.setup_cookies_page()
		self.page_data = self.setup_data_page()
		
		# Add all pages to content sizer
		self.contentSizer.Add(self.page_prefs, 1, wx.EXPAND | wx.ALL, 5)
		self.contentSizer.Add(self.page_download, 1, wx.EXPAND | wx.ALL, 5)
		self.contentSizer.Add(self.page_player, 1, wx.EXPAND | wx.ALL, 5)
		self.contentSizer.Add(self.page_cookies, 1, wx.EXPAND | wx.ALL, 5)
		self.contentSizer.Add(self.page_data, 1, wx.EXPAND | wx.ALL, 5)
		
		# --- Footer ---
		footerSizer = wx.BoxSizer(wx.HORIZONTAL)
		openConfigBtn = wx.Button(self, -1, _("Open Configuration Folder"))
		okButton = wx.Button(self, wx.ID_OK, _("O&K"))
		okButton.SetDefault()
		cancelButton = wx.Button(self, wx.ID_CANCEL, _("C&ancel"))
		
		footerSizer.Add(openConfigBtn, 0, wx.ALL, 5)
		footerSizer.AddStretchSpacer()
		footerSizer.Add(okButton, 0, wx.ALL, 5)
		footerSizer.Add(cancelButton, 0, wx.ALL, 5)
		
		# Bindings
		openConfigBtn.Bind(wx.EVT_BUTTON, self.onOpenConfig)
		okButton.Bind(wx.EVT_BUTTON, self.onOk)
		self.Bind(wx.EVT_CHAR_HOOK, self.onHook)
		
		# Assemble Layout
		mainSizer.Add(self.navBox, 0, wx.EXPAND | wx.ALL, 5)
		mainSizer.Add(self.contentSizer, 1, wx.EXPAND | wx.ALL, 5)
		mainSizer.Add(footerSizer, 0, wx.EXPAND | wx.ALL, 5)
		
		self.SetSizer(mainSizer)
		
		# Initialize View
		self.update_pages(0)
		self.onFormatChange(None) # Init dynamic UI for MP3
		
		self.navBox.SetFocus()
		self.ShowModal()

	def onHook(self, event):
		key = event.GetKeyCode()
		# Ctrl+Tab Navigation
		if key == wx.WXK_TAB and event.ControlDown():
			sel = self.navBox.GetSelection()
			count = self.navBox.GetCount()
			
			if event.ShiftDown():
				new_sel = (sel - 1) % count
			else:
				new_sel = (sel + 1) % count
				
			self.navBox.SetSelection(new_sel)
			self.update_pages(new_sel)
			self.navBox.SetFocus()
			return
		
		event.Skip()

	def setup_prefs_page(self):
		p = wx.Panel(self)
		sizer = wx.BoxSizer(wx.VERTICAL)
		
		# Language (Moved from General)
		lbl_lang = wx.StaticText(p, -1, _("Program Language: "))
		self.languageBox = wx.Choice(p, -1, name="language")
		self.languageBox.Set(list(supported_languages.keys()))
		try:
			self.languageBox.Selection = languages[config_get("lang")]
		except KeyError:
			self.languageBox.Selection = 0
		
		sizer.Add(lbl_lang, 0, wx.BOTTOM, 5)
		sizer.Add(self.languageBox, 0, wx.EXPAND | wx.BOTTOM, 15)
		
		# Existing Preferences
		self.autoDetectItem = wx.CheckBox(p, -1, _("Auto detect links on startup"), name="autodetect")
		self.autoCheckForUpdates = wx.CheckBox(p, -1, _("Auto check for updates on startup"), name="checkupdates")
		self.autoLoadItem = wx.CheckBox(p, -1, _("Load more results when reaching the end of the list"), name="autoload")
		self.swapPlayHotkeys = wx.CheckBox(p, -1, _("Swap Enter and Ctrl+Enter for Video/Audio"), name="swap_play_hotkeys")
		self.speakBackground = wx.CheckBox(p, -1, _("Speak notifications when window is inactive"), name="speak_background")
		
		# Values
		self.autoDetectItem.SetValue(config_get("autodetect"))
		self.autoCheckForUpdates.SetValue(config_get("checkupdates"))
		self.autoLoadItem.SetValue(config_get("autoload"))
		self.swapPlayHotkeys.SetValue(config_get("swap_play_hotkeys"))
		self.speakBackground.SetValue(config_get("speak_background"))
		
		# Bindings
		for ctrl in [self.autoDetectItem, self.autoCheckForUpdates, self.autoLoadItem, self.swapPlayHotkeys, self.speakBackground]:
			ctrl.Bind(wx.EVT_CHECKBOX, self.onCheck)
			sizer.Add(ctrl, 0, wx.ALL, 5)
			
		p.SetSizer(sizer)
		return p

	def setup_download_page(self):
		p = wx.Panel(self)
		sizer = wx.BoxSizer(wx.VERTICAL)
		
		# Download Folder (Moved from General)
		lbl_path = wx.StaticText(p, -1, _("Download Folder: "))
		pathSizer = wx.BoxSizer(wx.HORIZONTAL)
		self.pathField = wx.TextCtrl(p, -1, value=config_get("path"), name="path", style=wx.TE_READONLY|wx.TE_MULTILINE|wx.HSCROLL)
		changeButton = wx.Button(p, -1, _("&Change Path"))
		changeButton.Bind(wx.EVT_BUTTON, self.onChange)
		
		pathSizer.Add(self.pathField, 1, wx.EXPAND | wx.RIGHT, 5)
		pathSizer.Add(changeButton, 0)
		
		sizer.Add(lbl_path, 0, wx.BOTTOM, 5)
		sizer.Add(pathSizer, 0, wx.EXPAND | wx.BOTTOM, 15)
		
		# Existing Download Settings
		lbl_fmt = wx.StaticText(p, -1, _("Direct download format: "))
		self.formats = wx.Choice(p, -1, choices=[_("Video (mp4)"), _("Audio (m4a)"), _("Audio (mp3)")])
		self.formats.Selection = int(config_get('defaultformat'))
		self.formats.Bind(wx.EVT_CHOICE, self.onFormatChange)
		
		self.lblMp3 = wx.StaticText(p, -1, _("MP3 conversion quality: "))
		self.mp3Quality = wx.Choice(p, -1, choices=["96 kbps", "128 kbps", "192 kbps", "256 kbps", "320 kbps"], name="conversion")
		self.mp3Quality.Selection = int(config_get("conversion"))
		
		sizer.Add(lbl_fmt, 0, wx.TOP, 5)
		sizer.Add(self.formats, 0, wx.EXPAND | wx.BOTTOM, 15)
		sizer.Add(self.lblMp3, 0, wx.TOP, 5)
		sizer.Add(self.mp3Quality, 0, wx.EXPAND | wx.BOTTOM, 5)
		
		p.SetSizer(sizer)
		return p

	def setup_player_page(self):
		p = wx.Panel(self)
		sizer = wx.BoxSizer(wx.VERTICAL)
		
		# Audio Device Selector (First Item)
		lbl_device = wx.StaticText(p, -1, _("Audio Output Device: "))
		self.deviceBox = wx.Choice(p, -1, name="audio_device")
		
		# Fetch Devices
		# We need to access Player functionality. 
		# Since Player class logic wraps VLC, it's safer to use it or the global instance.
		from media_player.player import get_vlc_instance, Player
		
		# Try to get devices. 
		# We need a media player instance to enum devices (VLC limitation often requires a player instance, not just libvlc instance)
		# But player.py's get_audio_output_devices uses self.media which is a MediaPlayer.
		# Let's try to create a dummy player lightly or use the global vlc instance if possible.
		# Note: audio_output_device_enum is a method of MediaPlayer in vlc.py, 
		# but strictly it is 'libvlc_audio_output_device_enum' which takes a Player instance.
		
		self.device_map = []
		try:
			# Instantiate a lightweight dummy player just for querying
			# We pass dummy logic
			p_dummy = Player(filename="", hwnd=0)
			devices = p_dummy.get_audio_output_devices()
			
			choices = []
			current_device_id = config_get("audio_device")
			selection = 0
			
			for i, dev in enumerate(devices):
				choices.append(dev['name'])
				self.device_map.append(dev['id'])
				if dev['id'] == current_device_id:
					selection = i
			
			self.deviceBox.Set(choices)
			self.deviceBox.Selection = selection
			
			# Clean up dummy is auto handled by GC mostly, or we could stop it if it started playing (it shouldn't with empty file)
			p_dummy.media.stop()
			p_dummy = None
			
		except Exception as e:
			print(f"Error fetching audio devices: {e}")
			self.deviceBox.Set(["Default"])
			self.deviceBox.Selection = 0
			self.device_map = ["Default"]
			self.deviceBox.Disable()

		sizer.Add(lbl_device, 0, wx.TOP, 5)
		sizer.Add(self.deviceBox, 0, wx.EXPAND | wx.BOTTOM, 15)
		
		# Standard Settings
		self.continueWatching = wx.CheckBox(p, -1, _("Continue watching"), name="continue")
		self.repeateTracks = wx.CheckBox(p, -1, _("Repeat video"), name="repeatetracks")
		self.autoPlayNext = wx.CheckBox(p, -1, _("Auto play next video"), name="autonext")
		self.chkSkipSilence = wx.CheckBox(p, -1, _("Skip silence (Recommended only for music)"), name="skip_silence")
		self.chkPlayerNotifications = wx.CheckBox(p, -1, _("Speak player status notifications"), name="player_notifications")
		
		# Values
		self.continueWatching.SetValue(config_get("continue"))
		self.repeateTracks.SetValue(config_get("repeatetracks"))
		self.autoPlayNext.SetValue(config_get("autonext"))
		self.chkSkipSilence.SetValue(config_get("skip_silence"))
		self.chkPlayerNotifications.SetValue(config_get("player_notifications"))
		
		# Bindings
		for ctrl in [self.continueWatching, self.repeateTracks, self.autoPlayNext, self.chkSkipSilence, self.chkPlayerNotifications]:
			ctrl.Bind(wx.EVT_CHECKBOX, self.onCheck)
			sizer.Add(ctrl, 0, wx.ALL, 5)
			
		p.SetSizer(sizer)
		return p

	def setup_cookies_page(self):
		p = wx.Panel(self)
		sizer = wx.BoxSizer(wx.VERTICAL)
		
		info = wx.StaticText(p, -1, _("Import cookies.txt to fix login or 403 errors."))
		
		btnSizer = wx.BoxSizer(wx.HORIZONTAL)
		instructionBtn = wx.Button(p, -1, _("How to get cookies.txt?"))
		importCookiesBtn = wx.Button(p, -1, _("Import cookies.txt..."))
		
		btnSizer.Add(instructionBtn, 1, wx.RIGHT, 5)
		btnSizer.Add(importCookiesBtn, 1)
		
		clearCookiesBtn = wx.Button(p, -1, _("Clear cookies.txt"))
		
		instructionBtn.Bind(wx.EVT_BUTTON, self.onInstructions)
		importCookiesBtn.Bind(wx.EVT_BUTTON, self.onImportCookies)
		clearCookiesBtn.Bind(wx.EVT_BUTTON, self.onClearCookies)
		
		sizer.Add(info, 0, wx.ALL, 5)
		sizer.Add(btnSizer, 0, wx.EXPAND | wx.ALL, 5)
		sizer.Add(clearCookiesBtn, 0, wx.EXPAND | wx.ALL, 5)
		
		p.SetSizer(sizer)
		return p

	def setup_data_page(self):
		p = wx.Panel(self)
		sizer = wx.BoxSizer(wx.VERTICAL)
		
		info = wx.StaticText(p, -1, _("Backup or Restore your configuration."))
		
		dataSizer = wx.BoxSizer(wx.HORIZONTAL)
		backupBtn = wx.Button(p, -1, _("Backup Configuration..."))
		restoreBtn = wx.Button(p, -1, _("Restore Configuration..."))
		
		dataSizer.Add(backupBtn, 1, wx.RIGHT, 5)
		dataSizer.Add(restoreBtn, 1)
		
		backupBtn.Bind(wx.EVT_BUTTON, self.onBackup)
		restoreBtn.Bind(wx.EVT_BUTTON, self.onRestore)
		
		sizer.Add(info, 0, wx.ALL, 5)
		sizer.Add(dataSizer, 0, wx.EXPAND | wx.ALL, 5)
		
		p.SetSizer(sizer)
		return p

	def onNavChange(self, event):
		selection = self.navBox.GetSelection()
		self.update_pages(selection)

	def update_pages(self, selection):
		# Hide all pages first
		self.page_prefs.Hide()
		self.page_download.Hide()
		self.page_player.Hide()
		self.page_cookies.Hide()
		self.page_data.Hide()
		
		# Show selected
		target = None
		if selection == 0: target = self.page_prefs
		elif selection == 1: target = self.page_download
		elif selection == 2: target = self.page_player
		elif selection == 3: target = self.page_cookies
		elif selection == 4: target = self.page_data
		
		if target:
			target.Show()
			# target.SetFocus() # Removed to keep focus on NavBox
			
		self.Layout()

	def onFormatChange(self, event):
		# "Audio (mp3)" is index 2
		is_mp3 = (self.formats.Selection == 2)
		# Toggle visibility on Download Page Controls
		self.lblMp3.Show(is_mp3)
		self.mp3Quality.Show(is_mp3)
		self.page_download.Layout() # Re-layout the page
		self.Layout()

	def onCheck(self, event):
		obj = event.EventObject
		if all((self.repeateTracks.Value, self.autoPlayNext.Value)) and obj in (self.repeateTracks, self.autoPlayNext):
			self.repeateTracks.Value = self.autoPlayNext.Value = False
		if obj.Name in self.preferences and config_get(obj.Name) == obj.Value:
			del self.preferences[obj.Name]
		elif not obj.Value == config_get(obj.Name):
			self.preferences[obj.Name] = obj.Value
	def onChange(self, event):
		new = wx.DirSelector(_("Select Download Folder"), os.path.join(os.getenv("userprofile"), "downloads"), parent=self)
		if not new == "":
			self.preferences['path'] = new
			self.pathField.Value = new
			self.pathField.SetFocus()
	def onImportCookies(self, event):
		dlg = wx.FileDialog(self, _("Select cookies.txt"), wildcard="Text files (*.txt)|*.txt", style=wx.FD_OPEN | wx.FD_FILE_MUST_EXIST)
		if dlg.ShowModal() == wx.ID_OK:
			path = dlg.GetPath()
			try:
				target = os.path.join(settings_path, "cookies.txt")
				shutil.copyfile(path, target)
				wx.MessageBox(_("Cookies imported successfully. Restart functionality to apply."), _("Success"), parent=self)
			except Exception as e:
				wx.MessageBox(_("Failed to import cookies: {}").format(e), _("Error"), parent=self, style=wx.ICON_ERROR)
		dlg.Destroy()
	def onInstructions(self, event):
		msg = _("1. Install 'Get cookies.txt LOCALLY' extension for Chrome/Firefox.\n2. Open YouTube and log in.\n3. Open the extension and click 'Export'.\n4. Save the file.\n5. Click 'Import cookies.txt...' below and select that file.")
		wx.MessageBox(msg, _("Instructions"), parent=self)
	def onClearCookies(self, event):
		target = os.path.join(settings_path, "cookies.txt")
		if os.path.exists(target):
			if wx.MessageBox(_("Are you sure you want to delete your current cookies.txt?"), _("Confirm"), wx.YES_NO | wx.ICON_QUESTION, parent=self) == wx.YES:
				try:
					os.remove(target)
					wx.MessageBox(_("Cookies deleted successfully."), _("Success"), parent=self)
				except Exception as e:
					wx.MessageBox(_("An error occurred: {}").format(e), _("Error"), parent=self, style=wx.ICON_ERROR)
		else:
			wx.MessageBox(_("No cookies found to delete."), _("Info"), parent=self)
	def onOpenConfig(self, event):
		try:
			os.startfile(settings_path)
		except Exception as e:
			wx.MessageBox(_("An error occurred: {}").format(e), _("Error"), parent=self, style=wx.ICON_ERROR)
	def onBackup(self, event):
		dlg = wx.FileDialog(self, _("Save Backup File"), wildcard="ZIP files (*.zip)|*.zip", style=wx.FD_SAVE | wx.FD_OVERWRITE_PROMPT)
		if dlg.ShowModal() == wx.ID_OK:
			path = dlg.GetPath()
			if not path.lower().endswith(".zip"):
				path += ".zip"
			
			if backup_data(path):
				wx.MessageBox(_("Backup created successfully!"), _("Success"), parent=self)
			else:
				wx.MessageBox(_("Backup failed."), _("Error"), parent=self, style=wx.ICON_ERROR)
		dlg.Destroy()
	def onRestore(self, event):
		dlg = wx.FileDialog(self, _("Select Backup File"), wildcard="ZIP files (*.zip)|*.zip", style=wx.FD_OPEN | wx.FD_FILE_MUST_EXIST)
		if dlg.ShowModal() == wx.ID_OK:
			path = dlg.GetPath()
			msg = _("Restoring data will overwrite your current configuration and restart the program.\nAre you sure you want to proceed?")
			if wx.MessageBox(msg, _("Confirm Restore"), wx.YES_NO | wx.ICON_WARNING, parent=self) == wx.YES:
				if restore_data(path):
					wx.MessageBox(_("Restore successful! Program will now restart."), _("Success"), parent=self)
					# Restart Application
					os.execl(sys.executable, sys.executable, *sys.argv)
				else:
					wx.MessageBox(_("Restore failed."), _("Error"), parent=self, style=wx.ICON_ERROR)
		dlg.Destroy()
	def onOk(self, event):
		from settings_handler import config_set, config_update_many
		
		restart = False 
		if self.preferences:
			config_update_many(self.preferences)
		if not self.mp3Quality.Selection == int(config_get("conversion")):
			config_set("conversion", self.mp3Quality.Selection)
		
		# Save Audio Device
		selected_device_id = self.device_map[self.deviceBox.Selection]
		if not selected_device_id == config_get("audio_device"):
			config_set("audio_device", selected_device_id)
			# restart = True # Changing audio device requires restart or re-init of player, restart is safest for global effect
			
			# Apply immediately if possible
			try:
				parent = self.GetParent()
				if parent and hasattr(parent, 'player') and parent.player:
					parent.player.set_audio_output_device(selected_device_id)
			except Exception as e:
				print(f"Failed to apply audio device immediately: {e}")
			
		config_set("defaultformat", self.formats.Selection) if not self.formats.Selection == int(config_get('defaultformat')) else None
		
		lang = {value:key for key, value in languages.items()}
		if not lang[self.languageBox.Selection] == config_get("lang"):
			config_set("lang", lang[self.languageBox.Selection])
			restart = True
			
		if restart:
			msg = wx.MessageBox(_("Configuration changed. You must restart the program for the changes to take effect. Do you want to restart now?"), _("Alert"), style=wx.YES_NO | wx.ICON_WARNING, parent=self)
			if msg == 2: # wx.YES
				os.execl(sys.executable, sys.executable, *sys.argv)
		self.Destroy()
