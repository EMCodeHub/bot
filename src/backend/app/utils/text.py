import re
import unicodedata

CONTROL_CHAR_RE = re.compile(r"[\u0000-\u001f\u007f-\u009f]")
WHITESPACE_RE = re.compile(r"\s+")


def normalize_text(value: str) -> str:
    """Normalize whitespace, strip control characters, and unify Unicode."""
    if not value:
        return ""
    text = unicodedata.normalize("NFC", value)
    text = CONTROL_CHAR_RE.sub(" ", text)
    text = WHITESPACE_RE.sub(" ", text)
    return text.strip()
