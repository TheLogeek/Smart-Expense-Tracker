from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

# Define the West Africa Timezone (WAT)
WAT = ZoneInfo("Africa/Lagos")
AFRICA_LAGOS_TZ = WAT # Alias for consistency with other parts of the codebase

def to_wat(dt_utc: datetime) -> datetime:
    """
    Converts a UTC datetime object to a timezone-aware WAT datetime object.
    If dt_utc is naive, it's assumed to be UTC.
    """
    if dt_utc.tzinfo is None:
        # Assume naive datetime is UTC
        dt_utc = dt_utc.replace(tzinfo=timezone.utc)
    return dt_utc.astimezone(WAT)

def wat_day_bounds_utc(date_obj: datetime = None) -> tuple[datetime, datetime]:
    """
    Calculates the UTC start and end bounds for a specific day in WAT.
    If date_obj is None, it uses the current WAT day.
    
    Returns:
        tuple[datetime, datetime]: (start_of_day_utc, start_of_next_day_utc)
    """
    if date_obj is None:
        now_wat = datetime.now(timezone.utc).astimezone(WAT)
    else:
        # If date_obj is naive, assume it's already in WAT for the user's intent
        if date_obj.tzinfo is None:
            date_obj = date_obj.replace(tzinfo=WAT)
        now_wat = date_obj.astimezone(WAT) # Ensure it's in WAT for start_of_day calculation

    start_today_wat = now_wat.replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    start_tomorrow_wat = start_today_wat + timedelta(days=1)
    
    return (
        start_today_wat.astimezone(timezone.utc),
        start_tomorrow_wat.astimezone(timezone.utc),
    )

def wat_week_bounds_utc(date_obj: datetime = None) -> tuple[datetime, datetime]:
    """
    Calculates the UTC start and end bounds for a specific week in WAT.
    Weeks start on Monday.
    """
    if date_obj is None:
        now_wat = datetime.now(timezone.utc).astimezone(WAT)
    else:
        if date_obj.tzinfo is None:
            date_obj = date_obj.replace(tzinfo=WAT)
        now_wat = date_obj.astimezone(WAT)

    # Monday is weekday 0
    start_this_week_wat = now_wat - timedelta(days=now_wat.weekday())
    start_this_week_wat = start_this_week_wat.replace(hour=0, minute=0, second=0, microsecond=0)
    start_next_week_wat = start_this_week_wat + timedelta(days=7)

    return (
        start_this_week_wat.astimezone(timezone.utc),
        start_next_week_wat.astimezone(timezone.utc),
    )

def wat_month_bounds_utc(date_obj: datetime = None) -> tuple[datetime, datetime]:
    """
    Calculates the UTC start and end bounds for a specific month in WAT.
    """
    if date_obj is None:
        now_wat = datetime.now(timezone.utc).astimezone(WAT)
    else:
        if date_obj.tzinfo is None:
            date_obj = date_obj.replace(tzinfo=WAT)
        now_wat = date_obj.astimezone(WAT)

    start_this_month_wat = now_wat.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    
    # Calculate start of next month
    if now_wat.month == 12:
        start_next_month_wat = now_wat.replace(year=now_wat.year + 1, month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
    else:
        start_next_month_wat = now_wat.replace(month=now_wat.month + 1, day=1, hour=0, minute=0, second=0, microsecond=0)
    
    return (
        start_this_month_wat.astimezone(timezone.utc),
        start_next_month_wat.astimezone(timezone.utc),
    )
