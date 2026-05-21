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
DB_DIR = Path.home() / ".task_manager" # user's home + hidden folder .task_manager
DB_PATH = DB_DIR / "tasks.db"

# Initialize db
def init_db():
	"""
	Path.mkdir(exist_ok, parents)
	sqlite3.connect() as x:
	x.execute()
	x.commit()

	"""

	DB_DIR.mkdir(exist_ok=True, parents=True)

	with sqlite3.connect(DB_PATH) as conn:
		# This query auto create the db file
		conn.execute("""
CREATE TABLE IF NOT EXISTS tasks (
			   id INTEGER PRIMARY KEY AUTOINCREMENT,
			   title TEXT NOT NULL,
			   description TEXT,
			   due_date TEXT,
			   priority TEXT CHECK(priority IN ('low','medium','high')) DEFAULT 'medium',
			   status TEXT CHECK(status IN ('pending','in-progress','completed')) DEFAULT 'pending',
			   created_at TEXT DEFAULT CURRENT_TIMESTAMP,
			   updated_at TEXT DEFAULT CURRENT_TIMESTAMP
			)
""")
		conn.commit()

# Connect to db
def get_db_connection() -> sqlite3.Connection:
	"""
	"""

	conn = sqlite3.connect(DB_PATH)
	# row_factory is the blueprint for how rows are formatted when fetched. Default is tuple.
	# sqlite3.Row wrapped conn.row_factory object to behave like both tuple and dictionary.
	conn.row_factory = sqlite3.Row
	return conn

def add_task(title: str, description: str | None = None, due_date: str | None=None, priority: str = 'medium') -> int:
	"""
	isoformat()
	? - placeholder
	conn.execute() - return Cursor object
	cursor.lastrowid - metadata from Cursor object

	"""

	now = datetime.now().isoformat() # ISO 8601 format top choice for database and api
	with get_db_connection() as conn:
		# conn.execute() return Cursor object
		cursor = conn.execute("""
INSERT INTO tasks (title, description, due_date, priority, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?)
""", (title, description, due_date, priority, now, now))
	conn.commit()
	return cursor.lastrowid