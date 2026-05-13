"""Retry-aware base provider implementation."""

from __future__ import annotations

import random
import time
from collections.abc import Callable
from dataclasses import replace
from typing import NoReturn

from taskweavn.llm.contracts import (
    ChatRequest,
    ChatResponse,
    ErrorClassification,
    ProviderCapabilities,
    RetryPolicy,
    RetryRecord,
)
from taskweavn.llm.errors import (
    LLMAuthError,
    LLMCapabilityError,
    LLMContextLimitError,
    LLMProviderError,
    LLMRequestError,
    LLMRetryExhaustedError,
    UnsupportedCapabilityError,
)
from taskweavn.llm.logging import log_llm_retry

_RETRYABLE = {ErrorClassification.RETRYABLE, ErrorClassification.RATE_LIMIT}


class BaseLLMProvider:
    """Base provider with transport retry.

    Subclasses implement :meth:`_chat_once` and may override
    :meth:`classify_error`.
    """

    name: str = "base"
    capabilities: ProviderCapabilities = ProviderCapabilities()

    def __init__(
        self,
        *,
        retry_policy: RetryPolicy | None = None,
        sleeper: Callable[[float], None] = time.sleep,
        random_source: Callable[[], float] = random.random,
    ) -> None:
        self.retry_policy = retry_policy or RetryPolicy()
        self._sleeper = sleeper
        self._random_source = random_source

    def chat(self, request: ChatRequest) -> ChatResponse:
        """Run one chat request with retry handling."""
        return self._with_retry(request, lambda: self._chat_once(request))

    def _chat_once(self, request: ChatRequest) -> ChatResponse:
        raise NotImplementedError

    def complete(self, request: object) -> NoReturn:  # noqa: ARG002
        raise UnsupportedCapabilityError(
            "provider does not support legacy completion",
            provider_name=self.name,
            model="",
            classification=ErrorClassification.FATAL_CAPABILITY,
        )

    def count_tokens(self, request: object) -> NoReturn:  # noqa: ARG002
        raise UnsupportedCapabilityError(
            "provider does not support token counting",
            provider_name=self.name,
            model="",
            classification=ErrorClassification.FATAL_CAPABILITY,
        )

    def classify_error(self, exc: BaseException) -> ErrorClassification:
        """Map provider exceptions into retry classifications."""
        if isinstance(exc, LLMProviderError):
            return exc.classification

        status_code = getattr(exc, "status_code", None)
        if isinstance(status_code, int):
            if status_code in {401, 403}:
                return ErrorClassification.FATAL_AUTH
            if status_code == 429:
                return ErrorClassification.RATE_LIMIT
            if status_code in self.retry_policy.retry_on_status:
                return ErrorClassification.RETRYABLE
            if status_code == 400:
                return ErrorClassification.FATAL_REQUEST
            if status_code == 413:
                return ErrorClassification.CONTEXT_LIMIT

        name = type(exc).__name__.lower()
        message = str(exc).lower()
        if "timeout" in name or "timeout" in message:
            return ErrorClassification.RETRYABLE
        if "rate" in message and "limit" in message:
            return ErrorClassification.RATE_LIMIT
        if "context" in message and ("too long" in message or "length" in message):
            return ErrorClassification.CONTEXT_LIMIT
        if "auth" in name or "permission" in message or "api key" in message:
            return ErrorClassification.FATAL_AUTH
        if "badrequest" in name or "invalid" in message:
            return ErrorClassification.FATAL_REQUEST
        return ErrorClassification.UNKNOWN

    def _with_retry(
        self,
        request: ChatRequest,
        operation: Callable[[], ChatResponse],
    ) -> ChatResponse:
        policy = self.retry_policy
        records: list[RetryRecord] = []
        last_error: BaseException | None = None
        last_classification = ErrorClassification.UNKNOWN

        for attempt in range(1, policy.max_attempts + 1):
            try:
                response = operation()
            except BaseException as exc:
                last_error = exc
                last_classification = self.classify_error(exc)
                if last_classification in _RETRYABLE and attempt < policy.max_attempts:
                    delay = self._delay_seconds(attempt)
                    record = self._record(
                        request=request,
                        attempt=attempt,
                        classification=last_classification,
                        delay_seconds=delay,
                        exc=exc,
                    )
                    records.append(record)
                    self._log_retry(record)
                    self._sleeper(delay)
                    continue
                self._raise_final(
                    request=request,
                    exc=exc,
                    classification=last_classification,
                    retry_records=tuple(records),
                )
            else:
                if not records:
                    return response
                return replace(
                    response,
                    retry_count=len(records),
                    retry_records=tuple(records),
                )

        assert last_error is not None
        raise LLMRetryExhaustedError(
            f"{self.name} exhausted {policy.max_attempts} attempts for {request.model}",
            provider_name=self.name,
            model=request.model,
            classification=last_classification,
            original_error=last_error,
            retry_records=tuple(records),
        )

    def _delay_seconds(self, attempt: int) -> float:
        base = self.retry_policy.initial_delay_seconds
        delay = base * (self.retry_policy.backoff_multiplier ** (attempt - 1))
        delay = min(delay, self.retry_policy.max_delay_seconds)
        if self.retry_policy.jitter and delay > 0:
            delay *= 0.5 + self._random_source()
        return delay

    def _record(
        self,
        *,
        request: ChatRequest,
        attempt: int,
        classification: ErrorClassification,
        delay_seconds: float,
        exc: BaseException,
    ) -> RetryRecord:
        return RetryRecord(
            attempt=attempt,
            max_attempts=self.retry_policy.max_attempts,
            classification=classification,
            provider_name=self.name,
            model=request.model,
            delay_seconds=delay_seconds,
            error_type=type(exc).__name__,
            error_summary=str(exc)[:500],
        )

    def _log_retry(self, record: RetryRecord) -> None:
        log_llm_retry(record)

    def _raise_final(
        self,
        *,
        request: ChatRequest,
        exc: BaseException,
        classification: ErrorClassification,
        retry_records: tuple[RetryRecord, ...],
    ) -> NoReturn:
        if isinstance(exc, LLMProviderError):
            if retry_records and not exc.retry_records:
                raise LLMProviderError(
                    str(exc),
                    provider_name=exc.provider_name,
                    model=exc.model,
                    classification=exc.classification,
                    original_error=exc.original_error,
                    retry_records=retry_records,
                    metadata=exc.metadata,
                ) from exc
            raise exc

        message = f"{self.name} {classification.value}: {exc}"
        if classification in _RETRYABLE:
            raise LLMRetryExhaustedError(
                message,
                provider_name=self.name,
                model=request.model,
                classification=classification,
                original_error=exc,
                retry_records=retry_records,
            ) from exc
        if classification == ErrorClassification.FATAL_AUTH:
            raise LLMAuthError(
                message,
                provider_name=self.name,
                model=request.model,
                classification=classification,
                original_error=exc,
                retry_records=retry_records,
            ) from exc
        if classification == ErrorClassification.FATAL_CAPABILITY:
            raise LLMCapabilityError(
                message,
                provider_name=self.name,
                model=request.model,
                classification=classification,
                original_error=exc,
                retry_records=retry_records,
            ) from exc
        if classification == ErrorClassification.CONTEXT_LIMIT:
            raise LLMContextLimitError(
                message,
                provider_name=self.name,
                model=request.model,
                classification=classification,
                original_error=exc,
                retry_records=retry_records,
            ) from exc
        if classification == ErrorClassification.FATAL_REQUEST:
            raise LLMRequestError(
                message,
                provider_name=self.name,
                model=request.model,
                classification=classification,
                original_error=exc,
                retry_records=retry_records,
            ) from exc
        raise LLMProviderError(
            message,
            provider_name=self.name,
            model=request.model,
            classification=classification,
            original_error=exc,
            retry_records=retry_records,
        ) from exc


__all__ = ["BaseLLMProvider"]
