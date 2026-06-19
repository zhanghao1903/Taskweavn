#!/usr/bin/env python3
"""Report repository file counts and line counts for code and docs.

The script uses git-tracked files by default so generated folders such as
``frontend/node_modules`` and ``frontend/dist`` do not distort the totals.
"""

from __future__ import annotations

import argparse
import json
import subprocess
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from pathlib import Path

FRONTEND_CODE_EXTENSIONS = {
    ".cjs",
    ".css",
    ".html",
    ".js",
    ".jsx",
    ".mjs",
    ".scss",
    ".ts",
    ".tsx",
}
DOC_EXTENSIONS = {".md", ".mdx", ".rst", ".txt"}
DOC_HTML_ROOTS = ("docs/",)
EXCLUDED_PARTS = {
    ".git",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".venv",
    "__pycache__",
    "coverage",
    "dist",
    "node_modules",
}


@dataclass(frozen=True)
class Bucket:
    key: str
    label: str
    predicate: Callable[[Path], bool]


@dataclass
class Stat:
    files: int = 0
    lines: int = 0

    def add(self, line_count: int) -> None:
        self.files += 1
        self.lines += line_count


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Count Taskweavn Python, frontend, and documentation lines."
    )
    parser.add_argument(
        "--root",
        type=Path,
        default=Path.cwd(),
        help="Repository root. Defaults to the current working directory.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print machine-readable JSON instead of a table.",
    )
    args = parser.parse_args()

    root = args.root.resolve()
    files = list(_tracked_files(root))
    buckets = _buckets()
    stats = {bucket.key: Stat() for bucket in buckets}

    for path in files:
        relative = path.relative_to(root)
        for bucket in buckets:
            if bucket.predicate(relative):
                stats[bucket.key].add(_line_count(path))
                break

    code_total = _sum_stats(
        stats,
        (
            "python_src",
            "python_tests",
            "frontend_non_test",
            "frontend_tests",
        ),
    )
    grand_total = _sum_stats(
        stats,
        (
            "python_src",
            "python_tests",
            "frontend_non_test",
            "frontend_tests",
            "docs",
        ),
    )

    if args.json:
        print(
            json.dumps(
                {
                    "scope": _scope_description(),
                    "buckets": {
                        bucket.key: {
                            "label": bucket.label,
                            "files": stats[bucket.key].files,
                            "lines": stats[bucket.key].lines,
                        }
                        for bucket in buckets
                    },
                    "totals": {
                        "code": {"files": code_total.files, "lines": code_total.lines},
                        "docs_and_code": {
                            "files": grand_total.files,
                            "lines": grand_total.lines,
                        },
                    },
                },
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
            )
        )
        return 0

    _print_table(buckets, stats, code_total, grand_total)
    return 0


def _buckets() -> tuple[Bucket, ...]:
    return (
        Bucket("python_src", "Python code: src", _is_python_src),
        Bucket("python_tests", "Python code: tests", _is_python_test),
        Bucket("frontend_non_test", "Frontend code: non-test", _is_frontend_non_test),
        Bucket("frontend_tests", "Frontend code: test", _is_frontend_test),
        Bucket("docs", "Documentation", _is_doc),
    )


def _tracked_files(root: Path) -> Iterable[Path]:
    try:
        result = subprocess.run(
            ["git", "ls-files", "-z"],
            cwd=root,
            check=True,
            capture_output=True,
        )
    except (OSError, subprocess.CalledProcessError):
        yield from _walk_files(root)
        return

    for raw in result.stdout.split(b"\0"):
        if not raw:
            continue
        path = root / raw.decode("utf-8")
        if path.is_file() and not _has_excluded_part(path.relative_to(root)):
            yield path


def _walk_files(root: Path) -> Iterable[Path]:
    for path in root.rglob("*"):
        if path.is_file() and not _has_excluded_part(path.relative_to(root)):
            yield path


def _has_excluded_part(path: Path) -> bool:
    return any(part in EXCLUDED_PARTS for part in path.parts)


def _is_python_src(path: Path) -> bool:
    return path.parts[:1] == ("src",) and path.suffix == ".py"


def _is_python_test(path: Path) -> bool:
    return path.parts[:1] == ("tests",) and path.suffix == ".py"


def _is_frontend_non_test(path: Path) -> bool:
    return _is_frontend_code(path) and not _is_frontend_test_path(path)


def _is_frontend_test(path: Path) -> bool:
    return _is_frontend_code(path) and _is_frontend_test_path(path)


def _is_frontend_code(path: Path) -> bool:
    return path.parts[:1] == ("frontend",) and path.suffix in FRONTEND_CODE_EXTENSIONS


def _is_frontend_test_path(path: Path) -> bool:
    stem = path.name
    return (
        ".test." in stem
        or ".spec." in stem
        or ".e2e." in stem
        or "__tests__" in path.parts
        or "test" in path.parts
        or "tests" in path.parts
    )


def _is_doc(path: Path) -> bool:
    if path.suffix in DOC_EXTENSIONS:
        return True
    path_text = path.as_posix()
    return path.suffix == ".html" and path_text.startswith(DOC_HTML_ROOTS)


def _line_count(path: Path) -> int:
    text = path.read_text(encoding="utf-8", errors="replace")
    return len(text.splitlines())


def _sum_stats(stats: dict[str, Stat], keys: tuple[str, ...]) -> Stat:
    total = Stat()
    for key in keys:
        total.files += stats[key].files
        total.lines += stats[key].lines
    return total


def _print_table(
    buckets: tuple[Bucket, ...],
    stats: dict[str, Stat],
    code_total: Stat,
    grand_total: Stat,
) -> None:
    print("Repository line statistics")
    print(_scope_description())
    print()
    print(f"{'Category':<28} {'Files':>8} {'Lines':>10}")
    print("-" * 48)
    for bucket in buckets:
        stat = stats[bucket.key]
        print(f"{bucket.label:<28} {stat.files:>8} {stat.lines:>10}")
    print("-" * 48)
    print(f"{'Code total':<28} {code_total.files:>8} {code_total.lines:>10}")
    print(f"{'Docs + code total':<28} {grand_total.files:>8} {grand_total.lines:>10}")


def _scope_description() -> str:
    return (
        "Scope: git-tracked files only; Python=src/*.py + tests/*.py; "
        "frontend=frontend code extensions split by test naming; "
        "docs=*.md/*.mdx/*.rst/*.txt plus docs/*.html archives."
    )


if __name__ == "__main__":
    raise SystemExit(main())
