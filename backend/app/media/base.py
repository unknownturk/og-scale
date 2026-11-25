class MediaError(RuntimeError):
    """Der Anbieter hat sicher abgelehnt oder ist nicht eingerichtet."""


class SubmissionUncertain(RuntimeError):
    """Unklar, ob der Anbieter den (bezahlten) Auftrag angenommen hat."""
