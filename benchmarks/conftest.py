"""
Isolate the benchmarks from the user's setup, before term_timer loads it.

The configuration is the versioned one, the data directory a throwaway
one, and no sound is ever played: the user's own config, home and audio
device never shape, nor get touched by, a run.
"""
import os
import tempfile
from pathlib import Path

HOME = tempfile.TemporaryDirectory(prefix='term-timer-bench-')

os.environ['TERM_TIMER_CONFIG'] = str(Path(__file__).with_name('config.toml'))
os.environ['TERM_TIMER_HOME'] = HOME.name
os.environ['TERM_TIMER_SOUND'] = 'off'
os.environ['TERM_TIMER_PUBLISH'] = '0'
