import sqlite3
import argparse
import sys
from pathlib import Path
from datetime import datetime, date

# Try to import colorama for colored terminal output
# if unavailable (user did not pip install colorama), fall back to dummy classes so the script still runs without colors.
try:
	from colorama import init, Fore, Style
	# auto reset color after each print
	init(autoreset=True)
	COLOR_ENABLED = True

except ImportError:
	COLOR_ENABLED = False
	# Fore and Style are classes from colorama. Since colorama is not available in this case, we define ourself to empty string (no color) to prevent program crash
	class Fore:
		RED = GREEN = YELLOW = BLUE = CYAN = MAGENTA = WHITE = RESET = ''
	class Style:
		BRIGHT = DIM = NORMAL = RESET_ALL = ''

# database
print(Path.home())
DB_DIR = Path.home() / ".task_manager"