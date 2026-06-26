"""WeChat adapter assembly for Plato Computer Use Helper."""

from __future__ import annotations

from taskweavn.integrations.wechat_desktop import (
    MacOSWeChatSearchDriver,
    WeChatDesktopAdapter,
)
from taskweavn.server.computer_use_helper import WeChatHelperAdapter
from taskweavn.tools import ComputerUseBackend


def build_default_wechat_helper_adapter(
    backend: ComputerUseBackend | None,
) -> WeChatHelperAdapter | None:
    """Build the helper-owned WeChat adapter when a backend is configured."""

    if backend is None:
        return None
    return WeChatDesktopAdapter(
        backend,
        contact_search_driver=MacOSWeChatSearchDriver(),
    )


__all__ = ["build_default_wechat_helper_adapter"]
