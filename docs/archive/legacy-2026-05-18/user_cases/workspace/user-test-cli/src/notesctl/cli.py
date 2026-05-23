"""CLI entry point for notesctl."""

import argparse
import sys
from notesctl import commands


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        prog="notesctl",
        description="Manage local Markdown notes.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # add
    p_add = sub.add_parser("add", help="Create a new note")
    p_add.add_argument("slug", help="Short title/slug for the note")
    p_add.add_argument("content", nargs="*", help="Content of the note (reads stdin if omitted)")
    p_add.add_argument("--dir", default=None, help="Override notes directory")

    # list
    p_list = sub.add_parser("list", help="List all notes")
    p_list.add_argument("--dir", default=None, help="Override notes directory")
    p_list.add_argument("--tag", default=None, help="Filter notes by tag (e.g. #todo)")

    # show
    p_show = sub.add_parser("show", help="Display a note")
    p_show.add_argument("filename", help="Name of the note file (e.g. 2026-05-13-my-slug.md)")
    p_show.add_argument("--dir", default=None, help="Override notes directory")

    # search
    p_search = sub.add_parser("search", help="Full-text search across notes")
    p_search.add_argument("keyword", help="Keyword to search for")
    p_search.add_argument("--dir", default=None, help="Override notes directory")

    # delete
    p_del = sub.add_parser("delete", help="Delete a note")
    p_del.add_argument("filename", help="Name of the note file to delete")
    p_del.add_argument("--dir", default=None, help="Override notes directory")

    args = parser.parse_args(argv)

    if args.command == "add":
        commands.cmd_add(args.slug, args.content, args.dir)
    elif args.command == "list":
        commands.cmd_list(args.dir, tag=getattr(args, "tag", None))
    elif args.command == "show":
        commands.cmd_show(args.filename, args.dir)
    elif args.command == "search":
        commands.cmd_search(args.keyword, args.dir)
    elif args.command == "delete":
        commands.cmd_delete(args.filename, args.dir)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
