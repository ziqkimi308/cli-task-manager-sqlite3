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

	conn = sqlite3.connect(DB_PATH)
	# row_factory is the blueprint for how rows are formatted when fetched. Default is tuple.
	# sqlite3.Row wrapped conn.row_factory object to behave like both tuple and dictionary.
	conn.row_factory = sqlite3.Row

	return conn

# Add a task
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

	return cursor.lastrowid # return id of this cursor object

# Get a task by id
def get_task(task_id: int) -> dict | None:
	with get_db_connection() as conn:
		row = conn.execute('SELECT * FROM tasks WHERE id = ?', task_id).fetchone()

		return dict(row) if row else None

# Update a task
def update_task(task_id: int, **kwargs) -> bool:
	if not kwargs:
		return False
	
	# Format the data according to sql update query format
	set_clause = ', '.join(f"{key} = ?" for key in kwargs.keys())
	values = list(kwargs.values())
	values.append(datetime.now().isoformat())
	values.append(task_id)

	with get_db_connection() as conn:
		# we use """""" because SQL often multilines strings.
		cursor = conn.execute(f"""UPDATE tasks
						SET {set_clause}, updated_at = ?
						WHERE id = ?
""", values)
		conn.commit()

		# return affected row count
		return cursor.rowcount > 0

# Delete a Task by id
def delete_task(task_id: int) -> bool:
	with get_db_connection() as conn:
		cursor = conn.execute('DELETE FROM tasks WHERE id = ?', task_id)
		conn.commit()

		return cursor.rowcount > 0

# List tasks optionally filtered
def list_tasks(status: str | None = None, priority: str | None = None, due_before: str | None = None, limit: int | None = None) -> list[dict]:
	# WHERE is only needed if you add filters; 1=1 is a shortcut to always have a WHERE so you can safely append AND conditions.
	query = 'SELECT * FROM tasks WHERE 1=1'
	params = []

	if status:
		query += ' AND status = ?'
		params.append(status)
	
	if priority:
		query += ' AND priority = ?'
		params.append(priority)

	if due_before:
		query += ' AND due_before = ?'
		params.append(due_before)

	query += ' ORDER BY due_date ASC, priority DESC, created_at ASC'

	if limit:
		query += ' LIMIT ?'
		params.append(limit)

	with get_db_connection() as conn:
		rows = conn.execute(query, params).fetchall()

	return [dict(row) for row in rows]