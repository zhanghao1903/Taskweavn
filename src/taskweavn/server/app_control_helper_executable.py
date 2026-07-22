"""PyInstaller entrypoint for Plato Computer Use Helper."""

from __future__ import annotations

import sys
from collections.abc import Sequence

_COORDINATE_CLICK_MODULE = "computer_use_macos._coordinate_click"


def main(argv: Sequence[str] | None = None) -> int:
    """Run the Helper host or a supported package-internal Python worker.

    ``computer-use-macos`` launches selector workers with ``python -c`` and
    coordinate clicks with ``python -m computer_use_macos._coordinate_click``.
    A frozen Helper executable is ``sys.executable`` inside the bundle, so it
    must preserve those narrow contracts instead of recursively starting
    another service.
    """

    arguments = list(sys.argv[1:] if argv is None else argv)
    command_index = _python_command_index(arguments)
    if command_index is not None:
        return _run_python_command(arguments, command_index=command_index)
    module_index = _python_module_index(arguments)
    if module_index is not None:
        return _run_python_module(arguments, module_index=module_index)

    from taskweavn.server.app_control_helper import main as helper_main

    return helper_main(arguments)


def _python_command_index(arguments: Sequence[str]) -> int | None:
    """Locate the package worker's ``-c`` after supported interpreter flags."""

    for index, argument in enumerate(arguments):
        if argument == "-c":
            return index
        if argument not in {"-u"}:
            return None
    return None


def _python_module_index(arguments: Sequence[str]) -> int | None:
    """Locate a package worker's ``-m`` after supported interpreter flags."""

    for index, argument in enumerate(arguments):
        if argument == "-m":
            return index
        if argument not in {"-u"}:
            return None
    return None


def _run_python_command(
    arguments: Sequence[str],
    *,
    command_index: int,
) -> int:
    if len(arguments) <= command_index + 1:
        print("argument expected for -c", file=sys.stderr)
        return 2
    command = arguments[command_index + 1]
    sys.argv = ["-c", *arguments[command_index + 2 :]]
    namespace = {
        "__name__": "__main__",
        "__package__": None,
        "__builtins__": __builtins__,
    }
    exec(compile(command, "<string>", "exec"), namespace, namespace)  # noqa: S102
    return 0


def _run_python_module(
    arguments: Sequence[str],
    *,
    module_index: int,
) -> int:
    if len(arguments) <= module_index + 1:
        print("argument expected for -m", file=sys.stderr)
        return 2
    module_name = arguments[module_index + 1]
    if module_name != _COORDINATE_CLICK_MODULE:
        print(f"unsupported Helper worker module: {module_name}", file=sys.stderr)
        return 2

    from computer_use_macos._coordinate_click import main as coordinate_click_main

    return coordinate_click_main(arguments[module_index + 2 :])


if __name__ == "__main__":
    raise SystemExit(main())
