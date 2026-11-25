"""Der eine Zugang zu Bild- und Video-Erzeugung."""

from .. import settings
from .base import MediaError, SubmissionUncertain  # noqa: F401

_provider = None


def get_provider():
    global _provider
    if _provider is None:
        if settings.MEDIA_PROVIDER == "fake":
            from .fake import FakeProvider

            _provider = FakeProvider()
        else:
            from .kie import KieProvider

            _provider = KieProvider()
    return _provider


def set_provider(provider):
    """Für Tests."""
    global _provider
    _provider = provider
