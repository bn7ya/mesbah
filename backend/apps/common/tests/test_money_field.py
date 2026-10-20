from decimal import Decimal

from django.db import models
from django.test.utils import isolate_apps
from rest_framework import serializers

from apps.common.fields import MoneyField


def test_money_holds_baisa_precision() -> None:
    field: MoneyField = MoneyField()

    assert field.max_digits == 15
    assert field.decimal_places == 3


@isolate_apps("apps.common")
def test_money_reaches_the_api_as_a_three_place_string() -> None:
    class Price(models.Model):
        amount: MoneyField = MoneyField()

        class Meta:
            app_label = "common"

        def __str__(self) -> str:
            return str(self.amount)

    class PriceSerializer(serializers.ModelSerializer[Price]):
        class Meta:
            model = Price
            fields = ["amount"]

    data: dict[str, str] = PriceSerializer(Price(amount=Decimal("12.5"))).data

    assert data["amount"] == "12.500"
