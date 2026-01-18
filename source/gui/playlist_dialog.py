import wx
from youtube_browser.search_handler import PlaylistResult
from utiles import direct_download, get_audio_stream, get_video_stream
from media_player.media_gui import MediaGui
from nvda_client.client import speak
import pyperclip
from gui.download_progress import DownloadProgress
from settings_handler import config_get
import webbrowser
from threading import Thread
import os
from .activity_dialog import LoadingDialog
import application
from database import Collections, Favorite
class PlaylistDialog(wx.Dialog):
	def __init__(self, parent, url):
		super().__init__(parent, title=application.name)
		self.CenterOnParent()
		self.url = url
		self.Maximize(True)
		p = wx.Panel(self)
		l1 = wx.StaticText(p, -1, _("Playlist Videos: "))
		self.videosBox = wx.ListBox(p, -1)
		self.playButton = wx.Button(p, -1, _("Play"), name="control")
		self.downloadButton = wx.Button(p, -1, _("Download"), name="control")
		self.favCheckBox = wx.CheckBox(p, -1, _("Favorite"), name="control")
		self.menuButton = wx.Button(p, -1, _("Context Menu"), name="control")
		backButton = wx.Button(p, -1, _("Back"), name="control")
		self.contextSetup()
		
		swap = config_get("swap_play_hotkeys")
		video_flags = wx.ACCEL_CTRL if swap else 0
		audio_flags = 0 if swap else wx.ACCEL_CTRL
		hotkeys = wx.AcceleratorTable([
				(audio_flags, wx.WXK_RETURN, self.audioPlayItemId),
				(video_flags, wx.WXK_RETURN, self.videoPlayItemId),
				(wx.ACCEL_CTRL, ord("D"), self.directDownloadId),
			#(wx.ACCEL_CTRL, ord("L"), self.copyItemId),
			(wx.ACCEL_CTRL, ord("K"), self.copyItemId),
			(wx.ACCEL_CTRL, ord('L'), self.ID_ADD_COLLECTION),
			(wx.ACCEL_CTRL, ord('F'), self.ID_TOGGLE_FAVORITE)
			])
		self.videosBox.SetAcceleratorTable(hotkeys)

		sizer = wx.BoxSizer(wx.VERTICAL)
		sizer.Add(l1, 1)
		sizer.Add(self.videosBox, 1, wx.EXPAND)
		ctrlSizer = wx.BoxSizer(wx.HORIZONTAL)
		for control in p.GetChildren():
			if control.Name == "control":
				ctrlSizer.Add(control, 1)
		sizer.Add(ctrlSizer)
		p.SetSizer(sizer)
		self.videosBox.Bind(wx.EVT_LISTBOX, self.onListBox)
		self.playButton.Bind(wx.EVT_BUTTON, lambda e: self.playVideo())
		self.downloadButton.Bind(wx.EVT_BUTTON, self.onDownload)
		self.favCheckBox.Bind(wx.EVT_CHECKBOX, self.onFavCheck)
		self.menuButton.Bind(wx.EVT_BUTTON, self.onContextMenu)
		backButton.Bind(wx.EVT_BUTTON, lambda e: self.back())
		self.Bind(wx.EVT_CHAR_HOOK, self.onHook)
		self.Bind(wx.EVT_CLOSE, lambda e: wx.Exit())
		self.Bind(wx.EVT_CLOSE, lambda e: wx.Exit())
		
		dlg = LoadingDialog(self.Parent, _("Loading playlist"), PlaylistResult, self.url)
		if dlg.res is None:
			# Error handled by dialog
			self.Destroy()
			return
		
		self.result = dlg.res
		self.title = self.result.title
		self.SetTitle(f"{application.name} - {self.title}")
		self.videosBox.Set(self.result.get_display_titles())
		
		self.Parent.Hide()
		self.Parent.Hide()
		self.Show()
		self.videosBox.Selection = 0
	def contextSetup(self):
		self.contextMenu = wx.Menu()
		swap = config_get("swap_play_hotkeys")
		video_key = "Ctrl+Enter" if swap else "Enter"
		audio_key = "Enter" if swap else "Ctrl+Enter"
		videoPlayItem = self.contextMenu.Append(-1, _("Play") + f"\t{video_key}")
		self.videoPlayItemId = videoPlayItem.GetId()
		audioPlayItem = self.contextMenu.Append(-1, _("Play as Audio") + f"\t{audio_key}")
		self.audioPlayItemId = audioPlayItem.GetId()
		self.downloadMenu = wx.Menu()
		videoItem = self.downloadMenu.Append(-1, _("Video"))
		audioMenu = wx.Menu()
		m4aItem = audioMenu.Append(-1, "m4a")
		mp3Item = audioMenu.Append(-1, "mp3")
		self.downloadMenu.AppendSubMenu(audioMenu, _("Audio"))
		self.downloadId = self.contextMenu.AppendSubMenu(self.downloadMenu, _("Download")).GetId()
		directDownloadItem = self.contextMenu.Append(-1, _("Direct Download...\tctrl+d"))
		self.directDownloadId = directDownloadItem.GetId()
		copyItem = self.contextMenu.Append(-1, _("Copy Video Link\tCtrl+K"))
		self.copyItemId = copyItem.GetId()
		
		# Add To Collection
		addColItem = self.contextMenu.Append(-1, _("Add to Collection...\tCtrl+L"))
		self.ID_ADD_COLLECTION = addColItem.GetId()
		
		# Add To Favorite (Toggle)
		# Check current state? Typically context menu is static unless OnPopup.
		# Just "Toggle Favorite" for now is easier or "Add/Remove"?
		# User asked for Checkbox in Browser, but didn't specify UI for PlaylistDialog other than shortcuts.
		# Let's add simple Item.
		favItem = self.contextMenu.Append(-1, _("Toggle Favorite\tCtrl+F"))
		self.ID_TOGGLE_FAVORITE = favItem.GetId()

		webbrowserItem = self.contextMenu.Append(-1, _("Open in Web Browser"))


		self.videosBox.Bind(wx.EVT_CONTEXT_MENU, self.onContextMenu)
		# binding item events 
		self.videosBox.Bind(wx.EVT_MENU, lambda e: self.playVideo(), id=self.videoPlayItemId)
		self.videosBox.Bind(wx.EVT_MENU, lambda e: self.playAudio(), id=self.audioPlayItemId)
		self.videosBox.Bind(wx.EVT_MENU, self.onVideoDownload, videoItem)
		self.Bind(wx.EVT_MENU, self.onM4aDownload, m4aItem)
		self.Bind(wx.EVT_MENU, self.onMp3Download, mp3Item)
		self.videosBox.Bind(wx.EVT_MENU, lambda e: self.directDownload(), id=self.directDownloadId)

		self.contextMenu.AppendSeparator()
		channelItem = self.contextMenu.Append(-1, _("Go to Channel"))
		dlChannelItem = self.contextMenu.Append(-1, _("Download Channel"))
		self.Bind(wx.EVT_MENU, self.onOpenChannel, channelItem)
		self.Bind(wx.EVT_MENU, self.onDownloadChannel, dlChannelItem)

		self.videosBox.Bind(wx.EVT_MENU, self.onCopy, id=self.copyItemId)
		self.Bind(wx.EVT_MENU, self.onOpenInBrowser, webbrowserItem)
		
		self.Bind(wx.EVT_MENU, self.onAddToCollection, id=self.ID_ADD_COLLECTION)
		self.Bind(wx.EVT_MENU, self.onFavorite, id=self.ID_TOGGLE_FAVORITE)

	def onContextMenu(self, event):
		if self.result.videos:
			self.videosBox.PopupMenu(self.contextMenu)

	def onOpenInBrowser(self, event):
		n = self.videosBox.Selection
		webbrowser.open(self.result.get_url(n))

	def onCopy(self, event):
		n = self.videosBox.Selection
		pyperclip.copy(self.result.get_url(n))
		wx.MessageBox(_("Link copied successfully"), _("Done"), parent=self)

	def onOpenChannel(self, event):
		n = self.videosBox.Selection
		webbrowser.open(self.result.get_channel(n)['url'])

	def onDownloadChannel(self, event):
		n = self.videosBox.Selection
		title = self.result.get_channel(n)['name']
		url = self.result.get_channel(n)['url']
		dlg = DownloadProgress(wx.GetApp().GetTopWindow(), title)
		direct_download(int(config_get('defaultformat')), url, dlg, "channel")

	def playVideo(self):
		n = self.videosBox.Selection
		url = self.result.get_url(n)

		title = self.result.get_title(n)

		dlg = LoadingDialog(self, _("Playing"), get_video_stream, url)
		if dlg.res:
			gui = MediaGui(self, title, dlg.res, url, True, self.result)
			gui.path = os.path.join(gui.path, self.title)
			self.Hide()

	def playAudio(self):
		n = self.videosBox.Selection
		url = self.result.get_url(n)

		title = self.result.get_title(n)

		dlg = LoadingDialog(self, _("Playing"), get_audio_stream, url)
		if dlg.res:
			gui = MediaGui(self, title, dlg.res, url, audio_mode=True, results=self.result)
			gui.path = os.path.join(gui.path, self.title)
			self.Hide()


	def onListBox(self, event):
		n = self.videosBox.Selection
		if n != wx.NOT_FOUND:
			# Update favorite checkbox
			url = self.result.get_url(n)
			# Do this in thread to keep UI snappy? Or direct db check is fast?
			# DB check is fast enough usually.
			fav = Favorite()
			self.favCheckBox.SetValue(fav.is_favorite(url))

		if n == self.videosBox.Count-1:
			def load():
				try:
					if self.result.next():
						titles = self.result.get_new_titles()
						wx.CallAfter(self.videosBox.Append, titles)
						speak(_("More videos loaded"))
					else:
						speak(_("No more videos"))
				except Exception as e:
					speak(_("Could not load more videos"))
			t = Thread(target=load)
			t.daemon = True
			t.start()
	def onVideoDownload(self, event):
		n = self.videosBox.Selection
		url = self.result.get_url(n)
		title = self.result.get_title(n)
		dlg = DownloadProgress(self.Parent, title)
		direct_download(0, url, dlg, "video", os.path.join(config_get("path"), self.title))

	def directDownload(self):
		n = self.videosBox.Selection
		url = self.result.get_url(n)
		title = self.result.get_title(n)
		dlg = DownloadProgress(wx.GetApp().GetTopWindow(), title)
		direct_download(int(config_get('defaultformat')), url, dlg, "video", os.path.join(config_get("path"), self.title))


	def onM4aDownload(self, event):
		n = self.videosBox.Selection
		url = self.result.get_url(n)
		title = self.result.get_title(n)
		dlg = DownloadProgress(wx.GetApp().GetTopWindow(), title)
		direct_download(1, url, dlg, "video", os.path.join(config_get("path"), self.title))

	def onMp3Download(self, event):
		n = self.videosBox.Selection
		url = self.result.get_url(n)
		title = self.result.get_title(n)
		dlg = DownloadProgress(wx.GetApp().GetTopWindow(), title)
		direct_download(2, url, dlg, "video", os.path.join(config_get("path"), self.title))

	def onPlaylistDownload(self, format_type):
		# format_type: 0=Video, 1=m4a, 2=mp3
		dlg = DownloadProgress(wx.GetApp().GetTopWindow(), self.title)
		# download_type="playlist" ensures it creates a folder (handled in direct_download/Downloader)
		direct_download(format_type, self.url, dlg, "playlist", os.path.join(config_get("path")))

	def onDownload(self, event):
		downloadMenu = wx.Menu()
		videoItem = downloadMenu.Append(-1, _("Video"))
		audioMenu = wx.Menu()
		m4aItem = audioMenu.Append(-1, "m4a")
		mp3Item = audioMenu.Append(-1, "mp3")
		downloadMenu.Append(-1, _("Audio"), audioMenu)

		# Playlist Download Submenu
		playlistMenu = wx.Menu()
		plVideoItem = playlistMenu.Append(-1, _("Video"))
		plAudioMenu = wx.Menu()
		plM4aItem = plAudioMenu.Append(-1, "m4a")
		plMp3Item = plAudioMenu.Append(-1, "mp3")
		playlistMenu.Append(-1, _("Audio"), plAudioMenu)
		downloadMenu.Append(-1, _("Download Entire Playlist"), playlistMenu)

		self.Bind(wx.EVT_MENU, self.onVideoDownload, videoItem)
		self.Bind(wx.EVT_MENU, self.onM4aDownload, m4aItem)
		self.Bind(wx.EVT_MENU, self.onMp3Download, mp3Item)
		
		self.Bind(wx.EVT_MENU, lambda e: self.onPlaylistDownload(0), plVideoItem)
		self.Bind(wx.EVT_MENU, lambda e: self.onPlaylistDownload(1), plM4aItem)
		self.Bind(wx.EVT_MENU, lambda e: self.onPlaylistDownload(2), plMp3Item)
		self.PopupMenu(downloadMenu)
		self.videosBox.SetFocus()
	def back(self):
		self.Parent.Show()
		self.Destroy()

	def onHook(self, event):
		if event.KeyCode == wx.WXK_ESCAPE and not type(self.FindFocus()) == MediaGui:
			self.back()
		else:
			event.Skip()

	def onAddToCollection(self, event):
		n = self.videosBox.Selection
		if n == wx.NOT_FOUND: return
		
		title = self.result.get_title(n)
		url = self.result.get_url(n)
		channel = self.result.get_channel(n)
		
		db = Collections()
		cols = db.get_all_collections()
		
		if not cols:
			wx.MessageBox(_("No collections found. Please create one first."), _("Error"), parent=self)
			return
			
		names = [c['name'] for c in cols]
		dlg = wx.SingleChoiceDialog(self, _("Select collection to add video to:"), _("Add to Collection"), names)
		
		if dlg.ShowModal() == wx.ID_OK:
			sel = dlg.GetSelection()
			col_id = cols[sel]['id']
			
			data = {
				"title": title,
				"url": url,
				"channel_name": channel['name'],
				"channel_url": channel['url']
			}
			
			if db.add_to_collection(col_id, data):
				speak(_("Video added to collection"))
			else:
				speak(_("Video already in collection"))
				
		dlg.Destroy()

	def onFavorite(self, event):
		n = self.videosBox.Selection
		if n == wx.NOT_FOUND: return
		
		url = self.result.get_url(n)
		title = self.result.get_title(n)
		channel = self.result.get_channel(n)
		
		fav = Favorite()
		if fav.is_favorite(url):
			fav.remove_favorite(url)
			speak(_("Video removed from favorites"))
		else:
			data = {
				"title": title,
				"display_title": title, # Playlist items might not have full metadata
				"url": url,
				"live": 0,
				"channel_name": channel['name'],
				"channel_url": channel['url']
			}
			fav.add_favorite(data)
			speak(_("Video added to favorites"))
		# Update Checkbox UI
		self.favCheckBox.SetValue(fav.is_favorite(url))

	def onFavCheck(self, event):
		# Triggered by clicking the checkbox
		# Logic similar to onFavorite trigger
		n = self.videosBox.Selection
		if n == wx.NOT_FOUND: 
			self.favCheckBox.SetValue(False)
			return

		url = self.result.get_url(n)
		title = self.result.get_title(n)
		channel = self.result.get_channel(n)
		
		fav = Favorite()
		if self.favCheckBox.GetValue():
			# Add
			data = {
				"title": title,
				"display_title": title,
				"url": url,
				"live": 0,
				"channel_name": channel['name'],
				"channel_url": channel['url']
			}
			fav.add_favorite(data)
			speak(_("Video added to favorites"))
		else:
			# Remove
			fav.remove_favorite(url)
			speak(_("Video removed from favorites"))