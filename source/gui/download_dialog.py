import wx
import pyperclip
import os
from download_handler.downloader import downloadAction
from settings_handler import config_get, config_set
from .download_progress import DownloadProgress
from threading import Thread
from utiles import youtube_regexp


class DownloadDialog(wx.Frame):
	def __init__(self, parent, default_url=""):
		wx.Frame.__init__(self, parent=parent, title=_("Download"))
		self.path = config_get("path")
		self.Centre()
		self.downloading = False
		self.panel = wx.Panel(self)
		sizer = wx.BoxSizer(wx.VERTICAL)
		sizer1 = wx.BoxSizer(wx.HORIZONTAL)
		sizer2 = wx.BoxSizer(wx.HORIZONTAL)
		lbl = wx.StaticText(self.panel, -1, _("Download Link: "))
		self.videoLink = wx.TextCtrl(self.panel, -1, value=default_url)
		self.downloadingFormat = wx.RadioBox(self.panel, -1, _("Media Type"), choices=[_("Audio"), _("Video")])
		lbl2 = wx.StaticText(self.panel, -1, _("Format"), name="convert")
		self.convertingFormat = wx.Choice(self.panel, -1, choices=["m4a", "mp3"], name="convert")
		self.convertingFormat.SetSelection(int(config_get("defaultaudio")))
		self.downloadButton = wx.Button(self.panel, -1, _("Download"))
		self.downloadButton.SetDefault()
		self.changePath = wx.Button(self.panel, -1, f"{_('Download Folder: ')} {self.path}")
		self.changePath.Bind(wx.EVT_BUTTON, self.onChangePath)
		sizer1.Add(lbl, 1)
		sizer1.Add(self.videoLink, 1, wx.EXPAND)
		sizer.Add(sizer1, 1, wx.EXPAND)
		sizer.Add(self.downloadingFormat, 1, wx.EXPAND)
		sizer2.Add(lbl2)
		sizer2.Add(self.convertingFormat, 1, wx.EXPAND)
		sizer.Add(sizer2, 1, wx.EXPAND)
		sizer.Add(self.downloadButton, 1, wx.EXPAND)
		sizer.Add(self.changePath, 1, wx.EXPAND)
		self.panel.SetSizer(sizer)
		# event bindings
		self.downloadButton.Bind(wx.EVT_BUTTON, self.onDownload)
		self.Bind(wx.EVT_ACTIVATE, self.onActivate)
		self.Bind(wx.EVT_RADIOBOX, self.onRadioBox)
		self.Bind(wx.EVT_CHAR_HOOK, self.onHook)
	# a method to show/hide the audio formats box depending on the downloading type
	def toggleChoices(self):
		for control in self.panel.GetChildren():
			if self.downloadingFormat.Selection == 0:
				if control.Name == "convert":
					control.Show()
			elif self.downloadingFormat.Selection == 1:
				if control.Name == "convert":
					control.Hide()
	# an event method which is called when the radio box selection is changed
	def onRadioBox(self, event):
		self.toggleChoices()
	# an event method to call the detect clipboard function when activating the window
	def onActivate(self, event):
		if not self.downloading:
			self.detectFromClipboard()
		else:
			self.downloading = False
		event.Skip()
 # changing path button action
	def onChangePath(self, event):
		path = wx.DirSelector(_("Select Download Folder"), os.path.join(os.getenv("userprofile"), "downloads"), parent=self) # folder select dialog
		if path == "":
			return
		self.changePath.SetLabel(f"{_('Download Folder: ')} {path}") # editing the change path label to show the new path
		self.path = path
	# detect youtube links from the clipboard function
	def detectFromClipboard(self):
		clip_content = pyperclip.paste() # get the clipboard content
		match = youtube_regexp(clip_content)
		if match is not None and youtube_regexp(self.videoLink.Value) is None:
			self.videoLink.SetValue(match.group()) # set the url box content to the detected youtube link if the box was not impty

	def downloadingAction(self):
		url = self.videoLink.GetValue()
		if url == "" or youtube_regexp(url) is None:
			wx.CallAfter(wx.MessageBox, _("Please enter a valid link."), _("Error"), style=wx.ICON_ERROR, parent=self)
			wx.CallAfter(self.videoLink.SetFocus)
			return
		cases = ("list", "channel", "playlist", "/user/")
		for case in cases:
			if case in url:
				folder = True
				break
		else:
			folder = False
		formats = {0:"bestaudio[ext=m4a]", 1:"bestvideo[ext=mp4]+bestaudio[ext=m4a]/mp4"}
		format = formats[self.downloadingFormat.GetSelection()]
		if self.downloadingFormat.Selection == 0 and self.convertingFormat.Selection == 1:
			convert = True
		else:
			convert = False
		# Call shared download action which handles Smart Retry, Cookies, and Error Logging
		wx.CallAfter(self.Hide)
		self.downloading = True
		
		# We pass self.downloadFrame as the 'dlg' (Dialog/Progress)
		# downloadAction signature: (url, path, dlg, downloading_format, monitor, monitor1, convert=False, folder=False)
		downloadAction(
			url, 
			self.path, 
			self.downloadFrame, 
			format, 
			self.downloadFrame.gaugeProgress, 
			self.downloadFrame.textProgress, 
			convert=convert, 
			folder=folder,
			noplaylist=not folder
		)
		
		# downloadAction handles closing the dialog and showing errors.
		# We just need to reset our own state when it returns (it runs synchronously in this thread? No, wait)
		# downloadAction in downloader.py is designed to run in the thread.
		# But wait, downloadAction in downloader.py shows/destroys the dlg.
		# Our self.downloadFrame is created in onDownload.
		# Let's check downloadAction again.
		
		# Logic in downloadAction:
		# wx.CallAfter(dlg.Show) -> Calls Show on passed dlg.
		# ... attempts ...
		# wx.CallAfter(dlg.Destroy) -> Destroys dlg on completion.
		
		# So we don't need to manually destroy it here. 
		# We DO need to show our main window (this dialog) again after it finishes.
		# But downloadAction doesn't know about 'self' (DownloadDialog).
		# We might need a callback or wrapper?
		
		# downloadAction is blocking? 
		# No, downloadAction calls downloader.download() which IS blocking.
		# So downloadAction returns AFTER download finishes?
		# Yes, it calls attempt() which calls downloader.download().
		# So lines after downloadAction will execute when done.
		
		wx.CallAfter(self.Show)
		wx.CallAfter(self.videoLink.SetFocus)
		wx.CallAfter(self.videoLink.SetValue, "")

	def onDownload(self, event):
		config_set("defaultaudio", str(self.convertingFormat.Selection))
		self.downloadFrame = DownloadProgress(wx.GetApp().GetTopWindow())
		t = Thread(target=self.downloadingAction)
		t.daemon = True
		t.start()
	def onHook(self, event):
		if event.KeyCode == wx.WXK_ESCAPE:
			self.Destroy()
		event.Skip()