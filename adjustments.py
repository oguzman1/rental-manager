from calendar import monthrange
from datetime import date, timedelta

from models import AdjustmentFrequency




# Suma meses a una fecha, cuidando meses con distinta cantidad de días.
def add_months(base_date: date, months: int) -> date:
    month = base_date.month - 1 + months
    year = base_date.year + month // 12
    month = month % 12 + 1

    # Evita fechas inválidas como 31 de febrero.
    day = min(base_date.day, monthrange(year, month)[1])

    return date(year, month, day)


# Calcula la próxima fecha futura de reajuste según frecuencia.
def calculate_next_adjustment_date(
    start_date: date,
    adjustment_frequency: AdjustmentFrequency,
    today: date | None = None,
) -> date:
    current_day = today or date.today()

    if adjustment_frequency == AdjustmentFrequency.annual:
        months_to_add = 12
    else:
        months_to_add = 6

    next_date = start_date

    while next_date <= current_day:
        next_date = add_months(next_date, months_to_add)

    return next_date

# Calcula la fecha de aviso de reajuste según notice_days del contrato.
# notice_days <= 0 o None → fallback a 30 días.
def calculate_adjustment_notice_date(
    adjustment_date: date,
    notice_days: int | None = None,
) -> date:
    days = notice_days if notice_days is not None and notice_days > 0 else 30
    return adjustment_date - timedelta(days=days)


def months_between(earlier: date, later: date) -> int:
    """Diferencia en meses calendario: (año*12 + mes) de later menos earlier.
    Ignora el día del mes; útil para métricas operativas de display."""
    return (later.year - earlier.year) * 12 + (later.month - earlier.month)


def calculate_due_adjustment_date(
    start_date: date,
    adjustment_frequency: AdjustmentFrequency,
    today: date,
) -> date:
    """Retorna la fecha programada del ciclo actual de reajuste.
    El primer reajuste es un ciclo completo después de start_date.
    Si esa fecha ya pasó y no se aplicó, retorna la fecha vencida (puede ser pasado).
    months_between(today, resultado) < 0 indica reajuste atrasado."""
    months_to_add = 12 if adjustment_frequency == AdjustmentFrequency.annual else 6
    due = add_months(start_date, months_to_add)
    if due > today:
        return due
    prev = due
    while True:
        next_d = add_months(prev, months_to_add)
        if next_d > today:
            return prev
        prev = next_d