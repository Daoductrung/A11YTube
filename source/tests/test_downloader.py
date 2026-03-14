import pytest
import re
import sys
import os

# Add source directory to Python path for tests
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# We can just test the regex parsing here
def test_regex():
    prog_regex = re.compile(r'\[download\]\s+([0-9\.]+)\%\s+of\s+([~0-9\.\w\s]+?)\s+at\s+([0-9\.\w\s]+?)\/s\s+ETA\s+([0-9:]+|Unknown)')

    match = prog_regex.search("[download]   0.0% of ~  20.00MiB at  Unknown B/s ETA Unknown")
    assert match is not None
    assert match.groups() == ('0.0', '~  20.00MiB', 'Unknown B', 'Unknown')

    match = prog_regex.search("[download]   0.1% of ~  20.00MiB at    1.00MiB/s ETA 00:19")
    assert match is not None
    assert match.groups() == ('0.1', '~  20.00MiB', '1.00MiB', '00:19')

    match = prog_regex.search("[download]  10.0% of   10.00MiB at    1.00MiB/s ETA 00:09")
    assert match is not None
    assert match.groups() == ('10.0', '10.00MiB', '1.00MiB', '00:09')

    match = prog_regex.search("[download]  26.0% of ~ 265.51MiB at    3.64MiB/s ETA 00:53 (frag 5/20)")
    assert match is not None
    assert match.groups() == ('26.0', '~ 265.51MiB', '3.64MiB', '00:53')
