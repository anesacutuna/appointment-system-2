from datetime import date, datetime, time

from pydantic import BaseModel, ConfigDict, EmailStr, Field, model_validator

from app.models import AppointmentStatus, UserRole


class UserCreate(BaseModel):
    full_name: str = Field(min_length=2, max_length=120)
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)


class UserOut(BaseModel):
    id: int
    full_name: str
    email: EmailStr
    role: UserRole
    model_config = ConfigDict(from_attributes=True)


class ServiceInput(BaseModel):
    name: str = Field(min_length=2, max_length=140)
    description: str | None = None
    duration_minutes: int = Field(ge=5, le=480)
    is_active: bool = True


class ServiceOut(ServiceInput):
    id: int
    model_config = ConfigDict(from_attributes=True)


class EmployeeInput(BaseModel):
    full_name: str = Field(min_length=2, max_length=120)
    is_active: bool = True


class EmployeeOut(EmployeeInput):
    id: int
    model_config = ConfigDict(from_attributes=True)


class WorkingHoursInput(BaseModel):
    weekday: int = Field(ge=0, le=6)
    start_time: time
    end_time: time
    is_working: bool = True

    @model_validator(mode="after")
    def end_after_start(self):
        if self.is_working and self.end_time <= self.start_time:
            raise ValueError("End time must be after start time")
        return self


class WorkingHoursOut(WorkingHoursInput):
    id: int
    employee_id: int
    model_config = ConfigDict(from_attributes=True)


class ExceptionInput(BaseModel):
    exception_date: date
    is_closed: bool = True
    start_time: time | None = None
    end_time: time | None = None
    note: str | None = Field(default=None, max_length=250)

    @model_validator(mode="after")
    def validate_override(self):
        if not self.is_closed and (self.start_time is None or self.end_time is None):
            raise ValueError("Custom opening hours require start_time and end_time")
        if not self.is_closed and self.end_time <= self.start_time:
            raise ValueError("End time must be after start time")
        return self


class ExceptionOut(ExceptionInput):
    id: int
    employee_id: int
    model_config = ConfigDict(from_attributes=True)


class AppointmentCreate(BaseModel):
    service_id: int
    employee_id: int
    start_at: datetime


class AppointmentOut(BaseModel):
    id: int
    client_id: int
    employee_id: int
    service_id: int
    start_at: datetime
    end_at: datetime
    status: AppointmentStatus
    model_config = ConfigDict(from_attributes=True)


class AppointmentDetails(BaseModel):
    id: int
    client_name: str
    client_email: EmailStr
    employee_name: str
    service_name: str
    start_at: datetime
    end_at: datetime
    status: AppointmentStatus
