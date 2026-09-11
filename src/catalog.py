"""ViolationCatalog: code -> (label, demerit points). Pure Module."""
from __future__ import annotations

_CATALOG: dict[str, tuple[str, int]] = {
    "SMOKE": ("Smoking on campus", 1),
    "NOID": ("No ID worn", 1),
    "CUTTING": ("Cutting IT labs / classes", 2),
    "CHEAT": ("Academic dishonesty / quiz cheating", 3),
    "PLAGIARISM": ("Coding plagiarism", 4),
    "HACK": ("Cyber-offense / school portal hacking", 5),
}


class UnknownViolationError(ValueError):
    pass


def lookup(code: str) -> tuple[str, int]:
    key = code.strip().upper()
    try:
        return _CATALOG[key]
    except KeyError:
        raise UnknownViolationError(f"Unknown violation code: {code!r}") from None


def codes() -> list[str]:
    return sorted(_CATALOG)
