from utiles import run_ytdlp_json, BotDetectionError

class Video:
	@staticmethod
	def getInfo(url):
		return Video.get(url)

	@staticmethod
	def get(url):
		def extract(use_cookies):
			opts = ['--no-playlist']
			info = run_ytdlp_json(url, cookies=use_cookies, extra_args=opts)
			if not info:
				return {'description': _("Description not available.")}
			return {
				'description': info.get('description', _("No description available.")),
				'title': info.get('title', _("Unknown Video")),
				'viewCount': {'text': str(info.get('view_count', 0))},
				'id': info.get('id', ''),
				'channel_name': info.get('uploader', _("Unknown Channel")),
				'channel_url': info.get('uploader_url', '')
			}

		try:
			return extract(False)
		except BotDetectionError as e:
			try:
				return extract(True)
			except BotDetectionError as e2:
				return {'description': _("This video is age restricted or requires a valid cookies.txt file to play.")}
			except Exception as e2:
				return {'description': _("Error fetching description: {}").format(str(e2))}
		except Exception as e:
			return {'description': _("Error fetching description: {}").format(str(e))}
