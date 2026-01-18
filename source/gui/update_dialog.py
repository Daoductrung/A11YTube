import requests
import wx
from wx.lib.newevent import NewEvent
import os
from paths import update_path
from threading import Thread
import shutil
import subprocess
import sys


ProgressChangedEvent, EVT_PROGRESS_CHANGED = NewEvent()
DownloadFinishedEvent, EVT_DOWNLOAD_FINISHED = NewEvent()

class UpdateDialog(wx.Dialog):
	def __init__(self, parent, url):
		super().__init__(None, title=_("Downloading Updates"))
		self.CentreOnParent()

		panel = wx.Panel(self)
		self.status = wx.TextCtrl(panel, -1, value=_("Waiting to start download..."), style=wx.TE_READONLY|wx.TE_MULTILINE|wx.HSCROLL)
		cancelButton = wx.Button(panel, wx.ID_CANCEL, _("Stop Download"))
		self.progress = wx.Gauge(panel, -1, range=100)
		self.progress.Bind(EVT_PROGRESS_CHANGED, self.onChanged)
		self.Bind(EVT_DOWNLOAD_FINISHED, self.onFinished)
		cancelButton.Bind(wx.EVT_BUTTON, self.onCancel)
		self.Bind(wx.EVT_CLOSE, self.onClose)
		t = Thread(target=self.updateDownload, args=[url])
		t.daemon = True
		t.start()
		self.download = True
		self.ShowModal()

	def updateDownload(self, url):
		if os.path.exists(update_path):
			shutil.rmtree(update_path)
		os.mkdir(update_path)
		name = os.path.join(update_path, url.split("/")[-1])
		try:
			with requests.get(url, stream=True) as r:
				if r.status_code != 200:
					self.errorAction()
					return
				size = r.headers.get("content-length")
				try:
					size = int(size)
				except TypeError:
					self.errorAction()
					return
				recieved = 0
				progress = 0
				self.last_progress = -1
				with open(name, "wb") as file:
					for part in r.iter_content(1024):
						file.write(part)
						if not self.download:
							file.close()
							shutil.rmtree(update_path)
							self.Destroy()
							return

						recieved += len(part)
						if size:
							progress = int((recieved/size)*100)
						else:
							progress = 0
						
						if progress > self.last_progress:
							self.last_progress = progress
							wx.PostEvent(self.progress, ProgressChangedEvent(value=progress))
			wx.PostEvent(self, DownloadFinishedEvent(path=name))
		except requests.ConnectionError:
			self.errorAction()

	def errorAction(self):
		wx.CallAfter(wx.MessageBox, _("Cannot update at this time"), _("Error"), style=wx.ICON_ERROR, parent=self)
		shutil.rmtree(update_path)
		wx.CallAfter(self.Destroy)
	def onChanged(self, event):
		self.progress.SetValue(event.value)
		self.status.SetValue(_("Downloading update {}%").format(event.value))

	def onFinished(self, event):
		wx.MessageBox(_("Update downloaded successfully. Press OK to start installation."), _("Success"), parent=self)
		try:
			self.status.Value = _("Installing update")
			path = os.path.join(update_path, event.path)
			subprocess.Popen([path, "/silent"])
		except:
			wx.MessageBox(_("An error occurred while opening the installer. Please try again or contact the developer."), _("Error"), style=wx.ICON_ERROR, parent=self)
			self.Destroy()
			return
		sys.exit()
	def onCancel(self, event):
		self.download = False
	def onClose(self, event):
		if self.download:
			message = wx.MessageBox(_("Download in progress. Do you want to cancel?"), _("Exit"), style=wx.YES_NO, parent=self)
			if message == wx.YES:
				self.download = False
			return
		self.Destroy()