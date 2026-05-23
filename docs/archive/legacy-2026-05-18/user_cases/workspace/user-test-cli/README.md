# notesctl

A lightweight CLI tool to manage local Markdown notes.

## Installation

```bash
pip install -e .
```

This installs the `notesctl` command into your environment.

## Usage

```
notesctl add <slug> [content]        # create a new note
notesctl list                        # list all notes
notesctl list --tag <tag>            # list notes filtered by tag
notesctl show <filename>             # display a note (formatted)
notesctl search <keyword>            # full-text search across all notes
notesctl delete <filename>           # delete a note
```

## Examples

```bash
# Create a note with inline content
notesctl add meeting-notes "Discussed Q2 roadmap and timeline."

# Create a note with tags
notesctl add todo-list "Buy groceries #urgent and call dentist #health"

# Create a note by piping content
echo "Things to do tomorrow." | notesctl add todo-list

# List all notes (most recent first)
notesctl list

# List notes with a specific tag
notesctl list --tag urgent

# Show a specific note (with formatted output)
notesctl show 2026-05-13-meeting-notes.md

# Full-text search across notes
notesctl search roadmap

# Delete a note
notesctl delete 2026-05-13-todo-list.md

# Use a custom notes directory
notesctl add my-slug --dir /tmp/my-notes
```

## Tag support

Tags are extracted from note content in two ways:

- **Inline hashtags** — `#tag` anywhere in the body (e.g. `#todo`, `#work`)
- **Frontmatter** — a `tags:` line at the top of the note (YAML-like, comma-separated)

```
tags: todo, work, important

# My Note

Don't forget the #meeting at 3pm.
```

Filter with `notesctl list --tag <tagname>`.

## How it works

- Notes are stored as Markdown files under `./notes/` (or a custom directory via `--dir`).
- File names follow the pattern `YYYY-MM-DD-<slug>.md`.
- The slug is sanitised: lowercased, spaces replaced with hyphens, special characters stripped.

## Development

```bash
pip install -e ".[dev]"
pytest
```
