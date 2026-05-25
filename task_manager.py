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

# Database CRUD Functions
# Initialize db
def init_db():
	"""
    Initialize the SQLite database and create the tasks table if it does not exist.

    This function ensures the hidden `.task_manager` directory exists in the user's
    home folder, then creates a `tasks.db` file with a `tasks` table. The table
    includes fields for title, description, due date, priority, status, and timestamps.

    Returns:
        None
    """
    # Learning notes:
    # - Path.mkdir(exist_ok=True, parents=True) → ensures directory exists
    # - sqlite3.connect() auto-creates the DB file if missing
    # - conn.execute() runs SQL queries
    # - conn.commit() saves changes

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
    Establish a connection to the SQLite database.

    Configures the connection to use sqlite3.Row as the row factory, allowing
    query results to behave like both tuples and dictionaries.

    Returns:
        sqlite3.Connection: A connection object with row_factory set.
    """
    # Learning notes:
    # - row_factory defines how rows are returned
    # - sqlite3.Row allows dict-like access (row['column'])

	conn = sqlite3.connect(DB_PATH)
	# row_factory is the blueprint for how rows are formatted when fetched. Default is tuple.
	# sqlite3.Row wrapped conn.row_factory object to behave like both tuple and dictionary.
	conn.row_factory = sqlite3.Row

	return conn

# Add a task
def add_task(title: str, description: str | None = None, due_date: str | None=None, priority: str = 'medium') -> int:
	"""
    Insert a new task into the database.

    Args:
        title (str): Short title of the task.
        description (str | None): Optional longer description.
        due_date (str | None): Optional due date in ISO format (YYYY-MM-DD).
        priority (str): Task priority ('low', 'medium', 'high'). Defaults to 'medium'.

    Returns:
        int: The auto-generated ID of the newly inserted task.
    """
    # Learning notes:
    # - datetime.now().isoformat() → ISO 8601 format is best for DB/API storage
    # - conn.execute() returns a Cursor object
    # - cursor.lastrowid → gives the ID of the inserted row
    # - Using ? placeholders prevents SQL injection

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
	"""
    Retrieve a single task by its ID.

    Args:
        task_id (int): The unique ID of the task.

    Returns:
        dict | None: A dictionary representing the task if found, otherwise None.
    """

	with get_db_connection() as conn:
		# SQLite placeholders (?) always expect a tuple/list of values, so (task_id,) is required even for one parameter.
		row = conn.execute('SELECT * FROM tasks WHERE id = ?', (task_id,)).fetchone()

		return dict(row) if row else None

# Update a task
def update_task(task_id: int, **kwargs) -> bool:
	"""
    Update fields of an existing task.

    Args:
        task_id (int): The unique ID of the task.
        **kwargs: Key-value pairs of fields to update (e.g., title="New Title").

    Returns:
        bool: True if the task was updated, False otherwise.
    """
    # Learning notes:
    # - ', '.join(f"{key} = ?" ...) builds dynamic SQL SET clause
    # - Always update updated_at timestamp
    # - cursor.rowcount → number of affected rows

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
	"""
    Delete a task by its ID.

    Args:
        task_id (int): The unique ID of the task.

    Returns:
        bool: True if the task was deleted, False otherwise.
    """
    # Learning notes:
    # - DELETE query removes row permanently
    # - cursor.rowcount → confirms deletion

	with get_db_connection() as conn:
		cursor = conn.execute('DELETE FROM tasks WHERE id = ?', (task_id,))
		conn.commit()

		return cursor.rowcount > 0

# List tasks optionally filtered
def list_tasks(status: str | None = None, priority: str | None = None, due_before: str | None = None, limit: int | None = None) -> list[dict]:
	"""
    List tasks with optional filters.

    Args:
        status (str | None): Filter by status ('pending', 'in-progress', 'completed').
        priority (str | None): Filter by priority ('low', 'medium', 'high').
        due_before (str | None): Filter tasks due before a given date (YYYY-MM-DD).
        limit (int | None): Limit the number of tasks returned.

    Returns:
        list[dict]: A list of task dictionaries matching the filters.
    """
    # Learning notes:
    # - WHERE 1=1 trick allows easy AND conditions
    # - ORDER BY sorts tasks by due_date, then priority, then created_at
    # - fetchall() returns all rows

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

# Utility Functions
def colorize(text: str, color: str = '') -> str:
	"""
    Apply color formatting to text if colorama is available.

    Args:
        text (str): The text to colorize.
        color (str): The color code from colorama.Fore or Style.

    Returns:
        str: Colored text if colorama is enabled, otherwise plain text.
    """
    # Learning notes:
    # - Fore.RED + "text" + Style.RESET_ALL → colorized output
    # - init(autoreset=True) means reset after each print

	if COLOR_ENABLED:
		# colorama command 
		# eg: Fore.RED + "Error: Task not found" + Style.RESET_ALL
		# Don't need Style.RESET_ALL bcse already autoreset=True
		return f"{color}{text}"
	
	return text

def validate_date(date_str: str) -> bool:
	"""
    Validate whether a string is a valid date in YYYY-MM-DD format.

    Args:
        date_str (str): The date string to validate.

    Returns:
        bool: True if the string matches the format and is a real date, False otherwise.
    """

	try:
		# String Parse Time is opposite of String Format Time
		# strptime converts string to datetime object
		# strftime converts datetime object to string
		# strptime primary purpose is conversion but validation effect is side benefit. If string doesn't match format, it raises ValueError.
		datetime.strptime(date_str, "%Y-%m-%d")
		return True
	except ValueError:
		return False
		
def format_task(task: dict, show_id: bool = True) -> str:
	"""
    Format a single task into a detailed, multi-line string.

    This verbose formatter is intended for inspecting one task at a time.
    It includes labels ("Title", "Status", "Priority", etc.), shows the
    description if present, highlights overdue tasks in red, and displays
    timestamps. Colors are applied when colorama is available.

    Args:
        task (dict): A dictionary representing a task row from the database.
        show_id (bool): Whether to include the task ID at the top.

    Returns:
        str: A human-readable multi-line string with full details.
    """

	status_colors = {
		'pending': Fore.YELLOW,
		'in-progress': Fore.BLUE,
        'completed': Fore.GREEN,
	}

	priority_colors = {
		'low': Fore.WHITE,
        'medium': Fore.YELLOW,
        'high': Fore.RED,
	}

	status_color = status_colors.get(task['status'], '')
	priority_color = priority_colors.get(task['priority'], '')

	lines = []
	if show_id:
		lines.append(f"ID: {task['id']}")

	lines.extend([
		# colorize takes text and color args
		f"Title: {colorize(task['title'], Style.BRIGHT)}",
        f"Status: {colorize(task['status'].upper(), status_color)}",
        f"Priority: {colorize(task['priority'].upper(), priority_color)}",
	])

	if task['description']:
		lines.append(f"Description: {task['description']}")

	if task['due_date']:
		due = task['due_date']

		# Highlight overdue task
		if task['status'] != 'completed' and due < date.today().isoformat():
			due = colorize(due, Fore.RED + Style.BRIGHT)
		
		lines.append(f"Due Date: {due}")
	
	lines.append(f"Created: {task['created_at'][:16]}")

	return '\n'.join(lines)

def format_task_compact(task: dict) -> str:
	"""
    Format a single task into a compact, one-line string.

    This compact formatter is intended for listing many tasks at once.
    It replaces verbose labels with symbols:
        ○ pending, ◔ in-progress, ✔ completed
        ↓ low, = medium, ↑ high
    The output shows ID, status symbol, priority symbol, truncated title,
    and due date in parentheses, all aligned neatly with rjust/ljust.

    Args:
        task (dict): A dictionary representing a task row from the database.

    Returns:
        str: A concise single-line string with symbolic status/priority.
    """

	status_char = {'pending': '○', 'in-progress': '◔', 'completed': '✔'}.get(task['status'], '?')

	status_color = {'pending': Fore.YELLOW, 'in-progress': Fore.BLUE, 'completed': Fore.GREEN}.get(task['status'], '')

	priority_char = {'low': '↓', 'medium': '=', 'high': '↑'}.get(task['priority'], '')

	priority_color = {'low': Fore.WHITE, 'medium': Fore.YELLOW, 'high': Fore.RED}.get(task['priority'], '')

	# rjust(), center, ljust() are same as f"{var: >3}", f"{var: ^3}", f"{var: <3}"
	id_part = f"{colorize(str(task['id']).rjust(3), Fore.CYAN)}"
	status_part = colorize(status_char, status_color)
	priority_part = colorize(priority_char, priority_color)
	title_part = task['title'][:40] + ('...' if len(task['title']) > 40 else '')
	due_part = f"({task['due_date']})" if task['due_date'] else ''

	return f"{id_part} {status_part} {priority_part} {title_part:<42} {due_part}"

def handle_add(args):
	# Handle wrong date format
	if args.due and not validate_date(args.due):
		print(colorize("Error: Due date must be in YYYY-MM-DD format.", Fore.RED), file=sys.stderr)
		return 1
	
	task_id = add_task(
		title=args.title,
        description=args.description,
        due_date=args.due,
        priority=args.priority
		)
	print(colorize(f"✓ Task added with ID: {task_id}", Fore.GREEN))
	return 0
	
def handle_list(args):
	tasks = list_tasks(
        status=args.status,
        priority=args.priority,
        due_before=args.due_before,
        limit=args.limit
    )

	if not tasks:
		print(colorize("No tasks found.", Fore.YELLOW))
		return 0

	print(colorize(f"\nFound {len(tasks)} task(s):\n", Style.BRIGHT))
	for task in tasks:
		print(format_task_compact(task))
		
	return 0

def handle_show(args):
	task = get_task(args.id)
	if not task:
		print(colorize(f"Error: Task with ID {args.id} not found.", Fore.RED), file=sys.stderr)
		return 1

	print("\n" + format_task(task))
	return 0

def handle_update(args):
	task = get_task(args.id)
	if not task:
		print(colorize(f"Error: Task with ID {args.id} not found.", Fore.RED), file=sys.stderr)
		return 1
	
	updates = {}
	if args.title is not None:
		updates['title'] = args.title
	if args.description is not None:
		updates['description'] = args.description if args.description != '' else None
	if args.status is not None:
		updates['status'] = args.status
	if args.due is not None:
			if args.due and not validate_date(args.due):
				print(colorize("Error: Due date must be in YYYY-MM-DD format.", Fore.RED), file=sys.stderr)
				return 1
			updates['due_date'] = args.due
	if args.priority is not None:
			updates['priority'] = args.priority
	
	# extra layer safety guard before update query
	if not updates:
		print(colorize("No updates specified.", Fore.YELLOW))
		return 1
	
	# (**updates) is unpacking the keyword args
	if update_task(args.id, **updates):
		print(colorize(f"✓ Task {args.id} updated.", Fore.GREEN))
		return 0
	else:
		print(colorize(f"Error: Failed to update task {args.id}.", Fore.RED), file=sys.stderr)
		return 1

def handle_complete(args):
	if update_task(args.id, status='completed'):
		print(colorize(f"✓ Task {args.id} marked as completed.", Fore.GREEN))
		return 0
	else:
		print(colorize(f"Error: Task {args.id} not found.", Fore.RED), file=sys.stderr)
		return 1

def handle_delete(args):
	if not args.force:
		confirm = input(colorize(f"Are you sure you want to delete task {args.id}? [y/N] ", Fore.YELLOW))
		if confirm.lower() != 'y':
			print("Deletion cancelled.")
			return 0
		
	if delete_task(args.id):
		print(colorize(f"✓ Task {args.id} deleted.", Fore.GREEN))
		return 0
	else:
		print(colorize(f"Error: Task {args.id} not found.", Fore.RED), file=sys.stderr)
		return 1


def main():
	init_db()

	parser = argparse.ArgumentParser(
		description="CLI Task Manager with SQLite",
		epilog="""
Examples:
  # Add a task
  task_manager add "Finish report" --priority high --due 2026-12-31

  # List all pending tasks
  task_manager list --status pending

  # Show task details
  task_manager show 3

  # Update a task
  task_manager update 3 --title "Updated title" --priority medium

  # Mark as complete
  task_manager complete 3

  # Delete a task
  task_manager delete 3
""",
formatter_class=argparse.RawDescriptionHelpFormatter,
	)

	subparsers = parser.add_subparsers(dest='command', required=True, help='Sub-commands')

	# Add subcommands and arguments
	# add
	add_parser = subparsers.add_parser("add", help='Add a new task')
	add_parser.add_argument('title', help='Task title')
	add_parser.add_argument('-d', '--description', help='Task description')
	add_parser.add_argument('--due', help='Due date (YYYY-MM-DD)')
	add_parser.add_argument('-p', '--priority', choices=['low', 'medium', 'high'], default='medium', help='Task priority (default: medium)')
	# without this, you will have to manually write conditional logic to choose which func for which subcommand.
	add_parser.set_defaults(func=handle_add)

	# list
	list_parser = subparsers.add_parser('list', help='List tasks')
	list_parser.add_argument('-s', '--status', choices=['pending', 'in-progress', 'completed'], help='Filter by status')
	list_parser.add_argument('-p', '--priority', choices=['low', 'medium', 'high'], help='Filter by priority')
	list_parser.add_argument('--due-before', help='Show tasks due on or before this date (YYYY-MM-DD)')
	list_parser.add_argument('-n', '--limit', type=int, help='Limit number of results')
	list_parser.set_defaults(func=handle_list)

	# show
	show_parser = subparsers.add_parser('show', help='Show task details')
	show_parser.add_argument('id', type=int, help='Task ID')
	show_parser.set_defaults(func=handle_show)

	# update
	update_parser = subparsers.add_parser('update', help='Update a task')
	update_parser.add_argument('id', type=int, help='Task ID')
	update_parser.add_argument('-t', '--title', help='New title')
	update_parser.add_argument('-d', '--description', nargs='?', const='', help='New description (use empty string to clear)')
	update_parser.add_argument('--due', help='New due date (YYYY-MM-DD)')
	update_parser.add_argument('--status', choices=['pending', 'in-progress', 'completed'], help='New status')
	update_parser.add_argument('-p', '--priority', choices=['low', 'medium', 'high'], help='New priority')
	update_parser.set_defaults(func=handle_update)

	# complete
	complete_parser = subparsers.add_parser('complete', help='Mark task as completed')
	complete_parser.add_argument('id', type=int, help='Task ID')
	complete_parser.set_defaults(func=handle_complete)

	# delete
	delete_parser = subparsers.add_parser('delete', help='Delete a task')
	delete_parser.add_argument('id', type=int, help='Task ID')
	delete_parser.add_argument('-f', '--force', action='store_true', help='Skip confirmation prompt')
	delete_parser.set_defaults(func=handle_delete)

	# parse agrs
	args = parser.parse_args()
	sys.exit(args.func(args))

if __name__ == '__main__':
	main()