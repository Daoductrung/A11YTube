import speech_recognition as sr
import threading
import winsound
import time

from nvda_client.client import speak
from settings_handler import config_get

class VoiceHandler:
	def __init__(self):
		self.recognizer = sr.Recognizer()
		self.microphone = sr.Microphone()
		self.is_recording = False
		self.frames = []
		self.audio = None
		self.thread = None

	def start_recording(self):
		return self.start_recording_direct()


	# Retrying approach: Use PyAudio directly for recording to allow precise "Stop on release".
	
	def start_recording_direct(self):
		if self.is_recording: return
		import pyaudio
		self.CHUNK = 1024
		self.FORMAT = pyaudio.paInt16
		self.CHANNELS = 1
		self.RATE = 44100
		
		self.p = pyaudio.PyAudio()
		self.stream = self.p.open(format=self.FORMAT,
						channels=self.CHANNELS,
						rate=self.RATE,
						input=True,
						frames_per_buffer=self.CHUNK)
		
		self.is_recording = True
		self.frames = []
		winsound.Beep(600, 100) # Start Beep
		
		self.thread = threading.Thread(target=self._record_loop_direct)
		self.thread.daemon = True
		self.thread.start()

	def _record_loop_direct(self):
		while self.is_recording:
			try:
				data = self.stream.read(self.CHUNK)
				self.frames.append(data)
			except Exception:
				break

	def stop_recording(self):
		if not self.is_recording: return None
		
		self.is_recording = False
		# Wait for thread?
		if self.thread and self.thread.is_alive():
			self.thread.join(timeout=1.0)
			
		# Stop stream
		try:
			self.stream.stop_stream()
			self.stream.close()
			self.p.terminate()
		except: pass

		winsound.Beep(400, 100) # Stop Beep
		
		if not self.frames: return None
		
		# Process
		import io
		import wave
		
		# Create AudioData
		# SR needs PCM data.
		raw_data = b''.join(self.frames)
		audio_data = sr.AudioData(raw_data, 44100, 2) # rate, sample_width
		
		return audio_data

	def recognize(self, audio_data):
		if not audio_data: return None
		
		lang_map = {
			"vi": "vi-VN",
			"en": "en-US"
		}
		app_lang = config_get("lang")
		lang = lang_map.get(app_lang, "en-US")
		
		try:
			text = self.recognizer.recognize_google(audio_data, language=lang)
			return text
		except sr.UnknownValueError:
			# speak(_("Could not understand audio"))
			return None
		except sr.RequestError as e:
			print(f"Could not request results; {e}")
			return None
		except Exception as e:
			print(f"Recognition error: {e}")
			return None
