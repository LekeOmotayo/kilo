"""Chat controller routing."""
from app.api.v1.endpoints.chat import router, extract_canonical_prompt

__all__ = ["router", "extract_canonical_prompt"]
