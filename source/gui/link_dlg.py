import wx
import pyperclip
from utiles import youtube_regexp


class LinkDlg(wx.Dialog):
	def __init__(self, parent):
		wx.Dialog.__init__(self, parent=parent, title=_("Enter video link to play"))
		self.Centre()
		panel = wx.Panel(self)
		sizer = wx.BoxSizer(wx.VERTICAL)
		lbl = wx.StaticText(panel, -1, _("Video Link"))
		self.link = wx.TextCtrl(panel, -1, value="")
		self.mode = wx.RadioBox(panel, -1, _("Play as: "), choices=[_("Video"), _("Audio")])
		self.okButton = wx.Button(panel, wx.ID_OK, _("Play"))
		self.okButton.SetDefault()
		cancelButton = wx.Button(panel, wx.ID_CANCEL, _("Close"))
		sizer1 = wx.BoxSizer(wx.HORIZONTAL)
		sizer1.Add(lbl, 1)
		sizer1.Add(self.link, 1)
		sizer.Add(sizer1, 1, wx.EXPAND)
		sizer.Add(self.mode, 1, wx.ALL)
		okCancelSizer = wx.StdDialogButtonSizer()
		for btn in (self.okButton, cancelButton):
			okCancelSizer.Add(btn)
		okCancelSizer.Realize()
		sizer.Add(okCancelSizer, 1)
		panel.SetSizer(sizer)
		self.okButton.Bind(wx.EVT_BUTTON, self.onOk)
		self.link.Bind(wx.EVT_TEXT, self.onText)
		self.detectFromClipboard()
		self.ShowModal()
	def onOk(self, event):
		link = self.link.Value
		audio = True if self.mode.Selection == 1 else False
		self.data = {"link": link, "audio": audio}
		self.Destroy()
	def isYoutubeLink(self, value):
		match = youtube_regexp(value)
		return match is not None

	def onText(self, event):
		val = self.link.Value
		self.okButton.Enabled = self.isYoutubeLink(val)
		if "list=" in val:
			self.okButton.Label = _("Open")
		else:
			self.okButton.Label = _("Play")

	def detectFromClipboard(self):
		clip_content = pyperclip.paste() # get the clipboard content
		if self.isYoutubeLink(clip_content):
			self.link.Value = clip_content 
			self.okButton.Enabled = True
		else:
			self.okButton.Enabled = False
