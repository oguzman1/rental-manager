from datetime import date

from adjustments import calculate_next_adjustment_date
from models import AdjustmentFrequency


def test_calculate_next_annual_adjustment_date():
    result = calculate_next_adjustment_date(
        start_date=date(2022, 3, 12),
        adjustment_frequency=AdjustmentFrequency.annual,
        today=date(2026, 1, 1),
    )

    assert result == date(2026, 3, 12)

def test_calculate_next_semiannual_adjustment_date():
    result = calculate_next_adjustment_date(
        start_date=date(2024, 8, 15),
        adjustment_frequency=AdjustmentFrequency.semiannual,
        today=date(2026, 1, 1),
    )

    assert result == date(2026, 2, 15)