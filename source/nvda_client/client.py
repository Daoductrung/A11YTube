import ctypes
import platform

nvda = None

def get_nvda():
	global nvda
	if nvda is None:
		arch = platform.architecture()[0]
		dll_name = f"nvdaControllerClient{'32' if arch == '32bit' else '64'}.dll"
		import os
		import sys
		
		# Robust path finding
		if getattr(sys, 'frozen', False):
			# OneDir: dll is in _internal usually (if PyInstaller default) OR root
			# We check both
			base = os.path.dirname(sys.executable)
			paths = [
				os.path.join(base, dll_name),
				os.path.join(base, '_internal', dll_name),
				os.path.join(sys._MEIPASS, dll_name) if hasattr(sys, '_MEIPASS') else None
			]
		else:
			# Dev: relative to this file
			base = os.path.dirname(os.path.abspath(__file__))
			paths = [os.path.join(base, dll_name)]
			
		dll_path = None
		for p in paths:
			if p and os.path.exists(p):
				dll_path = p
				break
				
		if not dll_path:
			# Fallback to CWD
			dll_path = f".\\{dll_name}"

		try:
			nvda = ctypes.windll.LoadLibrary(dll_path)
		except Exception:
			nvda = False # Mark as failed to avoid retrying
	return nvda

def speak(msg):
	lib = get_nvda()
	if not lib: return
	try:
		# Check if we should speak based on focus and settings
		import wx
		from settings_handler import config_get
		
		# If speak_background is False (default), we only speak if active
		if not config_get("speak_background"):
			# We need to be careful about threading. wx.GetApp might be None during shutdown
			app = wx.GetApp()
			if app and app.IsActive():
				pass # Proceed
			else:
				return # Silent return
				
		running = lib.nvdaController_testIfRunning()
		if running == 0:
			lib.nvdaController_speakText(msg)
	except:
		pass
