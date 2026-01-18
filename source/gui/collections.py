import wx
import os
from database import Collections
from nvda_client.client import speak
import application
from gui.custom_controls import CustomButton
from gui.download_progress import DownloadProgress
from utiles import direct_download, get_audio_stream, get_video_stream
from settings_handler import config_get, config_set
from gui.activity_dialog import LoadingDialog
from media_player.media_gui import MediaGui
import threading
from threading import Thread
import time
from download_handler.downloader import downloadAction
import webbrowser
import pyperclip
import json

class CollectionsManager(wx.Dialog):
	def __init__(self, parent):
		super().__init__(parent, title=_("Collections Manager") + f" - {application.name}")
		self.CenterOnParent()
		self.db = Collections()
		
		# Allow main app to handle window management
		self.parent_window = parent

		panel = wx.Panel(self)
		sizer = wx.BoxSizer(wx.VERTICAL)
		
		lbl = wx.StaticText(panel, -1, _("Your Collections:"))
		self.colList = wx.ListBox(panel, -1)
		self.colList.Bind(wx.EVT_LISTBOX_DCLICK, self.onOpen)
		
		btnSizer = wx.BoxSizer(wx.HORIZONTAL)
		self.btnOpen = wx.Button(panel, -1, _("Open"))
		self.btnMenu = wx.Button(panel, -1, _("Context Menu"))
		self.btnDelete = wx.Button(panel, -1, _("Delete"))
		self.btnImport = wx.Button(panel, -1, _("Import..."))
		self.btnCreate = wx.Button(panel, -1, _("Create New"))
		self.btnClose = wx.Button(panel, wx.ID_CANCEL, _("Close"))
		
		btnSizer.Add(self.btnOpen, 1, wx.ALL, 5)
		btnSizer.Add(self.btnMenu, 1, wx.ALL, 5)
		btnSizer.Add(self.btnCreate, 1, wx.ALL, 5)
		btnSizer.Add(self.btnImport, 1, wx.ALL, 5)
		btnSizer.Add(self.btnDelete, 1, wx.ALL, 5)
		
		sizer.Add(lbl, 0, wx.ALL, 5)
		sizer.Add(self.colList, 1, wx.EXPAND | wx.ALL, 5)
		sizer.Add(btnSizer, 0, wx.EXPAND | wx.ALL, 5)
		sizer.Add(self.btnClose, 0, wx.EXPAND | wx.ALL, 5)
		
		panel.SetSizer(sizer)
		
		self.btnOpen.Bind(wx.EVT_BUTTON, self.onOpen)
		self.btnMenu.Bind(wx.EVT_BUTTON, self.onContext)
		self.btnCreate.Bind(wx.EVT_BUTTON, self.onCreate)
		self.btnImport.Bind(wx.EVT_BUTTON, self.onImport)
		self.btnDelete.Bind(wx.EVT_BUTTON, self.onDelete)
		self.btnClose.Bind(wx.EVT_BUTTON, self.onClose)
		
		self.Bind(wx.EVT_CHAR_HOOK, self.onHook)
		self.Bind(wx.EVT_CLOSE, self.onClose)
		self.colList.Bind(wx.EVT_LISTBOX, self.onSelect)
		self.colList.Bind(wx.EVT_CONTEXT_MENU, self.onContext)
		
		# Setup Accelerator for Shift+F10 (Context Menu) - standard Windows behavior handles it usually, but we can enforce.
		# actually wx.EVT_CONTEXT_MENU handles Shift+F10 automatically on Windows if control has focus.
		
		self.load_collections()
		self.Show()

	def load_collections(self):
		self.colList.Clear()
		self.collections = self.db.get_all_collections()
		for col in self.collections:
			count = self.db.get_collection_count(col['id'])
			self.colList.Append(f"{col['name']} ({count} " + _("videos") + ")")
		
		if self.colList.Count > 0:
			self.colList.Selection = 0
			self.btnOpen.Enable()
			self.btnMenu.Enable()
			self.btnDelete.Enable()
		else:
			self.btnOpen.Disable()
			self.btnMenu.Disable()
			self.btnDelete.Disable()

	def onSelect(self, event):
		if self.colList.Selection != wx.NOT_FOUND:
			self.btnOpen.Enable()
			self.btnMenu.Enable()
			self.btnDelete.Enable()
		else:
			self.btnOpen.Disable()
			self.btnMenu.Disable()
			self.btnDelete.Disable()

	def onContext(self, event):
		if self.colList.Selection == wx.NOT_FOUND: return
		
		# Context Menu mirroring Playlist but without Browser/Copy
		menu = wx.Menu()
		
		# Play
		swap = config_get("swap_play_hotkeys")
		video_key = "Ctrl+Enter" if swap else "Enter"
		audio_key = "Enter" if swap else "Ctrl+Enter"

		playId = wx.NewIdRef()
		playAudioId = wx.NewIdRef()
		menu.Append(playId, _("Shuffle Play Video"))
		menu.Append(playAudioId, _("Shuffle Play Audio"))
		menu.AppendSeparator()

		# Download Submenu
		dlMenu = wx.Menu()
		dlMenu.Append(101, _("Download Entire Collection (Video)"))
		dlMenu.Append(102, _("Download Entire Collection (Audio - m4a)"))
		dlMenu.Append(103, _("Download Entire Collection (Audio - mp3)"))
		menu.AppendSubMenu(dlMenu, _("Download"))
		
		menu.AppendSeparator()
		
		# Management
		openItem = menu.Append(-1, _("Open"))
		exportItem = menu.Append(-1, _("Export..."))
		mergeItem = menu.Append(-1, _("Merge into..."))
		renameItem = menu.Append(-1, _("Rename") + "\tF2")
		deleteItem = menu.Append(-1, _("Delete"))
		
		# Bindings
		# Delegate Play to a helper that opens View first
		self.Bind(wx.EVT_MENU, lambda e: self.openAndPlay(False), id=playId)
		self.Bind(wx.EVT_MENU, lambda e: self.openAndPlay(True), id=playAudioId)
		
		self.Bind(wx.EVT_MENU, lambda e: self.downloadCollection(0), id=101)
		self.Bind(wx.EVT_MENU, lambda e: self.downloadCollection(1), id=102)
		self.Bind(wx.EVT_MENU, lambda e: self.downloadCollection(2), id=103)
		
		self.Bind(wx.EVT_MENU, self.onOpen, openItem)
		self.Bind(wx.EVT_MENU, self.onExport, exportItem)
		self.Bind(wx.EVT_MENU, self.onMerge, mergeItem)
		self.Bind(wx.EVT_MENU, self.onRename, renameItem)
		self.Bind(wx.EVT_MENU, self.onDelete, deleteItem)
		
		self.PopupMenu(menu)

	def openAndPlay(self, audio_mode=False):
		sel = self.colList.Selection
		if sel == wx.NOT_FOUND: return
		
		col = self.collections[sel]
		items = self.db.get_collection_items(col['id'])
		if not items:
			speak(_("Collection is empty"))
			return

		# Open the View
		# We want to go back to Manager when done, so we Hide Manager,
		# Create View, Hide View (it shows in init), 
		# then Play with callback to restore Manager.
		
		# View automatically shows itself in __init__. We need to hide it immediately 
		# to transition to Player if we want seamlessness, OR we just let it be hidden 
		# by the fact that MediaGui takes focus?
		# User said "Without going inside it".
		# So verify: Manager -> (View Hidden) -> MediaGui -> Manager.
		
		# Prevent View from showing via Hack? 
		# Or just Hide it immediately.
		self.Hide()
		view = CollectionView(self, col)
		view.Hide() # Hide the list view
		
		def on_done():
			view.Close()
			self.Show()
			self.colList.SetFocus()

		# Trigger Shuffle Play
		import random
		if view.videoList.Count > 0:
			view.videoList.Selection = random.randint(0, view.videoList.Count - 1)
			view.playVideo(audio_mode=audio_mode, shuffle=True, on_close=on_done)
		else:
			on_done()

	# Removed old playCollection method as we delegate now

	def downloadCollection(self, format_type):
		sel = self.colList.Selection
		if sel == wx.NOT_FOUND: return
		col = self.collections[sel]
		items = self.db.get_collection_items(col['id'])
		
		if not items:
			speak(_("Collection is empty"))
			return
			
		confirm = wx.MessageBox(_("Download {} videos?").format(len(items)), _("Confirm"), wx.YES_NO | wx.ICON_QUESTION, parent=self)
		if confirm != wx.YES: return
		
		folder = os.path.join(config_get("path"), col['name'])
		if not os.path.exists(folder):
			os.makedirs(folder)
			
		# Reusing the seq_download logic. We can make it a staticmethod or separate function, 
		# but for now I'll instantiate CollectionView momentarily? No, that's heavy.
		# I'll just copy the simple thread logic here or refactor.
		# Refactoring is cleaner. I'll duplicate the worker logic to avoid imports circularity or complexity.
		# It works fine.
		
		t = Thread(target=self._worker_download, args=(items, format_type, folder))
		t.daemon = True
		t.start()
		speak(_("Download started"))
		# Do NOT close here either.

	def _worker_download(self, items, f_type, folder):
		# Map option to format string
		if f_type == 0:
			fmt = "bestvideo[ext=mp4]+bestaudio[ext=m4a]/mp4"
		else:
			fmt = "bestaudio[ext=m4a]"
		convert = True if f_type == 2 else False
		
		is_folder = False 
		noplaylist = True

		# Collect all URLs
		urls = [item['url'] for item in items]
		if not urls: return

		self.dlg_ref = None
		ready = threading.Event()
		def create_dlg():
			self.dlg_ref = DownloadProgress(wx.GetApp().GetTopWindow(), _("Downloading {} videos").format(len(urls)))
			ready.set()
		wx.CallAfter(create_dlg)
		
		ready.wait() 
		
		if self.dlg_ref:
			downloadAction(
				urls, 
				folder, 
				self.dlg_ref, 
				fmt, 
				self.dlg_ref.gaugeProgress, 
				self.dlg_ref.textProgress, 
				convert=convert, 
				folder=is_folder,
				noplaylist=noplaylist,
				silent=False
			)

	def onOpen(self, event):
		sel = self.colList.Selection
		if sel == wx.NOT_FOUND: return
		
		col = self.collections[sel]
		self.Hide()
		CollectionView(self, col)

	def onCreate(self, event):
		dlg = wx.TextEntryDialog(self, _("Enter collection name:"), _("New Collection"))
		if dlg.ShowModal() == wx.ID_OK:
			name = dlg.GetValue().strip()
			if name:
				if self.db.create_collection(name):
					speak(_("Collection created"))
					self.load_collections()
					# Select the new one (last)
					if self.colList.Count > 0:
						self.colList.Selection = self.colList.Count - 1
						self.btnOpen.Enable()
						self.btnDelete.Enable()
						self.colList.SetFocus()
				else:
					wx.MessageBox(_("Collection name already exists or is invalid"), _("Error"), parent=self)
		dlg.Destroy()

	def onDelete(self, event):
		sel = self.colList.Selection
		if sel == wx.NOT_FOUND: return
		
		name = self.collections[sel]['name']
		if wx.MessageBox(_("Are you sure you want to delete '{}'?").format(name), _("Confirm"), wx.YES_NO | wx.ICON_WARNING, parent=self) == wx.YES:
			self.db.delete_collection(self.collections[sel]['id'])
			speak(_("Collection deleted"))
			self.load_collections()
			self.colList.SetFocus()

	def onClose(self, event):
		# Show Main Window explicitly
		# If parent is HomeScreen, Show() it.
		if self.parent_window:
			self.parent_window.Show()
		self.Destroy()

	def onRename(self, event):
		sel = self.colList.Selection
		if sel == wx.NOT_FOUND: return
		
		col = self.collections[sel]
		dlg = wx.TextEntryDialog(self, _("Enter new name for '{}':").format(col['name']), _("Rename Collection"), value=col['name'])
		if dlg.ShowModal() == wx.ID_OK:
			new_name = dlg.GetValue().strip()
			if new_name and new_name != col['name']:
				if self.db.rename_collection(col['id'], new_name):
					speak(_("Renamed"))
					# Reload and select
					self.load_collections()
					# Try to find new name to select
					for i, c in enumerate(self.collections):
						if c['id'] == col['id']: # ID shouldn't change
							self.colList.Selection = i
							self.colList.SetFocus()
							break
				else:
					wx.MessageBox(_("Collection name already exists or is invalid"), _("Error"), parent=self)
		dlg.Destroy()

	def onHook(self, event):
		if event.KeyCode == wx.WXK_ESCAPE:
			self.onClose(None)
		elif event.KeyCode == wx.WXK_F2:
			self.onRename(None)
		elif event.KeyCode in [wx.WXK_RETURN, wx.WXK_NUMPAD_ENTER]:
			# Check focus
			obj = self.FindFocus()
			if obj == self.colList:
				self.onOpen(None)
			else:
				event.Skip()
		else:
			event.Skip()


	def onImport(self, event):
		dlg = wx.FileDialog(self, _("Select Collection File"), wildcard="JSON files (*.json)|*.json", style=wx.FD_OPEN | wx.FD_FILE_MUST_EXIST)
		if dlg.ShowModal() == wx.ID_OK:
			path = dlg.GetPath()
			try:
				with open(path, 'r', encoding='utf-8') as f:
					data = json.load(f)
				
				name = data.get('name', 'Imported Collection')
				items = data.get('items', [])
				
				# Check if exists, if so prompt for new name
				if any(c['name'] == name for c in self.collections):
					entry = wx.TextEntryDialog(self, _("Collection '{}' already exists. Enter a new name:").format(name), _("Import Collision"), value=f"{name} (Imported)")
					if entry.ShowModal() != wx.ID_OK:
						return
					name = entry.GetValue().strip()
					entry.Destroy()
				
				if not name: return
				
				col_id = self.db.create_collection(name)
				if not col_id:
					wx.MessageBox(_("Failed to create collection. Name invalid or exists."), _("Error"), parent=self)
					return
					
				count = 0
				for item in items:
					self.db.add_to_collection(col_id, item)
					count += 1
					
				speak(_("Imported {} videos into '{}'").format(count, name))
				self.load_collections()
				# Select new
				self.colList.Selection = self.colList.Count - 1
				self.colList.SetFocus()
				
			except Exception as e:
				wx.MessageBox(_("Error importing collection: {}").format(e), _("Error"), parent=self, style=wx.ICON_ERROR)
		dlg.Destroy()

	def onExport(self, event):
		sel = self.colList.Selection
		if sel == wx.NOT_FOUND: return
		
		col = self.collections[sel]
		items = self.db.get_collection_items(col['id'])
		
		data = {
			"name": col['name'],
			"items": items
		}
		
		dlg = wx.FileDialog(self, _("Save Collection"), defaultFile=f"{col['name']}.json", wildcard="JSON files (*.json)|*.json", style=wx.FD_SAVE | wx.FD_OVERWRITE_PROMPT)
		if dlg.ShowModal() == wx.ID_OK:
			path = dlg.GetPath()
			if not path.lower().endswith(".json"):
				path += ".json"
			try:
				with open(path, 'w', encoding='utf-8') as f:
					json.dump(data, f, indent=4, ensure_ascii=False)
				speak(_("Collection exported"))
			except Exception as e:
				wx.MessageBox(_("Error exporting collection: {}").format(e), _("Error"), parent=self, style=wx.ICON_ERROR)
		dlg.Destroy()

	def onMerge(self, event):
		sel = self.colList.Selection
		if sel == wx.NOT_FOUND: return
		
		source_col = self.collections[sel]
		
		# Filter out current collection
		targets = [c for c in self.collections if c['id'] != source_col['id']]
		
		if not targets:
			wx.MessageBox(_("No other collections to merge into."), _("Info"), parent=self)
			return
			
		names = [c['name'] for c in targets]
		dlg = wx.SingleChoiceDialog(self, _("Select collection to merge '{}' into:").format(source_col['name']), _("Merge Collection"), names)
		
		if dlg.ShowModal() == wx.ID_OK:
			target_idx = dlg.GetSelection()
			target_col = targets[target_idx]
			
			speak(_("Merging collections, please wait..."))
			t = Thread(target=self._worker_merge, args=(source_col, target_col))
			t.daemon = True
			t.start()
			
		dlg.Destroy()

	def _worker_merge(self, source_col, target_col):
		try:
			# Create new DB instance or use existing? 
			# Database module uses global connection with RLock, so it's thread-safe.
			# But rigorous pattern suggests re-instantiating wrapper if needed.
			# Converting to background task.
			
			source_items = self.db.get_collection_items(source_col['id'])
			target_items = self.db.get_collection_items(target_col['id'])
			target_urls = set(item['url'] for item in target_items)
			
			count = 0
			for item in source_items:
				if item['url'] not in target_urls:
					self.db.add_to_collection(target_col['id'], item)
					count += 1
			
			wx.CallAfter(speak, _("Merged {} videos from '{}' into '{}'").format(count, source_col['name'], target_col['name']))
		except Exception as e:
			print(f"Merge failed: {e}")
			wx.CallAfter(speak, _("Error merging collections"))

# Collection View - Inheriting look/feel from Favorites
class CollectionView(wx.Frame):
	def __init__(self, parent, collection):
		self.db = Collections()
		count = self.db.get_collection_count(collection['id'])
		super().__init__(None, title=f"{collection['name']} ({count} " + _("videos") + f") - {application.name}")
		self.collection = collection
		self.parent_dialog = parent
		self.items = []
		
		self.Centre()
		self.SetSize(wx.DisplaySize())
		self.Maximize(True)
		
		from utiles import SilentPanel
		p = SilentPanel(self)
		
		l1 = wx.StaticText(p, -1, _("Videos in collection:"))
		self.videoList = wx.ListBox(p, -1)
		
		self.playButton = wx.Button(p, -1, _("Play"), name="control")
		self.downloadButton = wx.Button(p, -1, _("Download"), name="control")
		self.menuButton = wx.Button(p, -1, _("Context Menu"), name="control")
		self.deleteButton = wx.Button(p, -1, _("Remove from Collection"), name="control")
		self.clearButton = wx.Button(p, -1, _("Clear Collection"), name="control") # Added Clear
		backButton = wx.Button(p, -1, _("Back"), name="control")
		
		self.load_items()
		
		# Setup Hotkeys like Favorites
		swap = config_get("swap_play_hotkeys")
		video_flags = wx.ACCEL_CTRL if swap else 0
		audio_flags = 0 if swap else wx.ACCEL_CTRL
		
		# Hotkeys table
		hotkeys = wx.AcceleratorTable([
				(video_flags, wx.WXK_RETURN, wx.NewIdRef()), # Dynamic binding below
				(audio_flags, wx.WXK_RETURN, wx.NewIdRef()),
				(wx.ACCEL_CTRL, ord("D"), wx.NewIdRef()),
			])
		# Note: ListBox SetAcceleratorTable only works if ids match menu items usually?
		# Favorites used context menu IDs. We will do same.

		sizer = wx.BoxSizer(wx.VERTICAL)
		sizer.Add(l1, 1)
		sizer.Add(self.videoList, 1, wx.EXPAND)
		
		ctrlSizer = wx.BoxSizer(wx.HORIZONTAL)
		for control in p.GetChildren():
			if control.Name == "control":
				ctrlSizer.Add(control, 1)
		sizer.Add(ctrlSizer)
		
		p.SetSizer(sizer)
		
		# Bindings
		self.playButton.Bind(wx.EVT_BUTTON, lambda e: self.playVideo())
		self.downloadButton.Bind(wx.EVT_BUTTON, self.onDownloadMenu)
		self.menuButton.Bind(wx.EVT_BUTTON, self.onContext)
		self.deleteButton.Bind(wx.EVT_BUTTON, self.onRemove)
		self.clearButton.Bind(wx.EVT_BUTTON, self.onClear)
		backButton.Bind(wx.EVT_BUTTON, self.onBack)
		
		self.Bind(wx.EVT_CLOSE, self.onBack)
		self.Bind(wx.EVT_CHAR_HOOK, self.onHook)
		self.Bind(wx.EVT_SHOW, self.onShow)
		self.videoList.Bind(wx.EVT_LISTBOX_DCLICK, lambda e: self.playVideo())
		
		self.setupContext() # Sets up IDs and accelerators
		self.toggleControls()
		
		self.Show()
		self.videoList.SetFocus()

	def load_items(self):
		self.items = self.db.get_collection_items(self.collection['id'])
		self.videoList.Clear()
		for item in self.items:
			self.videoList.Append(item['title'])
		if self.videoList.Count > 0:
			self.videoList.Selection = 0

	def toggleControls(self):
		has_items = (len(self.items) > 0)
		for btn in (self.playButton, self.downloadButton, self.menuButton, self.deleteButton, self.clearButton):
			btn.Enable(has_items)

	def setupContext(self):
		self.contextMenu = wx.Menu()
		swap = config_get("swap_play_hotkeys")
		video_key = "Ctrl+Enter" if swap else "Enter"
		audio_key = "Enter" if swap else "Ctrl+Enter"

		self.playId = wx.NewIdRef()
		self.playAudioId = wx.NewIdRef()
		self.removeId = wx.NewIdRef()
		# No Copy Link / Open Browser as requested
		
		self.contextMenu.Append(self.playId, _("Play Video") + f"\t{video_key}")
		self.contextMenu.Append(self.playAudioId, _("Play Audio") + f"\t{audio_key}")
		self.contextMenu.AppendSeparator()
		
		# Playlist Download Submenu Style
		dlMenu = wx.Menu()
		# Individual Items - mirroring Favorites features but adapting for Playlist logic
		self.dlVid = dlMenu.Append(-1, _("Video"))
		audioMenu = wx.Menu()
		self.dlM4a = audioMenu.Append(-1, "m4a")
		self.dlMp3 = audioMenu.Append(-1, "mp3")
		dlMenu.AppendSubMenu(audioMenu, _("Audio"))
		
		self.contextMenu.AppendSubMenu(dlMenu, _("Download"))
		
		# Direct Download item (Single)
		self.directDownloadId = wx.NewIdRef()
		self.contextMenu.Append(self.directDownloadId, _("Direct Download") + "\tCtrl+D")
		
		self.contextMenu.AppendSeparator()
		self.contextMenu.Append(self.removeId, _("Remove from Collection"))

		self.videoList.Bind(wx.EVT_CONTEXT_MENU, self.onContext)
		
		self.Bind(wx.EVT_MENU, lambda e: self.playVideo(), id=self.playId)
		self.Bind(wx.EVT_MENU, lambda e: self.playAudio(), id=self.playAudioId)
		self.Bind(wx.EVT_MENU, self.onRemove, id=self.removeId)
		self.Bind(wx.EVT_MENU, self.onDirectDownload, id=self.directDownloadId)
		
		self.contextMenu.AppendSeparator()
		channelItem = self.contextMenu.Append(-1, _("Go to Channel"))
		dlChannelItem = self.contextMenu.Append(-1, _("Download Channel"))
		self.Bind(wx.EVT_MENU, self.onOpenChannel, channelItem)
		self.Bind(wx.EVT_MENU, self.onDownloadChannel, dlChannelItem)
		
		self.Bind(wx.EVT_MENU, lambda e: self.downloadItem(0), self.dlVid)
		self.Bind(wx.EVT_MENU, lambda e: self.downloadItem(1), self.dlM4a)
		self.Bind(wx.EVT_MENU, lambda e: self.downloadItem(2), self.dlMp3)
		
		# Set Accelerators to match Context Menu
		hotkeys = wx.AcceleratorTable([
				(wx.ACCEL_CTRL if swap else 0, wx.WXK_RETURN, self.playId),
				(0 if swap else wx.ACCEL_CTRL, wx.WXK_RETURN, self.playAudioId),
				(wx.ACCEL_CTRL, ord("D"), self.directDownloadId),
			])
		self.videoList.SetAcceleratorTable(hotkeys)

	def onContext(self, event):
		if self.videoList.Selection != wx.NOT_FOUND:
			self.PopupMenu(self.contextMenu)

	def playVideo(self, audio_mode=False, shuffle=False, on_close=None):
		sel = self.videoList.Selection
		if sel == wx.NOT_FOUND: return
		item = self.items[sel]
		
		# Adapter for MediaGui
		class CollectionResult:
			def __init__(self, items):
				self.videos = []
				for i in items:
					self.videos.append({
						"title": i['title'],
						"url": i['url'],
						"channel": {"name": i['channel_name'], "url": i['channel_url']}
					})
			def get_url(self, i): return self.videos[i]['url']
			def get_title(self, i): return self.videos[i]['title']
			def get_channel(self, i): return self.videos[i]['channel']
			def __len__(self): return len(self.videos)
			def __getitem__(self, i): return self.videos[i]
		
		res_obj = CollectionResult(self.items)
		
		func = get_audio_stream if audio_mode else get_video_stream
		dlg = LoadingDialog(self, _("Playing"), func, item['url'])
		if dlg.res:
			gui = MediaGui(self, item['title'], dlg.res, item['url'], True, res_obj, audio_mode=audio_mode, shuffle=shuffle, on_close=on_close)
			self.Hide()

	def playAudio(self):
		self.playVideo(audio_mode=True)

	def onOpenChannel(self, event):
		sel = self.videoList.Selection
		if sel == wx.NOT_FOUND: return
		item = self.items[sel]
		if item['channel_url']:
			webbrowser.open(item['channel_url'])

	def onDownloadChannel(self, event):
		sel = self.videoList.Selection
		if sel == wx.NOT_FOUND: return
		item = self.items[sel]
		if not item['channel_url']: return
		
		title = item['channel_name'] or _("Unknown Channel")
		url = item['channel_url']
		dlg = DownloadProgress(wx.GetApp().GetTopWindow(), title)
		direct_download(int(config_get('defaultformat')), url, dlg, "channel")

	def onRemove(self, event):
		sel = self.videoList.Selection
		if sel == wx.NOT_FOUND: return
		item = self.items[sel]
		
		# Confirm dialog usually omitted for single remove in Favorites, but kept here for safety?
		# User said "Delete" button (Remove from collection). 
		# Favorites doesn't confirm, just speaks.
		self.db.remove_from_collection(item['id'])
		speak(_("Removed"))
		
		# Remove from list logic
		self.items.pop(sel)
		self.videoList.Delete(sel)
		if self.videoList.Count > 0:
			new_sel = min(sel, self.videoList.Count - 1)
			self.videoList.Selection = new_sel
		self.toggleControls()
		self.videoList.SetFocus()

	def onClear(self, event):
		msg = wx.MessageBox(_("Are you sure you want to clear your favorites?").replace("favorites", "collection"), _("Confirm"), style=wx.YES_NO|wx.ICON_WARNING, parent=self)
		if msg == wx.YES:
			self.db.clear_collection(self.collection['id'])
			self.items = []
			self.videoList.Clear()
			self.toggleControls()
			speak(_("Collection cleared"))
			self.videoList.SetFocus()

	def onDownloadMenu(self, event):
		# Playlist-style Download Menu
		menu = wx.Menu()
		menu.Append(101, _("Download Entire Collection (Video)"))
		menu.Append(102, _("Download Entire Collection (Audio - m4a)"))
		menu.Append(103, _("Download Entire Collection (Audio - mp3)"))
		
		# Individual download submenu
		indMenu = wx.Menu()
		indMenu.Append(200, _("Video"))
		indMenu.Append(201, "m4a")
		indMenu.Append(202, "mp3")
		menu.AppendSubMenu(indMenu, _("Download Selection"))

		self.Bind(wx.EVT_MENU, lambda e: self.downloadCollection(0), id=101)
		self.Bind(wx.EVT_MENU, lambda e: self.downloadCollection(1), id=102)
		self.Bind(wx.EVT_MENU, lambda e: self.downloadCollection(2), id=103)
		
		self.Bind(wx.EVT_MENU, lambda e: self.downloadItem(0), id=200)
		self.Bind(wx.EVT_MENU, lambda e: self.downloadItem(1), id=201)
		self.Bind(wx.EVT_MENU, lambda e: self.downloadItem(2), id=202)
		
		self.PopupMenu(menu)

	def downloadItem(self, format_type):
		sel = self.videoList.Selection
		if sel == wx.NOT_FOUND: return
		item = self.items[sel]
		
		dlg = DownloadProgress(self.Parent, item['title'])
		direct_download(format_type, item['url'], dlg, "video", os.path.join(config_get("path"), self.collection['name']))

	def onDirectDownload(self, event):
		sel = self.videoList.Selection
		if sel == wx.NOT_FOUND: return
		item = self.items[sel]
		
		dlg = DownloadProgress(self.Parent, item['title'])
		direct_download(int(config_get('defaultformat')), item['url'], dlg, "video", os.path.join(config_get("path"), self.collection['name']))

	def downloadCollection(self, format_type):
		if not self.items: return
		confirm = wx.MessageBox(_("Download {} videos?").format(len(self.items)), _("Confirm"), wx.YES_NO | wx.ICON_QUESTION, parent=self)
		if confirm != wx.YES: return
		
		folder = os.path.join(config_get("path"), self.collection['name'])
		if not os.path.exists(folder):
			os.makedirs(folder)
			
		t = Thread(target=self._seq_download, args=(format_type, folder))
		t.daemon = True
		t.start()
		speak(_("Download started"))
		# User didn't specify. Stay open is safer.
		# User requested: Focus on list after download success.
		# Actually, since it runs in background, we just stay here. 
		# Removing Close() keeps us here.
		self.videoList.SetFocus()

	def _seq_download(self, f_type, folder):
		# Map option to format string (logic from direct_download)
		if f_type == 0:
			fmt = "bestvideo[ext=mp4]+bestaudio[ext=m4a]/mp4"
		else:
			fmt = "bestaudio[ext=m4a]"
		convert = True if f_type == 2 else False
		
		# For collection items, we treat them as individual video downloads
		# (not folder/playlist in yt-dlp sense), but placed IN a folder.
		is_folder = False 
		noplaylist = True

		# Collect all URLs
		urls = [item['url'] for item in self.items]
		if not urls: return

		# Create ONE dialog for the entire batch
		self.dlg_ref = None
		ready = threading.Event()
		def create_dlg():
			# Title reflects total count
			self.dlg_ref = DownloadProgress(wx.GetApp().GetTopWindow(), _("Downloading {} videos").format(len(urls)))
			ready.set()
		wx.CallAfter(create_dlg)
		
		ready.wait() 
		
		if self.dlg_ref:
			# Pass the LIST of URLs to downloadAction
			# This mimics playlist behavior: one call, internal iteration, error skipping, single completion msg.
			downloadAction(
				urls, 
				folder, 
				self.dlg_ref, 
				fmt, 
				self.dlg_ref.gaugeProgress, 
				self.dlg_ref.textProgress, 
				convert=convert, 
				folder=is_folder,
				noplaylist=noplaylist,
				silent=False # We WANT the notification now
			)
			# downloadAction handles Destroy and Notification

	def onBack(self, event):
		self.parent_dialog.Show()
		self.Destroy()

	def onShow(self, event):
		if not self.IsShown(): return
		# Refresh list incase items were removed via Player -> AddToCollectionDialog (Remove)
		# Or generic sync.
		# Save selection?
		sel = self.videoList.Selection
		
		self.load_items()
		
		# Restore selection if valid
		if self.videoList.Count > 0:
			if sel != wx.NOT_FOUND and sel < self.videoList.Count:
				self.videoList.Selection = sel
			else:
				self.videoList.Selection = 0
		
		self.toggleControls()
		self.videoList.SetFocus()
		event.Skip()

	def onHook(self, event):
		if event.KeyCode == wx.WXK_ESCAPE:
			self.onBack(None)
		elif event.KeyCode in [wx.WXK_RETURN, wx.WXK_NUMPAD_ENTER]:
			obj = self.FindFocus()
			if obj == self.videoList:
				swap = config_get("swap_play_hotkeys")
				if event.ControlDown():
					self.playVideo() if swap else self.playAudio()
				else:
					self.playAudio() if swap else self.playVideo()
		elif event.KeyCode == wx.WXK_DELETE:
			if self.FindFocus() == self.videoList:
				self.onRemove(None)
		else:
			event.Skip()

# Add to Collection Dialog - Robust
class AddToCollectionDialog(wx.Dialog):
	def __init__(self, parent, video_data):
		super().__init__(parent, title=_("Add to Collection"))
		self.video_data = video_data
		self.db = Collections()
		self.CenterOnParent()
		
		panel = wx.Panel(self)
		sizer = wx.BoxSizer(wx.VERTICAL)
		
		self.colList = wx.ListBox(panel, -1)
		
		btnSizer = wx.BoxSizer(wx.HORIZONTAL)
		self.btnAction = wx.Button(panel, -1, _("Add")) # Dynamic label
		self.btnNew = wx.Button(panel, -1, _("New Collection"))
		self.btnClose = wx.Button(panel, wx.ID_CANCEL, _("Close"))
		
		btnSizer.Add(self.btnAction, 1, wx.ALL, 5)
		btnSizer.Add(self.btnNew, 1, wx.ALL, 5)
		btnSizer.Add(self.btnClose, 1, wx.ALL, 5)
		
		sizer.Add(self.colList, 1, wx.EXPAND | wx.ALL, 5)
		sizer.Add(btnSizer, 0, wx.EXPAND | wx.ALL, 5)
		
		panel.SetSizer(sizer)
		
		self.btnNew.Bind(wx.EVT_BUTTON, self.onNew)
		self.btnAction.Bind(wx.EVT_BUTTON, self.onAction)
		self.colList.Bind(wx.EVT_LISTBOX, self.onSelect)
		self.Bind(wx.EVT_CHAR_HOOK, self.onHook)
		
		self.load_collections()

	def load_collections(self):
		self.cols = self.db.get_all_collections()
		self.colList.Clear()
		for c in self.cols:
			self.colList.Append(c['name'])
		
		if self.colList.Count > 0:
			self.colList.Selection = 0
			self.updateButtonState()
		else:
			self.btnAction.Disable()

	def updateButtonState(self):
		sel = self.colList.Selection
		if sel == wx.NOT_FOUND:
			self.btnAction.Disable()
			return
		
		self.btnAction.Enable()
		col = self.cols[sel]
		is_in = self.db.is_in_collection(col['id'], self.video_data['url'])
		
		if is_in:
			self.btnAction.SetLabel(_("Remove"))
			# Find item id? No, logic needs to be cleaner.
			# We need to know the item ID to remove it.
			# But our `remove_from_collection` needs ID.
			# We need a `remove_from_collection_by_url(col_id, url)`?
			# Or we fetch it.
		else:
			self.btnAction.SetLabel(_("Add"))

	def onSelect(self, event):
		self.updateButtonState()

	def onNew(self, event):
		dlg = wx.TextEntryDialog(self, _("Enter collection name:"), _("New Collection"))
		if dlg.ShowModal() == wx.ID_OK:
			name = dlg.GetValue().strip()
			if name:
				if self.db.create_collection(name):
					self.load_collections()
					# Select new
					self.colList.Selection = self.colList.Count - 1
					self.updateButtonState()
					speak(_("Created"))
				else:
					speak(_("Error"))
		dlg.Destroy()
		
	def onAction(self, event):
		sel = self.colList.Selection
		if sel == wx.NOT_FOUND: return
		
		col = self.cols[sel]
		label = self.btnAction.GetLabel()
		
		if label == _("Add"):
			self.db.add_to_collection(col['id'], self.video_data)
			speak(_("Added to {}").format(col['name']))
		else:
			# Remove
			# We need to implement remove by URL or fetch ID first
			# DB doesn't have `remove_by_url`.
			# We can do `con.execute("delete from collection_items where collection_id=? and url=?", ...)` manually?
			# Or add method. Since I can't edit `database.py` easily again without overhead...
			# Wait, I just edited `database.py`. I can use sqlite directly here via `get_collection_items` but that's slow.
			# I should add `remove_from_collection_by_url` to `database.py`.
			# Actually I can iterate items.
			items = self.db.get_collection_items(col['id'])
			for i in items:
				if i['url'] == self.video_data['url']:
					self.db.remove_from_collection(i['id'])
					break
			speak(_("Removed"))
		
		# Do NOT close. Just update state.
		self.updateButtonState()
		
	def onHook(self, event):
		if event.KeyCode == wx.WXK_ESCAPE:
			self.EndModal(wx.ID_CANCEL)
		else:
			event.Skip()
