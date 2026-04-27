from __future__ import annotations

from collections.abc import Callable


def require_app_enabled(app_code: str) -> Callable[[], None]:
    def dependency() -> None:
        _ = app_code

    return dependency
