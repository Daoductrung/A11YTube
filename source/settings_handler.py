import configparser
import os
from language_handler import get_default_language
from paths import settings_path



defaults = {
	"path": f"{os.getenv('USERPROFILE')}\\downloads\\A11YTube",
	"defaultaudio": 0,
	"lang": get_default_language(),
	"autodetect": True,
	"checkupdates": True,
	"autoload": True,
	"seek": 5,
	"conversion": 1,
	"repeatetracks":False,
	"autonext": False,
	"defaultformat": 0,
	"volume": 100,
	"continue": True,
	"swap_play_hotkeys": False,
	"fullscreen": False,
	"speak_background": False,
	"skip_silence": False,
	"player_notifications": True,
}

from threading import RLock

settings_lock = RLock()

def config_initialization():
	try:
		os.makedirs(settings_path, exist_ok=True)
	except OSError:
		pass
	if not os.path.exists(os.path.join(settings_path, "settings.ini")):
		config = configparser.ConfigParser()
		config.add_section("settings")
		for key, value in defaults.items():
			config["settings"][key] = str(value)
		with open(os.path.join(settings_path, "settings.ini"), "w") as file:
			config.write(file)

def string_to_bool(string):
	if string == "True":
		return True
	elif string == "False":
		return False
	else:
		return string


def config_get(string):
	config = configparser.ConfigParser()
	config.read(os.path.join(settings_path, "settings.ini"))
	try:
		value = config["settings"][string]
		return string_to_bool(value)
	except KeyError:
		config_set(string, defaults[string])
		return defaults[string]


def config_set(key, value):
	with settings_lock:
		config = configparser.ConfigParser()
		config.read(os.path.join(settings_path, "settings.ini"))
		config["settings"][key] = str(value)
		with open(os.path.join(settings_path, "settings.ini"), "w") as file:
			config.write(file)


def config_update_many(updates):
	with settings_lock:
		config = configparser.ConfigParser()
		path = os.path.join(settings_path, "settings.ini")
		config.read(path)
		for key, value in updates.items():
			config["settings"][key] = str(value)
		with open(path, "w") as file:
			config.write(file)

