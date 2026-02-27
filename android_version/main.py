import flet as ft
from core.settings import config_get
from core.database import DatabaseManager, Favorite, History, Collections
from core.paths import get_data_dir
from core.utils import get_video_info, time_formatting, format_relative_time
import threading
import time
import os

class AppManager:
    def __init__(self, page: ft.Page):
        self.page = page
        self.page.title = "A11YTube"
        self.page.theme_mode = ft.ThemeMode.LIGHT
        self.page.padding = 20
        self.page.spacing = 20
        self.page.scroll = ft.ScrollMode.AUTO

        # Initialize Database
        self.db_manager = DatabaseManager()
        self.favorites_db = Favorite()
        self.history_db = History()
        self.collections_db = Collections()

        self.setup_ui()

    def setup_ui(self):
        # App Bar
        self.appbar = ft.AppBar(
            title=ft.Text("A11YTube", size=20, weight=ft.FontWeight.BOLD, semantics_label="A11YTube Home"),
            center_title=True,
            bgcolor=ft.Colors.BLUE,
            color=ft.Colors.WHITE,
            actions=[
                ft.IconButton(
                    icon=ft.Icons.SETTINGS,
                    tooltip="Settings",
                    on_click=self.go_settings,
                    icon_color=ft.Colors.WHITE
                )
            ]
        )
        self.page.appbar = self.appbar

        # Tabs for Navigation
        self.tabs = ft.Tabs(
            selected_index=0,
            animation_duration=300,
            tabs=[
                ft.Tab(
                    text="Home",
                    icon=ft.Icons.HOME,
                    content=self.build_home_tab()
                ),
                ft.Tab(
                    text="Library",
                    icon=ft.Icons.LIBRARY_BOOKS,
                    content=self.build_library_tab()
                ),
                ft.Tab(
                    text="Search",
                    icon=ft.Icons.SEARCH,
                    content=self.build_search_tab()
                ),
            ],
            expand=1,
        )
        self.page.add(self.tabs)

    def build_home_tab(self):
        self.home_content = ft.Column(
            controls=[
                ft.Text("Quick Actions", size=18, weight=ft.FontWeight.BOLD),
                ft.ElevatedButton(
                    "Paste Link from Clipboard",
                    icon=ft.Icons.PASTE,
                    on_click=self.on_paste_link,
                    width=300,
                    height=50
                ),
                ft.ElevatedButton(
                    "Search YouTube",
                    icon=ft.Icons.SEARCH,
                    on_click=lambda e: self.switch_tab(2),
                    width=300,
                    height=50
                ),
                ft.Divider(),
                ft.Text("Recent Activity", size=16, weight=ft.FontWeight.BOLD),
                # Placeholder for recent history items
                ft.ListView(
                    expand=1,
                    spacing=10,
                    padding=10,
                    auto_scroll=False
                )
            ],
            alignment=ft.MainAxisAlignment.START,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            spacing=20,
            expand=True,
            scroll=ft.ScrollMode.AUTO
        )
        return self.home_content

    def build_library_tab(self):
        return ft.Column(
            controls=[
                ft.ListTile(
                    leading=ft.Icon(ft.Icons.HISTORY),
                    title=ft.Text("Watch History"),
                    subtitle=ft.Text("View recently played videos"),
                    on_click=self.go_history
                ),
                ft.Divider(),
                ft.ListTile(
                    leading=ft.Icon(ft.Icons.FAVORITE),
                    title=ft.Text("Favorites"),
                    subtitle=ft.Text("Your saved videos"),
                    on_click=self.go_favorites
                ),
                ft.Divider(),
                ft.ListTile(
                    leading=ft.Icon(ft.Icons.COLLECTIONS),
                    title=ft.Text("Collections"),
                    subtitle=ft.Text("Manage your playlists"),
                    on_click=self.go_collections
                ),
                ft.Divider(),
                ft.ListTile(
                    leading=ft.Icon(ft.Icons.DOWNLOAD),
                    title=ft.Text("Downloads"),
                    subtitle=ft.Text("Access downloaded content"),
                    on_click=self.go_downloads
                )
            ],
            expand=True,
            scroll=ft.ScrollMode.AUTO
        )

    def build_search_tab(self):
        self.search_field = ft.TextField(
            label="Search YouTube",
            hint_text="Enter keywords...",
            on_submit=self.on_search_submit,
            autofocus=False,
            expand=True
        )
        self.search_results_list = ft.ListView(expand=1, spacing=10, padding=10)

        return ft.Column(
            controls=[
                ft.Row(
                    controls=[
                        self.search_field,
                        ft.IconButton(ft.Icons.SEARCH, on_click=self.on_search_submit, tooltip="Search")
                    ],
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN
                ),
                ft.Divider(),
                self.search_results_list
            ],
            expand=True
        )

    def switch_tab(self, index):
        self.tabs.selected_index = index
        self.page.update()

    def on_search_submit(self, e):
        query = self.search_field.value
        if not query: return

        self.search_results_list.controls.clear()
        self.search_results_list.controls.append(
            ft.Text("Searching...", italic=True, text_align=ft.TextAlign.CENTER)
        )
        self.page.update()

        # Run search in background
        threading.Thread(target=self._perform_search, args=(query,), daemon=True).start()

    def _perform_search(self, query):
        import yt_dlp

        results = []
        try:
            ydl_opts = {
                'quiet': True,
                'extract_flat': True,
                'default_search': 'ytsearch20', # Get 20 results
                'ignoreerrors': True,
            }
            from core.utils import get_cookie_opts
            ydl_opts.update(get_cookie_opts())

            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(query, download=False)
                if 'entries' in info:
                    for entry in info['entries']:
                        if not entry: continue
                        title = entry.get('title', 'Unknown')
                        url = entry.get('url', '')
                        if not url: url = f"https://www.youtube.com/watch?v={entry.get('id')}"

                        results.append({
                            "title": title,
                            "url": url,
                            "uploader": entry.get('uploader', 'Unknown Channel'),
                            "duration": entry.get('duration')
                        })
        except Exception as e:
            print(f"Search error: {e}")

        # Update UI on main thread
        def update_ui():
            self.search_results_list.controls.clear()
            if not results:
                self.search_results_list.controls.append(ft.Text("No results found."))
            else:
                for res in results:
                    self.search_results_list.controls.append(
                        self.create_video_tile(res)
                    )
            self.page.update()

        update_ui()

    def create_video_tile(self, video_data):
        return ft.ListTile(
            title=ft.Text(video_data['title'], weight=ft.FontWeight.BOLD, max_lines=2, overflow=ft.TextOverflow.ELLIPSIS),
            subtitle=ft.Text(f"{video_data['uploader']}"),
            leading=ft.Icon(ft.Icons.VIDEO_LIBRARY),
            trailing=ft.PopupMenuButton(
                icon=ft.Icons.MORE_VERT,
                items=[
                    ft.PopupMenuItem(text="Play Video", on_click=lambda e: self.play_video(video_data)),
                    ft.PopupMenuItem(text="Play Audio", on_click=lambda e: self.play_audio(video_data)),
                    ft.PopupMenuItem(text="Download", on_click=lambda e: self.download_video(video_data)),
                    ft.PopupMenuItem(text="Add to Favorites", on_click=lambda e: self.add_favorite(video_data)),
                    ft.PopupMenuItem(text="Add to Collection", on_click=lambda e: self.add_collection(video_data)),
                    ft.PopupMenuItem(text="Copy Link", on_click=lambda e: self.copy_link(video_data['url'])),
                ]
            ),
            on_click=lambda e: self.play_video(video_data)
        )

    def play_video(self, video_data):
        self.show_player(video_data, audio_only=False)

    def play_audio(self, video_data):
        self.show_player(video_data, audio_only=True)

    def show_player(self, video_data, audio_only=False):
        # We need to extract stream URL first
        def extract_and_play():
            from core.utils import get_video_info
            # Show loading
            self.page.snack_bar = ft.SnackBar(ft.Text(f"Loading {'Audio' if audio_only else 'Video'}..."))
            self.page.snack_bar.open = True
            self.page.update()

            stream_info = get_video_info(video_data['url'])

            if stream_info:
                # Add to History
                self.history_db.add_history({
                    "title": video_data['title'],
                    "display_title": video_data['title'],
                    "url": video_data['url'],
                    "live": 0,
                    "channel_name": video_data.get('uploader', ''),
                    "channel_url": ""
                })

                if audio_only:
                    # Use Audio Control
                    audio = ft.Audio(
                        src=stream_info.url,
                        autoplay=True,
                        volume=1.0,
                        balance=0,
                        on_loaded=lambda _: print("Audio Loaded"),
                        on_duration_changed=lambda e: print("Duration:", e.data),
                        on_position_changed=lambda e: print("Position:", e.data),
                    )
                    self.page.overlay.append(audio)
                    self.page.update()
                    self.page.snack_bar = ft.SnackBar(ft.Text(f"Playing Audio: {video_data['title']}"))
                    self.page.snack_bar.open = True
                    self.page.update()
                else:
                    # Use ft.Video control if available (Recent Flet versions)
                    # If not, fallback to WebView or simulated UI.
                    # Assuming we are on recent Flet which supports Video control.

                    try:
                        video_player = ft.Video(
                            expand=True,
                            playlist=[ft.VideoMedia(stream_info.url)],
                            playlist_mode=ft.PlaylistMode.SINGLE,
                            fill_color=ft.Colors.BLACK,
                            aspect_ratio=16/9,
                            volume=100,
                            autoplay=True,
                            filter_quality=ft.FilterQuality.HIGH,
                            muted=False,
                        )

                        # Fullscreen overlay
                        overlay = ft.Container(
                            content=ft.Stack([
                                video_player,
                                ft.IconButton(
                                    ft.Icons.CLOSE,
                                    icon_color=ft.Colors.WHITE,
                                    top=10,
                                    right=10,
                                    on_click=lambda e: self.close_overlay(overlay)
                                )
                            ]),
                            bgcolor=ft.Colors.BLACK,
                            expand=True,
                            alignment=ft.alignment.center
                        )

                        # Add to page overlay (Dialog/Full screen)
                        # We use a full-screen Dialog without padding
                        dlg = ft.AlertDialog(
                            content=overlay,
                            modal=True,
                            content_padding=0,
                            inset_padding=0,
                        )
                        self.page.dialog = dlg
                        dlg.open = True
                        self.page.update()

                    except AttributeError:
                        # Fallback for older Flet without Video control
                        player_dlg = ft.AlertDialog(
                            title=ft.Text(video_data['title']),
                            content=ft.Column([
                                ft.Text("Video Playback Not Supported in this Flet version directly."),
                                ft.Text(f"Stream URL: {stream_info.url[:50]}..."),
                                ft.ElevatedButton("Open in Browser", on_click=lambda e: self.page.launch_url(stream_info.url))
                            ], height=150),
                            actions=[
                                ft.TextButton("Close", on_click=lambda e: self.close_dialog(player_dlg))
                            ]
                        )
                        self.page.dialog = player_dlg
                        player_dlg.open = True
                        self.page.update()

            else:
                self.page.snack_bar = ft.SnackBar(ft.Text("Failed to load stream."))
                self.page.snack_bar.open = True
                self.page.update()

        threading.Thread(target=extract_and_play, daemon=True).start()

    def close_overlay(self, overlay):
        # If using dialog
        self.page.dialog.open = False
        self.page.update()

    def close_dialog(self, dlg):
        dlg.open = False
        self.page.update()

    def download_video(self, video_data):
        def start_dl(fmt):
            from core.downloader import start_download
            from core.paths import get_downloads_dir
            import os

            path = get_downloads_dir()

            self.page.snack_bar = ft.SnackBar(ft.Text("Download started..."))
            self.page.snack_bar.open = True
            self.page.update()

            def on_progress(p, s):
                pass

            def on_complete(success, err):
                msg = "Download Completed" if success else f"Download Failed: {err}"
                self.page.snack_bar = ft.SnackBar(ft.Text(msg))
                self.page.snack_bar.open = True
                self.page.update()

            threading.Thread(target=start_download, args=(video_data['url'], path, fmt, on_progress, on_complete), daemon=True).start()
            self.close_dialog(self.page.dialog)

        dl_dlg = ft.AlertDialog(
            title=ft.Text("Download"),
            content=ft.Column([
                ft.ElevatedButton("Video (MP4)", on_click=lambda e: start_dl(0)),
                ft.ElevatedButton("Audio (M4A)", on_click=lambda e: start_dl(1)),
                ft.ElevatedButton("Audio (MP3)", on_click=lambda e: start_dl(2)),
            ], height=150, alignment=ft.MainAxisAlignment.CENTER),
            actions=[ft.TextButton("Cancel", on_click=lambda e: self.close_dialog(dl_dlg))]
        )
        self.page.dialog = dl_dlg
        dl_dlg.open = True
        self.page.update()

    def add_favorite(self, video_data):
        self.favorites_db.add_favorite({
            "title": video_data['title'],
            "display_title": video_data['title'],
            "url": video_data['url'],
            "live": 0,
            "channel_name": video_data.get('uploader', ''),
            "channel_url": ""
        })
        self.page.snack_bar = ft.SnackBar(ft.Text("Added to Favorites"))
        self.page.snack_bar.open = True
        self.page.update()

    def add_collection(self, video_data):
        cols = self.collections_db.get_all_collections()
        if not cols:
            self.page.snack_bar = ft.SnackBar(ft.Text("No collections found. Create one in Library."))
            self.page.snack_bar.open = True
            self.page.update()
            return

        def add_to_col(col_id):
            self.collections_db.add_to_collection(col_id, {
                "title": video_data['title'],
                "url": video_data['url'],
                "channel_name": video_data.get('uploader', ''),
                "channel_url": ""
            })
            self.page.snack_bar = ft.SnackBar(ft.Text("Added to Collection"))
            self.page.snack_bar.open = True
            self.page.update()
            self.close_dialog(self.page.dialog)

        items = []
        for c in cols:
            items.append(ft.ListTile(title=ft.Text(c['name']), on_click=lambda e, cid=c['id']: add_to_col(cid)))

        col_dlg = ft.AlertDialog(
            title=ft.Text("Select Collection"),
            content=ft.Column(items, height=200, scroll=ft.ScrollMode.AUTO),
            actions=[ft.TextButton("Cancel", on_click=lambda e: self.close_dialog(col_dlg))]
        )
        self.page.dialog = col_dlg
        col_dlg.open = True
        self.page.update()

    def copy_link(self, url):
        self.page.set_clipboard(url)
        self.page.snack_bar = ft.SnackBar(ft.Text("Link copied to clipboard"))
        self.page.snack_bar.open = True
        self.page.update()

    def on_paste_link(self, e):
        # Dialog to paste link
        link_field = ft.TextField(label="Video Link", hint_text="Paste YouTube link here")

        def process_paste(e):
            url = link_field.value
            if not url: return
            self.close_dialog(self.page.dialog)

            # Immediately try to fetch and play or show info
            # We'll treat it like a search result with 1 item
            self._perform_search(url) # yt-dlp handles url as search/extract

        paste_dlg = ft.AlertDialog(
            title=ft.Text("Paste Link"),
            content=link_field,
            actions=[
                ft.TextButton("Open", on_click=process_paste),
                ft.TextButton("Cancel", on_click=lambda e: self.close_dialog(paste_dlg))
            ]
        )
        self.page.dialog = paste_dlg
        paste_dlg.open = True
        self.page.update()

    def go_history(self, e):
        self.show_list_view("Watch History", self.history_db.get_history())

    def go_favorites(self, e):
        self.show_list_view("Favorites", self.favorites_db.get_all())

    def go_collections(self, e):
        cols = self.collections_db.get_all_collections()

        def open_col(col):
            items = self.collections_db.get_collection_items(col['id'])
            mapped = []
            for i in items:
                mapped.append({
                    "title": i['title'],
                    "url": i['url'],
                    "uploader": i['channel_name']
                })
            self.show_list_view(col['name'], mapped)

        list_items = []
        for c in cols:
            list_items.append(
                ft.ListTile(
                    title=ft.Text(c['name']),
                    leading=ft.Icon(ft.Icons.FOLDER),
                    on_click=lambda e, col=c: open_col(col)
                )
            )

        list_items.insert(0, ft.ElevatedButton("New Collection", on_click=self.create_collection_dialog))

        self.show_generic_view("Collections", list_items)

    def create_collection_dialog(self, e):
        tf = ft.TextField(label="Collection Name")
        def create(e):
            if tf.value:
                self.collections_db.create_collection(tf.value)
                self.close_dialog(self.page.dialog)
                self.go_collections(None)

        dlg = ft.AlertDialog(
            title=ft.Text("New Collection"),
            content=tf,
            actions=[
                ft.TextButton("Create", on_click=create),
                ft.TextButton("Cancel", on_click=lambda e: self.close_dialog(dlg))
            ]
        )
        self.page.dialog = dlg
        dlg.open = True
        self.page.update()

    def go_downloads(self, e):
        from core.paths import get_downloads_dir
        path = get_downloads_dir()

        if not os.path.exists(path):
            files = []
        else:
            files = os.listdir(path)

        file_items = []
        if not files:
            file_items.append(ft.Text("No downloads found."))
        else:
            for f in files:
                file_items.append(ft.ListTile(
                    leading=ft.Icon(ft.Icons.AUDIO_FILE),
                    title=ft.Text(f),
                    # On click could play or open
                ))

        self.show_generic_view("Downloads", file_items)

    def show_list_view(self, title, data_list):
        items = []
        for item in data_list:
            items.append(self.create_video_tile(item))

        self.show_generic_view(title, items)

    def show_generic_view(self, title, controls):
        view = ft.AlertDialog(
            title=ft.Text(title),
            content=ft.Column(controls, height=400, width=300, scroll=ft.ScrollMode.AUTO),
            actions=[ft.TextButton("Close", on_click=lambda e: self.close_dialog(view))]
        )
        self.page.dialog = view
        view.open = True
        self.page.update()

    def go_settings(self, e):
        dlg = ft.AlertDialog(
            title=ft.Text("Settings"),
            content=ft.Column([
                ft.Text("Settings not fully implemented in prototype."),
                ft.Switch(label="Dark Mode", value=False, on_change=lambda e: self.toggle_theme(e.control.value))
            ]),
            actions=[ft.TextButton("Close", on_click=lambda e: self.close_dialog(dlg))]
        )
        self.page.dialog = dlg
        dlg.open = True
        self.page.update()

    def toggle_theme(self, is_dark):
        self.page.theme_mode = ft.ThemeMode.DARK if is_dark else ft.ThemeMode.LIGHT
        self.page.update()

def main(page: ft.Page):
    app = AppManager(page)

if __name__ == "__main__":
    ft.app(target=main)
