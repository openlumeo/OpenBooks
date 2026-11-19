"""Exceptions. A Refusal is a document-level outcome; an EngineFault is an environment problem and never a refusal."""
from __future__ import annotations


class OpenBooksError(Exception):
    """Base class for everything Open Books raises on purpose."""


class Refusal(OpenBooksError):
    """The file cannot be proven. `code` is one of the typed refusal codes (UNKNOWN_LAYOUT, PARSE_ERROR, ...)."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


class ProviderMissing(Refusal):
    """The file matches a known layout whose provider is not registered. Never falls through to another layout."""

    def __init__(self, layout_id: str, distribution: str) -> None:
        super().__init__("UNKNOWN_LAYOUT", f"this looks like {layout_id}, but its provider {distribution!r} is not "
                                           "registered (a broken install): pip install --force-reinstall openbooks")
        self.layout_id = layout_id
        self.distribution = distribution


class EngineFault(OpenBooksError):
    """The engine could not do its job (broken install, unreadable plugin). Not a statement about the document."""


class PluginLoadError(EngineFault):
    """An installed provider failed to load or conflicts with another. Deliberately not an ImportError subclass."""
