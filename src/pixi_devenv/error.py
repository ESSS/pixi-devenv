from __future__ import annotations


class DevEnvError(Exception):
    """
    Errors raised explicitly by pixi-devenv.

    We might decide later to provide more fine-grained exceptions for specific scenarios. If/when that happens,
    the new exceptions will be subclasses of `DevEnvError` in order to support backward compatibility.
    """
