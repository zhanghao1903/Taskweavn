"""Tests for notesctl commands."""

import io
import os
import sys
import tempfile
import pytest
from notesctl.commands import (
    cmd_add,
    cmd_list,
    cmd_show,
    cmd_delete,
    cmd_search,
    _make_filename,
    _parse_tags,
)


class TestMakeFilename:
    def test_basic_slug(self):
        name = _make_filename("hello-world")
        assert name.endswith("-hello-world.md")
        assert name.startswith("20")  # starts with year

    def test_spaces_become_hyphens(self):
        name = _make_filename("my note")
        assert "-my-note.md" in name

    def test_special_chars_stripped(self):
        name = _make_filename("hello!!!@#world")
        assert "-hello-world.md" in name

    def test_empty_slug_defaults(self):
        name = _make_filename("!!!")
        assert name.endswith("-note.md")


class TestParseTags:
    def test_inline_hashtags(self):
        tags = _parse_tags("This is a note with #todo and #python tags.")
        assert tags == {"todo", "python"}

    def test_skip_headings(self):
        """Markdown headings (# Foo) should not be parsed as tags."""
        tags = _parse_tags("# My Heading\n\nReal tag: #tag")
        assert tags == {"tag"}

    def test_yaml_frontmatter_tags(self):
        content = "tags: todo, python, notes\n\n# Title\n\nContent #inline"
        tags = _parse_tags(content)
        assert "todo" in tags
        assert "python" in tags
        assert "notes" in tags
        assert "inline" in tags

    def test_yaml_frontmatter_tags_brackets(self):
        content = "tags: [todo, python]\n\n# Title"
        tags = _parse_tags(content)
        assert tags == {"todo", "python"}

    def test_no_tags(self):
        tags = _parse_tags("Plain content without any tags.")
        assert tags == set()


class TestAddAndList:
    def test_add_and_list(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            cmd_add("my-first-note", ["Hello", "world"], notes_dir=tmpdir)
            cmd_add("second-note", ["Another"], notes_dir=tmpdir)

            buf = io.StringIO()
            old = sys.stdout
            sys.stdout = buf
            try:
                cmd_list(notes_dir=tmpdir)
            finally:
                sys.stdout = old

            output = buf.getvalue()
            assert "my-first-note.md" in output
            assert "second-note.md" in output
            # most recent first: second comes before first
            lines = [l for l in output.strip().split("\n") if l]
            idx_first = lines.index(
                next(l for l in lines if "my-first-note" in l)
            )
            idx_second = lines.index(
                next(l for l in lines if "second-note" in l)
            )
            assert idx_second < idx_first

    def test_add_duplicate(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            cmd_add("dup", ["first"], notes_dir=tmpdir)
            with pytest.raises(SystemExit):
                cmd_add("dup", ["second"], notes_dir=tmpdir)

    def test_add_no_content_no_stdin(self, monkeypatch):
        """When stdin is a tty and no content args, should exit."""
        with tempfile.TemporaryDirectory() as tmpdir:
            monkeypatch.setattr("sys.stdin.isatty", lambda: True)
            with pytest.raises(SystemExit):
                cmd_add("empty", [], notes_dir=tmpdir)

    @pytest.mark.parametrize(
        "slug,content_parts", [("simple", ["one"]), ("two-part", ["a", "b"])]
    )
    def test_add_creates_file(self, slug, content_parts):
        with tempfile.TemporaryDirectory() as tmpdir:
            cmd_add(slug, content_parts, notes_dir=tmpdir)
            files = os.listdir(tmpdir)
            assert len(files) == 1
            filepath = os.path.join(tmpdir, files[0])
            with open(filepath) as fh:
                content = fh.read()
            assert content.startswith(f"# {slug}")


class TestListTagFilter:
    def test_list_tag_filter_matching(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            cmd_add("tagged-note", ["This has #todo content"], notes_dir=tmpdir)
            cmd_add("untagged-note", ["No tags here"], notes_dir=tmpdir)

            buf = io.StringIO()
            old = sys.stdout
            sys.stdout = buf
            try:
                cmd_list(notes_dir=tmpdir, tag="todo")
            finally:
                sys.stdout = old

            output = buf.getvalue()
            assert "tagged-note" in output
            assert "untagged-note" not in output

    def test_list_tag_filter_no_match(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            cmd_add("only-note", ["Just #work stuff"], notes_dir=tmpdir)

            buf = io.StringIO()
            old = sys.stdout
            sys.stdout = buf
            try:
                cmd_list(notes_dir=tmpdir, tag="nonexistent")
            finally:
                sys.stdout = old

            output = buf.getvalue()
            assert "nonexistent" in output  # error-like message


class TestShow:
    def test_show_existing(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            cmd_add("show-test", ["visible"], notes_dir=tmpdir)
            files = [f for f in os.listdir(tmpdir) if f.endswith(".md")]
            assert len(files) == 1

            buf = io.StringIO()
            old = sys.stdout
            sys.stdout = buf
            try:
                cmd_show(files[0], notes_dir=tmpdir)
            finally:
                sys.stdout = old
            assert "visible" in buf.getvalue()

    def test_show_missing(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with pytest.raises(SystemExit):
                cmd_show("nope.md", notes_dir=tmpdir)


class TestSearch:
    def test_search_finds_keyword(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            cmd_add("alpha", ["Python is great for scripting"], notes_dir=tmpdir)
            cmd_add("beta", ["Rust is fast and safe"], notes_dir=tmpdir)

            buf = io.StringIO()
            old = sys.stdout
            sys.stdout = buf
            try:
                cmd_search("python", notes_dir=tmpdir)
            finally:
                sys.stdout = old

            output = buf.getvalue()
            assert "Python" in output
            assert "Rust" not in output

    def test_search_case_insensitive(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            cmd_add("note", ["HELLO World"], notes_dir=tmpdir)

            buf = io.StringIO()
            old = sys.stdout
            sys.stdout = buf
            try:
                cmd_search("hello", notes_dir=tmpdir)
            finally:
                sys.stdout = old

            output = buf.getvalue()
            assert "HELLO" in output

    def test_search_no_match(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            cmd_add("lonely", ["just some text"], notes_dir=tmpdir)

            buf = io.StringIO()
            old = sys.stdout
            sys.stdout = buf
            try:
                cmd_search("missing", notes_dir=tmpdir)
            finally:
                sys.stdout = old

            output = buf.getvalue()
            assert "No matches" in output

    def test_search_empty_notes_dir(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            buf = io.StringIO()
            old = sys.stdout
            sys.stdout = buf
            try:
                cmd_search("anything", notes_dir=tmpdir)
            finally:
                sys.stdout = old

            output = buf.getvalue()
            # Should exit gracefully
            assert not output or "No notes" in output or "not found" in output.lower()


class TestDelete:
    def test_delete_removes_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            cmd_add("del-me", ["gone"], notes_dir=tmpdir)
            files = [f for f in os.listdir(tmpdir) if f.endswith(".md")]
            assert len(files) == 1
            cmd_delete(files[0], notes_dir=tmpdir)
            assert os.listdir(tmpdir) == []

    def test_delete_missing(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with pytest.raises(SystemExit):
                cmd_delete("nope.md", notes_dir=tmpdir)
