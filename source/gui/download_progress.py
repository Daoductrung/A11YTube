import wx


class DownloadProgress(wx.Frame):
	def __init__(self, parent, title=""):
		wx.Frame.__init__(self, parent=parent)
		self.Title = _("Downloading - {}").format(title if title != "" else "A11YTube")
		self.Centre()
		panel = wx.Panel(self)
		self.textProgress = wx.Choice(panel, -1, choices=[_("Percentage: {}%").format(0), _("Total Size: {} {}"), _("Downloaded: {} {}"), _("Remaining: {} {}"), _("Speed: {} {}")])
		self.textProgress.Selection = 0
		self.gaugeProgress = wx.Gauge(panel, -1, range=100)
		self.Bind(wx.EVT_CLOSE, self.onClose)
	def onClose(self, event):
		message = wx.MessageBox(_("Download in progress. Do you want to cancel?"), _("Exit"), style=wx.YES_NO, parent=self)
		if message == 2:
			self.Destroy()


