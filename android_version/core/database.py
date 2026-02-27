import sqlite3 as sql
import os
from .paths import get_data_dir, DB_NAME

class DatabaseManager:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(DatabaseManager, cls).__new__(cls)
            cls._instance.con = None
        return cls._instance

    def get_connection(self):
        if self.con is None:
            try:
                db_path = os.path.join(get_data_dir(), DB_NAME)
                self.con = sql.connect(db_path, check_same_thread=False)
                self.prepare_tables()
            except Exception as e:
                print(f"Database Error: {e}")
                self.con = None
        return self.con

    def prepare_tables(self):
        if not self.con: return

        # Favorites
        self.con.execute("""create table if not exists favorite (
            id integer primary key,
            title text not null,
            display_title text not null,
            url text not null,
            is_live integer not null,
            channel_name text not null,
            channel_url not null
        )""")

        # Continue Watching (Renamed from 'continue' to avoid keyword issues, though sqlite allows it)
        # We will migrate or just use new table for Android version
        self.con.execute("create table if not exists continue_watching (id integer primary key, url text not null, position real not null, audio_track integer default -1)")

        # History
        self.con.execute("""create table if not exists history (
            id integer primary key,
            title text not null,
            display_title text not null,
            url text not null,
            is_live integer not null,
            channel_name text not null,
            channel_url not null,
            timestamp datetime default current_timestamp
        )""")

        # Collections
        self.con.execute("create table if not exists collections (id integer primary key, name text not null unique)")
        self.con.execute("""create table if not exists collection_items (
            id integer primary key,
            collection_id integer not null,
            title text not null,
            url text not null,
            channel_name text,
            channel_url text,
            foreign key(collection_id) references collections(id) on delete cascade
        )""")

        # Indexes
        self.con.execute("CREATE INDEX IF NOT EXISTS idx_fav_url ON favorite(url)")
        self.con.execute("CREATE INDEX IF NOT EXISTS idx_hist_url ON history(url)")
        self.con.execute("CREATE INDEX IF NOT EXISTS idx_col_items_url ON collection_items(url)")

        self.con.commit()

    def close(self):
        if self.con:
            self.con.close()
            self.con = None

# Helper wrapper for simplified access
def get_db():
    return DatabaseManager().get_connection()

class Favorite:
    def add_favorite(self, data):
        con = get_db()
        if not con: return
        query = "insert into favorite (title, display_title, url, is_live, channel_name, channel_url) values (?, ?, ?, ?, ?, ?)"
        c_name = data.get('channel_name') or ""
        c_url = data.get('channel_url') or ""
        con.execute(query, (data['title'], data['display_title'], data['url'], data['live'], c_name, c_url))
        con.commit()

    def remove_favorite(self, url):
        con = get_db()
        if not con: return
        con.execute('delete from favorite where url=?', (url,))
        con.commit()

    def is_favorite(self, url):
        con = get_db()
        if not con: return False
        cursor = con.execute('select id from favorite where url=?', (url,)).fetchone()
        return cursor is not None

    def get_all(self):
        con = get_db()
        if not con: return []
        cursor = con.execute("select title, display_title, url, is_live, channel_name, channel_url from favorite").fetchall()
        data = []
        for title, display_title, url, live, channel_name, channel_url in cursor:
            data.append({
                "title": title,
                "display_title": display_title,
                "url": url,
                "live": live,
                "channel_name": channel_name,
                "channel_url": channel_url
            })
        return data

class History:
    def add_history(self, data):
        con = get_db()
        if not con: return
        # Remove existing to bring to top
        self.remove_history(data['url'])

        query = "insert into history (title, display_title, url, is_live, channel_name, channel_url) values (?, ?, ?, ?, ?, ?)"
        c_name = data.get('channel_name') or ""
        c_url = data.get('channel_url') or ""
        con.execute(query, (data['title'], data['display_title'], data['url'], data['live'], c_name, c_url))
        con.commit()

    def remove_history(self, url):
        con = get_db()
        if not con: return
        con.execute('delete from history where url=?', (url,))
        con.commit()

    def clear_history(self):
        con = get_db()
        if not con: return
        con.execute("delete from history")
        con.commit()

    def get_history(self):
        con = get_db()
        if not con: return []
        cursor = con.execute("select title, display_title, url, is_live, channel_name, channel_url from history order by id desc").fetchall()
        data = []
        for title, display_title, url, live, channel_name, channel_url in cursor:
            data.append({
                "title": title,
                "display_title": display_title,
                "url": url,
                "live": live,
                "channel_name": channel_name,
                "channel_url": channel_url
            })
        return data

class Collections:
    def create_collection(self, name):
        con = get_db()
        if not con: return False
        try:
            cursor = con.execute("insert into collections (name) values (?)", (name,))
            con.commit()
            return cursor.lastrowid
        except sql.IntegrityError:
            return False

    def get_all_collections(self):
        con = get_db()
        if not con: return []
        cursor = con.execute("select id, name from collections order by name").fetchall()
        return [{"id": id, "name": name} for id, name in cursor]

    def add_to_collection(self, collection_id, data):
        con = get_db()
        if not con: return False
        if self.is_in_collection(collection_id, data['url']):
            return False
        query = "insert into collection_items (collection_id, title, url, channel_name, channel_url) values (?, ?, ?, ?, ?)"
        c_name = data.get('channel_name') or ""
        c_url = data.get('channel_url') or ""
        con.execute(query, (collection_id, data['title'], data['url'], c_name, c_url))
        con.commit()
        return True

    def remove_from_collection(self, item_id):
        con = get_db()
        if not con: return
        con.execute("delete from collection_items where id=?", (item_id,))
        con.commit()

    def get_collection_items(self, collection_id):
        con = get_db()
        if not con: return []
        cursor = con.execute("select id, title, url, channel_name, channel_url from collection_items where collection_id=?", (collection_id,)).fetchall()
        data = []
        for id, title, url, c_name, c_url in cursor:
            data.append({
                "id": id,
                "title": title,
                "url": url,
                "channel_name": c_name,
                "channel_url": c_url,
                "display_title": title
            })
        return data

    def is_in_collection(self, collection_id, url):
        con = get_db()
        if not con: return False
        res = con.execute("select id from collection_items where collection_id=? and url=?", (collection_id, url)).fetchone()
        return res is not None

    def delete_collection(self, collection_id):
        con = get_db()
        if not con: return
        con.execute("delete from collections where id=?", (collection_id,))
        con.execute("delete from collection_items where collection_id=?", (collection_id,))
        con.commit()
