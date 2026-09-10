"""Small date helpers shared by the orchestrator and Cost Estimator tools."""

from datetime import date, datetime


def add_months(reference_date: date, months: int) -> date:
    total_month_index = reference_date.month - 1 + months
    year = reference_date.year + total_month_index // 12
    month = total_month_index % 12 + 1
    day = min(reference_date.day, 28)  # sidesteps invalid dates (e.g. Feb 30)
    return date(year, month, day)


def parse_date(value: str) -> date:
    return datetime.strptime(value, "%Y-%m-%d").date()


def age_years(install_date: date, as_of: date) -> float:
    return (as_of - install_date).days / 365.25
