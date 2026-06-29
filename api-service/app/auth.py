import logging
import os

import jwt
from jwt import PyJWKClient

logger = logging.getLogger(__name__)

JWKS_URL = os.environ["JWKS_URL"]
_jwk_client = PyJWKClient(JWKS_URL, cache_keys=True)


def verify_token(authorization: str | None) -> str:
    if not authorization:
        raise ValueError("Missing Authorization header")

    parts = authorization.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise ValueError("Invalid Authorization header")

    token = parts[1]
    try:
        signing_key = _jwk_client.get_signing_key_from_jwt(token)
        payload = jwt.decode(
            token,
            signing_key.key,
            algorithms=["RS256"],
            options={"verify_aud": False},
        )
    except jwt.PyJWTError as e:
        raise ValueError(f"Invalid token: {e}") from e

    sub = payload.get("sub")
    if not sub:
        raise ValueError("Token missing sub claim")
    return sub
