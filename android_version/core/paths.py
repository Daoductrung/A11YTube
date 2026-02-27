import os

# Flet provides access to standard storage paths.
# We will initialize this properly in the main app logic or use a cross-platform approach.
# For now, we define default relative paths or placeholders.

# In Android (Flet), we usually get the data directory at runtime.
# But we can define constants for keys or filenames.

APP_NAME = "A11YTube"
DB_NAME = "A11YTube.db"
SETTINGS_FILE = "settings.json"
COOKIES_FILE = "cookies.txt"

def get_data_dir():
    # This should be set by the main app initialization
    # or we use a standard location if possible.
    # On Android, we might not have 'HOME' set as expected for Termux vs Native.
    # We will rely on Flet's `page.client_storage` or similar,
    # OR standard python `platformdirs` if available.
    # Fallback to current working directory for development.
    return os.getcwd()

def get_downloads_dir():
    # Android standard Download folder
    # In Flet/Python on Android, typically `/storage/emulated/0/Download`
    if os.path.exists("/storage/emulated/0/Download"):
        return "/storage/emulated/0/Download/A11YTube"
    return os.path.join(get_data_dir(), "Downloads")
