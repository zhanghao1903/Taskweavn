import logging

from taskweavn.observability.main_page_trace import main_page_trace


def test_main_page_trace_suppresses_high_frequency_poll_events(
    caplog,
    capsys,
    monkeypatch,
    tmp_path,
) -> None:
    trace_file = tmp_path / "trace.jsonl"
    monkeypatch.setenv("PLATO_MAIN_PAGE_TRACE", "1")
    monkeypatch.setenv("PLATO_MAIN_PAGE_TRACE_PRINT", "1")
    monkeypatch.setenv("PLATO_MAIN_PAGE_TRACE_FILE", str(trace_file))
    caplog.set_level(logging.INFO, logger="taskweavn.main_page.trace")

    main_page_trace("http.events.request", cursor="cursor-1", session_id="s1")
    main_page_trace("ui_event.subscribe.result", event_count=0, session_id="s1")

    assert capsys.readouterr().out == ""
    assert not trace_file.exists()
    assert not caplog.records


def test_main_page_trace_uses_logger_without_duplicate_stdout_by_default(
    caplog,
    capsys,
    monkeypatch,
) -> None:
    monkeypatch.setenv("PLATO_MAIN_PAGE_TRACE", "1")
    monkeypatch.delenv("PLATO_MAIN_PAGE_TRACE_PRINT", raising=False)
    monkeypatch.delenv("PLATO_MAIN_PAGE_TRACE_FILE", raising=False)
    caplog.set_level(logging.INFO, logger="taskweavn.main_page.trace")

    main_page_trace("task_lifecycle.event.emit", session_id="s1", task_id="t1")

    assert capsys.readouterr().out == ""
    assert len(caplog.records) == 1
    assert "task_lifecycle.event.emit" in caplog.records[0].message
