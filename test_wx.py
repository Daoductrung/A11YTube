import wx

app = wx.App()
frame = wx.Frame(None)
choice = wx.Choice(frame, choices=["A", "B"])
try:
    print("Strings:", choice.Strings)
except Exception as e:
    print("Error:", e)
