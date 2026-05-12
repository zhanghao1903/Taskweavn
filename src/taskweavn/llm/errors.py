"""Typed LLM provider errors."""

from __future__ import annotations

from typing import Any

from taskweavn.llm.contracts import ErrorClassification, RetryRecord


class LLMError(Exception):
    """Base class for LLM layer failures."""


class LLMProviderError(LLMError):
    """A provider failure with safe, structured metadata."""

    def __init__(
        self,
        message: str,
        *,
        provider_name: str,
        model: str,
        classification: ErrorClassification,
        original_error: BaseException | None = None,
        retry_records: tuple[RetryRecord, ...] = (),
        metadata: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.provider_name = provider_name
        self.model = model
        self.classification = classification
        self.original_error = original_error
        self.retry_records = retry_records
        self.metadata = dict(metadata or {})


class LLMRetryExhaustedError(LLMProviderError):
    """All retry attempts were exhausted."""


class LLMAuthError(LLMProviderError):
    """Authentication or permission failure."""


class LLMRequestError(LLMProviderError):
    """Fatal request/schema/provider parameter failure."""


class LLMCapabilityError(LLMProviderError):
    """Requested capability is unsupported by provider/model."""


class LLMContextLimitError(LLMProviderError):
    """The request exceeded provider context limits."""


class UnsupportedCapabilityError(LLMCapabilityError):
    """Provider method or model capability is unsupported."""


__all__ = [
    "LLMAuthError",
    "LLMCapabilityError",
    "LLMContextLimitError",
    "LLMError",
    "LLMProviderError",
    "LLMRequestError",
    "LLMRetryExhaustedError",
    "UnsupportedCapabilityError",
]
