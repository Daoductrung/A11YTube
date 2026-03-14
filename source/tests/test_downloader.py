import pytest
import sys
import os
from unittest.mock import MagicMock

# Add source directory to Python path for tests
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Mock wx and other dependencies
import ctypes
if not hasattr(ctypes, 'windll'):
    ctypes.windll = MagicMock()
    ctypes.windll.kernel32.GetUserDefaultUILanguage.return_value = 1033

# Define dummy environment for path mock
os.environ["appdata"] = "/tmp"
os.environ["userprofile"] = "/tmp"

sys.modules['wx'] = MagicMock()
sys.modules['wx.adv'] = MagicMock()
sys.modules['pyperclip'] = MagicMock()
sys.modules['application'] = MagicMock()

import builtins
builtins._ = lambda x: x # Mock translation func

import configparser
from paths import settings_path
config = configparser.ConfigParser()
config.add_section("settings")
os.makedirs(settings_path, exist_ok=True)
with open(os.path.join(settings_path, "settings.ini"), "w") as f:
    config.write(f)

from download_handler.downloader import parse_progress_line

def test_parse_progress_line():
    res = parse_progress_line("[download]   0.0% of ~  20.00MiB at  Unknown B/s ETA Unknown")
    assert res == ('0.0', '20.00MiB', 'Unknown B', 'Unknown')

    res = parse_progress_line("[download]   0.1% of ~  20.00MiB at    1.00MiB/s ETA 00:19")
    assert res == ('0.1', '20.00MiB', '1.00MiB', '00:19')

    res = parse_progress_line("[download]  10.0% of   10.00MiB at    1.00MiB/s ETA 00:09")
    assert res == ('10.0', '10.00MiB', '1.00MiB', '00:09')

    res = parse_progress_line("[download]  26.0% of ~ 265.51MiB at    3.64MiB/s ETA 00:53 (frag 5/20)")
    assert res == ('26.0', '265.51MiB', '3.64MiB', '00:53')

    res = parse_progress_line("[download] 100% of    3.27MiB in 00:00:00 at 13.36MiB/s")
    assert res == ('100', '3.27MiB', '13.36MiB', '00:00')

    res = parse_progress_line("[download]  15.2% of Unknown size at    7.62MiB/s ETA Unknown")
    assert res == ('15.2', 'Unknown size', '7.62MiB', 'Unknown')
