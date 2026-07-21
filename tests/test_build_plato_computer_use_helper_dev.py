from __future__ import annotations

from pathlib import Path
from plistlib import dump, load

from scripts.build_plato_computer_use_helper_dev import (
    HELPER_EXECUTABLE_NAME,
    RELEASE_HELPER_BUNDLE_ID,
    RELEASE_HELPER_NAME,
    DevHelperBuildConfig,
    _customize_app_bundle,
    build_pyinstaller_command,
)


def test_pyinstaller_command_builds_onedir_worker_compatible_helper(
    tmp_path: Path,
) -> None:
    config = DevHelperBuildConfig(
        repo_root=tmp_path,
        build_root=tmp_path / "build",
        app_path=tmp_path / "Helper.app",
        python_executable="/python",
    )
    entrypoint = tmp_path / "helper.py"

    command = build_pyinstaller_command(config, entrypoint=entrypoint)

    assert "--onedir" in command
    assert "--windowed" in command
    assert "--onefile" not in command
    assert "computer_use_macos" in command
    assert "wechat_desktop_tool" in command
    assert command.count("--collect-all") == 3
    assert "app_control_protocol" in command
    assert "ApplicationServices" in command
    assert command[-1] == str(entrypoint)


def test_customize_app_bundle_preserves_pyinstaller_runtime(tmp_path: Path) -> None:
    app_path = tmp_path / "Helper.app"
    contents = app_path / "Contents"
    resources = contents / "Resources"
    frameworks = contents / "Frameworks"
    resources.mkdir(parents=True)
    frameworks.mkdir()
    (frameworks / "runtime.dat").write_text("runtime", encoding="utf-8")
    with (contents / "Info.plist").open("wb") as handle:
        dump({"PyInstallerTestKey": True}, handle)

    _customize_app_bundle(app_path, version="0.1.0")

    assert (frameworks / "runtime.dat").is_file()
    assert (resources / "permission-guide.md").is_file()
    with (contents / "Info.plist").open("rb") as handle:
        info = load(handle)
    assert info["PyInstallerTestKey"] is True
    assert info["CFBundleExecutable"] == HELPER_EXECUTABLE_NAME


def test_customize_release_bundle_uses_release_identity(tmp_path: Path) -> None:
    app_path = tmp_path / "Helper.app"
    contents = app_path / "Contents"
    contents.mkdir(parents=True)
    with (contents / "Info.plist").open("wb") as handle:
        dump({}, handle)

    _customize_app_bundle(
        app_path,
        version="1.1.0",
        app_name=RELEASE_HELPER_NAME,
        bundle_id=RELEASE_HELPER_BUNDLE_ID,
    )

    with (contents / "Info.plist").open("rb") as handle:
        info = load(handle)
    assert info["CFBundleDisplayName"] == RELEASE_HELPER_NAME
    assert info["CFBundleIdentifier"] == RELEASE_HELPER_BUNDLE_ID
