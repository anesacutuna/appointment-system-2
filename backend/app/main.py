from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

from fastapi import Depends, FastAPI, HTTPException, Query, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.booking import available_starts, is_available
from app.config import settings
from app.database import Base, engine, get_db
from app.models import Appointment, AppointmentStatus, AvailabilityException, Employee, Service, User, UserRole, WorkingHours
from app.schemas import AppointmentCreate, AppointmentDetails, AppointmentOut, EmployeeInput, EmployeeOut, ExceptionInput, ExceptionOut, ServiceInput, ServiceOut, UserCreate, UserOut, WorkingHoursInput, WorkingHoursOut
from app.security import create_access_token, get_current_user, hash_password, require_admin, verify_password


Base.metadata.create_all(bind=engine)

app = FastAPI(title="Smart Appointment Booking and Management System", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_origin],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/auth/register", response_model=UserOut, status_code=201)
def register(payload: UserCreate, db: Session = Depends(get_db)):
    email = payload.email.lower()
    if db.scalar(select(User).where(User.email == email)):
        raise HTTPException(status_code=409, detail="An account with this email already exists")
    user = User(full_name=payload.full_name, email=email, password_hash=hash_password(payload.password), role=UserRole.client)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@app.post("/auth/token")
def login(form: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = db.scalar(select(User).where(User.email == form.username.lower()))
    if not user or not verify_password(form.password, user.password_hash) or not user.is_active:
        raise HTTPException(status_code=401, detail="Incorrect email or password")
    return {"access_token": create_access_token(user), "token_type": "bearer", "user": UserOut.model_validate(user)}


@app.get("/auth/me", response_model=UserOut)
def me(user: User = Depends(get_current_user)):
    return user


@app.get("/services", response_model=list[ServiceOut])
def list_services(db: Session = Depends(get_db)):
    return list(db.scalars(select(Service).where(Service.is_active.is_(True)).order_by(Service.name)))


@app.get("/employees", response_model=list[EmployeeOut])
def list_employees(db: Session = Depends(get_db)):
    return list(db.scalars(select(Employee).where(Employee.is_active.is_(True)).order_by(Employee.full_name)))


@app.get("/admin/services", response_model=list[ServiceOut])
def admin_list_services(db: Session = Depends(get_db), _: User = Depends(require_admin)):
    return list(db.scalars(select(Service).order_by(Service.name)))


@app.get("/admin/employees", response_model=list[EmployeeOut])
def admin_list_employees(db: Session = Depends(get_db), _: User = Depends(require_admin)):
    return list(db.scalars(select(Employee).order_by(Employee.full_name)))


@app.get("/availability")
def get_availability(
    service_id: int,
    employee_id: int,
    day: date = Query(alias="date"),
    db: Session = Depends(get_db),
):
    service, employee = db.get(Service, service_id), db.get(Employee, employee_id)
    if not service or not employee or not service.is_active or not employee.is_active:
        raise HTTPException(status_code=404, detail="Service or employee not found")
    return {"date": day.isoformat(), "timezone": settings.app_timezone, "duration_minutes": service.duration_minutes,
            "slots": [slot.isoformat() for slot in available_starts(db, employee, service, day)]}


@app.post("/appointments", response_model=AppointmentOut, status_code=201)
def create_appointment(payload: AppointmentCreate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    service, employee = db.get(Service, payload.service_id), db.get(Employee, payload.employee_id)
    if not service or not employee or not service.is_active or not employee.is_active:
        raise HTTPException(status_code=404, detail="Service or employee not found")
    if not is_available(db, employee, service, payload.start_at):
        raise HTTPException(status_code=409, detail="The selected time is no longer available")
    start_at = payload.start_at.astimezone(timezone.utc)
    appointment = Appointment(
        client_id=user.id,
        employee_id=employee.id,
        service_id=service.id,
        start_at=start_at,
        end_at=start_at + timedelta(minutes=service.duration_minutes),
        status=AppointmentStatus.booked,
    )
    db.add(appointment)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="The selected time was booked by another client")
    db.refresh(appointment)
    return appointment


@app.get("/appointments/me", response_model=list[AppointmentOut])
def my_appointments(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return list(db.scalars(select(Appointment).where(Appointment.client_id == user.id).order_by(Appointment.start_at.desc())))


@app.post("/appointments/{appointment_id}/cancel", response_model=AppointmentOut)
def cancel_appointment(appointment_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    appointment = db.get(Appointment, appointment_id)
    if not appointment or (appointment.client_id != user.id and user.role != UserRole.admin):
        raise HTTPException(status_code=404, detail="Appointment not found")
    if appointment.status == AppointmentStatus.cancelled:
        raise HTTPException(status_code=409, detail="Appointment is already cancelled")
    appointment.status = AppointmentStatus.cancelled
    db.commit()
    db.refresh(appointment)
    return appointment


@app.get("/admin/appointments", response_model=list[AppointmentDetails])
def admin_appointments(
    from_date: date | None = None,
    to_date: date | None = None,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    query = select(Appointment).order_by(Appointment.start_at)
    if from_date:
        query = query.where(Appointment.start_at >= datetime.combine(from_date, time.min, tzinfo=ZoneInfo(settings.app_timezone)).astimezone(timezone.utc))
    if to_date:
        query = query.where(Appointment.start_at < datetime.combine(to_date + timedelta(days=1), time.min, tzinfo=ZoneInfo(settings.app_timezone)).astimezone(timezone.utc))
    rows = db.scalars(query).all()
    return [AppointmentDetails(
        id=a.id, client_name=a.client.full_name, client_email=a.client.email,
        employee_name=a.employee.full_name, service_name=a.service.name,
        start_at=a.start_at, end_at=a.end_at, status=a.status,
    ) for a in rows]


@app.get("/admin/statistics")
def admin_statistics(db: Session = Depends(get_db), _: User = Depends(require_admin)):
    local_now = datetime.now(ZoneInfo(settings.app_timezone))
    today_start = datetime.combine(local_now.date(), time.min, tzinfo=ZoneInfo(settings.app_timezone)).astimezone(timezone.utc)
    tomorrow_start = datetime.combine(local_now.date() + timedelta(days=1), time.min, tzinfo=ZoneInfo(settings.app_timezone)).astimezone(timezone.utc)
    booked = Appointment.status == AppointmentStatus.booked
    return {
        "active_appointments": db.scalar(select(func.count()).select_from(Appointment).where(booked)) or 0,
        "today_appointments": db.scalar(select(func.count()).select_from(Appointment).where(booked, Appointment.start_at >= today_start, Appointment.start_at < tomorrow_start)) or 0,
        "upcoming_appointments": db.scalar(select(func.count()).select_from(Appointment).where(booked, Appointment.start_at >= datetime.now(timezone.utc))) or 0,
        "cancelled_appointments": db.scalar(select(func.count()).select_from(Appointment).where(Appointment.status == AppointmentStatus.cancelled)) or 0,
    }


@app.post("/admin/services", response_model=ServiceOut, status_code=201)
def create_service(payload: ServiceInput, db: Session = Depends(get_db), _: User = Depends(require_admin)):
    service = Service(**payload.model_dump())
    db.add(service)
    db.commit()
    db.refresh(service)
    return service


@app.patch("/admin/services/{service_id}", response_model=ServiceOut)
def update_service(service_id: int, payload: ServiceInput, db: Session = Depends(get_db), _: User = Depends(require_admin)):
    service = db.get(Service, service_id)
    if not service:
        raise HTTPException(status_code=404, detail="Service not found")
    for key, value in payload.model_dump().items():
        setattr(service, key, value)
    db.commit()
    db.refresh(service)
    return service


@app.post("/admin/employees", response_model=EmployeeOut, status_code=201)
def create_employee(payload: EmployeeInput, db: Session = Depends(get_db), _: User = Depends(require_admin)):
    employee = Employee(**payload.model_dump())
    db.add(employee)
    db.commit()
    db.refresh(employee)
    return employee


@app.patch("/admin/employees/{employee_id}", response_model=EmployeeOut)
def update_employee(employee_id: int, payload: EmployeeInput, db: Session = Depends(get_db), _: User = Depends(require_admin)):
    employee = db.get(Employee, employee_id)
    if not employee:
        raise HTTPException(status_code=404, detail="Employee not found")
    for key, value in payload.model_dump().items():
        setattr(employee, key, value)
    db.commit()
    db.refresh(employee)
    return employee


@app.get("/admin/employees/{employee_id}/working-hours", response_model=list[WorkingHoursOut])
def get_working_hours(employee_id: int, db: Session = Depends(get_db), _: User = Depends(require_admin)):
    if not db.get(Employee, employee_id):
        raise HTTPException(status_code=404, detail="Employee not found")
    return list(db.scalars(select(WorkingHours).where(WorkingHours.employee_id == employee_id).order_by(WorkingHours.weekday)))


@app.put("/admin/employees/{employee_id}/working-hours", response_model=WorkingHoursOut)
def set_working_hours(employee_id: int, payload: WorkingHoursInput, db: Session = Depends(get_db), _: User = Depends(require_admin)):
    if not db.get(Employee, employee_id):
        raise HTTPException(status_code=404, detail="Employee not found")
    hours = db.scalar(select(WorkingHours).where(WorkingHours.employee_id == employee_id, WorkingHours.weekday == payload.weekday))
    if hours is None:
        hours = WorkingHours(employee_id=employee_id, **payload.model_dump())
        db.add(hours)
    else:
        for key, value in payload.model_dump().items():
            setattr(hours, key, value)
    db.commit()
    db.refresh(hours)
    return hours


@app.post("/admin/employees/{employee_id}/exceptions", response_model=ExceptionOut, status_code=201)
def create_exception(employee_id: int, payload: ExceptionInput, db: Session = Depends(get_db), _: User = Depends(require_admin)):
    if not db.get(Employee, employee_id):
        raise HTTPException(status_code=404, detail="Employee not found")
    exception = AvailabilityException(employee_id=employee_id, **payload.model_dump())
    db.add(exception)
    db.commit()
    db.refresh(exception)
    return exception


@app.delete("/admin/exceptions/{exception_id}", status_code=204)
def delete_exception(exception_id: int, db: Session = Depends(get_db), _: User = Depends(require_admin)):
    exception = db.get(AvailabilityException, exception_id)
    if not exception:
        raise HTTPException(status_code=404, detail="Availability exception not found")
    db.delete(exception)
    db.commit()
