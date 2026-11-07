"""Term Timer - Terminal-based speedcubing timer and training application."""
import os

__version__ = '0.1.0'

# numpy, imported for the sounds, only runs elementwise arithmetic, yet
# OpenBLAS starts one spinning thread per core when numpy is imported:
# 1.6s of CPU at every command on a 20 cores machine. It has to be set
# before that import, hence here. A count exported by the user wins.
os.environ.setdefault('OPENBLAS_NUM_THREADS', '1')
