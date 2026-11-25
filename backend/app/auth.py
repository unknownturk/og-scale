"""Ein Nutzer, ein gemeinsames Geheimnis zwischen Frontend-Proxy und Backend."""

import hmac

from fastapi import Header, HTTPException, status

from . import settings


def require_key(x_api_key: str = Header(default="")):
    expected = settings.BACKEND_API_KEY
    if not expected:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "BACKEND_API_KEY ist nicht gesetzt")
    if not hmac.compare_digest(x_api_key.encode(), expected.encode()):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Nicht angemeldet")
