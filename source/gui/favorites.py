import wx
import application
from database import Favorite
from utiles import direct_download, get_audio_stream, get_video_stream
from media_player.media_gui import MediaGui
from nvda_client.client import speak
import pyperclip
from gui.download_progress import DownloadProgress
from .activity_dialog import LoadingDialog
from settings_handler import config_get
import webbrowser


class Favorites(wx.Frame):
	def __init__(self, parent):
		super().__init__(None, title=application.name)
		self.caller = parent
		self.Centre()
		self.SetSize(wx.DisplaySize())
		from utiles import force_taskbar_style
		force_taskbar_style(self)
		self.Maximize(True)
		from utiles import SilentPanel
		p = SilentPanel(self)
		l1 = wx.StaticText(p, -1, _("Favorites: "))
		self.favList = wx.ListBox(p, -1)
		self.playButton = wx.Button(p, -1, _("Play"), name="control")
		self.downloadButton = wx.Button(p, -1, _("Download"), name="control")
		self.menuButton = wx.Button(p, -1, _("Context Menu"), name="control")
		self.deleteButton = wx.Button(p, -1, _("Remove from Favorites"), name="control")
		self.clearButton = wx.Button(p, -1, _("Clear Favorites"), name="control")
		backButton = wx.Button(p, -1, _("Back to Main Window"), name="control")
		self.favorites = Favorite()
		self.rows = self.favorites.get_all()
		self.favList.Set([row["display_title"] for row in self.rows])
		if self.favList.Strings:
			self.favList.Selection = 0
			self.contextSetup()
			swap = config_get("swap_play_hotkeys")
			video_flags = wx.ACCEL_CTRL if swap else 0
			audio_flags = 0 if swap else wx.ACCEL_CTRL
			hotkeys = wx.AcceleratorTable([
				(video_flags, wx.WXK_RETURN, self.videoPlayItemId),
				(audio_flags, wx.WXK_RETURN, self.audioPlayItemId),
				(wx.ACCEL_CTRL, ord("D"), self.directDownloadId),
				(wx.ACCEL_CTRL, ord("D"), self.directDownloadId),
			(wx.ACCEL_CTRL, ord("K"), self.copyItemId),
			])
			self.favList.SetAcceleratorTable(hotkeys)
		sizer = wx.BoxSizer(wx.VERTICAL)
		sizer.Add(l1, 1)
		sizer.Add(self.favList, 1, wx.EXPAND)
		ctrlSizer = wx.BoxSizer(wx.HORIZONTAL)
		for control in p.GetChildren():
			if control.Name == "control":
				ctrlSizer.Add(control, 1)
		sizer.Add(ctrlSizer)
		self.toggleControls()

		self.playButton.Bind(wx.EVT_BUTTON, lambda e: self.playVideo())
		self.downloadButton.Bind(wx.EVT_BUTTON, self.onDownload)
		self.menuButton.Bind(wx.EVT_BUTTON, self.onContextMenu)
		self.deleteButton.Bind(wx.EVT_BUTTON, self.onDelete)
		self.clearButton.Bind(wx.EVT_BUTTON, self.onClear)
		backButton.Bind(wx.EVT_BUTTON, self.onBack)
		self.Bind(wx.EVT_CLOSE, lambda e: wx.Exit())
		self.Bind(wx.EVT_CHAR_HOOK, self.onHook)
		self.Bind(wx.EVT_SHOW, self.onShow)
		p.SetSizer(sizer)
		sizer.Fit(p)
		self.Show()

	def onShow(self, event):
		if not self.IsShown(): return
		self.rows = self.favorites.get_all()
		self.favList.Set([row["display_title"] for row in self.rows])
		if self.favList.Strings:
			self.favList.Selection = 0
		self.toggleControls()
		self.favList.SetFocus()

	def onClear(self, event):
		msg = wx.MessageBox(_("Are you sure you want to clear your favorites?"), _("Confirm"), style=wx.YES_NO|wx.ICON_WARNING, parent=self)
		if msg == wx.YES:
			self.favorites.clear_favorites()
			self.rows = []
			self.favList.Clear()
			self.toggleControls()
			speak(_("Favorites cleared"))
			self.playButton.SetFocus()

	def onDelete(self, event):
		n = self.favList.Selection
		if n == -1:
			return
		url = self.rows[n]["url"]
		self.favorites.remove_favorite(url)
		self.favList.Delete(n)
		self.rows.pop(n)
		self.toggleControls()
		try:
			self.favList.Selection = n
		except Exception:
			pass
		self.favList.SetFocus()
		speak(_("Video removed from favorites"))
	def playVideo(self):
		n = self.favList.Selection
		url = self.rows[n]["url"]
		title = self.rows[n]["title"]
		dlg = LoadingDialog(self, _("Playing"), get_video_stream, url)
		if dlg.res:
			gui = MediaGui(self, title, dlg.res, url, True if not self.rows[n]["live"] else False, self.rows)
			self.Hide()

	def playAudio(self):
		n = self.favList.Selection
		url = self.rows[n]["url"]
		title = self.rows[n]["title"]
		dlg = LoadingDialog(self, _("Playing"), get_audio_stream, url)
		if dlg.res:
			gui = MediaGui(self, title, dlg.res, url, audio_mode=True, results=self.rows)
			self.Hide()

	def toggleControls(self):
		for control in (self.playButton, self.downloadButton, self.menuButton, self.deleteButton, self.clearButton):
			if self.rows == []:
				control.Disable()

	def contextSetup(self):
		self.contextMenu = wx.Menu()
		swap = config_get("swap_play_hotkeys")
		video_key = "Ctrl+Enter" if swap else "Enter"
		audio_key = "Enter" if swap else "Ctrl+Enter"
		videoPlayItem = self.contextMenu.Append(-1, _("Play Video") + f"\t{video_key}")
		self.videoPlayItemId = videoPlayItem.GetId()
		audioPlayItem = self.contextMenu.Append(-1, _("Play Audio") + f"\t{audio_key}")
		self.audioPlayItemId = audioPlayItem.GetId()
		self.downloadMenu = wx.Menu()
		videoItem = self.downloadMenu.Append(-1, _("Video"))
		audioMenu = wx.Menu()
		m4aItem = audioMenu.Append(-1, "m4a")
		mp3Item = audioMenu.Append(-1, "mp3")
		self.downloadMenu.AppendSubMenu(audioMenu, _("Audio"))
		self.contextMenu.AppendSubMenu(self.downloadMenu, _("Download")).GetId()
		directDownloadItem = self.contextMenu.Append(-1, _("Direct Download...\tctrl+d"))
		self.directDownloadId = directDownloadItem.GetId()
		
		self.contextMenu.AppendSeparator()
		channelItem = self.contextMenu.Append(-1, _("Go to Channel"))
		dlChannelItem = self.contextMenu.Append(-1, _("Download Channel"))
		self.Bind(wx.EVT_MENU, self.onOpenChannel, channelItem)
		self.Bind(wx.EVT_MENU, self.onDownloadChannel, dlChannelItem)
		self.contextMenu.AppendSeparator()

		self.contextMenu.AppendSeparator()
		copyItem = self.contextMenu.Append(-1, _("Copy Video Link\tCtrl+K"))
		self.copyItemId = copyItem.GetId()
		webbrowserItem = self.contextMenu.Append(-1, _("Open in Web Browser"))
		
		self.favList.Bind(wx.EVT_CONTEXT_MENU, self.onContextMenu)
		self.favList.Bind(wx.EVT_MENU, lambda e: self.playVideo(), id=self.videoPlayItemId)
		self.favList.Bind(wx.EVT_MENU, lambda e: self.playAudio(), id=self.audioPlayItemId)
		self.favList.Bind(wx.EVT_MENU, self.onCopy, id=self.copyItemId)
		self.favList.Bind(wx.EVT_MENU, lambda e: self.directDownload(), id=self.directDownloadId)
		self.Bind(wx.EVT_MENU, self.onVideoDownload, videoItem)
		self.Bind(wx.EVT_MENU, self.onM4aDownload, m4aItem)
		self.Bind(wx.EVT_MENU, self.onMp3Download, mp3Item)
		self.Bind(wx.EVT_MENU, self.onOpenInBrowser, webbrowserItem)
	
	def onContextMenu(self, event):
		if self.rows != []:
			self.favList.PopupMenu(self.contextMenu)
		

	def onOpenInBrowser(self, event):
		n = self.favList.Selection
		webbrowser.open(self.rows[n]["url"])

	def onOpenChannel(self, event):
		n = self.favList.Selection
		webbrowser.open(self.rows[n]["channel_url"])

	def onDownloadChannel(self, event):
		n = self.favList.Selection
		title = self.rows[n]["channel_name"]
		url = self.rows[n]["channel_url"]
		dlg = DownloadProgress(wx.GetApp().GetTopWindow(), title)
		direct_download(int(config_get('defaultformat')), url, dlg, "channel")



	def onCopy(self, event):
		pyperclip.copy(self.rows[self.favList.Selection]["url"])
		wx.MessageBox(_("Link copied successfully"), _("Done"), parent=self)

	def directDownload(self):
		n = self.favList.Selection

		url = self.rows[n]["url"]
		title = self.rows[n]["title"]
		dlg = DownloadProgress(wx.GetApp().GetTopWindow(), title)
		direct_download(int(config_get('defaultformat')), url, dlg, "video")

	def onM4aDownload(self, event):
		n = self.favList.Selection
		url = self.rows[n]["url"]
		title = self.rows[n]["title"]

		dlg = DownloadProgress(wx.GetApp().GetTopWindow(), title)
		direct_download(1, url, dlg, "video")


	def onMp3Download(self, event):
		n = self.favList.Selection
		url = self.rows[n]["url"]
		title = self.rows[n]["title"]
		dlg = DownloadProgress(wx.GetApp().GetTopWindow(), title)
		direct_download(2, url, dlg, "video")

	def onVideoDownload(self, event):
		n = self.favList.Selection
		url = self.rows[n]["url"]
		title = self.rows[n]["title"]
		dlg = DownloadProgress(wx.GetApp().GetTopWindow(), title)
		direct_download(0, url, dlg, "video")


	def onDownload(self, event):
		downloadMenu = wx.Menu()
		videoItem = downloadMenu.Append(-1, _("Video"))
		audioMenu = wx.Menu()
		m4aItem = audioMenu.Append(-1, "m4a")
		mp3Item = audioMenu.Append(-1, "mp3")
		downloadMenu.Append(-1, _("Audio"), audioMenu)
		self.Bind(wx.EVT_MENU, self.onVideoDownload, videoItem)
		self.Bind(wx.EVT_MENU, self.onM4aDownload, m4aItem)
		self.Bind(wx.EVT_MENU, self.onMp3Download, mp3Item)
		self.PopupMenu(downloadMenu)
	def onHook(self, event):
		# Global Key Hook for accessibility
		obj = self.FindFocus()
		if event.KeyCode in [wx.WXK_RETURN, wx.WXK_NUMPAD_ENTER]:
			if obj == self.favList:
				swap = config_get("swap_play_hotkeys")
				if event.ControlDown():
					self.playVideo() if swap else self.playAudio()
				else:
					self.playAudio() if swap else self.playVideo()
			elif obj == self.playButton:
				self.playVideo()
			elif obj == self.downloadButton:
				self.onDownload(None)
			elif obj == self.deleteButton:
				self.onDelete(None)
			elif obj == self.clearButton:
				self.onClear(None)
		elif event.KeyCode == wx.WXK_BACK or event.KeyCode == wx.WXK_ESCAPE:
			self.onBack(None)
		elif event.KeyCode in (wx.WXK_DELETE, wx.WXK_NUMPAD_DELETE) and self.FindFocus() == self.favList:
			self.onDelete(None)
		elif event.KeyCode == wx.WXK_TAB:
			# Ensure tab works if trapped (though wx.Frame usually handles it, explict fallback helps)
			event.Skip()
		else:
			event.Skip()

	def onBack(self, event):
		self.caller.Show()
		self.Destroy()