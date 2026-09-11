"""ConsequenceEngine: total demerits -> (status, sanction). Pure Module.

Returns results; never mutates records. The matrix lives here only,
so policy changes concentrate in one place (Locality).
"""
from __future__ import annotations

from src.models import Consequence

_MATRIX: dict[int, Consequence] = {
    0: Consequence("Good Standing", "No sanction"),
    1: Consequence("Warned", "Written Warning issued"),
    2: Consequence("Probation", "Mandatory Parent Conference"),
    3: Consequence("Suspended", "3-Day Campus Suspension plus zero score on the task"),
    4: Consequence("Lab Banned", "Automatic failure of current subject and ban from IT laboratories"),
    5: Consequence("Expelled", "Immediate expulsion from the IT Department"),
}


def evaluate(total_demerits: int) -> Consequence:
    if total_demerits <= 0:
        return _MATRIX[0]
    if total_demerits >= 5:
        return _MATRIX[5]
    return _MATRIX[total_demerits]
