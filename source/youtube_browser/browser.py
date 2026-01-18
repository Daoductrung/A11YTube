
import webbrowser
from threading import Thread
import os


import pyperclip
import wx
from gui.download_progress import DownloadProgress
from gui.search_dialog import SearchDialog
from gui.settings_dialog import SettingsDialog
from gui.playlist_dialog import PlaylistDialog
from gui.activity_dialog import LoadingDialog

from download_handler.downloader import downloadAction
from media_player.media_gui import MediaGui
from nvda_client.client import speak
from settings_handler import config_get
from youtube_browser.search_handler import Search, PlaylistResult
from utiles import direct_download, get_audio_stream, get_video_stream
from database import Favorite, Collections


class YoutubeBrowser(wx.Frame):
	def __init__(self, parent):
		wx.Frame.__init__(self, parent=None, title=parent.Title)
		self.caller = parent
		self.Centre()
		self.SetSize(wx.DisplaySize())
		from utiles import force_taskbar_style
		force_taskbar_style(self)
		self.Maximize(True)
		from utiles import SilentPanel
		self.panel = SilentPanel(self)
		lbl = wx.StaticText(self.panel, -1, _("Search Results: "))
		self.searchResults = wx.ListBox(self.panel, -1)
		self.loadMoreButton = wx.Button(self.panel, -1, _("Load more results"))
		self.loadMoreButton.Enabled = False
		self.loadMoreButton.Show(not config_get("autoload"))
		self.playButton = wx.Button(self.panel, -1, _("Play (enter)"), name="controls")
		self.downloadButton = wx.Button(self.panel, -1, _("Download"), name="controls")
		self.menuButton = wx.Button(self.panel, -1, _("Context Menu"), name="controls") # New Button
		self.favCheck = wx.CheckBox(self.panel, -1, _("Add to Favorites"))
		searchButton = wx.Button(self.panel, -1, _("Search... (ctrl+s)"))
		backButton = wx.Button(self.panel, -1, _("Back to Main Window"))
		sizer = wx.BoxSizer(wx.VERTICAL)
		sizer1 = wx.BoxSizer(wx.HORIZONTAL)
		sizer1.Add(backButton, 1, wx.ALL)
		sizer1.Add(searchButton, 1, wx.ALL)
		sizer2 = wx.BoxSizer(wx.HORIZONTAL)
		for control in self.panel.GetChildren():
			if control.Name == "controls":
				sizer2.Add(control, 1)
		sizer.Add(sizer1, 1, wx.EXPAND)
		sizer.Add(lbl, 1, wx.ALL)
		sizer.Add(self.searchResults, 1, wx.EXPAND)
		sizer.Add(self.loadMoreButton, 1)
		sizer.Add(sizer2, 1)
		self.panel.SetSizer(sizer)
		self.contextSetup()
		
		# Define Global IDs
		self.ID_ADD_COLLECTION = wx.NewIdRef()
		self.ID_TOGGLE_FAVORITE = wx.NewIdRef()

		swap = config_get("swap_play_hotkeys")
		video_flags = wx.ACCEL_CTRL if swap else 0
		audio_flags = 0 if swap else wx.ACCEL_CTRL
		results_shortcuts = wx.AcceleratorTable([
			(video_flags, wx.WXK_RETURN, self.videoPlayItemId),
			(audio_flags, wx.WXK_RETURN, self.audioPlayItemId)
		])
		self.searchResults.SetAcceleratorTable(results_shortcuts)
		menuBar = wx.MenuBar()
		optionsMenu = wx.Menu()
		settingsItem = optionsMenu.Append(-1, _("Settings...\tCtrl+Shift+S"))
		hotKeys = wx.AcceleratorTable([
			(wx.ACCEL_CTRL|wx.ACCEL_SHIFT, ord("S"), settingsItem.GetId()),
			(wx.ACCEL_CTRL, ord("S"), searchButton.GetId()), # Ctrl+S
			(wx.ACCEL_CTRL, ord("D"), self.directDownloadId),
			#(wx.ACCEL_CTRL, ord("L"), self.copyItemId), # Removed
			(wx.ACCEL_CTRL, ord("K"), self.copyItemId), # Ctrl+K
			(wx.ACCEL_CTRL, ord('L'), self.ID_ADD_COLLECTION),
			(wx.ACCEL_CTRL, ord('F'), self.ID_TOGGLE_FAVORITE) # Ctrl+F
		])
		# hotkey table
		self.SetAcceleratorTable(hotKeys)
		menuBar.Append(optionsMenu, _("Options"))
		self.SetMenuBar(menuBar)
		self.Bind(wx.EVT_MENU, lambda event: SettingsDialog(self), settingsItem)
		self.loadMoreButton.Bind(wx.EVT_BUTTON, self.onLoadMore)
		self.playButton.Bind(wx.EVT_BUTTON, lambda event: self.playVideo())
		self.downloadButton.Bind(wx.EVT_BUTTON, self.onDownload)
		self.menuButton.Bind(wx.EVT_BUTTON, self.onContextMenu) # Bind new button
		self.favCheck.Bind(wx.EVT_CHECKBOX, self.onFavorite)
		searchButton.Bind(wx.EVT_BUTTON, self.onSearch)
		backButton.Bind(wx.EVT_BUTTON, lambda event: self.backAction())
		self.Bind(wx.EVT_CHAR_HOOK, self.onHook)
		
		# Bind Global Shortcuts
		self.Bind(wx.EVT_MENU, self.onAddToCollection, id=self.ID_ADD_COLLECTION)
		self.Bind(wx.EVT_MENU, self.onFavorite, id=self.ID_TOGGLE_FAVORITE)

		self.Bind(wx.EVT_LISTBOX_DCLICK, lambda event: self.playVideo(), self.searchResults)
		self.searchResults.Bind(wx.EVT_LISTBOX, self.onListBox)
		self.Bind(wx.EVT_SHOW, self.onShow)
		self.Bind(wx.EVT_CLOSE, lambda event: wx.Exit())
		if self.searchAction():
			self.Show()
			self.caller.Hide()
		else:
			self.Destroy()
		self.favorites = Favorite()
		self.toggleFavorite()

	def searchAction(self, value=""):
		dialog = SearchDialog(self, value=value)
		query = dialog.query
		filter = dialog.filter
		if query is None:
			self.toggleControls()
			return

		
		dlg = LoadingDialog(self, _("Searching"), Search, query, filter)
		if dlg.res is None:
			# Error handled by dialog
			return
		
		self.search = dlg.res
		titles = self.search.get_titles()
		self.searchResults.Set(titles)
		self.toggleControls()
		try:
			self.searchResults.SetSelection(0)
		except Exception:
			pass
		self.searchResults.SetFocus()
		self.toggleDownload()
		self.togglePlay()
		return True

	def onSearch(self, event):
		if hasattr(self, "search"):
			self.searchAction(self.search.query)
		else:
			self.searchAction()

	def playVideo(self):
		number = self.searchResults.Selection
		if number == wx.NOT_FOUND: return
		if self.search.get_type(number) == "playlist":

			self.playlist_dlg = PlaylistDialog(self, self.search.get_url(number))
			return
		title = self.search.get_title(number)
		url = self.search.get_url(number)
		dlg = LoadingDialog(self, _("Playing"), get_video_stream, url)
		if dlg.res:
			gui = MediaGui(self, title, dlg.res, url, True if self.search.get_views(number) is not None else False, results=self.search)
			self.Hide()

	def playAudio(self):
		number = self.searchResults.Selection
		if number == wx.NOT_FOUND: return
		if self.search.get_type(number) == "playlist":
			return
		title = self.search.get_title(number)
		url = self.search.get_url(number)
		dlg = LoadingDialog(self, _("Playing"), get_audio_stream, url)
		if dlg.res:
			gui = MediaGui(self, title, dlg.res, url, results=self.search, audio_mode=True)
			self.Hide()


	def onHook(self, event):

		if event.KeyCode == wx.WXK_SPACE and self.search.get_type(self.searchResults.Selection) == "video" and self.FindFocus() == self.searchResults:
			self.favCheck.Value = not self.favCheck.Value
			self.onFavorite(None)
		elif (event.KeyCode == wx.WXK_BACK or event.KeyCode == wx.WXK_ESCAPE) and not type(self.FindFocus()) == MediaGui:
			self.backAction()
		else:
			event.Skip()
	def contextSetup(self):
		# Video Context Menu
		self.videoMenu = wx.Menu()
		swap = config_get("swap_play_hotkeys")
		video_key = "Ctrl+Enter" if swap else "Enter"
		audio_key = "Enter" if swap else "Ctrl+Enter"

		videoPlayItem = self.videoMenu.Append(-1, _("Play Video") + f"\t{video_key}")
		self.videoPlayItemId = videoPlayItem.GetId()
		audioPlayItem = self.videoMenu.Append(-1, _("Play Audio") + f"\t{audio_key}")
		self.audioPlayItemId = audioPlayItem.GetId()
		
		self.downloadMenu = wx.Menu()
		videoItem = self.downloadMenu.Append(-1, _("Video"))
		audioMenu = wx.Menu()
		m4aItem = audioMenu.Append(-1, "m4a")
		mp3Item = audioMenu.Append(-1, "mp3")
		self.downloadMenu.AppendSubMenu(audioMenu, _("Audio"))
		self.downloadId = self.videoMenu.AppendSubMenu(self.downloadMenu, _("Download")).GetId()
		directDownloadItem = self.videoMenu.Append(-1, _("Direct Download...\tctrl+d"))
		self.directDownloadId = directDownloadItem.GetId()
		
		# Add To Collection for Video
		addColItem = self.videoMenu.Append(-1, _("Add to Collection...\tCtrl+L"))
		self.Bind(wx.EVT_MENU, self.onAddToCollection, addColItem)

		copyItem = self.videoMenu.Append(-1, _("Copy Link\tCtrl+K"))
		self.copyItemId = copyItem.GetId()
		webbrowserItem = self.videoMenu.Append(-1, _("Open in Web Browser"))
		
		self.videoMenu.AppendSeparator()
		channelItem = self.videoMenu.Append(-1, _("Go to Channel"))
		downloadChannelItem = self.videoMenu.Append(-1, _("Download Channel"))

		# Bind Video Events
		self.Bind(wx.EVT_MENU, self.onCopy, copyItem)
		self.Bind(wx.EVT_MENU, self.onOpenInBrowser, webbrowserItem)
		self.Bind(wx.EVT_MENU, self.onOpenChannel, channelItem)
		self.Bind(wx.EVT_MENU, self.onDownloadChannel, downloadChannelItem)
		

		
		self.searchResults.Bind(wx.EVT_MENU, lambda e: self.playVideo(), id=self.videoPlayItemId)
		self.searchResults.Bind(wx.EVT_MENU, lambda e: self.playAudio(), id=self.audioPlayItemId)
		self.Bind(wx.EVT_MENU, self.onVideoDownload, videoItem)
		self.Bind(wx.EVT_MENU, self.onM4aDownload, m4aItem)
		self.Bind(wx.EVT_MENU, self.onMp3Download, mp3Item) # Binding works for both menus if ID reused? No, create distinct items.
		# Note: wx.Menu items must be unique per menu. We'll duplicate logic or reuse handlers.
		self.Bind(wx.EVT_MENU, lambda event: self.directDownload(), directDownloadItem)

		# Playlist Context Menu
		self.playlistMenu = wx.Menu()
		
		# Shuffle Play
		shuffleVideo = self.playlistMenu.Append(-1, _("Shuffle Play Video"))
		shuffleAudio = self.playlistMenu.Append(-1, _("Shuffle Play Audio"))
		self.Bind(wx.EVT_MENU, lambda e: self.onShufflePlay(False), shuffleVideo)
		self.Bind(wx.EVT_MENU, lambda e: self.onShufflePlay(True), shuffleAudio)
		
		self.playlistMenu.AppendSeparator()
		
		# Download Playlist
		plDlMenu = wx.Menu()
		plVideoItem = plDlMenu.Append(-1, _("Video"))
		plAudioMenu = wx.Menu()
		plM4aItem = plAudioMenu.Append(-1, "m4a")
		plMp3Item = plAudioMenu.Append(-1, "mp3")
		plDlMenu.AppendSubMenu(plAudioMenu, _("Audio"))
		self.playlistMenu.AppendSubMenu(plDlMenu, _("Download Playlist"))
		
		# Re-bind download handlers (using processDownload with format arg)
		self.Bind(wx.EVT_MENU, lambda e: self.processDownload(0), plVideoItem)
		self.Bind(wx.EVT_MENU, lambda e: self.processDownload(1), plM4aItem)
		self.Bind(wx.EVT_MENU, lambda e: self.processDownload(2), plMp3Item)

		
		self.playlistMenu.AppendSeparator()
		
		# Collection Submenu
		colMenu = wx.Menu()
		cloneNew = colMenu.Append(-1, _("Clone as New Collection..."))
		mergeExist = colMenu.Append(-1, _("Merge into Existing Collection..."))
		self.playlistMenu.AppendSubMenu(colMenu, _("Add to Collection"))
		
		self.Bind(wx.EVT_MENU, self.onCloneCollection, cloneNew)
		self.Bind(wx.EVT_MENU, self.onMergeCollection, mergeExist)
		
		self.playlistMenu.AppendSeparator()
		
		
		# Common Items (Channel, Browser, Copy) - Duplicated for distinct menu
		plCopy = self.playlistMenu.Append(-1, _("Copy Link\tCtrl+K"))
		plBrowser = self.playlistMenu.Append(-1, _("Open in Web Browser"))
		
		self.Bind(wx.EVT_MENU, self.onCopy, plCopy)
		self.Bind(wx.EVT_MENU, self.onOpenInBrowser, plBrowser)

		# Add to Collection (Shortcut Handler)
		# Handled in __init__ globally now

		self.searchResults.Bind(wx.EVT_CONTEXT_MENU, self.onContextMenu)

	def onContextMenu(self, event):
		n = self.searchResults.Selection
		if n == wx.NOT_FOUND: return
		
		res_type = self.search.get_type(n)
		
		if res_type == "playlist":
			self.searchResults.PopupMenu(self.playlistMenu)
		else:
			# Update dynamic labels if needed (though standard menu is static now)
			self.updateDownloadLabel() # Only updates legacy button label now
			self.searchResults.PopupMenu(self.videoMenu)

	def updateDownloadLabel(self):
		n = self.searchResults.Selection
		if n != wx.NOT_FOUND:
			res_type = self.search.get_type(n)
			label = _("Download Playlist") if res_type == "playlist" else _("Download")
			self.downloadButton.Label = label
			# Menu items are now static/separate, so no need to update labels/enablement here

	def onOpenChannel(self, event):
		n = self.searchResults.Selection
		if n == wx.NOT_FOUND: return
		channel = self.search.get_channel(n)
		if channel and channel.get('url'):
			webbrowser.open(channel['url'])

	def onDownloadChannel(self, event):
		n = self.searchResults.Selection
		if n == wx.NOT_FOUND: return
		channel = self.search.get_channel(n)
		if not channel or not channel.get('url'):
			return
		
		title = channel.get('name', _("Unknown Channel"))
		url = channel.get('url')
		dlg = DownloadProgress(wx.GetApp().GetTopWindow(), title)
		direct_download(int(config_get('defaultformat')), url, dlg, "channel")

	def onOpenInBrowser(self, event):
		number = self.searchResults.Selection
		url = self.search.get_url(number)
		webbrowser.open(url)
	def onDownload(self, event):
		n = self.searchResults.Selection
		if n == wx.NOT_FOUND: return
		
		res_type = self.search.get_type(n)
		
		downloadMenu = wx.Menu()
		
		if res_type == "playlist":
			videoItem = downloadMenu.Append(-1, _("Download Playlist (Video)"))
			audioMenu = wx.Menu()
			m4aItem = audioMenu.Append(-1, "m4a")
			mp3Item = audioMenu.Append(-1, "mp3")
			downloadMenu.Append(-1, _("Download Playlist (Audio)"), audioMenu)
		else:
			videoItem = downloadMenu.Append(-1, _("Video"))
			audioMenu = wx.Menu()
			m4aItem = audioMenu.Append(-1, "m4a")
			mp3Item = audioMenu.Append(-1, "mp3")
			downloadMenu.Append(-1, _("Audio"), audioMenu)

		self.Bind(wx.EVT_MENU, self.onVideoDownload, videoItem)
		self.Bind(wx.EVT_MENU, self.onM4aDownload, m4aItem)
		self.Bind(wx.EVT_MENU, self.onMp3Download, mp3Item)
		self.PopupMenu(downloadMenu)

	def onM4aDownload(self, event):
		self.processDownload(1)

	def onMp3Download(self, event):
		self.processDownload(2)

	def onVideoDownload(self, event):
		self.processDownload(0)
		
	def processDownload(self, format_type):
		n = self.searchResults.Selection
		url = self.search.get_url(n)
		title = self.search.get_title(n)
		res_type = self.search.get_type(n)
		
		if res_type == "playlist":
			# For playlists, we need a special download type or handling
			# The current direct_download might need "playlist" as download_type
			dlg = DownloadProgress(wx.GetApp().GetTopWindow(), title)
			# Assuming direct_download handles "playlist" type correctly to create folders
			direct_download(format_type, url, dlg, "playlist", os.path.join(config_get("path")))
		else:
			dlg = DownloadProgress(wx.GetApp().GetTopWindow(), title)
			direct_download(format_type, url, dlg, res_type)



	def onCopy(self, event):
		pyperclip.copy(self.search.get_url(self.searchResults.Selection))
		wx.MessageBox(_("Link copied successfully"), _("Done"), parent=self)
	def loadMore(self):
		if self.searchResults.Strings == []:
			return
		speak(_("Loading more results"))
		if self.search.load_more() is None:
			speak(_("Could not load more results"))
			return
		# position = self.searchResults.Selection
		wx.CallAfter(self.searchResults.Append, self.search.get_last_titles())
		speak(_("More search results loaded"))
		wx.CallAfter(self.searchResults.SetFocus)
	def onListBox(self, event):
		self.toggleDownload()
		self.togglePlay()
		self.toggleFavorite()
		if self.searchResults.Selection == len(self.searchResults.Strings)-1:
			if not config_get("autoload"):
				self.loadMoreButton.Enabled = True
				return
			t = Thread(target=self.loadMore)
			t.daemon = True
			t.start()
		else:
			self.loadMoreButton.Enabled = False
	def onLoadMore(self, event):
		t = Thread(target=self.loadMore)
		t.daemon = True
		t.start()
	def backAction(self):
		self.Destroy()
		self.caller.Show()
	def toggleControls(self):
		if self.searchResults.Strings == []:
			for control in self.panel.GetChildren():
				if control.Name == "controls":
					control.Hide()
			self.loadMoreButton.Hide()
		else:
			for control in self.panel.GetChildren():
				if control.Name == "controls":
					control.Show()
			self.loadMoreButton.Show(not config_get("autoload"))
	def toggleDownload(self):
		n = self.searchResults.Selection
		if n == wx.NOT_FOUND:
			self.videoMenu.Enable(self.downloadId, False)
			self.videoMenu.Enable(self.directDownloadId, False)
			self.downloadButton.Enabled = False
			self.menuButton.Enabled = False
			return
		if self.search.get_views(n) is None and self.search.get_type(n) == "video":
			self.videoMenu.Enable(self.downloadId, False)
			self.videoMenu.Enable(self.directDownloadId, False)
			self.downloadButton.Enabled = False
			self.menuButton.Enabled = False
			return
		self.videoMenu.Enable(self.downloadId, True)
		self.videoMenu.Enable(self.directDownloadId, True)
		self.downloadButton.Enabled = True
		self.menuButton.Enabled = True

	def togglePlay(self):
		n = self.searchResults.Selection
		contextMenuIds = (self.videoPlayItemId, self.audioPlayItemId)
		if n == wx.NOT_FOUND:
			self.playButton.Enabled = False
			for i in contextMenuIds:
				self.videoMenu.Enable(i, False)
			return
		
		if self.search.get_type(n) == "playlist":
			self.playButton.Label = _("Open")
			for i in contextMenuIds:
				self.videoMenu.Enable(i, False)
			# Playlist play is handled differently (opens dialog), so enable button
			self.playButton.Enabled = True 
			return
		
		swap = config_get("swap_play_hotkeys")
		video_key = "Ctrl+Enter" if swap else "Enter"
		self.playButton.Label = _("Play") + f" ({video_key})"
		self.playButton.Enabled = True
		for i in contextMenuIds:
			self.videoMenu.Enable(i, True)
	def onFavorite(self, event):
		if event and event.GetId() == self.ID_TOGGLE_FAVORITE:
			self.favCheck.Value = not self.favCheck.Value

		n = self.searchResults.Selection
		number = self.searchResults.Selection
		if number == wx.NOT_FOUND: return
		
		# Prevent adding Playlists to Favorites
		if self.search.get_type(number) == "playlist":
			self.favCheck.SetValue(False)
			wx.MessageBox(_("You cannot add playlists to favorites."), _("Error"), parent=self, style=wx.ICON_WARNING)
			return

		title = self.search.get_title(number)
		url = self.search.get_url(number)
		channel = self.search.get_channel(number)
		
		if self.favCheck.GetValue():
			display_title = f"{title}. {channel['name']}"
			live = 1 if not self.search.get_views(number) else 0
			self.favorites.add_favorite({
				"title": title,
				"display_title": display_title,
				"url": url,
				"live": live,
				"channel_name": channel['name'],
				"channel_url": channel['url']
			})
			speak(_("Video added to favorites"))
		else:
			self.favorites.remove_favorite(url)
			speak(_("Video removed from favorites"))

	def toggleFavorite(self):
		n = self.searchResults.Selection
		if n == wx.NOT_FOUND:
			self.favCheck.Enabled = False
			return
		self.favCheck.Enabled = self.search.get_type(n) == "video"
		if not self.favCheck.Enabled:
			return
		
		url = self.search.get_url(n)
		
		def check_url(target_url):
			# Use optimized DB check instead of fetching all
			is_fav = self.favorites.is_favorite(target_url)
			wx.CallAfter(self.updateFavCheck, is_fav, target_url)

		t = Thread(target=check_url, args=[url])
		t.daemon = True
		t.start()

	def updateFavCheck(self, is_fav, check_url):
		# Verify we are still on the same item
		n = self.searchResults.Selection
		if n == wx.NOT_FOUND: return
		
		current_url = self.search.get_url(n)
		if current_url == check_url:
			self.favCheck.SetValue(is_fav)

	def directDownload(self):
		n = self.searchResults.Selection
		if self.search.get_views(n) is None and self.search.get_type(n) == "video":
			return
		url = self.search.get_url(self.searchResults.Selection)
		title = self.search.get_title(self.searchResults.Selection)
		download_type = self.search.get_type(self.searchResults.Selection)
		dlg = DownloadProgress(wx.GetApp().GetTopWindow(), title)
		direct_download(int(config_get('defaultformat')), url, dlg, download_type)
	def onShow(self, event):
		self.searchResults.SetFocus()
		self.toggleFavorite()
		event.Skip()

	def onCloneCollection(self, event):
		n = self.searchResults.Selection
		if n == wx.NOT_FOUND: return
		
		# Double check type
		if self.search.get_type(n) != "playlist":
			return
			
		url = self.search.get_url(n)
		default_name = self.search.get_title(n)
		
		dlg = wx.TextEntryDialog(self, _("Enter collection name:"), _("Clone Playlist"), value=default_name)
		if dlg.ShowModal() != wx.ID_OK:
			dlg.Destroy()
			return
			
		name = dlg.GetValue().strip()
		dlg.Destroy()
		
		if not name: return
		
		# Create Collection
		db = Collections()
		col_id = db.create_collection(name)
		
		if not col_id:
			wx.MessageBox(_("Collection name already exists or is invalid"), _("Error"), parent=self)
			return
			
		speak(_("Cloning playlist..."))
		
		# Background Worker to fetch and add
		t = Thread(target=self._worker_clone, args=(col_id, url, db))
		t.daemon = True
		t.start()

	def onMergeCollection(self, event):
		n = self.searchResults.Selection
		if n == wx.NOT_FOUND: return
		
		url = self.search.get_url(n)
		
		db = Collections()
		cols = db.get_all_collections()
		
		if not cols:
			wx.MessageBox(_("No collections found"), _("Error"), parent=self)
			return
			
		names = [c['name'] for c in cols]
		dlg = wx.SingleChoiceDialog(self, _("Select collection to merge into:"), _("Merge Collection"), names)
		
		if dlg.ShowModal() == wx.ID_OK:
			sel = dlg.GetSelection()
			col_id = cols[sel]['id']
			name = cols[sel]['name']
			
			speak(_("Merging into {}...").format(name))
			t = Thread(target=self._worker_clone, args=(col_id, url, db))
			t.daemon = True
			t.start()
			
		dlg.Destroy()

	def onShufflePlay(self, audio_mode=False):
		n = self.searchResults.Selection
		if n == wx.NOT_FOUND: return
		
		url = self.search.get_url(n)
		title = self.search.get_title(n)
		
		speak(_("Loading playlist for shuffle..."))
		t = Thread(target=self._worker_shuffle, args=(url, title, audio_mode))
		t.daemon = True
		t.start()

	def onAddToCollection(self, event):
		n = self.searchResults.Selection
		if n == wx.NOT_FOUND: return
		
		# If it's a playlist, we probably want "Merge" behavior?
		# Spec says "Add to collection for video items".
		# But shortcuts might trigger on playlist.
		# If playlist, treating as "Merge" seems appropriate or ask?
		# Let's handle Video primarily.
		
		res_type = self.search.get_type(n)
		if res_type == "playlist":
			self.onMergeCollection(event)
			return

		# It is a video
		url = self.search.get_url(n)
		title = self.search.get_title(n)
		channel = self.search.get_channel(n)
		
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

	def _worker_shuffle(self, url, title, audio_mode):
		try:
			pl = PlaylistResult(url)
			while pl.next():
				pass
				
			if not pl.videos:
				wx.CallAfter(speak, _("Playlist is empty"))
				return
				
			import random
			# Shuffle logic is handled by MediaGui if we pass shuffle=True
			# But MediaGui expects an index. We pick random start?
			# Or MediaGui handles it. 
			# Checking MediaGui init: it takes `shuffle=False`.
			
			def start_player():
				# We need a valid stream for the FIRST video to init MediaGui?
				# MediaGui typically takes (title, stream, url...).
				# If we pass shuffle=True, maybe it handles the first track?
				# Usually we resolve the stream first.
				
				# Let's pick a random start index
				idx = random.randint(0, len(pl.videos) - 1)
				vid = pl.videos[idx]
				
				func = get_audio_stream if audio_mode else get_video_stream
				stream = func(vid['url'])
				
				if stream:
					# We need to pass the result object `pl` so MediaGui can navigate
					# But we want to ensure `pl` behaves like the search results object Expected by MediaGui
					# MediaGui expects: get_url(n), get_title(n)... PlaylistResult has these!
					
					# However, MediaGui init usually takes the stream of the *current* url.
					# And `url` arg in MediaGui is the specific video URL.
					
					gui = MediaGui(self, vid['title'], stream, vid['url'], True, pl, audio_mode=audio_mode, shuffle=True)
					self.Hide()
				else:
					speak(_("Could not play video"))

			wx.CallAfter(start_player)
			
		except Exception as e:
			wx.CallAfter(speak, _("Error loading playlist"))

	def _worker_clone(self, col_id, url, db):
		try:
			# Fetch Playlist items
			pl = PlaylistResult(url)
			
			# Iterate to load ALL items
			while pl.next():
				pass # Just exhaust the generator/loader
				
			# Now we have all videos in pl.videos
			count = 0
			for vid in pl.videos:
				data = {
					"title": vid.get('title', ''),
					"url": vid.get('url', ''),
					"channel_name": vid.get('channel', {}).get('name', ''),
					"channel_url": vid.get('channel', {}).get('url', '')
				}
				db.add_to_collection(col_id, data)
				count += 1
				
			wx.CallAfter(speak, _("Added {} videos to collection").format(count))
			
		except Exception as e:
			wx.CallAfter(speak, _("Error cloning playlist"))
