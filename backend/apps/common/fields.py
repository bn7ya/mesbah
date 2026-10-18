from decimal import Decimal
from typing import Any

from django.db import models

MONEY_MAX_DIGITS: int = 15
MONEY_DECIMAL_PLACES: int = 3


class MoneyField(models.DecimalField[Decimal, Decimal]):
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        kwargs.setdefault("max_digits", MONEY_MAX_DIGITS)
        kwargs.setdefault("decimal_places", MONEY_DECIMAL_PLACES)
        super().__init__(*args, **kwargs)
