from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session

from app.config import settings
from app.models import Appointment, AppointmentStatus, AvailabilityException, Employee, Service, WorkingHours


SLOT_STEP_MINUTES = 15


def _local_interval(day: date, start: time, end: time) -> tuple[datetime, datetime]:
    zone = ZoneInfo(settings.app_timezone)
    start_at = datetime.combine(day, start, tzinfo=zone)
    end_at = datetime.combine(day, end, tzinfo=zone)
    return start_at.astimezone(timezone.utc), end_at.astimezone(timezone.utc)


def available_starts(db: Session, employee: Employee, service: Service, day: date) -> list[datetime]:
    """Return UTC-aware starts that fit working hours and do not overlap a booking."""
    if not employee.is_active or not service.is_active or day < datetime.now(ZoneInfo(settings.app_timezone)).date():
        return []

    exception = db.scalar(select(AvailabilityException).where(
        AvailabilityException.employee_id == employee.id,
        AvailabilityException.exception_date == day,
    ))

    if exception:
        if exception.is_closed:
            return []
        intervals = [(exception.start_time, exception.end_time)]
    else:
        regular = db.scalar(select(WorkingHours).where(
            WorkingHours.employee_id == employee.id,
            WorkingHours.weekday == day.weekday(),
        ))
        if not regular or not regular.is_working:
            return []
        intervals = [(regular.start_time, regular.end_time)]

    duration = timedelta(minutes=service.duration_minutes)
    step = timedelta(minutes=SLOT_STEP_MINUTES)
    day_start, day_end = _local_interval(day, time.min, time.max)
    booked = list(db.scalars(select(Appointment).where(
        Appointment.employee_id == employee.id,
        Appointment.status != AppointmentStatus.cancelled,
        Appointment.start_at < day_end,
        Appointment.end_at > day_start,
    )))

    starts: list[datetime] = []
    for opens, closes in intervals:
        window_start, window_end = _local_interval(day, opens, closes)
        candidate = window_start
        while candidate + duration <= window_end:
            candidate_end = candidate + duration
            if not any(candidate < appointment.end_at and candidate_end > appointment.start_at for appointment in booked):
                starts.append(candidate)
            candidate += step
    return starts


def is_available(db: Session, employee: Employee, service: Service, start_at: datetime) -> bool:
    if start_at.tzinfo is None:
        return False
    local_start = start_at.astimezone(ZoneInfo(settings.app_timezone))
    day_slots = available_starts(db, employee, service, local_start.date())
    return start_at.astimezone(timezone.utc) in day_slots
