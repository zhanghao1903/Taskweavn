"""Local macOS WeChat Desktop integration."""

from taskweavn.integrations.wechat_desktop.adapter import (
    WeChatDesktopAdapter,
    WeChatDesktopAdapterConfig,
)
from taskweavn.integrations.wechat_desktop.confirmation import (
    WeChatSendActionFingerprint,
    WeChatSendConfirmationAuthorization,
    WeChatSendConfirmationAuthorizer,
    WeChatSendConfirmationPayload,
    build_wechat_send_confirmation_payload,
)
from taskweavn.integrations.wechat_desktop.fake_adapter import FakeWeChatDesktopAdapter
from taskweavn.integrations.wechat_desktop.helper_adapter import (
    WeChatDesktopHelperAdapter,
    WeChatHelperHttpClient,
)
from taskweavn.integrations.wechat_desktop.macos_driver import (
    MacOSWeChatSearchDriver,
    WeChatContactSearchResult,
    WeChatInputFocusResult,
    WeChatMessageSubmitResult,
    WeChatWindowReadinessResult,
)
from taskweavn.integrations.wechat_desktop.models import (
    WeChatContactCandidate,
    WeChatContactResolution,
    WeChatDraftState,
    WeChatOperationResult,
    WeChatReadiness,
    WeChatSendAttemptResult,
    WeChatSendTaskInput,
    wechat_message_hash,
    wechat_message_preview,
)

__all__ = [
    "WeChatContactCandidate",
    "WeChatContactResolution",
    "WeChatDesktopAdapter",
    "WeChatDesktopAdapterConfig",
    "WeChatDesktopHelperAdapter",
    "WeChatDraftState",
    "FakeWeChatDesktopAdapter",
    "MacOSWeChatSearchDriver",
    "WeChatOperationResult",
    "WeChatReadiness",
    "WeChatSendAttemptResult",
    "WeChatSendActionFingerprint",
    "WeChatSendConfirmationAuthorization",
    "WeChatSendConfirmationAuthorizer",
    "WeChatSendConfirmationPayload",
    "WeChatSendTaskInput",
    "WeChatContactSearchResult",
    "WeChatInputFocusResult",
    "WeChatMessageSubmitResult",
    "WeChatWindowReadinessResult",
    "WeChatHelperHttpClient",
    "build_wechat_send_confirmation_payload",
    "wechat_message_hash",
    "wechat_message_preview",
]
