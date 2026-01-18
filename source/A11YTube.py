
# the main module 
import sys
import os
try:
	from nvda_client.client import speak
	speak("A11YTube is starting...")
except:
	pass


os.chdir(os.path.abspath(os.path.dirname(__file__)))
os.add_dll_directory(os.getcwd())
import settings_handler

import database
import application
import pyperclip
import wx
speak("Loading core components...")
import webbrowser

from language_handler import init_translation, codes
from threading import Thread
import time

def preload_modules(splash=None):
	try:
		if splash: wx.CallAfter(splash.update_progress, 15, _("Loading media player..."))
		import media_player.media_gui
		
		if splash: wx.CallAfter(splash.update_progress, 30, _("Loading browser..."))
		import youtube_browser.browser
		
		if splash: wx.CallAfter(splash.update_progress, 45, _("Loading history..."))
		import gui.history
		
		if splash: wx.CallAfter(splash.update_progress, 60, _("Loading favorites..."))
		import gui.favorites
		
		if splash: wx.CallAfter(splash.update_progress, 75, _("Loading download manager..."))
		import gui.download_dialog
		
		if splash: wx.CallAfter(splash.update_progress, 90, _("Loading link manager..."))
		import gui.link_dlg

		if splash: wx.CallAfter(splash.update_progress, 100, _("Ready"))
		time.sleep(0.5)
		if splash: wx.CallAfter(start_main_app, splash)
	except Exception as e:
		print(e)
		if splash: wx.CallAfter(start_main_app, splash)

def start_main_app(splash):
	HomeScreen()
	splash.Destroy()

class SplashScreen(wx.Frame):
	def __init__(self):
		wx.Frame.__init__(self, None, title=_("A11YTube Starting"), style=wx.FRAME_NO_TASKBAR | wx.STAY_ON_TOP)
		self.SetSize((400, 100))
		self.Centre()
		
		panel = wx.Panel(self)
		sizer = wx.BoxSizer(wx.VERTICAL)
		
		self.status = wx.StaticText(panel, label=_("A11YTube is starting..."))
		self.gauge = wx.Gauge(panel, range=100)
		
		sizer.Add(self.status, 0, wx.ALL | wx.EXPAND, 10)
		sizer.Add(self.gauge, 0, wx.ALL | wx.EXPAND, 10)
		
		panel.SetSizer(sizer)
		
		# Initial announcement
		speak(_("A11YTube is starting..."))

	def update_progress(self, value, msg):
		self.gauge.SetValue(value)
		self.status.SetLabel(msg)
		speak(msg)

settings_handler.config_initialization() 
init_translation("A11YTube") 

def preload_vlc():
	"""
	Background task to warm up the VLC instance.
	This ensures the heavy library loading happens while the user is 
	browsing the UI, preventing lag on the first 'Play' command.
	"""
	try:
		from media_player import player
		player.get_vlc_instance()
	except Exception as e:
		print(f"VLC Preload Error: {e}")


class HomeScreen(wx.Frame):
	def __init__(self):
		wx.Frame.__init__(self, parent=None, title=application.name)
		self.Centre()
		self.SetSize(wx.DisplaySize())
		self.Maximize(True)
		from utiles import force_taskbar_style
		force_taskbar_style(self)
		
		# Background VLC Preload (User Request)
		# Starts immediately after UI init to eliminate first-play lag
		Thread(target=preload_vlc, daemon=True).start()
		
		# Define IDs for hotkeys if needed, or use specific IDs
		self.ID_SEARCH = wx.NewIdRef()
		self.ID_DOWNLOAD = wx.NewIdRef()
		self.ID_PLAY = wx.NewIdRef()
		self.ID_FAV = wx.NewIdRef()
		self.ID_HISTORY = wx.NewIdRef()
		self.ID_OPEN_DIR = wx.NewIdRef()
		self.ID_SETTINGS = wx.NewIdRef()
		self.ID_EXIT = wx.NewIdRef()
		self.ID_GUIDE = wx.NewIdRef()
		self.ID_UPDATE = wx.NewIdRef()
		self.ID_CHANGELOG = wx.NewIdRef()
		self.ID_COLLECTIONS = wx.NewIdRef()

		# Main Sizer
		mainSizer = wx.BoxSizer(wx.VERTICAL)
		
		# --- Data Definitions ---
		self.homeOptions = [
			_("Search YouTube (Ctrl+S)"),
			_("Download from link (Ctrl+D)"),
			_("Play YouTube video from link (Ctrl+P)"),
			_("Favorite Videos (Ctrl+F)"),
			_("Watch History (Ctrl+H)"),
			_("Collections (Ctrl+L)"),
			_("Open downloads folder (Ctrl+O)")
		]
		self.toolsOptions = [
			_("Settings (Ctrl+Shift+S)"),
			_("Check for updates (Ctrl+Shift+U)")
		]
		self.helpOptions = [
			_("User Guide (F1)"),
			_("Changelog (Ctrl+Shift+C)"),
			_("About..."),
			_("Email: trung@ddt.one"),
			_("Website: https://ddt.one")
		]
		
		# --- Navigation Area (Tabs Replacement) ---
		# Using RadioBox for accessible "1 of N" selection without nesting content
		self.navChoices = [_("Home"), _("Tools"), _("Help")]
		self.navBox = wx.RadioBox(self, label=_("Navigation"), choices=self.navChoices, majorDimension=1, style=wx.RA_SPECIFY_ROWS)
		self.navBox.Bind(wx.EVT_RADIOBOX, self.onNavChange)
		
		# --- Content Area ---
		self.contentLabel = wx.StaticText(self, -1, _("Options"))
		self.contentList = wx.ListBox(self, -1, name=_("Options List"))
		self.contentList.Bind(wx.EVT_LISTBOX_DCLICK, self.onListAction)
		
		# Layout
		mainSizer.Add(self.navBox, 0, wx.EXPAND | wx.ALL, 5)
		mainSizer.Add(self.contentLabel, 0, wx.LEFT | wx.RIGHT | wx.TOP, 5)
		mainSizer.Add(self.contentList, 1, wx.EXPAND | wx.ALL, 5)
		
		self.SetSizer(mainSizer)

		# Accelerators (Global Hotkeys)
		hotKeys = wx.AcceleratorTable([
			(wx.ACCEL_CTRL, ord("S"), self.ID_SEARCH),      # Was Ctrl+F
			(wx.ACCEL_CTRL, ord("D"), self.ID_DOWNLOAD),    # No Change
			(wx.ACCEL_CTRL, ord("P"), self.ID_PLAY),        # Was Ctrl+Y
			(wx.ACCEL_CTRL, ord("F"), self.ID_FAV),         # Was Ctrl+Shift+F
			(wx.ACCEL_CTRL, ord("H"), self.ID_HISTORY),     # No Change
			(wx.ACCEL_CTRL, ord("O"), self.ID_OPEN_DIR),    # Was Ctrl+P
			(wx.ACCEL_CTRL|wx.ACCEL_SHIFT, ord("S"), self.ID_SETTINGS), # No Change
			(wx.ACCEL_CTRL, ord("W"), self.ID_EXIT),        # No Change
			(wx.ACCEL_NORMAL, wx.WXK_F1, self.ID_GUIDE),
			(wx.ACCEL_CTRL|wx.ACCEL_SHIFT, ord("U"), self.ID_UPDATE), # Was Ctrl+U
			(wx.ACCEL_CTRL|wx.ACCEL_SHIFT, ord("C"), self.ID_CHANGELOG),
			(wx.ACCEL_CTRL, ord("L"), self.ID_COLLECTIONS)  # Was Ctrl+Shift+L
		])
		self.SetAcceleratorTable(hotKeys)

		# Global Event Bindings for Hotkeys
		self.Bind(wx.EVT_MENU, self.onSearch, id=self.ID_SEARCH)
		self.Bind(wx.EVT_MENU, self.onDownload, id=self.ID_DOWNLOAD)
		self.Bind(wx.EVT_MENU, self.onPlay, id=self.ID_PLAY)
		self.Bind(wx.EVT_MENU, self.onFavorite, id=self.ID_FAV)
		self.Bind(wx.EVT_MENU, self.onHistory, id=self.ID_HISTORY)
		self.Bind(wx.EVT_MENU, self.onOpen, id=self.ID_OPEN_DIR)
		
		# Lazy load SettingsDialog for lambda
		def show_settings(evt):
			from gui.settings_dialog import SettingsDialog
			SettingsDialog(self)

		self.Bind(wx.EVT_MENU, show_settings, id=self.ID_SETTINGS)
		self.Bind(wx.EVT_MENU, lambda event: wx.Exit(), id=self.ID_EXIT)
		self.Bind(wx.EVT_MENU, self.onGuide, id=self.ID_GUIDE)
		self.Bind(wx.EVT_MENU, self.onCheckForUpdates, id=self.ID_UPDATE)
		self.Bind(wx.EVT_MENU, self.onChangelog, id=self.ID_CHANGELOG)
		self.Bind(wx.EVT_MENU, self.onCollections, id=self.ID_COLLECTIONS)

		# Regular Event Bindings
		self.Bind(wx.EVT_CHAR_HOOK, self.onHook)
		self.Bind(wx.EVT_SHOW, self.onShow)
		self.Bind(wx.EVT_CLOSE, self.onClose)
		
		# Initial State
		self.updateContent(0) # Load Home
		
		self.Show()
		self.navBox.SetFocus()

		speak(_("Welcome to A11YTube"))

		from utiles import youtube_regexp
		self.detectFromClipboard(settings_handler.config_get("autodetect"))
		if settings_handler.config_get("checkupdates"):
			from utiles import check_for_updates
			Thread(target=check_for_updates, args=[True]).start()

	def onNavChange(self, event):
		sel = self.navBox.GetSelection()
		self.updateContent(sel)

	def updateContent(self, selection):
		# Clear and populate list based on selection
		self.contentList.Clear()
		
		if selection == 0: # Home
			self.contentList.Set(self.homeOptions)
			self.contentLabel.SetLabel(_("Home Options"))
		elif selection == 1: # Tools
			self.contentList.Set(self.toolsOptions)
			self.contentLabel.SetLabel(_("Tools Options"))
		elif selection == 2: # Help
			self.contentList.Set(self.helpOptions)
			self.contentLabel.SetLabel(_("Help Options"))
			
		if self.contentList.GetCount() > 0:
			self.contentList.SetSelection(0)
			
		# Accessibility announcement handled by RadioBox focus change normally,
		# but updating list might need a hint? 
		# NVDA reads RadioBox item "Home 1 of 3". That is sufficient.

	def onListAction(self, event):
		selection = self.navBox.GetSelection()
		index = self.contentList.GetSelection()
		
		if selection == 0: # Home
			self.executeHomeAction(index)
		elif selection == 1: # Tools
			self.executeToolsAction(index)
		elif selection == 2: # Help
			self.executeHelpAction(index)

	def executeHomeAction(self, index):
		if index == 0: self.onSearch(None)
		elif index == 1: self.onDownload(None)
		elif index == 2: self.onPlay(None)
		elif index == 3: self.onFavorite(None)
		elif index == 4: self.onHistory(None)
		elif index == 5: self.onCollections(None)
		elif index == 6: self.onOpen(None)

	def executeToolsAction(self, index):
		if index == 0:
			from gui.settings_dialog import SettingsDialog
			SettingsDialog(self)
		elif index == 1:
			self.onCheckForUpdates(None)

	def executeHelpAction(self, index):
		if index == 0: self.onGuide(None)
		elif index == 1: self.onChangelog(None)
		elif index == 2: self.onAbout(None)
		elif index == 3: webbrowser.open("mailto:trung@ddt.one")
		elif index == 4: webbrowser.open("https://ddt.one")

	def onHook(self, event):
		# Robust Global Key Handling for Accessibility
		obj = self.FindFocus()
		key = event.GetKeyCode()
		
		# Ctrl+Tab to cycle Navigation (Tabs simulation)
		if key == wx.WXK_TAB and event.ControlDown():
			current = self.navBox.GetSelection()
			count = self.navBox.GetCount()
			next_sel = (current + 1) % count
			if event.ShiftDown():
				next_sel = (current - 1) % count
			self.navBox.SetSelection(next_sel)
			self.updateContent(next_sel)
			self.navBox.SetFocus()
			return

		# Explicit Tab Navigation (User Request)
		# Force Tab/Shift+Tab to switch between NavBox and ContentList
		if key == wx.WXK_TAB:
			# Check hierarchy 
			# Note: RadioBox children usage varies; checking obj directly or parent
			is_nav_focused = (obj == self.navBox or obj.GetParent() == self.navBox)
			is_list_focused = (obj == self.contentList)
			
			if event.ShiftDown():
				# Shift+Tab: List -> Nav
				if is_list_focused:
					self.navBox.SetFocus()
					return # Handled
				elif is_nav_focused:
					# Shift+Tab from Nav -> Cycle back to List (or let native handle?)
					# Native might go to window controls. User asked to move between them.
					self.contentList.SetFocus()
					return
			else:
				# Tab: Nav -> List
				if is_nav_focused:
					self.contentList.SetFocus()
					return
				elif is_list_focused:
					# Tab from List -> Nav
					self.navBox.SetFocus()
					return
		
		# Handle Content List Enter
		if obj == self.contentList:
			if key in [wx.WXK_RETURN, wx.WXK_NUMPAD_ENTER]:
				self.onListAction(None)
				return
		
		# Handle RadioBox Enter override (Enter -> List)
		if obj == self.navBox or obj.GetParent() == self.navBox:
			if key == wx.WXK_RETURN:
				self.contentList.SetFocus()
				return
			
		# Global F1
		if key == wx.WXK_F1:
			self.onGuide(None)
			return

		event.Skip()

	def onPlay(self, event):
		from gui.link_dlg import LinkDlg
		from media_player.media_gui import MediaGui
		from gui.activity_dialog import LoadingDialog
		from utiles import get_audio_stream, get_video_stream, get_related_videos

		linkDlg = LinkDlg(self)
		data = linkDlg.data
		if not data: return # User cancelled
		
		url = data["link"]
		
		# Playlist Detection
		if "list=" in url:
			from gui.playlist_dialog import PlaylistDialog
			# Open Playlist Dialog directly
			PlaylistDialog(self, url)
			return

		dlg = LoadingDialog(self, _("Playing"), get_video_stream if not data["audio"] else get_audio_stream, url)
		if dlg.res:
			stream = dlg.res
			gui = MediaGui(self, stream.title, stream, data["link"])
			self.Hide()

	def onDownload(self, event):
		from gui.download_dialog import DownloadDialog
		dlg = DownloadDialog(self)
		dlg.Show()
	def onSearch(self, event):
		from youtube_browser.browser import YoutubeBrowser
		browser = YoutubeBrowser(self)
	def detectFromClipboard(self, config):
		if not config:
			return
		clip_content = pyperclip.paste()
		from utiles import youtube_regexp
		match = youtube_regexp(clip_content)
		if match is not None:
			from gui.auto_detect_dialog import AutoDetectDialog
			AutoDetectDialog(self, clip_content)
	def onFavorite(self, event):
		from gui.favorites import Favorites
		Favorites(self)
		self.Hide()
	def onHistory(self, event):
		if not settings_handler.config_get("continue"):
			wx.MessageBox(_("This feature is disabled because 'Continue watching' is turned off in Settings."), _("Feature Disabled"), parent=self, style=wx.ICON_INFORMATION)
			return
		from gui.history import HistoryWindow
		HistoryWindow(self)
		self.Hide()
	def onCollections(self, event):
		from gui.collections import CollectionsManager
		CollectionsManager(self)
		self.Hide()
	def onOpen(self, event):
		path = settings_handler.config_get("path")
		if not os.path.exists(path):
			os.mkdir(path)
		os.startfile(path)

	def onShow(self, event):
		# Refocus if showing again
		self.navBox.SetFocus() 
	
	def onGuide(self, event):
		from doc_handler import documentation_get
		content = documentation_get()
		if content is None:
			return
		from gui.text_viewer import Viewer
		Viewer(self, _("A11YTube User Guide"), content).ShowModal()
	def onChangelog(self, event):
		from doc_handler import changelog_get
		content = changelog_get()
		if content is None:
			wx.MessageBox(_("No changelog available."), _("Error"), parent=self, style=wx.ICON_ERROR)
			return
		from gui.text_viewer import Viewer
		Viewer(self, _("Changelog"), content).ShowModal()

	def onCheckForUpdates(self, event):
		from gui.activity_dialog import LoadingDialog
		from utiles import check_for_updates
		LoadingDialog(self, _("Checking for updates. Please wait"), check_for_updates)
		self.Raise()
		# Return focus to tools logic? Just set focus to nav
		self.navBox.SetFocus()

	def onAbout(self, event):
		about = f"""{_('Program Name')}: {application.name}.
{_('Version')}: {application.version}.
{_('Developed By')}: {application.author}.
{_('Description: ')}{_(application.description)}."""
		wx.MessageBox(about, _("About"), parent=self)
	def onClose(self, event):
		database.disconnect()
		wx.Exit()

if __name__ == "__main__":
	try:
		app = wx.App()
		
		# Single Instance Checker
		instance_name = f"A11YTube-{application.version}-{os.getlogin()}"
		checker = wx.SingleInstanceChecker(instance_name)
		if checker.IsAnotherRunning():
			# Find and activate existing window
			from utiles import find_app_window
			import ctypes
			hwnd = find_app_window(application.name)
			
			if hwnd:
				# Show window if minimized or hidden
				if ctypes.windll.user32.IsIconic(hwnd):
					ctypes.windll.user32.ShowWindow(hwnd, 9) # SW_RESTORE
				else:
					# Force show just in case
					ctypes.windll.user32.ShowWindow(hwnd, 5) # SW_SHOW
					
				ctypes.windll.user32.SetForegroundWindow(hwnd)
			speak(_("Application is already running"))
			sys.exit(0)

		lang_id = codes.get(settings_handler.config_get("lang"), wx.LANGUAGE_ARABIC)
		locale = wx.Locale(lang_id)
		
		# Show Splash Screen
		splash = SplashScreen()
		splash.Show()
		
		# Start loading modules in a thread
		Thread(target=preload_modules, args=[splash]).start()
		
		app.MainLoop()
	except Exception as e:
		import traceback
		with open("crash.log", "w") as f:
			f.write(traceback.format_exc())
		raise e
