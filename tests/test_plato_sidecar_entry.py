from __future__ import annotations

from taskweavn.server.plato_sidecar import _parse_args


def test_plato_sidecar_parse_args_reads_read_only_inquiry_llm_env(
    monkeypatch,
) -> None:
    monkeypatch.setenv("PLATO_ENABLE_READ_ONLY_INQUIRY_LLM", "1")

    args = _parse_args(["--workspace", "/tmp/workspace", "--port", "0"])

    assert args.enable_read_only_inquiry_llm is True


def test_plato_sidecar_parse_args_defaults_read_only_inquiry_llm_on(
    monkeypatch,
) -> None:
    monkeypatch.delenv("PLATO_ENABLE_READ_ONLY_INQUIRY_LLM", raising=False)

    args = _parse_args(["--workspace", "/tmp/workspace", "--port", "0"])

    assert args.enable_read_only_inquiry_llm is True


def test_plato_sidecar_parse_args_can_disable_read_only_inquiry_llm_env(
    monkeypatch,
) -> None:
    monkeypatch.setenv("PLATO_ENABLE_READ_ONLY_INQUIRY_LLM", "0")

    args = _parse_args(["--workspace", "/tmp/workspace", "--port", "0"])

    assert args.enable_read_only_inquiry_llm is False


def test_plato_sidecar_parse_args_can_disable_read_only_inquiry_llm_flag(
    monkeypatch,
) -> None:
    monkeypatch.delenv("PLATO_ENABLE_READ_ONLY_INQUIRY_LLM", raising=False)

    args = _parse_args(
        [
            "--workspace",
            "/tmp/workspace",
            "--port",
            "0",
            "--disable-read-only-inquiry-llm",
        ]
    )

    assert args.enable_read_only_inquiry_llm is False
