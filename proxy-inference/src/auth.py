from .config import settings


def verify_node_authorization(authorization: str | None) -> bool:
    """Validate Authorization header for an AI-node WS connect. Returns True if ok."""
    if not authorization:
        return False
    expected = f"Bearer {settings.proxy_node_api_key}"
    return authorization == expected
