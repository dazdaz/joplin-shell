#!/usr/bin/env python3
"""
joplin-console.py
Interactive console browser for a Joplin database.sqlite file.
"""

import os
import sys
import sqlite3
import argparse
import textwrap
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any, Optional

# Try to import readline, but don't fail if not available
try:
    import readline
    READLINE_AVAILABLE = True
except ImportError:
    readline = None
    READLINE_AVAILABLE = False

# ----------------------------------------------------------------------
# Helper functions
# ----------------------------------------------------------------------
def ts_to_str(ts: Optional[int]) -> str:
    """Convert Unix timestamp (ms) to human-readable string."""
    if ts is None or ts == 0:
        return "—"
    return datetime.fromtimestamp(ts / 1000).strftime("%Y-%m-%d %H:%M:%S")

def print_wrapped(text: str, indent: int = 0, width: int = 80):
    """Print a long text with nice line-wrapping."""
    wrapper = textwrap.TextWrapper(
        initial_indent=" " * indent,
        subsequent_indent=" " * indent,
        width=width,
    )
    print(wrapper.fill(text))

# Enhanced terminal input with arrow key support
command_history: List[str] = []
current_input = ""
cursor_position = 0

def setup_terminal():
    """Setup terminal for raw input if needed."""
    if not READLINE_AVAILABLE:
        try:
            import tty
            import termios
            return True
        except ImportError:
            pass
    return False

def get_terminal_raw_input(prompt: str = "") -> str:
    """Get input with arrow key support for systems without readline."""
    global command_history, current_input, cursor_position
    
    import sys
    import tty
    import termios
    
    current_input = ""
    cursor_position = 0
    
    print(prompt, end="", flush=True)
    
    try:
        # Get terminal settings
        fd = sys.stdin.fileno()
        old_settings = termios.tcgetattr(fd)
        
        try:
            # Set terminal to raw mode
            tty.setraw(sys.stdin.fileno())
            
            while True:
                ch = sys.stdin.read(1)
                
                if ch == '\n' or ch == '\r':
                    # Enter key
                    print()  # New line
                    if current_input.strip():
                        command_history.append(current_input)
                    return current_input
                    
                elif ch == '\x03':
                    # Ctrl-C
                    print("^C")
                    return ""
                    
                elif ch == '\x1b':
                    # Escape sequence (arrow keys)
                    next1 = sys.stdin.read(1)
                    next2 = sys.stdin.read(1)
                    
                    if next1 == '[':
                        if next2 == 'A':
                            # Up arrow
                            if command_history and current_input != command_history[-1]:
                                current_input = command_history[-1]
                                cursor_position = len(current_input)
                                print('\r' + ' ' * (len(prompt) + len(current_input)) + '\r', end="")
                                print(prompt + current_input, end="", flush=True)
                        elif next2 == 'B':
                            # Down arrow - clear input if we were navigating up
                            if current_input:
                                print('\r' + ' ' * (len(prompt) + len(current_input)) + '\r', end="")
                                current_input = ""
                                cursor_position = 0
                                print(prompt, end="", flush=True)
                        elif next2 == 'C':
                            # Right arrow
                            if cursor_position < len(current_input):
                                cursor_position += 1
                                print('\x1b[C', end="", flush=True)
                        elif next2 == 'D':
                            # Left arrow
                            if cursor_position > 0:
                                cursor_position -= 1
                                print('\x1b[D', end="", flush=True)
                                
                elif ch == '\x7f' or ch == '\b':
                    # Backspace
                    if cursor_position > 0:
                        cursor_position -= 1
                        current_input = current_input[:cursor_position] + current_input[cursor_position+1:]
                        print('\r' + ' ' * (len(prompt) + len(current_input)) + '\r', end="")
                        print(prompt + current_input, end="", flush=True)
                        for _ in range(cursor_position, len(current_input)):
                            print('\x1b[D', end="", flush=True)
                            
                elif ord(ch) >= 32 and ord(ch) <= 126:
                    # Regular printable character
                    current_input = current_input[:cursor_position] + ch + current_input[cursor_position:]
                    cursor_position += 1
                    print('\r' + ' ' * (len(prompt) + len(current_input)) + '\r', end="")
                    print(prompt + current_input, end="", flush=True)
                    for _ in range(cursor_position, len(current_input)):
                        print('\x1b[D', end="", flush=True)
                        
        finally:
            # Restore terminal settings
            termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
            
    except Exception:
        # Fallback to basic input
        return input(prompt)
    
    return ""

def enhanced_input(prompt: str = "") -> str:
    """Enhanced input with command history and arrow key support."""
    global command_history
    
    # Try readline first if available
    if READLINE_AVAILABLE:
        try:
            # Setup readline if not done
            if not hasattr(readline, '_setup_done'):
                readline.set_history_length(100)
                
                # Load history from file
                histfile = os.path.expanduser("~/.joplin_history")
                try:
                    if os.path.exists(histfile):
                        readline.read_history_file(histfile)
                except:
                    pass
                    
                readline._setup_done = True
            
            # Use readline input
            line = input(prompt)
            
            # Add to history if not empty
            if line.strip():
                command_history.append(line)
                try:
                    readline.add_history(line)
                    # Save history
                    histfile = os.path.expanduser("~/.joplin_history")
                    readline.write_history_file(histfile)
                except:
                    pass
            return line
            
        except Exception:
            pass
    
    # Fallback to custom terminal handling
    if setup_terminal():
        return get_terminal_raw_input(prompt)
    else:
        # Simple fallback
        print(prompt, end="", flush=True)
        try:
            line = sys.stdin.readline().rstrip('\n\r')
            if line.strip():
                command_history.append(line)
            return line
        except (EOFError, KeyboardInterrupt):
            print()
            return ""

def safe_input(prompt: str = "") -> str:
    """Python 3 compatible input with command history support."""
    try:
        return enhanced_input(prompt)
    except EOFError:
        print()
        return ""

# ----------------------------------------------------------------------
# Database wrapper
# ----------------------------------------------------------------------
class JoplinDB:
    def __init__(self, db_path: str):
        if not Path(db_path).exists():
            raise FileNotFoundError(f"Database not found: {db_path}")
        self.conn = sqlite3.connect(db_path)
        self.conn.row_factory = sqlite3.Row
        self.cur = self.conn.cursor()

    # ------------------------------------------------------------------
    # Low-level helpers
    # ------------------------------------------------------------------
    def _exec(self, sql: str, params=()):
        self.cur.execute(sql, params)
        return self.cur.fetchall()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def get_folders(self, parent_id: Optional[str] = None) -> List[sqlite3.Row]:
        if parent_id is None:
            # Handle root folders - Joplin uses empty string as root marker
            sql = "SELECT * FROM folders WHERE parent_id = '' ORDER BY title"
            return self._exec(sql)
        else:
            sql = "SELECT * FROM folders WHERE parent_id = ? ORDER BY title"
            return self._exec(sql, (parent_id,))

    def get_note(self, note_id: str) -> Optional[sqlite3.Row]:
        rows = self._exec("SELECT * FROM notes WHERE id = ?", (note_id,))
        return rows[0] if rows else None

    def get_notes_in_folder(self, folder_id: str) -> List[sqlite3.Row]:
        return self._exec(
            "SELECT * FROM notes WHERE parent_id = ? ORDER BY title", (folder_id,)
        )

    def get_tags_for_note(self, note_id: str) -> List[str]:
        sql = """
            SELECT t.title
            FROM tags t
            JOIN note_tags nt ON t.id = nt.tag_id
            WHERE nt.note_id = ?
            ORDER BY t.title
        """
        return [row["title"] for row in self._exec(sql, (note_id,))]

    def get_resources_for_note(self, note_id: str) -> List[sqlite3.Row]:
        sql = """
            SELECT r.*
            FROM resources r
            JOIN note_resources nr ON r.id = nr.resource_id
            WHERE nr.note_id = ?
            ORDER BY r.title
        """
        return self._exec(sql, (note_id,))

    def get_resource_data(self, resource_id: str) -> Optional[bytes]:
        """Get the binary data for a resource."""
        rows = self._exec("SELECT data FROM resources WHERE id = ?", (resource_id,))
        return rows[0]["data"] if rows else None

    def search_notes(self, term: str) -> List[sqlite3.Row]:
        """Simple full-text search using the built-in FTS table."""
        sql = """
            SELECT n.*, f.parent_id
            FROM notes_fts ft
            JOIN notes n ON ft.rowid = n.rowid
            LEFT JOIN folders f ON n.parent_id = f.id
            WHERE notes_fts MATCH ?
            LIMIT 50
        """
        return self._exec(sql, (term,))

    def close(self):
        self.conn.close()

# ----------------------------------------------------------------------
# Export utilities
# ----------------------------------------------------------------------
def extract_attachments(db: JoplinDB, resources: List[sqlite3.Row], note_title: str, out_dir: Path) -> Dict[str, str]:
    """
    Extract and save file attachments from a note.
    
    Args:
        db: Database instance
        resources: List of resource rows for the note
        note_title: Title of the note (used for creating directory name)
        out_dir: Output directory for the note
        
    Returns:
        Dict mapping resource titles to their saved file paths
    """
    saved_files = {}
    
    if not resources:
        return saved_files
    
    # Create attachments directory
    safe_title = "".join(c if c not in r'\/:*?"<>|' else "_" for c in note_title)
    attachments_dir = out_dir / "attachments" / safe_title
    attachments_dir.mkdir(parents=True, exist_ok=True)
    
    print(f"    Extracting {len(resources)} attachments...")
    
    for resource in resources:
        try:
            resource_data = db.get_resource_data(resource["id"])
            if not resource_data:
                print(f"    ⚠️  No data found for resource: {resource['title']}")
                continue
                
            # Use original filename if available, otherwise use title or ID
            filename = resource.get("filename") or resource.get("title", f"resource_{resource['id'][:8]}")
            
            # Ensure filename is safe for filesystem
            safe_filename = "".join(c if c not in r'\/:*?"<>|' else "_" for c in filename)
            
            # If no extension, try to determine from mime type
            if "." not in safe_filename:
                mime = resource.get("mime", "")
                if mime.startswith("image/"):
                    ext = mime.split("/")[-1]
                    if ext:
                        safe_filename = f"{safe_filename}.{ext}"
                elif mime == "application/pdf":
                    safe_filename = f"{safe_filename}.pdf"
                elif mime.startswith("text/"):
                    ext = mime.split("/")[-1] or "txt"
                    safe_filename = f"{safe_filename}.{ext}"
            
            file_path = attachments_dir / safe_filename
            
            # Write the data
            with open(file_path, "wb") as f:
                f.write(resource_data)
            
            saved_files[resource["title"]] = str(file_path.relative_to(out_dir))
            print(f"    ✓ {safe_filename} ({resource.get('mime', 'unknown')})")
            
        except Exception as e:
            print(f"    ❌ Failed to extract {resource['title']}: {e}")
    
    return saved_files

def export_note_to_format(note: sqlite3.Row, tags: List[str], resources: List[sqlite3.Row], out_dir: Path, format_type: str = "md", include_metadata: bool = False, db: Optional[JoplinDB] = None):
    """
    Export a note to either markdown (.md) or text (.txt) format.
    
    Args:
        note: The note row from database
        tags: List of tags for the note
        resources: List of resources/attachments for the note
        out_dir: Output directory
        format_type: "md" for markdown, "txt" for plain text
        include_metadata: Whether to include metadata (timestamps, tags, attachments)
        db: Database instance (required for extracting attachments)
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    safe_title = "".join(c if c not in r'\/:*?"<>|' else "_" for c in note["title"])
    extension = "md" if format_type.lower() == "md" else "txt"
    file_path = out_dir / f"{safe_title}.{extension}"

    # Extract attachments if database is provided and metadata is included
    saved_files = {}
    if include_metadata and db and resources:
        saved_files = extract_attachments(db, resources, note["title"], out_dir)

    with open(file_path, "w", encoding="utf-8") as f:
        if format_type.lower() == "md":
            # Markdown format
            f.write(f"# {note['title']}\n\n")
            
            if include_metadata:
                f.write(f"*Created:* {ts_to_str(note['created_time'])}\n")
                f.write(f"*Updated:* {ts_to_str(note['updated_time'])}\n")
                if tags:
                    f.write(f"*Tags:* {', '.join(tags)}\n")
                f.write("\n---\n\n")
            
            f.write(note["body"] or "")
            f.write("\n")

            if include_metadata and resources:
                f.write("\n## Attachments\n")
                for res in resources:
                    # Use saved file path if available, otherwise use original filename
                    if res["title"] in saved_files:
                        f.write(f"- [{res['title']}]({saved_files[res['title']]})\n")
                    else:
                        f.write(f"- [{res['title']}]({res['filename'] or 'unknown'})\n")
        else:
            # Plain text format
            f.write(f"{note['title']}\n")
            f.write("=" * len(note['title']) + "\n\n")
            
            if include_metadata:
                f.write(f"Created: {ts_to_str(note['created_time'])}\n")
                f.write(f"Updated: {ts_to_str(note['updated_time'])}\n")
                if tags:
                    f.write(f"Tags: {', '.join(tags)}\n")
                f.write("\n" + "-" * 40 + "\n\n")
            
            f.write(note["body"] or "")
            f.write("\n")

            if include_metadata and resources:
                f.write("\n\nAttachments:\n")
                for res in resources:
                    if res["title"] in saved_files:
                        f.write(f"- {res['title']} ({saved_files[res['title']]})\n")
                    else:
                        f.write(f"- {res['title']} ({res['filename'] or 'unknown'})\n")
                    
    print(f" → {file_path}")

def export_notebook_recursive(db: JoplinDB, folder: sqlite3.Row, out_dir: Path, format_type: str = "md", include_metadata: bool = False):
    """
    Export a notebook recursively to the specified format.
    
    Args:
        db: Database instance
        folder: Current folder to export
        out_dir: Output directory
        format_type: "md" for markdown, "txt" for plain text
        include_metadata: Whether to include metadata in exported files
    """
    folder_dir = out_dir / folder["title"]
    folder_dir.mkdir(parents=True, exist_ok=True)

    # Export notes in this folder
    notes = db.get_notes_in_folder(folder["id"])
    for note in notes:
        tags = db.get_tags_for_note(note["id"])
        resources = db.get_resources_for_note(note["id"])
        export_note_to_format(note, tags, resources, folder_dir, format_type, include_metadata, db)

    # Recurse into sub-folders
    subfolders = db.get_folders(folder["id"])
    for sub in subfolders:
        export_notebook_recursive(db, sub, folder_dir, format_type, include_metadata)

# ----------------------------------------------------------------------
# Interactive browser
# ----------------------------------------------------------------------
def interactive_browser(db: JoplinDB, export_root: Optional[Path] = None, export_format: str = "md", include_metadata: bool = False):
    print("\n=== Joplin Console Browser ===")
    print("Browse, search, and export your Joplin notes.\n")
    print("Commands:")
    print("  l                 - List folders/notes at current location")
    print("  cd <folder-id>    - Navigate into folder")
    print("  cd ..             - Go back to parent folder")
    print("  cd /              - Go back to root level")
    print("  s <search-term>   - Search all notes (full-text search)")
    print("  n <note-id>       - View full note content")
    print("  n <notebook-id>/<note-id> - View note with notebook context")
    print("  cat <note-id>     - View note content (no metadata)")
    print("  cat <notebook-id>/<note-id> - View note content with notebook context")
    print("  vim <note-id>     - Open note in Vim editor")
    print(f"  e [note-id]       - Export to {export_format.upper()} (current folder or single note)")
    print("  q                 - Quit")
    print()
    print("Quick start:")
    print("  1. 'l' - see your folders")
    print("  2. 'cd <id>' - enter a folder")
    print("  3. 'n <id>' - read a note")
    print("  4. 'cd /' - return to root level")
    print()
    print("💡 Tip: Use first 8 chars of any ID!")
    print()

    current_folder_id: Optional[str] = None
    history = []  # for '..' navigation

    while True:
        # ------------------------------------------------------------------
        # Build prompt
        # ------------------------------------------------------------------
        path_parts = []
        fid = current_folder_id
        while fid:
            folder = next((f for f in db.get_folders() if f["id"] == fid), None)
            if not folder:
                break
            path_parts.append(folder["title"])
            fid = folder["parent_id"]
        path_parts.reverse()
        prompt = "/".join(path_parts) if path_parts else "(root)"
        cmd = safe_input(f"{prompt} > ").strip()

        if not cmd:
            continue

        parts = cmd.split(maxsplit=1)
        action = parts[0].lower()
        arg = parts[1] if len(parts) > 1 else ""

        # ------------------------------------------------------------------
        # Quit
        # ------------------------------------------------------------------
        if action in {"q", "quit", "exit"}:
            print("Bye!")
            break

        # ------------------------------------------------------------------
        # List
        # ------------------------------------------------------------------
        if action in {"l", "list"}:
            folders = db.get_folders(current_folder_id)
            notes = db.get_notes_in_folder(current_folder_id) if current_folder_id else []

            if current_folder_id:
                current_folder_name = next((f["title"] for f in db.get_folders() if f["id"] == current_folder_id), "Unknown Folder")
                print(f"\n=== {current_folder_name} ===")
            else:
                print("\n=== Your Joplin Folders ===")

            if folders:
                print("\nFolders:")
                for f in folders:
                    note_count = len(db.get_notes_in_folder(f["id"]))
                    print(f"  [{f['id'][:8]}] {f['title']} ({note_count} notes)")
            else:
                print("(No subfolders)")

            if notes:
                print(f"\nNotes ({len(notes)}):")
                for n in notes:
                    tag_str = ", ".join(db.get_tags_for_note(n["id"])) or "—"
                    print(f"  [{n['id'][:8]}] {n['title']} | tags: {tag_str}")
            else:
                print("(No notes)")

            continue

        # ------------------------------------------------------------------
        # Change directory
        # ------------------------------------------------------------------
        if action in {"cd", "go", "enter"}:
            if arg == "..":
                if history:
                    current_folder_id = history.pop()
                    print("Going back to parent folder")
                else:
                    current_folder_id = None
                    print("Going back to root level")
            elif arg == "/":
                # Go to root folder
                if current_folder_id:
                    history.append(current_folder_id)
                current_folder_id = None
                print("Going to root level")
            else:
                if not arg:
                    print("Usage: cd <folder-id>, cd .., or cd /")
                    continue
                    
                # Try to find folder by id prefix (first 8 chars are enough)
                candidates = [f for f in db.get_folders(current_folder_id) if f["id"].startswith(arg)]
                if len(candidates) == 1:
                    if current_folder_id:
                        history.append(current_folder_id)
                    current_folder_id = candidates[0]["id"]
                    print(f"Entered: {candidates[0]['title']}")
                elif len(candidates) > 1:
                    print("Ambiguous ID - matches:")
                    for c in candidates:
                        print(f"  [{c['id'][:8]}] {c['title']}")
                else:
                    print("Folder not found.")
            continue

        # ------------------------------------------------------------------
        # Helper function to find note by ID (with folder context)
        # ------------------------------------------------------------------
        def find_note_in_context(note_id: str) -> Optional[sqlite3.Row]:
            # Handle path format: notebook-id/note-id
            if '/' in note_id:
                notebook_id, note_id = note_id.split('/', 1)
                
                # First try to find the notebook
                notebook = db.get_note(notebook_id)  # This will return None since notebook_id is a folder ID
                # Get folder directly
                folders = db.get_folders()
                notebook_folder = next((f for f in folders if f["id"].startswith(notebook_id)), None)
                
                if not notebook_folder:
                    print(f"Notebook {notebook_id[:8]} not found.")
                    return None
                
                # Now look for the note in that specific notebook
                notes_in_notebook = db.get_notes_in_folder(notebook_folder["id"])
                matching_notes = [n for n in notes_in_notebook if n["id"].startswith(note_id)]
                
                if len(matching_notes) == 1:
                    return matching_notes[0]
                elif len(matching_notes) > 1:
                    print("Ambiguous note ID - multiple notes match:")
                    for n in matching_notes:
                        print(f"  [{n['id'][:8]}] {n['title']}")
                    return None
                else:
                    print(f"Note {note_id[:8]} not found in notebook {notebook_folder['title']}.")
                    return None
            
            # Standard behavior (no path format)
            # First try to get note globally (full ID)
            note = db.get_note(note_id)
            
            # If not found and we're in a folder, try partial match within current folder
            if not note and current_folder_id:
                notes_in_folder = db.get_notes_in_folder(current_folder_id)
                matching_notes = [n for n in notes_in_folder if n["id"].startswith(note_id)]
                if len(matching_notes) == 1:
                    note = matching_notes[0]
                elif len(matching_notes) > 1:
                    print("Ambiguous ID - multiple notes match:")
                    for n in matching_notes:
                        print(f"  [{n['id'][:8]}] {n['title']}")
                    return None
            
            return note

        # ------------------------------------------------------------------
        # Show note details (full view)
        # ------------------------------------------------------------------
        if action in {"n", "note", "view", "read", "show"}:
            note_id = arg
            if not note_id:
                print("Usage: n <note-id>")
                continue
                
            note = find_note_in_context(note_id)
            if not note:
                continue

            print(f"\n=== {note['title']} ===")
            print(f"ID: {note['id']}")
            print(f"Created: {ts_to_str(note['created_time'])}")
            print(f"Updated: {ts_to_str(note['updated_time'])}")
            
            tags = db.get_tags_for_note(note['id'])
            if tags:
                print(f"Tags: {', '.join(tags)}")
            else:
                print("Tags: (no tags)")
                
            resources = db.get_resources_for_note(note['id'])
            if resources:
                print(f"\nAttachments ({len(resources)}):")
                for r in resources:
                    print(f"  • {r['title']} ({r['mime']})")
                    if r['filename']:
                        print(f"    File: {r['filename']}")
            else:
                print("\nAttachments: (none)")
                
            print(f"\n--- Content ---")
            content = note["body"]
            if content:
                print_wrapped(content, indent=0)
            else:
                print("(No content)")
            print()
            continue

        # ------------------------------------------------------------------
        # Show note content only (cat style)
        # ------------------------------------------------------------------
        if action in {"cat", "content", "body"}:
            note_id = arg
            if not note_id:
                print("Usage: cat <note-id>")
                continue
                
            note = find_note_in_context(note_id)
            if not note:
                continue

            print(f"# {note['title']}\n")
            content = note["body"]
            if content:
                print(content)
            else:
                print("(This note has no content)")
            print()
            continue

        # ------------------------------------------------------------------
        # Open note in vim editor
        # ------------------------------------------------------------------
        if action in {"vim", "edit", "vi"}:
            note_id = arg
            if not note_id:
                print("Usage: vim <note-id>")
                continue
                
            note = find_note_in_context(note_id)
            if not note:
                continue

            import tempfile
            import subprocess
            
            # Create temporary file with note content
            with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False) as temp_file:
                temp_file.write(f"# {note['title']}\n\n")
                if note["body"]:
                    temp_file.write(note["body"])
                temp_file_path = temp_file.name
            
            try:
                # Open in vim
                print(f"Opening '{note['title']}' in Vim...")
                
                if WRITE_MODE:
                    print("📝 EDIT MODE: Changes will be saved to database!")
                else:
                    print("🔒 READ-ONLY MODE: Changes will NOT be saved to database")
                
                subprocess.call(['vim', '+', '+startinsert', temp_file_path])
                
                # Read back the content
                with open(temp_file_path, 'r') as f:
                    new_content = f.read()
                
                # Remove the title line we added
                if new_content.startswith(f"# {note['title']}\n\n"):
                    new_content = new_content[len(f"# {note['title']}\n\n"):]
                elif new_content.startswith(f"# {note['title']}\n"):
                    new_content = new_content[len(f"# {note['title']}\n"):]
                
                # Check if content changed
                if new_content != note["body"]:
                    if WRITE_MODE:
                        # Save changes to database
                        try:
                            # Update the note in database
                            updated_time = int(datetime.now().timestamp() * 1000)
                            db.cur.execute(
                                "UPDATE notes SET body = ?, updated_time = ?, user_updated_time = ? WHERE id = ?",
                                (new_content, updated_time, updated_time, note["id"])
                            )
                            db.conn.commit()
                            print(f"✅ Note '{note['title']}' has been updated in database!")
                            print(f"   Updated time: {ts_to_str(updated_time)}")
                        except Exception as e:
                            print(f"❌ Failed to save changes to database: {e}")
                            print("💡 Use 'e <note-id>' to export the modified version")
                    else:
                        print(f"Note '{note['title']}' has been modified.")
                        print("🔒 READ-ONLY: Changes are not saved to database.")
                        print("💡 Restart with '--write' flag to enable saving changes")
                        print("📤 Or use 'e <note-id>' to export the modified version")
                else:
                    print("No changes made to the note.")
                    
            except FileNotFoundError:
                print("Vim not found. Please ensure Vim is installed.")
            finally:
                # Clean up temp file
                import os
                os.unlink(temp_file_path)
            
            continue

        # ------------------------------------------------------------------
        # Search
        # ------------------------------------------------------------------
        if action in {"s", "search", "find"}:
            if not arg:
                print("Usage: s <search-term>")
                continue
            
            print(f"Searching for: '{arg}'...")
            results = db.search_notes(arg)
            
            if not results:
                print("No matches found.")
                continue
                
            print(f"\nSearch results for '{arg}' ({len(results)} hits):")
            for result in results:
                # Access results as sqlite3.Row objects
                note_id = result['id']
                note_title = result['title']
                parent_id = result.get('parent_id', '') if 'parent_id' in result.keys() else ''
                
                # Show notebook context if available
                notebook_path = ""
                if parent_id and parent_id != "":
                    # Get the notebook ID for context
                    notebook_path = f"{parent_id[:8]}/"
                print(f"  [{notebook_path}{note_id[:8]}] {note_title}")
            print()
            print("💡 Tip: Use the full path format (notebook-id/note-id) with n, cat, or vim commands!")
            print()
            continue

        # ------------------------------------------------------------------
        # Export
        # ------------------------------------------------------------------
        if action == "e":
            export_dir = export_root or Path("./joplin_export")
            if not arg:
                # Export *current* notebook (or everything if at root)
                if current_folder_id is None:
                    print("Exporting **all** notebooks…")
                    for top in db.get_folders(None):
                        export_notebook_recursive(db, top, export_dir, export_format, include_metadata)
                else:
                    folder = next((f for f in db.get_folders() if f["id"] == current_folder_id), None)
                    if folder:
                        print(f"Exporting notebook “{folder['title']}”…")
                        export_notebook_recursive(db, folder, export_dir, export_format, include_metadata)
                    else:
                        print("Current folder not found.")
                print(f"\nExport finished → {export_dir.resolve()}")
            else:
                # Export single note
                note = db.get_note(arg)
                if not note:
                    print("Note not found.")
                    continue
                tags = db.get_tags_for_note(note["id"])
                resources = db.get_resources_for_note(note["id"])
                export_note_to_format(note, tags, resources, export_dir, export_format, include_metadata, db)
                safe_title = "".join(c if c not in r'\/:*?"<>|' else "_" for c in note["title"])
                extension = "md" if export_format.lower() == "md" else "txt"
                print(f"Exported → {export_dir / f'{safe_title}.{extension}'}")
            continue

        # ------------------------------------------------------------------
        # Help command
        # ------------------------------------------------------------------
        if action in {"h", "help", "?"}:
            print("\n=== Joplin Console Browser ===")
            print("Browse, search, and export your Joplin notes.\n")
            print("Commands:")
            print("  l                 - List folders/notes at current location")
            print("  cd <folder-id>    - Navigate into folder")
            print("  cd ..             - Go back to parent folder")
            print("  cd /              - Go back to root level")
            print("  s <search-term>   - Search all notes (full-text search)")
            print("  n <note-id>       - View full note content with metadata")
            print("  cat <note-id>     - View note content (no metadata)")
            print("  vim <note-id>     - Open note in Vim editor")
            print("  e [note-id]       - Export to Markdown (current folder or single note)")
            print("  h, help, ?        - Show this help message")
            print("  q                 - Quit")
            print()
            print("Quick start:")
            print("  1. 'l' - see your folders")
            print("  2. 'cd <id>' - enter a folder")
            print("  3. 'n <id>' - read a note")
            print("  4. 'cd /' - return to root level")
            print()
            print("💡 Tip: Use first 8 chars of any ID!")
            print("💡 Use UP/DOWN arrows to navigate command history")
            print()
            continue

        # ------------------------------------------------------------------
        # Unknown command
        # ------------------------------------------------------------------
        print("Unknown command. Available: l, cd <id>, n <id>, s <term>, cat <id>, vim <id>, e [id], h, q")

# ----------------------------------------------------------------------
# Main entry point
# ----------------------------------------------------------------------
# Global variable to track write mode
WRITE_MODE = False

def main():
    parser = argparse.ArgumentParser(
        description="Interactive console browser for Joplin's database.sqlite"
    )
    parser.add_argument(
        "db",
        nargs="?",
        help="Path to database.sqlite (default: auto-detect for desktop app)",
    )
    parser.add_argument(
        "--export-dir",
        type=Path,
        help="Directory where exported files will be written",
    )
    parser.add_argument(
        "--export-format",
        choices=["md", "txt"],
        default="md",
        help="Export format: 'md' for Markdown or 'txt' for plain text (default: md)",
    )
    parser.add_argument(
        "--export-all",
        action="store_true",
        help="Export all notebooks to the specified directory and exit (no interactive mode)",
    )
    parser.add_argument(
        "--include-metadata",
        action="store_true",
        help="Include metadata (timestamps, tags, attachments) in exported files (default: disabled)",
    )
    parser.add_argument(
        "--write",
        action="store_true",
        help="Enable write mode - allows vim command to save changes back to database (default: read-only)",
    )
    
    args = parser.parse_args()
    
    global WRITE_MODE
    WRITE_MODE = args.write
    
    if WRITE_MODE:
        print("🔒 WRITE MODE ENABLED - vim edits will be saved to database")
        print("⚠️  Changes will be written to database.sqlite")
        print("   Use with caution - this modifies your Joplin data")
        print()

    # ------------------------------------------------------------------
    # Auto-detect default location if not supplied
    # ------------------------------------------------------------------
    db_path = args.db
    if not db_path:
        candidates = [
            # Linux
            Path.home() / ".config/joplin-desktop/database.sqlite",
            # macOS
            Path.home() / ".config/joplin-desktop/database.sqlite",
            # Windows
            Path(os.getenv("APPDATA", "")) / "Joplin/database.sqlite",
        ]
        for p in candidates:
            if p.exists():
                db_path = str(p)
                break
        if not db_path:
            print("Could not auto-detect database.sqlite. Please provide the path explicitly.")
            sys.exit(1)

    print(f"Opening database: {db_path}")
    try:
        db = JoplinDB(db_path)
    except Exception as e:
        print(f"Failed to open database: {e}")
        sys.exit(1)

    try:
        # Handle direct export mode
        if args.export_all:
            export_dir = args.export_dir or Path("./joplin_export")
            print(f"Exporting all notebooks to {export_dir.resolve()} in {args.export_format.upper()} format...")
            print(f"Metadata inclusion: {'enabled' if args.include_metadata else 'disabled'}")
            
            top_folders = db.get_folders(None)
            if not top_folders:
                print("No notebooks found to export.")
            else:
                for folder in top_folders:
                    print(f"Exporting notebook: {folder['title']}")
                    export_notebook_recursive(db, folder, export_dir, args.export_format, args.include_metadata)
                print(f"\nExport completed successfully!")
                print(f"Files saved to: {export_dir.resolve()}")
            return
            
        # Interactive mode (existing functionality)
        interactive_browser(db, export_root=args.export_dir, export_format=args.export_format, include_metadata=args.include_metadata)
    finally:
        db.close()

if __name__ == "__main__":
    main()
