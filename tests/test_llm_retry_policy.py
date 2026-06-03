"""Retry behavior for provider base class."""

from __future__ import annotations

from dataclasses import dataclass

import pytest

from taskweavn.llm import ChatRequest, ChatResponse, ErrorClassification, RetryPolicy
from taskweavn.llm.errors import LLMAuthError, LLMProviderError, LLMRetryExhaustedError
from taskweavn.llm.retry import BaseLLMProvider


@dataclass
class _Boom(Exception):
    status_code: int
    message: str

    def __str__(self) -> str:
        return self.message


class _RetryProvider(BaseLLMProvider):
    name = "retry-test"

    def __init__(self, outcomes: list[ChatResponse | Exception]) -> None:
        super().__init__(
            retry_policy=RetryPolicy(
                max_attempts=3,
                initial_delay_seconds=0,
                max_delay_seconds=0,
                jitter=False,
            ),
            sleeper=lambda _delay: None,
        )
        self.outcomes = outcomes
        self.calls = 0

    def _chat_once(self, request: ChatRequest) -> ChatResponse:  # noqa: ARG002
        self.calls += 1
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


def _response() -> ChatResponse:
    return ChatResponse(content="ok", tool_calls=[], raw_assistant_message={})


def test_retryable_error_then_success_records_retry() -> None:
    provider = _RetryProvider([_Boom(429, "rate limit"), _response()])
    result = provider.chat(ChatRequest(model="m", messages=[]))
    assert result.content == "ok"
    assert result.retry_count == 1
    assert result.retry_records[0].classification == ErrorClassification.RATE_LIMIT
    assert provider.calls == 2


def test_request_timeout_does_not_retry_when_timeout_boundary_is_configured() -> None:
    provider = _RetryProvider([TimeoutError("provider timed out"), _response()])

    with pytest.raises(LLMRetryExhaustedError) as exc_info:
        provider.chat(ChatRequest(model="m", messages=[], timeout_seconds=1.0))

    assert exc_info.value.classification == ErrorClassification.RETRYABLE
    assert len(exc_info.value.retry_records) == 0
    assert provider.calls == 1


def test_retry_exhaustion_raises_structured_error() -> None:
    provider = _RetryProvider(
        [_Boom(500, "server"), _Boom(500, "server"), _Boom(500, "server")]
    )
    with pytest.raises(LLMRetryExhaustedError) as exc_info:
        provider.chat(ChatRequest(model="m", messages=[]))
    assert exc_info.value.classification == ErrorClassification.RETRYABLE
    assert len(exc_info.value.retry_records) == 2
    assert provider.calls == 3


def test_auth_error_does_not_retry() -> None:
    provider = _RetryProvider([_Boom(401, "bad key"), _response()])
    with pytest.raises(LLMAuthError):
        provider.chat(ChatRequest(model="m", messages=[]))
    assert provider.calls == 1


def test_provider_error_classification_is_preserved() -> None:
    provider = _RetryProvider(
        [
            LLMProviderError(
                "fatal",
                provider_name="x",
                model="m",
                classification=ErrorClassification.FATAL_REQUEST,
            ),
            _response(),
        ]
    )
    with pytest.raises(LLMProviderError) as exc_info:
        provider.chat(ChatRequest(model="m", messages=[]))
    assert exc_info.value.classification == ErrorClassification.FATAL_REQUEST
    assert provider.calls == 1
