"""Add neutral demonstration data to an empty database: python -m app.seed."""

from datetime import time

from sqlalchemy import select

from app.database import SessionLocal
from app.models import Employee, Service, WorkingHours


def seed():
    with SessionLocal() as db:
        if not db.scalar(select(Service.id).limit(1)):
            db.add(Service(name="Standardna usluga", description="Primjer usluge; administrator može promijeniti naziv i trajanje.", duration_minutes=30))
        if not db.scalar(select(Employee.id).limit(1)):
            employee = Employee(full_name="Zaposlenik 1")
            employee.working_hours = [WorkingHours(weekday=weekday, start_time=time(9), end_time=time(17), is_working=True) for weekday in range(5)]
            db.add(employee)
        db.commit()


if __name__ == "__main__":
    seed()
