from yt_dlp import YoutubeDL
from utiles import time_formatting, get_cookie_opts


class PlaylistResult:
	def __init__(self, url):
		self.url = url
		self.videos = []
		self.count = 0
		self.ydl_opts = {
			'extract_flat': True,
			'quiet': True,
			'ignoreerrors': True,
		}
		self.ydl_opts.update(get_cookie_opts())
		self.parse()

	def parse(self):
		with YoutubeDL(self.ydl_opts) as ydl:
			info = ydl.extract_info(self.url, download=False)
			self.title = info.get('title', _("Unknown Playlist"))
			if 'entries' in info:
				for vid in info['entries']:
					if not vid: continue
					video = {
						"title": vid.get("title", _("Unknown Title")),
						"url": vid.get("url") if vid.get("url") else f"https://youtube.com/watch?v={vid.get('id')}",
						"duration": time_formatting(str(int(vid.get("duration", 0)))) if vid.get("duration") else "",
						"channel": {
							"name": vid.get("uploader", _("Unknown Channel")),
							"url": vid.get("uploader_url", "")
						},
					}
					self.videos.append(video)
		self.count = len(self.videos)

	def next(self):
		return False

	def get_new_titles(self):
		titles = self.get_display_titles()
		return titles

	def get_title(self, n):
		return self.videos[n]["title"]

	def get_display_titles(self):
		titles = []
		for vid in self.videos:
			title = [vid['title'], _("Duration: {}").format(vid['duration']), f"{_('By')} {vid['channel']['name']}"]
			titles.append(", ".join(title))
		return titles

	def get_url(self, n):
		return self.videos[n]["url"]

	def get_channel(self, n):
		return self.videos[n]["channel"]


class Search:
	def __init__(self, query, filter=0):
		self.query = query
		self.filter = filter
		self.results = {}
		self.count = 1
		self.limit = 30 # Initial batch size
		self.ydl_opts = {
			'extract_flat': 'in_playlist', 
			'quiet': True,
			'ignoreerrors': True,
		}
		self.ydl_opts.update(get_cookie_opts())
		self.perform_search()

	def perform_search(self, load_more=False):
		search_query = self.query
		
		# Update items limit
		# For direct string search (video), we use ytsearchN:
		# For URL search (playlist), we use --playlist-end N (via separate opt, but passing it in ydl_opts is cleaner)
		
		current_opts = self.ydl_opts.copy()
		
		if self.filter == 1:
			import urllib.parse
			encoded_query = urllib.parse.quote(search_query)
			search_query = f"https://www.youtube.com/results?search_query={encoded_query}&sp=EgIQAw%3D%3D"
			# Limit results for URL search
			current_opts['playlistend'] = self.limit
		else:
			# Use ytsearch with limit
			search_query = f"ytsearch{self.limit}:{search_query}"

		with YoutubeDL(current_opts) as ydl:
			info = ydl.extract_info(search_query, download=False)
			if 'entries' in info:
				self.parse_entries(info['entries'], load_more)

	def parse_entries(self, entries, load_more=False):
		if not load_more: 
			self.results = {}
			self.count = 1

		temp_count = 1 # Always start internal counting from 1, matching the dict keys
		
		# If loading more, we need to skip the ones we already have, OR just re-populate everything.
		# yt-dlp returns the whole list [0...N].
		# Re-populating is safer to ensure order, but we can optimize by just updating.
		# Given the dictionary structure self.results[temp_count], we can just overwrite.
		
		current_items = 0
		
		for result in entries:
			if not result: continue
			current_items += 1
			
			res_type = "video"
			if result.get("_type") == "playlist" or result.get("ie_key") == "YoutubeTab":
				res_type = "playlist"
			elif result.get("url") and "playlist" in result.get("url"): 
				res_type = "playlist"
			
			# Filter Logic
			if self.filter == 1 and res_type != "playlist":
				continue

			duration_str = ""
			if result.get("duration"):
				duration_str = time_formatting(str(int(result.get("duration"))))
			
			views_str = None
			if result.get("view_count"):
				try:
					views_str = "{:,}".format(int(result.get("view_count")))
				except Exception:
					views_str = str(result.get("view_count"))

			# Robust parsing for different yt-dlp versions/response formats
			channel_name = result.get("uploader") or result.get("channel")
			channel_url = result.get("uploader_url") or result.get("channel_url") or ""
			
			vid_count = result.get("playlist_count") or result.get("video_count") or 0
			
			url = result.get("url")
			if not url and result.get("id"):
				if res_type == "playlist":
					url = f"https://www.youtube.com/playlist?list={result.get('id')}"
				else:
					url = f"https://www.youtube.com/watch?v={result.get('id')}"

			entry = {
				"type": res_type,
				"title": result.get("title", _("Unknown")),
				"url": url,
				"duration": result.get("duration"),
				"duration_formatted": duration_str, 
				"elements": vid_count, 
				"channel": {
					"name": channel_name,
					"url": channel_url
				},
				"views": views_str
			}
			self.results[temp_count] = entry
			temp_count += 1
		
		self.new_videos = temp_count - self.count
		self.count = temp_count

	def get_titles(self):
		titles = []
		sorted_keys = sorted(self.results.keys())
		for k in sorted_keys:
			data = self.results[k]
			title = [data['title']]
			
			# Info parts construction
			info_parts = []
			
			if data["type"] == "video":
				dur = self.get_duration(data['duration'])
				if dur: info_parts.append(dur)
					
				if data['channel']['name']:
					info_parts.append(f"{_('By')} {data['channel']['name']}")
					
				views = self.views_part(data['views'])
				if views: info_parts.append(views)

			elif data["type"] == "playlist":
				info_parts.append(_("Playlist"))
				
				if data['channel']['name']:
					info_parts.append(f"{_('By')} {data['channel']['name']}")
			
			title.extend(info_parts)
			titles.append(", ".join([element for element in title if element != ""]))
		return titles

	def get_last_titles(self):
		titles = self.get_titles()
		if self.new_videos > 0:
			return titles[-self.new_videos:]
		return []

	def get_title(self, number):
		return self.results[number+1]["title"]
	def get_url(self, number):
		return self.results[number+1]["url"]
	def get_type(self, number):
		return self.results[number+1]["type"]
	def get_channel(self, number):
		return self.results[number+1]["channel"]

	def load_more(self):
		self.limit += 30
		self.perform_search(load_more=True)
		return True 

	def parse_views(self, string):
		return string

	def get_views(self, number):
		return self.results[number+1]['views']

	def views_part(self, data):
		if data is not None:
			return _("{} views").format(data)
		else:
			return _("Live")

	def get_duration(self, data):
		if data is not None:
			try:
				val = str(int(data))
				return _("Duration: {}").format(time_formatting(val))
			except Exception:
				return ""
		else:
			return ""