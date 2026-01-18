import wx


class CustomLabel(wx.StaticText):
	# a customed focussable wx.StaticText 
	def __init__(self, *args, **kwargs):
		wx.StaticText.__init__(self, *args, **kwargs)
	def AcceptsFocusFromKeyboard(self):
		# overwriting the AcceptsFocusFromKeyboard to return True
		return True


class CustomButton(wx.Button):
	def __init__(self, *args, **kwargs):
		wx.Button.__init__(self, *args, **kwargs)
		self.Bind(wx.EVT_KEY_DOWN, self.OnKeyDown)

	def OnKeyDown(self, event):
		key = event.GetKeyCode()
		if key in (wx.WXK_SPACE, wx.WXK_RETURN, wx.WXK_NUMPAD_ENTER):
			# Manually trigger click to avoid default "Press" announcement
			self.Command(wx.CommandEvent(wx.EVT_BUTTON.typeId, self.GetId()))
		else:
			event.Skip()

