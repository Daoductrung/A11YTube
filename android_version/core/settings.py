import json
import os
from .paths import get_data_dir, SETTINGS_FILE

DEFAULT_SETTINGS = {
    "path": "", # Will be set dynamically
    "defaultaudio": 0, # 0=m4a, 1=mp3
    "lang": "en",
    "autodetect": True,
    "checkupdates": True,
    "autoload": True,
    "seek": 5,
    "conversion": 1,
    "repeatetracks": False,
    "autonext": False,
    "defaultformat": 0, # 0=Video, 1=Audio(m4a), 2=Audio(mp3)
    "volume": 100,
    "continue": True,
    "swap_play_hotkeys": False, # Less relevant on touch, but good for keyboards
    "fullscreen": False,
    "speak_background": False,
    "skip_silence": False,
    "player_notifications": True,
    "audio_device": "Default",
}

class SettingsManager:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(SettingsManager, cls).__new__(cls)
            cls._instance.settings = DEFAULT_SETTINGS.copy()
            cls._instance.load()
        return cls._instance

    def load(self):
        path = os.path.join(get_data_dir(), SETTINGS_FILE)
        if os.path.exists(path):
            try:
                with open(path, 'r') as f:
                    data = json.load(f)
                    self.settings.update(data)
            except Exception as e:
                print(f"Error loading settings: {e}")

        # Ensure download path is set
        if not self.settings["path"]:
            from .paths import get_downloads_dir
            self.settings["path"] = get_downloads_dir()

    def save(self):
        path = os.path.join(get_data_dir(), SETTINGS_FILE)
        try:
            with open(path, 'w') as f:
                json.dump(self.settings, f, indent=4)
        except Exception as e:
            print(f"Error saving settings: {e}")

    def get(self, key):
        return self.settings.get(key, DEFAULT_SETTINGS.get(key))

    def set(self, key, value):
        self.settings[key] = value
        self.save()

# Global accessor
def config_get(key):
    return SettingsManager().get(key)

def config_set(key, value):
    SettingsManager().set(key, value)
