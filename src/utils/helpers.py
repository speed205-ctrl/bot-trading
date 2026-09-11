"""General helper functions for Strategy Lab."""
from datetime import datetime
from typing import Union
import pandas as pd


def parse_date(date_val: Union[str, datetime, pd.Timestamp]) -> pd.Timestamp:
    """Parses various date formats to a consistent pandas Timestamp (UTC)."""
    ts = pd.to_datetime(date_val, utc=True)
    return ts


def to_milliseconds(date_val: Union[str, datetime, pd.Timestamp]) -> int:
    """Converts a date to UTC milliseconds timestamp."""
    ts = parse_date(date_val)
    return int(ts.timestamp() * 1000)


def format_pct(val: float, decimals: int = 2) -> str:
    """Formats float to percentage string, e.g., 0.1234 -> '12.34%'."""
    if pd.isna(val) or val is None:
        return "N/A"
    return f"{val * 100:.{decimals}f}%"


def format_currency(val: float, decimals: int = 2, symbol: str = "$") -> str:
    """Formats number to currency string, e.g., 12345.67 -> '$12,345.67'."""
    if pd.isna(val) or val is None:
        return "N/A"
    return f"{symbol}{val:,.{decimals}f}"


def safe_div(num: float, den: float, default: float = 0.0) -> float:
    """Performs safe division avoiding ZeroDivisionError or NaN."""
    if den == 0.0 or pd.isna(den) or pd.isna(num):
        return default
    return num / den
