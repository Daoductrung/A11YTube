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
		self.SetSize(500, 500)
		self.Centre()
		self.preferences = {}
		panel = wx.Panel(self)
		lbl = wx.StaticText(panel, -1, _("Program Language: "), name="language")
		self.languageBox = wx.Choice(panel, -1, name="language")
		self.languageBox.Set(list(supported_languages.keys()))
		try:
			self.languageBox.Selection = languages[config_get("lang")]
		except KeyError:
			self.languageBox.Selection = 0
		lbl1 = wx.StaticText(panel, -1, _("Download Folder: "), name="path")
		self.pathField = wx.TextCtrl(panel, -1, value=config_get("path"), name="path", style=wx.TE_READONLY|wx.TE_MULTILINE|wx.HSCROLL)
		changeButton = wx.Button(panel, -1, _("&Change Path"), name="path")
		preferencesBox = wx.StaticBox(panel, -1, _("General preferences"))
		self.autoDetectItem = wx.CheckBox(preferencesBox, -1, _("Auto detect links on startup"), name="autodetect")
		self.autoCheckForUpdates = wx.CheckBox(preferencesBox, -1, _("Auto check for updates on startup"), name="checkupdates")
		self.autoLoadItem = wx.CheckBox(preferencesBox, -1, _("Load more results when reaching the end of the list"), name="autoload")
		self.autoCheckForUpdates.SetValue(config_get("checkupdates"))
		self.autoDetectItem.SetValue(config_get("autodetect"))
		self.autoLoadItem.SetValue(config_get("autoload"))
		self.swapPlayHotkeys = wx.CheckBox(preferencesBox, -1, _("Swap Enter and Ctrl+Enter for Video/Audio"), name="swap_play_hotkeys")
		self.swapPlayHotkeys.SetValue(config_get("swap_play_hotkeys"))
		self.swapPlayHotkeys.SetValue(config_get("swap_play_hotkeys"))
		self.speakBackground = wx.CheckBox(preferencesBox, -1, _("Speak notifications when window is inactive"), name="speak_background")
		self.speakBackground.SetValue(config_get("speak_background"))
		downloadPreferencesBox = wx.StaticBox(panel, -1, _("Download settings"))
		lbl2 = wx.StaticText(downloadPreferencesBox, -1, _("Direct download format: "))
		self.formats = wx.Choice(downloadPreferencesBox, -1, choices=[_("Video (mp4)"), _("Audio (m4a)"), _("Audio (mp3)")])
		self.formats.Selection = int(config_get('defaultformat'))
		self.lblMp3 = wx.StaticText(downloadPreferencesBox, -1, _("MP3 conversion quality: "))
		self.mp3Quality = wx.Choice(downloadPreferencesBox, -1, choices=["96 kbps", "128 kbps", "192 kbps", "256 kbps", "320 kbps"], name="conversion")
		self.mp3Quality.Selection = int(config_get("conversion"))
		playerOptions = wx.StaticBox(panel, -1, _("Player settings"))
		self.continueWatching = wx.CheckBox(playerOptions, -1, _("Continue watching"), name="continue")
		self.continueWatching.Value = config_get("continue")
		self.repeateTracks = wx.CheckBox(playerOptions, -1, _("Repeat video"), name="repeatetracks")
		self.autoPlayNext = wx.CheckBox(playerOptions, -1, _("Auto play next video"), name="autonext")
		self.autoPlayNext.Value = config_get('autonext')
		self.repeateTracks.Value = config_get("repeatetracks")
		self.chkSkipSilence = wx.CheckBox(playerOptions, -1, _("Skip silence (Recommended only for music)"), name="skip_silence")
		self.chkSkipSilence.SetValue(config_get("skip_silence"))
		self.chkPlayerNotifications = wx.CheckBox(playerOptions, -1, _("Speak player status notifications"), name="player_notifications")
		self.chkPlayerNotifications.SetValue(config_get("player_notifications"))
		
		cookiesBox = wx.StaticBox(panel, -1, _("YouTube Cookies (Fix Login/Bot errors)"))

		
		
		# Data Management Box
		dataBox = wx.StaticBox(panel, -1, _("Data Management (Backup/Restore)"))
		dataSizer = wx.BoxSizer(wx.HORIZONTAL)
		backupBtn = wx.Button(dataBox, -1, _("Backup Configuration..."))
		restoreBtn = wx.Button(dataBox, -1, _("Restore Configuration..."))
		dataSizer.Add(backupBtn, 1, wx.ALL, 5)
		dataSizer.Add(restoreBtn, 1, wx.ALL, 5)
		dataBox.SetSizer(dataSizer)
		
		# bindings
		backupBtn.Bind(wx.EVT_BUTTON, self.onBackup)
		restoreBtn.Bind(wx.EVT_BUTTON, self.onRestore)
		
		btnSizer = wx.BoxSizer(wx.HORIZONTAL)
		instructionBtn = wx.Button(cookiesBox, -1, _("How to get cookies.txt?"))
		importCookiesBtn = wx.Button(cookiesBox, -1, _("Import cookies.txt..."))
		
		btnSizer.Add(instructionBtn, 1, wx.ALL, 5)
		btnSizer.Add(importCookiesBtn, 1, wx.ALL, 5)
		
		# Clear Cookies Button
		clearCookiesBtn = wx.Button(cookiesBox, -1, _("Clear cookies.txt"))
		btnSizer.Add(clearCookiesBtn, 1, wx.ALL, 5)
		
		instructionBtn.Bind(wx.EVT_BUTTON, self.onInstructions)
		importCookiesBtn.Bind(wx.EVT_BUTTON, self.onImportCookies)
		clearCookiesBtn.Bind(wx.EVT_BUTTON, self.onClearCookies)
		
		# Open Config Button (General)
		openConfigBtn = wx.Button(panel, -1, _("Open Configuration Folder"))
		openConfigBtn.Bind(wx.EVT_BUTTON, self.onOpenConfig)
		
		self.formats.Bind(wx.EVT_CHOICE, self.onFormatChange)

		
		okButton = wx.Button(panel, wx.ID_OK, _("O&K"), name="ok_cancel")
		okButton.SetDefault()
		cancelButton = wx.Button(panel, wx.ID_CANCEL, _("C&ancel"), name="ok_cancel")
		sizer = wx.BoxSizer(wx.VERTICAL)
		sizer1 = wx.BoxSizer(wx.HORIZONTAL)
		sizer2 = wx.BoxSizer(wx.HORIZONTAL)
		sizer3 = wx.BoxSizer(wx.HORIZONTAL)
		sizer4 = wx.BoxSizer(wx.VERTICAL)
		sizer5 = wx.BoxSizer(wx.HORIZONTAL)
		sizer6 = wx.BoxSizer(wx.HORIZONTAL)
		sizer7 = wx.BoxSizer(wx.HORIZONTAL)
		okCancelSizer = wx.BoxSizer(wx.HORIZONTAL)
		sizer1.Add(lbl, 1)
		sizer1.Add(self.languageBox, 1, wx.EXPAND)
		for control in panel.GetChildren():
			if control.Name == "ok_cancel":
				okCancelSizer.Add(control, 1)
			elif control.Name == "path":
				sizer2.Add(control, 1)
		for item in preferencesBox.GetChildren():
			sizer3.Add(item, 1)
		preferencesBox.SetSizer(sizer3)
		sizer5.Add(self.lblMp3, 1)
		sizer5.Add(self.mp3Quality, 1)
		sizer6.Add(lbl2, 1)
		sizer6.Add(self.formats, 1)
		sizer4.Add(sizer5)
		sizer4.Add(sizer6)
		downloadPreferencesBox.SetSizer(sizer4)
		for ctrl in playerOptions.GetChildren():
			sizer7.Add(ctrl, 1)
		playerOptions.SetSizer(sizer7)
		sizer.Add(sizer1, 1, wx.EXPAND)
		sizer.Add(sizer2, 1, wx.EXPAND)
		sizer.Add(preferencesBox, 1, wx.EXPAND)
		sizer.Add(downloadPreferencesBox, 1, wx.EXPAND)
		sizer.Add(playerOptions, 1, wx.EXPAND)
		sizer.Add(cookiesBox, 1, wx.EXPAND)
		sizer.Add(dataBox, 1, wx.EXPAND)
		
		# Cookie Sizer
		cookieSizer = wx.BoxSizer(wx.VERTICAL)
		cookieSizer.Add(btnSizer, 0, wx.EXPAND)
		cookiesBox.SetSizer(cookieSizer)
		
		okCancelSizer.Add(openConfigBtn, 1) # Add Open Config to bottom row
		sizer.Add(okCancelSizer, 1, wx.EXPAND)
		panel.SetSizer(sizer)
		changeButton.Bind(wx.EVT_BUTTON, self.onChange)
		self.autoDetectItem.Bind(wx.EVT_CHECKBOX, self.onCheck)
		self.autoLoadItem.Bind(wx.EVT_CHECKBOX, self.onCheck)
		self.autoCheckForUpdates.Bind(wx.EVT_CHECKBOX, self.onCheck)
		self.repeateTracks.Bind(wx.EVT_CHECKBOX, self.onCheck)
		self.autoPlayNext.Bind(wx.EVT_CHECKBOX, self.onCheck)
		self.continueWatching.Bind(wx.EVT_CHECKBOX, self.onCheck)
		self.swapPlayHotkeys.Bind(wx.EVT_CHECKBOX, self.onCheck)
		self.speakBackground.Bind(wx.EVT_CHECKBOX, self.onCheck)
		self.chkSkipSilence.Bind(wx.EVT_CHECKBOX, self.onCheck)
		self.chkPlayerNotifications.Bind(wx.EVT_CHECKBOX, self.onCheck)
		okButton.Bind(wx.EVT_BUTTON, self.onOk)
		
		# Initial state check
		self.onFormatChange(None)
		
		self.ShowModal()
	def onFormatChange(self, event):
		# "Audio (mp3)" is index 2, check self.formats choices
		is_mp3 = (self.formats.Selection == 2)
		self.lblMp3.Show(is_mp3)
		self.mp3Quality.Show(is_mp3)
		self.Layout()
	def onCheck(self, event):
		obj = event.EventObject
		if all((self.repeateTracks.Value, self.autoPlayNext.Value)) and obj in (self.repeateTracks, self.autoPlayNext):
			self.repeateTracks.Value = self.autoPlayNext.Value = False
		if obj.Name in self.preferences and config_get(obj.Name) == obj.Value:
			del self.preferences[obj.Name]
		elif not obj.Value == config_get(obj.Name):
			self.preferences[obj.Name] = obj.Value
			
		# Purge History if Continue Watching is disabled
		if obj.Name == "continue" and not obj.Value:
			from database import History
			History().clear_history()
			wx.MessageBox(_("History cleared because 'Continue watching' was disabled."), _("Info"), parent=self)
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
			msg = _("Restoring data will overwrite your current configuration and restart the application.\nAre you sure you want to proceed?")
			if wx.MessageBox(msg, _("Confirm Restore"), wx.YES_NO | wx.ICON_WARNING, parent=self) == wx.YES:
				if restore_data(path):
					wx.MessageBox(_("Restore successful! Application will now restart."), _("Success"), parent=self)
					# Restart Application
					os.execl(sys.executable, sys.executable, *sys.argv)
				else:
					wx.MessageBox(_("Restore failed."), _("Error"), parent=self, style=wx.ICON_ERROR)
		dlg.Destroy()

	def onOk(self, event):

		from settings_handler import config_set, config_update_many
		
		restart = False # Initialize variable

		if self.preferences:
			config_update_many(self.preferences)
		if not self.mp3Quality.Selection == int(config_get("conversion")):
			config_set("conversion", self.mp3Quality.Selection)
		config_set("defaultformat", self.formats.Selection) if not self.formats.Selection == int(config_get('defaultformat')) else None
		# Check Skip Silence Change
		# if "skip_silence" in self.preferences:
		# 	restart = True # No longer needed with dynamic media options
			
		lang = {value:key for key, value in languages.items()}
		if not lang[self.languageBox.Selection] == config_get("lang"):
			config_set("lang", lang[self.languageBox.Selection])
			restart = True
			
		if restart:
			msg = wx.MessageBox(_("Configuration changed. You must restart the program for the changes to take effect. Do you want to restart now?"), _("Alert"), style=wx.YES_NO | wx.ICON_WARNING, parent=self)
			if msg == 2: # wx.YES
				os.execl(sys.executable, sys.executable, *sys.argv)

		self.Destroy()
