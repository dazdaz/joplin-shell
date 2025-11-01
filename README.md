# Joplin Console Browser

An interactive command-line browser for Joplin database files, providing a powerful terminal-based interface to browse, search, view, edit, and export your Joplin notes.

## Features

- 🗂️ **Browse Navigation**: Navigate through your Joplin folders and notes with intuitive commands
- 🔍 **Full-text Search**: Search across all notes using Joplin's built-in full-text search
- 📖 **Multiple View Modes**: View notes with metadata or content-only display
- ✏️ **Edit Support**: Open notes in Vim editor with optional database saving
- 📤 **Export to Multiple Formats**: Export individual notes or entire notebooks as Markdown (.md) or plain text (.txt) files
- 🏗️ **Organized Folder Structure**: Automatic creation of folders for each subnotebook during export
- ⌨️ **Arrow Key Support**: Navigate command history with UP/DOWN arrows
- 💾 **Read/Write Modes**: Choose between read-only or edit-enabled modes

## Installation

### Prerequisites

- Python 3.6 or higher
- Joplin desktop application (for database location)
- Vim (optional, for editing notes)

### Setup

1. Download or clone the `joplin-console.py` script
2. Make it executable:
   ```bash
   chmod +x joplin-console.py
   ```

## Usage

### Basic Usage

Launch the browser (it will auto-detect your Joplin database):

```bash
python3 joplin-console.py
```

Or specify a database path explicitly:

```bash
python3 joplin-console.py /path/to/your/database.sqlite
```

### Command-Line Options

- `--export-dir <path>`: Specify directory for exported files
- `--export-format <format>`: Choose export format ('md' for Markdown or 'txt' for plain text, default: md)
- `--export-all`: Export all notebooks to the specified directory and exit (no interactive mode)
- `--include-metadata`: Include metadata (timestamps, tags, attachments) in exported files (default: disabled)
- `--write`: Enable write mode (allows saving vim edits back to database)

Example with options:

```bash
# Direct export all notebooks as Markdown files with metadata (no interactive mode)
python3 joplin-console.py --export-dir ./my_markdown_exports --export-format md --export-all --include-metadata

# Direct export all notebooks as plain text files without metadata (default)
python3 joplin-console.py --export-dir ./my_text_exports --export-format txt --export-all

# Export with metadata disabled (default behavior)
python3 joplin-console.py --export-dir ./my_exports --export-format md --include-metadata

# Interactive mode with metadata disabled (default)
python3 joplin-console.py --export-format txt --export-dir ./my_exports

# Enable write mode for interactive editing
python3 joplin-console.py --export-dir ./my_exports --write
```

### Interactive Commands

Once in the interactive browser, use these commands:

#### Navigation
- `l` - List current folder contents (folders and notes)
- `cd <folder-id>` - Navigate into a folder (use first 8 chars of ID)
- `cd ..` - Go back to parent folder
- `cd` (no args) - Go back to root level

#### Viewing Notes
- `n <note-id>` - View note with full metadata (timestamps, tags, attachments)
- `cat <note-id>` - View note content only (no metadata)
- `s <search-term>` - Search all notes (full-text search)

#### Editing
- `vim <note-id>` - Open note in Vim editor
  - Read-only mode: Changes are not saved to database
  - Write mode (`--write` flag): Changes are saved back to database

#### Exporting
- `e` - Export current folder (or all notes if at root level) in the chosen format
- `e <note-id>` - Export single note as file in the chosen format

#### Help
- `h`, `help`, or `?` - Show help message

#### Exit
- `q`, `quit`, or `exit` - Exit the browser

### Quick Start Example

1. **List your folders:**
   ```
   (root) > l
   ```

2. **Navigate into a folder:**
   ```
   (root) > cd a1b2c3d4
   ```

3. **View a note:**
   ```
   FolderName > n e5f6g7h8
   ```

4. **Search for content:**
   ```
   FolderName > s meeting notes
   ```

5. **Export notes:**
   ```
   FolderName > e
   ```

## Tips & Tricks

- **ID Shortening**: Use only the first 8 characters of any ID for convenience
- **Command History**: Use UP/DOWN arrow keys to navigate through previous commands
- **Fuzzy Navigation**: `cd` commands work with partial ID matches
- **Automatic Database Detection**: The script automatically finds your Joplin database on:
  - Linux: `~/.config/joplin-desktop/database.sqlite`
  - macOS: `~/Library/Application Support/Joplin/database.sqlite`
  - Windows: `%APPDATA%\Joplin\database.sqlite`

## Export Format

Exported notes are saved in your chosen format (Markdown or plain text) with content-only output by default. Use `--include-metadata` to add metadata.

### Markdown Format (.md)

**Without Metadata (default):**
- Original note title as header
- Note content only

**With Metadata (`--include-metadata`):**
- Original note title as header
- Creation and update timestamps in italics
- Associated tags
- Note content
- List of attachments as markdown links
- Horizontal separators between metadata and content

### Plain Text Format (.txt)

**Without Metadata (default):**
- Original note title as header with underline
- Note content only

**With Metadata (`--include-metadata`):**
- Original note title as header with underline
- Creation and update timestamps
- Associated tags
- Note content
- List of attachments as simple text entries
- Visual separators between metadata and content

### Directory Structure
The export preserves your complete notebook hierarchy:
- Each main notebook becomes a folder
- Subnotebooks create nested subdirectories
- Notes are exported as individual files within their respective folders
- Filenames are sanitized to be filesystem-safe (replacing invalid characters with underscores)

## Direct Export (Batch Mode)

For quick, non-interactive export of all your notebooks, use the `--export-all` flag:

```bash
# Export everything as Markdown without metadata (default, content-only)
python3 joplin-console.py --export-all --export-dir ./markdown_export

# Export everything as Markdown with full metadata
python3 joplin-console.py --export-all --export-format md --export-dir ./markdown_with_metadata --include-metadata

# Export everything as plain text with metadata
python3 joplin-console.py --export-all --export-format txt --export-dir ./text_with_metadata --include-metadata
```

This will:
- Export **all** notebooks from your Joplin database
- Create organized folder structure matching your notebook hierarchy
- Use the specified format (Markdown or plain text)
- Include or exclude metadata based on the `--include-metadata` flag
- Exit automatically after completion (no interactive mode)
- Display progress and metadata inclusion status as each notebook is processed

Perfect for:
- Creating backups of your entire Joplin database
- Converting large amounts of notes to other formats
- Automated backup scripts
- Migration to other note-taking systems
- Exporting clean content-only files for external use
- Exporting with full metadata for archival purposes

## Write Mode

By default, the browser runs in read-only mode for safety. Use the `--write` flag to enable write mode:

```bash
python3 joplin-console.py --write
```

In write mode:
- `vim` command saves changes directly back to your Joplin database
- You'll see a confirmation message when notes are updated
- ⚠️ **Warning**: Changes are permanent and affect your Joplin data

## Error Handling

The browser includes robust error handling:
- Invalid IDs show helpful error messages
- Search with no results displays an appropriate message
- Database connection issues are reported clearly
- Fallback input methods for systems without readline support

## Troubleshooting

### Database Not Found
If auto-detection fails, provide the database path explicitly:
```bash
python3 joplin-console.py /full/path/to/database.sqlite
```

### Vim Not Available
If Vim is not installed, the `vim` command will show an error. Install Vim or use other viewing commands instead.

### Permission Issues
Ensure you have read access to the database file. For write mode, you'll need write access to the database file.

## Technical Details

- Built with Python's SQLite3 module
- Uses Joplin's database schema directly
- Supports Joplin's full-text search (FTS) capabilities
- Cross-platform compatible (Linux, macOS, Windows)
- Handles Joplin's folder hierarchy and note relationships

## License

This tool is provided as-is for interacting with Joplin database files. Please ensure you have appropriate permissions to access and modify your Joplin data.

## Contributing

Feel free to submit issues and enhancement requests to improve this console browser for Joplin users.