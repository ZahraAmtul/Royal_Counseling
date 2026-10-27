from datetime import datetime, timedelta, date, time
from typing import Dict, List, Optional, Tuple

from django.conf import settings
from django.utils import timezone

from .models import Counselor, Availability, Appointment, Service

BUFFER_MINUTES = 10          # gap kept before/after every booked appointment
ACTIVE_STATUSES = ['pending', 'confirmed']


def local_now() -> datetime:
    """Current time in settings.TIME_ZONE (Asia/Karachi), as a naive datetime."""
    if settings.USE_TZ:
        return timezone.localtime().replace(tzinfo=None)
    return datetime.now()


def local_today() -> date:
    return local_now().date()


def _slots_for_day(
    selected_date: date,
    windows: List[Tuple[time, time]],
    booked: List[Tuple[time, time]],
    duration: int,
    buffer_minutes: int,
    now: datetime,
) -> List[Tuple[time, time]]:
    """Pure slot calculation for one day (no database access)."""
    if selected_date < now.date():
        return []

    step = timedelta(minutes=duration + buffer_minutes)
    length = timedelta(minutes=duration)
    buffer = timedelta(minutes=buffer_minutes)
    # Booked appointments as full datetimes, widened by the buffer (no midnight wrap-around)
    blocked = [
        (datetime.combine(selected_date, s) - buffer, datetime.combine(selected_date, e) + buffer)
        for s, e in booked
    ]

    slots = []
    for window_start, window_end in sorted(windows):
        current = datetime.combine(selected_date, window_start)
        end = datetime.combine(selected_date, window_end)
        while current + length <= end:
            slot_end = current + length
            overlaps = any(current < b_end and slot_end > b_start for b_start, b_end in blocked)
            if not overlaps and current > now:
                slots.append((current.time(), slot_end.time()))
            current += step
    return slots


def get_available_slots(
    counselor: Counselor,
    selected_date: date,
    service: Service,
    buffer_minutes: int = BUFFER_MINUTES,
) -> List[Tuple[time, time]]:
    """Open (start, end) slots for a counselor on one date, in Pakistan time."""
    windows = list(
        Availability.objects.filter(counselor=counselor, day_of_week=selected_date.weekday())
        .values_list('start_time', 'end_time')
    )
    if not windows:
        return []
    booked = list(
        Appointment.objects.filter(
            counselor=counselor, appointment_date=selected_date, status__in=ACTIVE_STATUSES
        ).values_list('start_time', 'end_time')
    )
    return _slots_for_day(selected_date, windows, booked, service.duration_minutes, buffer_minutes, local_now())


def get_counselor_available_dates(
    counselor: Counselor,
    days_ahead: int = 30,
    service: Optional[Service] = None,
    buffer_minutes: int = BUFFER_MINUTES,
) -> List[date]:
    """
    Dates in the next `days_ahead` days that still have at least one open slot
    (fully booked days and days already over are left out). Two queries in total.
    """
    now = local_now()
    today = now.date()
    last_day = today + timedelta(days=days_ahead - 1)

    windows_by_day: Dict[int, List[Tuple[time, time]]] = {}
    for day, start, end in Availability.objects.filter(counselor=counselor).values_list(
        'day_of_week', 'start_time', 'end_time'
    ):
        windows_by_day.setdefault(day, []).append((start, end))
    if not windows_by_day:
        return []

    booked_by_date: Dict[date, List[Tuple[time, time]]] = {}
    for appt_date, start, end in Appointment.objects.filter(
        counselor=counselor,
        appointment_date__range=(today, last_day),
        status__in=ACTIVE_STATUSES,
    ).values_list('appointment_date', 'start_time', 'end_time'):
        booked_by_date.setdefault(appt_date, []).append((start, end))

    # Without a service, assume the shortest possible session.
    duration = service.duration_minutes if service else 15

    available = []
    for i in range(days_ahead):
        day = today + timedelta(days=i)
        windows = windows_by_day.get(day.weekday())
        if windows and _slots_for_day(day, windows, booked_by_date.get(day, []), duration, buffer_minutes, now):
            available.append(day)
    return available


def is_slot_available(
    counselor: Counselor,
    selected_date: date,
    start_time: time,
    service: Service,
) -> bool:
    """Re-check a slot right before saving (handles two people booking at once)."""
    return any(slot[0] == start_time for slot in get_available_slots(counselor, selected_date, service))
