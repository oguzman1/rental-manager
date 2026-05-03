from datetime import date

from adjustments import calculate_adjustment_notice_date, calculate_next_adjustment_date
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


def test_calculate_adjustment_notice_date_60_days():
    # 2027-01-01 - 60 days = 2026-11-02
    result = calculate_adjustment_notice_date(date(2027, 1, 1), notice_days=60)
    assert result == date(2026, 11, 2)


def test_calculate_adjustment_notice_date_default_30_days():
    # no notice_days supplied → fallback to 30; 2027-01-01 - 30 days = 2026-12-02
    result = calculate_adjustment_notice_date(date(2027, 1, 1))
    assert result == date(2026, 12, 2)


def test_calculate_adjustment_notice_date_zero_falls_back_to_30():
    # notice_days=0 is treated as missing → fallback to 30
    result = calculate_adjustment_notice_date(date(2027, 1, 1), notice_days=0)
    assert result == date(2026, 12, 2)

