import sqlite3 as sql
from paths import db_path
import os

def db_init():
	try:
		con = sql.connect(db_path, check_same_thread=False)
	except Exception as e:
		print(e)
		con = None
	return con


def get_con():
	global con
	if con is None:
		con = db_init()
		if con is not None:
			prepare_tables()
	return con

from threading import RLock

db_lock = RLock()

def is_valid(function):
	def rapper(*args, **kwargs):
		with db_lock:
			if get_con() is not None:
				return function(*args, **kwargs)
	return rapper


con = None


@is_valid
def prepare_tables():
	favorites_query = """create table if not exists favorite (id integer primary key, title text not null, display_title text not null, url text not null, is_live integer not null, channel_name text not null, channel_url not null)"""
	con.execute(favorites_query)
	con.commit()
	continue_query = "create table if not exists continue (id integer primary key, url text not null, position real not null)"
	con.execute(continue_query)
	con.commit()
	history_query = """create table if not exists history (id integer primary key, title text not null, display_title text not null, url text not null, is_live integer not null, channel_name text not null, channel_url not null, timestamp datetime default current_timestamp)"""
	con.execute(history_query)
	con.commit()
	
	col_query = "create table if not exists collections (id integer primary key, name text not null unique)"
	con.execute(col_query)
	con.commit()
	
	col_items_query = "create table if not exists collection_items (id integer primary key, collection_id integer not null, title text not null, url text not null, channel_name text, channel_url text, foreign key(collection_id) references collections(id) on delete cascade)"
	con.execute(col_items_query)
	con.commit()
	
	# Migration for audio_track
	try:
		con.execute("ALTER TABLE continue ADD COLUMN audio_track INTEGER DEFAULT -1")
		con.commit()
	except Exception:
		pass # Column likely exists

	# Indexes for performance
	con.execute("CREATE INDEX IF NOT EXISTS idx_fav_url ON favorite(url)")
	con.execute("CREATE INDEX IF NOT EXISTS idx_hist_url ON history(url)")
	con.execute("CREATE INDEX IF NOT EXISTS idx_col_items_url ON collection_items(url)")
	con.commit()

@is_valid
def disconnect():
	con.close()

class Favorite:
	@is_valid
	def add_favorite(self, data):
		query = "insert into favorite (title, display_title, url, is_live, channel_name, channel_url) values (?, ?, ?, ?, ?, ?)"
		# Sanitize inputs to prevent NOT NULL constraint failures
		c_name = data.get('channel_name') or ""
		c_url = data.get('channel_url') or ""
		con.execute(query, (data['title'], data['display_title'], data['url'], data['live'], c_name, c_url))
		con.commit()

	@is_valid
	def remove_favorite(self, url):
		con.execute('delete from favorite where url=?', (url,))
		con.commit()
	@is_valid
	def is_favorite(self, url):
		cursor = con.execute('select id from favorite where url=?', (url,)).fetchone()
		return cursor is not None

	@is_valid
	def get_all(self):
		cursor = con.execute("select title, display_title, url, is_live, channel_name, channel_url from favorite").fetchall()
		data = []
		for title, display_title, url, live, channel_name, channel_url in cursor:
			row = {
				"title": title,
				"display_title": display_title,
				"url": url,
				"live": live,
				"channel_name": channel_name,
				"channel_url": channel_url
			}
			data.append(row)
		return data

	@is_valid
	def clear_favorites(self):
		con.execute("delete from favorite")
		con.commit()

class History:
	@is_valid
	def add_history(self, data):
		# check if url exists to move it to top (optional, or just duplicate? Let's avoid duplicates for now or just simple insert)
		# User didn't specify, but typical history moves recent to top. 
		# For simplicity and speed, we delete old entry if exists then insert new.
		self.remove_history(data['url'])
		
		query = "insert into history (title, display_title, url, is_live, channel_name, channel_url) values (?, ?, ?, ?, ?, ?)"
		# Sanitize inputs
		c_name = data.get('channel_name') or ""
		c_url = data.get('channel_url') or ""
		con.execute(query, (data['title'], data['display_title'], data['url'], data['live'], c_name, c_url))
		con.commit()

	@is_valid
	def remove_history(self, url):
		con.execute('delete from history where url=?', (url,))
		con.commit()

	@is_valid
	def clear_history(self):
		con.execute("delete from history")
		con.commit()

	@is_valid
	def get_history(self):
		# Order by ID desc (newest first)
		cursor = con.execute("select title, display_title, url, is_live, channel_name, channel_url from history order by id desc").fetchall()
		data = []
		for title, display_title, url, live, channel_name, channel_url in cursor:
			row = {
				"title": title,
				"display_title": display_title,
				"url": url,
				"live": live,
				"channel_name": channel_name,
				"channel_url": channel_url
			}
			data.append(row)
		return data


class Continue:
	@classmethod
	@is_valid
	def new_continue(self, url, position, audio_track=-1):
		query = "insert into continue (url, position, audio_track) values (?, ?, ?)"
		con.execute(query, (url, position, audio_track))
		con.commit()
	@classmethod
	@is_valid
	def get_all(self):
		# Now returns full dict with position and track
		try:
			cursor = con.execute("select url, position, audio_track from continue").fetchall()
		except Exception:
			# Fallback for old schema if migration failed (unlikely)
			cursor = con.execute("select url, position from continue").fetchall()
			data = {}
			for url, position in cursor:
				data[url] = {"position": position, "audio_track": -1}
			return data
			
		data = {}
		for url, position, audio_track in cursor:
			data[url] = {"position": position, "audio_track": audio_track}
		return data

	@classmethod
	@is_valid
	def update(self, url, position, audio_track=-1):
		query = "update continue set position=?, audio_track=? where url=?"
		con.execute(query, (position, audio_track, url))
		con.commit()

	@classmethod
	@is_valid
	def remove_continue(self, url):
		con.execute('delete from continue where url=?', (url,))
		con.commit()




class Collections:
	@is_valid
	def create_collection(self, name):
		try:
			cursor = con.execute("insert into collections (name) values (?)", (name,))
			con.commit()
			return cursor.lastrowid
		except sql.IntegrityError:
			return False

	@is_valid
	def rename_collection(self, collection_id, new_name):
		try:
			con.execute("update collections set name=? where id=?", (new_name, collection_id))
			con.commit()
			return True
		except sql.IntegrityError:
			return False

	@is_valid
	def delete_collection(self, collection_id):
		con.execute("delete from collections where id=?", (collection_id,))
		# Cascade delete might not work by default in all sqlite versions without enabling PRAGMA
		con.execute("delete from collection_items where collection_id=?", (collection_id,))
		con.commit()

	@is_valid
	def get_all_collections(self):
		cursor = con.execute("select id, name from collections order by name").fetchall()
		data = []
		for id, name in cursor:
			data.append({"id": id, "name": name})
		return data

	@is_valid
	def add_to_collection(self, collection_id, data):
		query = "insert into collection_items (collection_id, title, url, channel_name, channel_url) values (?, ?, ?, ?, ?)"
		c_name = data.get('channel_name') or ""
		c_url = data.get('channel_url') or ""
		con.execute(query, (collection_id, data['title'], data['url'], c_name, c_url))
		con.commit()

	@is_valid
	def remove_from_collection(self, item_id):
		con.execute("delete from collection_items where id=?", (item_id,))
		con.commit()

	@is_valid
	def get_collection_items(self, collection_id):
		cursor = con.execute("select id, title, url, channel_name, channel_url from collection_items where collection_id=?", (collection_id,)).fetchall()
		data = []
		for id, title, url, c_name, c_url in cursor:
			data.append({
				"id": id,
				"title": title,
				"url": url,
				"channel_name": c_name,
				"channel_url": c_url,
				"display_title": title # Helper for UI consistency
			})
		return data

	@is_valid
	def clear_collection(self, collection_id):
		con.execute("delete from collection_items where collection_id=?", (collection_id,))
		con.commit()

	@is_valid
	def is_in_collection(self, collection_id, url):
		res = con.execute("select id from collection_items where collection_id=? and url=?", (collection_id, url)).fetchone()
		return res is not None

	@is_valid
	def get_collection_count(self, collection_id):
		cursor = con.execute("select count(*) from collection_items where collection_id=?", (collection_id,)).fetchone()
		return cursor[0] if cursor else 0
