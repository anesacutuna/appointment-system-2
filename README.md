# Smart Appointment Booking and Management System

Web-based appointment booking and management system for one configurable service organization.

## Stack

- Frontend: React + Vite
- Backend: FastAPI + SQLAlchemy
- Database: PostgreSQL
- Authentication: signed JWT access tokens and Argon2 password hashes
- Organization-local appointment timezone: `Europe/Sarajevo` by default

## First-version scope

Clients can register, sign in, browse active services and employees, view available appointment starts, book appointments, review their appointments, and cancel them. Administrators can review all appointments and manage services, employees, working hours, and availability exceptions. Payments, SMS, and a mobile application are outside the first version.

## Start the backend

1. Create a PostgreSQL database and copy `backend/.env.example` to `backend/.env`.
2. From `backend/`, create a virtual environment and install `requirements.txt`.
3. Start the API with `uvicorn app.main:app --reload`.
4. Open `/docs` on the API host to use the generated API documentation.
5. Apply `backend/migrations/001_prevent_overlapping_appointments.sql` to enable PostgreSQL's database-level overlap protection.
6. Add neutral demonstration service and employee records with `python -m app.seed` from `backend/`.

The application creates its SQLAlchemy tables on startup for this initial prototype. The SQL migration adds the exclusion constraint that cannot be represented portably across database engines. A later thesis iteration can replace startup table creation with versioned Alembic migrations.

## Start the frontend

From `frontend/`, run `npm install` and `npm run dev`. Set `VITE_API_URL` to the backend base URL if it is not `http://localhost:8000`.

## Initial administrator

Public registration always creates a client. Create an administrator deliberately using a one-time database update after registering the account:

```sql
UPDATE users SET role = 'admin' WHERE email = 'admin@example.com';
```

Do not expose administrator role selection in the public registration form.

## Booking rules

- Availability is computed for a service, employee, and local calendar date.
- Slot starts advance in 15-minute increments; appointment length comes from the selected service.
- An appointment must fit inside working hours or an approved custom-hours exception.
- Closed-day exceptions override regular working hours.
- Cancelled appointments do not block a slot.
- The API checks availability before creating an appointment. PostgreSQL also rejects overlapping active appointments for the same employee, so concurrent requests cannot both reserve the same time.
- Time intervals are half-open (`[start, end)`): one appointment may end exactly when the next begins.

## Domain entities

`User`, `Service`, `Employee`, `WorkingHours`, `Appointment`, and `AvailabilityException`. Appointments connect one client, one employee, and one service. Availability exceptions can close a whole date or replace an employee's regular hours for that date.

## Thesis alignment

The implementation is organized to support the planned System Analysis, Application Design, Implementation, System Testing, and Maintenance Analysis chapters. The API's OpenAPI schema also provides a concrete basis for sequence diagrams and integration documentation. The booking algorithm and database overlap constraint are central technical contributions to explain and evaluate.
