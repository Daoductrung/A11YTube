import winsdk.windows.media.playback as playback
from winsdk.windows.media import SystemMediaTransportControlsButton, MediaPlaybackType, MediaPlaybackStatus
from winsdk.windows.storage.streams import RandomAccessStreamReference
from winsdk.windows.media.core import MediaSource
import datetime

class SMTCManager:
	def __init__(self, callbacks=None):
		"""
		Initialize SMTC Manager.
		callbacks: dict with keys 'on_play', 'on_pause', 'on_next', 'on_previous'
		"""
		self.callbacks = callbacks or {}
		
		# Create a dummy MediaPlayer to gain access to SMTC
		self.player = playback.MediaPlayer()
		self.player.command_manager.is_enabled = False # Disable default management to allow manual control
		
		# Get SMTC
		self.smtc = self.player.system_media_transport_controls
		self.smtc.is_enabled = True
		self.smtc.is_play_enabled = True
		self.smtc.is_pause_enabled = True
		self.smtc.is_next_enabled = True
		self.smtc.is_previous_enabled = True
		self.smtc.is_rewind_enabled = False # Optional
		self.smtc.is_fast_forward_enabled = False # Optional
		
		# Connect Events
		self.smtc.add_button_pressed(self._on_button_pressed)
		
		# Initial State
		self.smtc.playback_status = MediaPlaybackStatus.CLOSED
		
	def _on_button_pressed(self, sender, args):
		"""Handle SMTC button presses."""
		button = args.button
		
		if button == SystemMediaTransportControlsButton.PLAY:
			if 'on_play' in self.callbacks:
				self.callbacks['on_play']()
				
		elif button == SystemMediaTransportControlsButton.PAUSE:
			if 'on_pause' in self.callbacks:
				self.callbacks['on_pause']()
				
		elif button == SystemMediaTransportControlsButton.NEXT:
			if 'on_next' in self.callbacks:
				self.callbacks['on_next']()
				
		elif button == SystemMediaTransportControlsButton.PREVIOUS:
			if 'on_previous' in self.callbacks:
				self.callbacks['on_previous']()

	def update_metadata(self, title, artist, album_artist="", album_title="", thumbnail_path=None):
		"""Update SMTC metadata."""
		updater = self.smtc.display_updater
		updater.type = MediaPlaybackType.VIDEO # Or MUSIC, VIDEO allows more fields usually?
		
		music_props = updater.music_properties
		music_props.title = title
		music_props.artist = artist
		music_props.album_artist = album_artist
		music_props.album_title = album_title
		
		if thumbnail_path:
			try:
				# winsdk specific way to load local file might be tricky without async
				# RandomAccessStreamReference.create_from_uri(Uri("file://..."))
				# For now, skip thumbnail or implement if critical.
				# A11YTube seems to rely on audio/basic video. 
				# Let's keep it simple for now to avoid async/await in this sync method.
				pass
			except Exception as e:
				print(f"Failed to set thumbnail: {e}")
				
		updater.update()

	def update_status(self, is_playing):
		"""Update playback status."""
		# Since we are using MediaPlayer wrapper, we might need to trick it or set status directly.
		# With MediaPlayer, accessing SMTC properties directly works if CommandManager doesn't override.
		# Let's try setting the property.
		try:
			status = MediaPlaybackStatus.PLAYING if is_playing else MediaPlaybackStatus.PAUSED
			self.smtc.playback_status = status
		except Exception as e:
			print(f"SMTC Status Update Error: {e}")

	def close(self):
		"""Release resources."""
		try:
			self.smtc.is_enabled = False
			# self.player.close() # MediaPlayer doesn't have close() in Python projection typically, relying on GC
		except:
			pass
