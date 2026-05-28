"""Command implementations for notesctl."""

import os
import re
import sys
from datetime import date


def _default_dir(cli_dir: str | None) -> str:
    """Return the effective notes directory."""
    return cli_dir or os.path.join(os.getcwd(), "notes")


def _ensure_dir(path: str) -> None:
    os.makedirs(path, exist_ok=True)


def _make_filename(slug: str) -> str:
    """Build a filename like 2026-05-13-my-slug.md."""
    today = date.today().isoformat()  # YYYY-MM-DD
    # sanitise slug: lowercase, replace spaces with hyphens, remove non-safe chars
    clean = slug.strip().lower()
    safe = "".join(c if c.isalnum() or c in "-_" else "-" for c in clean)
    # collapse consecutive hyphens
    safe = re.sub(r"-{2,}", "-", safe)
    safe = safe.strip("-").strip("_")
    if not safe:
        safe = "note"
    return f"{today}-{safe}.md"


# ---------------------------------------------------------------------------
# Terminal helpers (no external dependencies)
# ---------------------------------------------------------------------------

def _bold(text: str) -> str:
    """Wrap text with ANSI bold escape codes (when stdout is a tty)."""
    if sys.stdout.isatty():
        return f"\033[1m{text}\033[0m"
    return text


def _dim(text: str) -> str:
    """Wrap text with ANSI dim escape codes (when stdout is a tty)."""
    if sys.stdout.isatty():
        return f"\033[2m{text}\033[0m"
    return text


def _cyan(text: str) -> str:
    """Wrap text with ANSI cyan foreground (when stdout is a tty)."""
    if sys.stdout.isatty():
        return f"\033[36m{text}\033[0m"
    return text


def _yellow(text: str) -> str:
    """Wrap text with ANSI yellow foreground (when stdout is a tty)."""
    if sys.stdout.isatty():
        return f"\033[33m{text}\033[0m"
    return text


def _red(text: str) -> str:
    """Wrap text with ANSI red foreground (when stdout is a tty)."""
    if sys.stdout.isatty():
        return f"\033[31m{text}\033[0m"
    return text


def _green(text: str) -> str:
    """Wrap text with ANSI green foreground (when stdout is a tty)."""
    if sys.stdout.isatty():
        return f"\033[32m{text}\033[0m"
    return text


# ---------------------------------------------------------------------------
# Subcommands
# ---------------------------------------------------------------------------

def cmd_add(slug: str, content_parts: list[str], notes_dir: str | None) -> None:
    """Create a new note."""
    notes_dir = _default_dir(notes_dir)
    _ensure_dir(notes_dir)

    filename = _make_filename(slug)
    filepath = os.path.join(notes_dir, filename)

    if os.path.exists(filepath):
        print(f"Error: note '{filename}' already exists.", file=sys.stderr)
        sys.exit(1)

    if content_parts:
        text = " ".join(content_parts)
    elif not sys.stdin.isatty():
        text = sys.stdin.read().strip()
    else:
        print("Error: no content provided. Pipe content or pass as argument.", file=sys.stderr)
        sys.exit(1)

    with open(filepath, "w", encoding="utf-8") as fh:
        fh.write(f"# {slug}\n\n{text}\n")

    print(f"Created: {filepath}")


def _parse_tags(content: str) -> set[str]:
    """Extract tags from note content (inline #tag or YAML-like tags: line)."""
    tags: set[str] = set()

    # Inline hashtags: #tag (word-boundary-aware, skip Markdown headings)
    for m in re.finditer(r"(?<!\w)#([a-zA-Z][a-zA-Z0-9._-]*)", content):
        tags.add(m.group(1).lower())

    # YAML-like frontmatter "tags:" line (comma-separated)
    for m in re.finditer(r"(?im)^tags:\s*\[?(.+?)\]?\s*$", content):
        for raw in re.split(r"[,;]", m.group(1)):
            t = raw.strip().strip("'\"").lstrip("#").lower()
            if t:
                tags.add(t)

    return tags


def cmd_list(notes_dir: str | None, tag: str | None = None) -> None:
    """List all notes in the notes directory, optionally filtered by tag."""
    notes_dir = _default_dir(notes_dir)

    if not os.path.isdir(notes_dir):
        print("No notes directory found. Create a note first with 'notesctl add'.", file=sys.stderr)
        sys.exit(0)

    entries = sorted(
        [e for e in os.listdir(notes_dir) if e.endswith(".md")],
        reverse=True,
    )

    if not entries:
        print("No notes found.")
        return

    # When filtering by tag, read each file and check for tag presence.
    filtered: list[str] = []
    for entry in entries:
        if tag is not None:
            filepath = os.path.join(notes_dir, entry)
            with open(filepath, encoding="utf-8") as fh:
                content = fh.read()
            tags = _parse_tags(content)
            if tag.lower() not in tags:
                continue
        filtered.append(entry)

    if not filtered:
        msg = f"No notes found with tag '{tag}'." if tag else "No notes found."
        print(msg)
        return

    # Show count
    if tag:
        tag_label = _yellow(f"#{tag}")
        print(f"Notes tagged {tag_label} ({len(filtered)}):")
    else:
        print(f"Notes ({len(filtered)}):")

    for entry in filtered:
        print(f"  {_bold(entry)}")


def cmd_show(filename: str, notes_dir: str | None) -> None:
    """Display a note's content with terminal-friendly formatting."""
    notes_dir = _default_dir(notes_dir)
    filepath = os.path.join(notes_dir, filename)

    if not os.path.isfile(filepath):
        print(f"Error: note '{filename}' not found.", file=sys.stderr)
        sys.exit(1)

    with open(filepath, encoding="utf-8") as fh:
        raw = fh.read()

    # ── Header ──
    print(_dim("─────┬" + "─" * (len(filename) + 2)))
    print(_dim("     │") + "  " + _bold(filename))
    print(_dim("─────┼" + "─" * (len(filename) + 2)))

    lines = raw.splitlines()
    for lineno, line in enumerate(lines, 1):
        prefix = _dim(f"{lineno:>4} │")

        # Style headings
        if line.startswith("# "):
            print(f"{prefix}  {_bold(_cyan(line))}")
        elif line.startswith("## "):
            print(f"{prefix}  {_bold(line)}")
        elif line.startswith("### "):
            print(f"{prefix}  {_cyan(line)}")
        # Style inline tags
        elif re.search(r"(?<!\w)#[a-zA-Z][a-zA-Z0-9._-]*", line):
            # Highlight hashtags in yellow
            highlighted = re.sub(
                r"(?<!\w)(#[a-zA-Z][a-zA-Z0-9._-]*)",
                lambda m: _yellow(m.group(1)),
                line,
            )
            print(f"{prefix}  {highlighted}")
        else:
            print(f"{prefix}  {line}")

    print(_dim("─────┴" + "─" * (len(filename) + 2)))


def cmd_search(keyword: str, notes_dir: str | None) -> None:
    """Full-text search across all notes."""
    notes_dir = _default_dir(notes_dir)

    if not os.path.isdir(notes_dir):
        print("No notes directory found. Create a note first with 'notesctl add'.", file=sys.stderr)
        sys.exit(0)

    entries = sorted(
        [e for e in os.listdir(notes_dir) if e.endswith(".md")],
        reverse=True,
    )

    if not entries:
        print("No notes found.")
        return

    pattern = re.compile(re.escape(keyword), re.IGNORECASE)
    results: list[tuple[str, int, str]] = []  # (filename, line_no, line_text)

    for entry in entries:
        filepath = os.path.join(notes_dir, entry)
        with open(filepath, encoding="utf-8") as fh:
            for lineno, line in enumerate(fh, 1):
                if pattern.search(line):
                    results.append((entry, lineno, line.strip()))

    if not results:
        print(f"No matches found for '{keyword}'.")
        return

    # Group by file
    print(f"Search results for {_yellow(keyword)} ({len(results)} matches):")
    current_file = None
    for filename, lineno, text in results:
        if filename != current_file:
            current_file = filename
            print(f"\n  {_bold(_cyan(filename))}")

        # Highlight the keyword in the line
        highlighted = pattern.sub(
            lambda m: _yellow(m.group(0)), text
        )
        print(f"    {_dim(f'{lineno}:')} {highlighted}")


def cmd_delete(filename: str, notes_dir: str | None) -> None:
    """Delete a note."""
    notes_dir = _default_dir(notes_dir)
    filepath = os.path.join(notes_dir, filename)

    if not os.path.isfile(filepath):
        print(f"Error: note '{filename}' not found.", file=sys.stderr)
        sys.exit(1)

    os.remove(filepath)
    print(f"Deleted: {filepath}")
