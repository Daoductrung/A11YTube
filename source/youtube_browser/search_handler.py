from utiles import run_ytdlp_json, time_formatting

class PlaylistResult:
	def __init__(self, url):
		self.url = url
		self.videos = []
		self.count = 0
		self.parse()

	def parse(self):
		try:
			info = run_ytdlp_json(self.url, extract_flat=True, cookies=True)
			entries = info.get('entries', [])
			self.title = info.get('title', _("Unknown Playlist"))

			for vid in entries:
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
		except Exception as e:
			pass
		self.count = len(self.videos)

	def next(self):
		return False
	def get_new_titles(self):
		return self.get_display_titles()
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
		self.limit = 30
		self.perform_search()

	def perform_search(self, load_more=False):
		search_query = self.query
		opts = []
		
		if self.filter == 1:
			import urllib.parse
			encoded_query = urllib.parse.quote(search_query)
			search_query = f"https://www.youtube.com/results?search_query={encoded_query}&sp=EgIQAw%3D%3D"
			opts.extend(['--playlist-end', str(self.limit)])
		else:
			search_query = f"ytsearch{self.limit}:{search_query}"

		try:
			info = run_ytdlp_json(search_query, extract_flat=True, cookies=True, extra_args=opts)
			if 'entries' in info:
				self.parse_entries(info['entries'], load_more)
		except Exception as e:
			pass

	def parse_entries(self, entries, load_more=False):
		if not load_more: 
			self.results = {}
			self.count = 1
		temp_count = 1
		
		for result in entries:
			if not result: continue
			
			res_type = "video"
			if result.get("_type") == "playlist" or result.get("ie_key") == "YoutubeTab": res_type = "playlist"
			elif result.get("url") and "playlist" in result.get("url"): res_type = "playlist"
			
			if self.filter == 1 and res_type != "playlist": continue

			duration_str = time_formatting(str(int(result.get("duration")))) if result.get("duration") else ""
			
			views_str = None
			if result.get("view_count"):
				try: views_str = "{:,}".format(int(result.get("view_count")))
				except Exception: views_str = str(result.get("view_count"))

			channel_name = result.get("uploader") or result.get("channel")
			channel_url = result.get("uploader_url") or result.get("channel_url") or ""
			vid_count = result.get("playlist_count") or result.get("video_count") or 0
			
			url = result.get("url")
			if not url and result.get("id"):
				if res_type == "playlist": url = f"https://www.youtube.com/playlist?list={result.get('id')}"
				else: url = f"https://www.youtube.com/watch?v={result.get('id')}"

			entry = {
				"type": res_type,
				"title": result.get("title", _("Unknown")),
				"url": url,
				"duration": result.get("duration"),
				"duration_formatted": duration_str, 
				"elements": vid_count, 
				"channel": {"name": channel_name, "url": channel_url},
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
			info_parts = []
			
			if data["type"] == "video":
				dur = self.get_duration(data['duration'])
				if dur: info_parts.append(dur)
				if data['channel']['name']: info_parts.append(f"{_('By')} {data['channel']['name']}")
				views = self.views_part(data['views'])
				if views: info_parts.append(views)

			elif data["type"] == "playlist":
				info_parts.append(_("Playlist"))
				if data['channel']['name']: info_parts.append(f"{_('By')} {data['channel']['name']}")
			
			title.extend(info_parts)
			titles.append(", ".join([element for element in title if element != ""]))
		return titles

	def get_last_titles(self):
		titles = self.get_titles()
		if self.new_videos > 0: return titles[-self.new_videos:]
		return []

	def get_title(self, number): return self.results[number+1]["title"]
	def get_url(self, number): return self.results[number+1]["url"]
	def get_type(self, number): return self.results[number+1]["type"]
	def get_channel(self, number): return self.results[number+1]["channel"]
	def load_more(self):
		self.limit += 30
		self.perform_search(load_more=True)
		return True 
	def parse_views(self, string): return string
	def get_views(self, number): return self.results[number+1]['views']
	def views_part(self, data): return _("{} views").format(data) if data is not None else _("Live")
	def get_duration(self, data):
		if data is not None:
			try:
				val = str(int(data))
				return _("Duration: {}").format(time_formatting(val))
			except Exception: return ""
		else: return ""
