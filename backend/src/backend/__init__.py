from __future__ import annotations

from importlib import import_module

__all__ = ["create_app", "main"]

_EXPORTS = {
    "create_app": (".app", "create_app"),
    "main": (".app", "main"),
}


def __getattr__(name: str):
    try:
        module_name, attr_name = _EXPORTS[name]
    except KeyError as exc:
        raise AttributeError(name) from exc
    module = import_module(module_name, __name__)
    return getattr(module, attr_name)
