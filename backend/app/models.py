from datetime import date, datetime, time
from enum import Enum

from sqlalchemy import Boolean, CheckConstraint, Date, DateTime, Enum as SqlEnum, ForeignKey, Integer, String, Text, Time, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class UserRole(str, Enum):
    client = "client"
    admin = "admin"


class AppointmentStatus(str, Enum):
    booked = "booked"
    cancelled = "cancelled"


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    full_name: Mapped[str] = mapped_column(String(120))
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[UserRole] = mapped_column(SqlEnum(UserRole), default=UserRole.client)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    appointments: Mapped[list["Appointment"]] = relationship(back_populates="client")


class Service(Base):
    __tablename__ = "services"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(140), unique=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    duration_minutes: Mapped[int] = mapped_column(Integer)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    appointments: Mapped[list["Appointment"]] = relationship(back_populates="service")


class Employee(Base):
    __tablename__ = "employees"

    id: Mapped[int] = mapped_column(primary_key=True)
    full_name: Mapped[str] = mapped_column(String(120))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    working_hours: Mapped[list["WorkingHours"]] = relationship(back_populates="employee", cascade="all, delete-orphan")
    appointments: Mapped[list["Appointment"]] = relationship(back_populates="employee")
    exceptions: Mapped[list["AvailabilityException"]] = relationship(back_populates="employee", cascade="all, delete-orphan")


class WorkingHours(Base):
    __tablename__ = "working_hours"
    __table_args__ = (UniqueConstraint("employee_id", "weekday", name="uq_working_hours_employee_weekday"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    employee_id: Mapped[int] = mapped_column(ForeignKey("employees.id", ondelete="CASCADE"), index=True)
    weekday: Mapped[int] = mapped_column(Integer)  # Monday=0 ... Sunday=6
    start_time: Mapped[time] = mapped_column(Time)
    end_time: Mapped[time] = mapped_column(Time)
    is_working: Mapped[bool] = mapped_column(Boolean, default=True)
    employee: Mapped[Employee] = relationship(back_populates="working_hours")


class AvailabilityException(Base):
    __tablename__ = "availability_exceptions"
    __table_args__ = (UniqueConstraint("employee_id", "exception_date", name="uq_exception_employee_date"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    employee_id: Mapped[int] = mapped_column(ForeignKey("employees.id", ondelete="CASCADE"), index=True)
    exception_date: Mapped[date] = mapped_column(Date, index=True)
    is_closed: Mapped[bool] = mapped_column(Boolean, default=True)
    start_time: Mapped[time | None] = mapped_column(Time, nullable=True)
    end_time: Mapped[time | None] = mapped_column(Time, nullable=True)
    note: Mapped[str | None] = mapped_column(String(250), nullable=True)
    employee: Mapped[Employee] = relationship(back_populates="exceptions")


class Appointment(Base):
    __tablename__ = "appointments"
    __table_args__ = (CheckConstraint("end_at > start_at", name="ck_appointment_end_after_start"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    client_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    employee_id: Mapped[int] = mapped_column(ForeignKey("employees.id"), index=True)
    service_id: Mapped[int] = mapped_column(ForeignKey("services.id"), index=True)
    start_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    end_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    status: Mapped[AppointmentStatus] = mapped_column(SqlEnum(AppointmentStatus), default=AppointmentStatus.booked, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    client: Mapped[User] = relationship(back_populates="appointments")
    employee: Mapped[Employee] = relationship(back_populates="appointments")
    service: Mapped[Service] = relationship(back_populates="appointments")
