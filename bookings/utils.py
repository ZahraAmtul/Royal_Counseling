from datetime import datetime, timedelta, date, time
from typing import List, Tuple
from .models import Counselor, Availability, Appointment, Service


def get_available_slots(
    counselor: Counselor, 
    selected_date: date, 
    service: Service,
    buffer_minutes: int = 10
) -> List[Tuple[time, time]]:
    """
    Generate available time slots for a counselor on a specific date.
    
    Args:
        counselor: The counselor to check availability for
        selected_date: The date to check
        service: The service being booked (determines slot duration)
        buffer_minutes: Buffer time between appointments
    
    Returns:
        List of (start_time, end_time) tuples representing available slots
    """
    # Get day of week (0=Monday, 6=Sunday)
    day_of_week = selected_date.weekday()
    
    # Get counselor's availability for this day
    availabilities = Availability.objects.filter(
        counselor=counselor,
        day_of_week=day_of_week
    )
    
    if not availabilities.exists():
        return []
    
    # Get existing appointments for this counselor on this date
    existing_appointments = Appointment.objects.filter(
        counselor=counselor,
        appointment_date=selected_date,
        status__in=['pending', 'confirmed']
    ).values_list('start_time', 'end_time')
    
    booked_slots = [(apt[0], apt[1]) for apt in existing_appointments]
    
    available_slots = []
    slot_duration = service.duration_minutes
    
    for availability in availabilities:
        current_time = datetime.combine(selected_date, availability.start_time)
        end_time = datetime.combine(selected_date, availability.end_time)
        
        while current_time + timedelta(minutes=slot_duration) <= end_time:
            slot_start = current_time.time()
            slot_end = (current_time + timedelta(minutes=slot_duration)).time()
            
            # Check if this slot overlaps with any booked appointment
            is_available = True
            for booked_start, booked_end in booked_slots:
                # Add buffer to booked slots
                booked_start_with_buffer = (
                    datetime.combine(selected_date, booked_start) - timedelta(minutes=buffer_minutes)
                ).time()
                booked_end_with_buffer = (
                    datetime.combine(selected_date, booked_end) + timedelta(minutes=buffer_minutes)
                ).time()
                
                # Check overlap
                if not (slot_end <= booked_start_with_buffer or slot_start >= booked_end_with_buffer):
                    is_available = False
                    break
            
            if is_available:
                # Don't show past slots for today
                if selected_date == date.today():
                    if slot_start > datetime.now().time():
                        available_slots.append((slot_start, slot_end))
                else:
                    available_slots.append((slot_start, slot_end))
            
            # Move to next potential slot
            current_time += timedelta(minutes=slot_duration + buffer_minutes)
    
    return available_slots


def get_counselor_available_dates(
    counselor: Counselor, 
    days_ahead: int = 30
) -> List[date]:
    """
    Get list of dates where counselor has availability in the next X days.
    """
    available_dates = []
    today = date.today()
    
    # Get all days of week where counselor has availability
    available_days = Availability.objects.filter(
        counselor=counselor
    ).values_list('day_of_week', flat=True).distinct()
    
    for i in range(days_ahead):
        check_date = today + timedelta(days=i)
        if check_date.weekday() in available_days:
            available_dates.append(check_date)
    
    return available_dates


def is_slot_available(
    counselor: Counselor,
    selected_date: date,
    start_time: time,
    service: Service
) -> bool:
    """
    Check if a specific slot is still available (for race condition handling).
    """
    available_slots = get_available_slots(counselor, selected_date, service)
    return any(slot[0] == start_time for slot in available_slots)
