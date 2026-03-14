import pytest
import sys
import os
from unittest.mock import MagicMock
import ctypes

# Fix windll mock for Linux
if not hasattr(ctypes, 'windll'):
    ctypes.windll = MagicMock()
    ctypes.windll.kernel32.GetUserDefaultUILanguage.return_value = 1033

# Define dummy environment for path mock
os.environ["appdata"] = "/tmp"
os.environ["userprofile"] = "/tmp"

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Initialize settings before importing
import configparser
from paths import settings_path
config = configparser.ConfigParser()
config.add_section("settings")
os.makedirs(settings_path, exist_ok=True)
with open(os.path.join(settings_path, "settings.ini"), "w") as f:
    config.write(f)

# Mock modules
import builtins
builtins._ = lambda x: x # Mock translation func
sys.modules['wx'] = MagicMock()
sys.modules['wx.adv'] = MagicMock()
sys.modules['pyperclip'] = MagicMock()
sys.modules['application'] = MagicMock()

from utiles import check_bot_error

def test_check_bot_error():
    assert check_bot_error("ERROR: Sign in to confirm your age") == True
    assert check_bot_error("ERROR: Sign in to confirm you're not a bot") == True
    assert check_bot_error("HTTP Error 403") == True
    assert check_bot_error("ERROR: Video is unavailable") == False
    assert check_bot_error("ERROR: private video") == True
    assert check_bot_error("Some random error") == False
