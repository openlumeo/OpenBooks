from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True)
class Params:
    currency: str | None = None
    opening: Decimal | None = None
    account: str | None = None
    allow_derived_opening: bool = False
    ocr: bool = True
    model: bool = False
    date_order: str | None = None
