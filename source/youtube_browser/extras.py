from yt_dlp import YoutubeDL
import time

class QuietLogger:
	def debug(self, msg):
		pass
	def warning(self, msg):
		pass
	def error(self, msg):
		pass

class Video:
	@staticmethod
	def getInfo(url):
		return Video.get(url)

	@staticmethod
	def get(url):
		ydl_opts = {
			'quiet': True,
			'ignoreerrors': True,
			'noplaylist': True,
			'extract_flat': False,
			'logger': QuietLogger()
		}
		
		# Inner function to perform extraction
		def extract(use_cookies):
			opts = ydl_opts.copy()
			if use_cookies:
				from utiles import get_cookie_opts
				opts.update(get_cookie_opts())
				if 'cookiefile' not in opts:
					raise RuntimeError(_("This video is age restricted or requires a valid cookies.txt file to play."))
			
			with YoutubeDL(opts) as ydl:
				info = ydl.extract_info(url, download=False)
				if not info:
					# If we got no info but no exception, it might be a silent failure or empty result
					# For description purposes, we return a fallback dict
					return {'description': _("Description not available.")}
				return {
					'description': info.get('description', _("No description available.")),
					'title': info.get('title', _("Unknown Video")),
					'viewCount': {'text': str(info.get('view_count', 0))},
					'id': info.get('id', ''),
					'channel_name': info.get('uploader', _("Unknown Channel")),
					'channel_url': info.get('uploader_url', '')
				}

		# Attempt 1: No cookies
		try:
			return extract(False)
		except Exception as e:
			from utiles import check_bot_error
			# Check for auth/age restriction
			if check_bot_error(str(e)):
				try:
					# Attempt 2: With Cookies
					return extract(True)
				except Exception as e2:
					# If second attempt fails, return specific error message in description
					if check_bot_error(str(e2)):
						return {'description': _("This video is age restricted or requires a valid cookies.txt file to play.")}
					return {'description': _("Error fetching description: {}").format(str(e2))}
			
			# Generic error
			return {'description': _("Error fetching description: {}").format(str(e))}


