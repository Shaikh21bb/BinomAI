"""Conservative model matching shared by discovery and evidence checks."""

import re


_MODEL = re.compile(
    r"\b(?=[a-z0-9/._-]{4,}\b)(?=[a-z0-9/._-]*\d)[a-z][a-z0-9]*(?:[/._-][a-z0-9]+)*\b",
    re.I,
)


def model_identifiers(text: str) -> list[str]:
    return list(dict.fromkeys(match.group(0) for match in _MODEL.finditer(text)))


def contains_model(text: str, model: str) -> bool:
    """Treat FC9734/01, FC9734-01 and FC973401 as the same full identifier."""
    compact = re.sub(r"[^a-z0-9]", "", model.casefold())
    if not compact:
        return False
    pattern = r"(?<![a-z0-9])" + r"[\s/._-]*".join(map(re.escape, compact)) + r"(?![a-z0-9])"
    return bool(re.search(pattern, text.casefold()))
