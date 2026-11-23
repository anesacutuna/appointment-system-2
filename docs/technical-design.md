# Technical Design Baseline

## System boundary

The first version serves one configurable service organization. It supports client and administrator accounts, services, employees, weekly working hours, date-specific availability exceptions, and appointments. It does not process payments, send SMS messages, or provide a native mobile application.

## Actors and responsibilities

| Actor | Responsibilities |
| --- | --- |
| Visitor | Browse active services and employees; view available starts. |
| Client | Register, sign in, create and review personal appointments, cancel a personal appointment. |
| Administrator | Review all appointments; manage services and employees; set weekly hours and date exceptions. |

## Core functional requirements

1. The system allows a visitor to register with an email and password. Public registration always creates a client role.
2. The system authenticates users and distinguishes client and administrator permissions.
3. The system lists active services with their duration and active employees.
4. The system calculates available starts from the selected employee's working hours, service duration, exceptions, and existing appointments.
5. A client can reserve only an available start and can see and cancel their own appointments.
6. An administrator can review appointments and manage service, employee, working-hours, and exception records.
7. The system rejects overlapping active appointments for the same employee.

## Core nonfunctional requirements

- **Consistency:** the database is the authority for appointment persistence and overlap prevention.
- **Security:** passwords are stored as Argon2 hashes; protected API routes use signed bearer tokens; client registration cannot assign administrator privileges.
- **Privacy:** clients can read or cancel only their own appointments; the administrator can view all appointment details.
- **Usability:** the client booking flow exposes service, employee, date, and available starts before confirmation.
- **Maintainability:** frontend, API, domain models, and booking rules are separated into distinct modules.
- **Time correctness:** working hours are interpreted in the organization's configured IANA timezone and appointment timestamps are stored as timezone-aware instants.

## Data model

| Entity | Main attributes | Relationship / rule |
| --- | --- | --- |
| User | id, full_name, email, password_hash, role, is_active | One client can have many appointments. |
| Service | id, name, description, duration_minutes, is_active | One service can be used by many appointments. |
| Employee | id, full_name, is_active | Has weekly hours, date exceptions, and appointments. |
| WorkingHours | employee_id, weekday, start_time, end_time, is_working | At most one row per employee and weekday. |
| AvailabilityException | employee_id, exception_date, is_closed, optional start_time/end_time | At most one exception per employee and date; may close or override hours. |
| Appointment | client_id, employee_id, service_id, start_at, end_at, status | Connects one client, employee, and service; cancelled records do not block time. |

## Availability algorithm

1. Load the active employee and service and determine the organization's local date.
2. Check for an availability exception. A closed-day exception returns no starts. A custom-hours exception replaces that day's usual hours.
3. If no exception exists, load the employee's weekly hours for that weekday. A missing or non-working record returns no starts.
4. Convert the resulting local opening and closing times to timezone-aware instants.
5. Load active appointments that intersect that local workday.
6. Starting at opening time, generate candidates at 15-minute increments. Keep a candidate only when `candidate + service duration <= closing time` and its half-open interval does not intersect a booked appointment.
7. Before saving a booking, the API recalculates availability. The database exclusion constraint independently rejects concurrent overlapping inserts for the same employee.

Intervals use `[start, end)`. Therefore, a 10:00–10:30 booking and a 10:30–11:00 booking do not overlap.

## API outline

| Area | Routes |
| --- | --- |
| Authentication | `POST /auth/register`, `POST /auth/token`, `GET /auth/me` |
| Public catalogue | `GET /services`, `GET /employees`, `GET /availability` |
| Client bookings | `POST /appointments`, `GET /appointments/me`, `POST /appointments/{id}/cancel` |
| Administration | `GET /admin/appointments`, service and employee create/update routes, working-hours and exception routes |

## Key design decision: overlap prevention

An API-only availability check has a race condition: two clients may request the same time before either transaction commits. PostgreSQL's GiST exclusion constraint on `employee_id` and `tstzrange(start_at, end_at, '[)')` makes the database reject the second overlapping active appointment. The API translates that constraint failure into HTTP 409 Conflict.

## Design diagrams

### Use cases

```mermaid
flowchart TD
    Visitor[Visitor] --> Browse[Browse services and employees]
    Visitor --> Check[Check available starts]
    Client[Client] --> Register[Register and sign in]
    Client --> Book[Create appointment]
    Client --> Own[Review or cancel own appointments]
    Admin[Administrator] --> All[Review all appointments]
    Admin --> Manage[Manage services and employees]
    Admin --> Schedule[Manage hours and exceptions]
    Check --> Book
```

### Booking activity

```mermaid
flowchart TD
    A[Select service, employee, date] --> B{Working hours or exception exists?}
    B -->|No| X[Show no available starts]
    B -->|Yes| C[Generate starts using service duration]
    C --> D[Remove starts that overlap appointments]
    D --> E[Client selects a start]
    E --> F[API recalculates availability]
    F --> G{Still available?}
    G -->|No| X
    G -->|Yes| H[Insert appointment]
    H --> I{Database overlap constraint passes?}
    I -->|No| X
    I -->|Yes| J[Confirm appointment]
```

### Booking sequence

```mermaid
sequenceDiagram
    actor Client
    participant Web as React application
    participant API as FastAPI
    participant DB as PostgreSQL
    Client->>Web: Select service, employee and date
    Web->>API: GET /availability
    API->>DB: Read hours, exceptions and active appointments
    DB-->>API: Schedule data
    API-->>Web: Available starts
    Client->>Web: Confirm a start
    Web->>API: POST /appointments with bearer token
    API->>DB: Recheck and insert appointment
    DB-->>API: Saved or overlap conflict
    API-->>Web: Appointment or HTTP 409
    Web-->>Client: Show confirmation or choose another start
```

### Entity relationships

```mermaid
erDiagram
    USER ||--o{ APPOINTMENT : books
    EMPLOYEE ||--o{ APPOINTMENT : serves
    SERVICE ||--o{ APPOINTMENT : defines
    EMPLOYEE ||--o{ WORKING_HOURS : has
    EMPLOYEE ||--o{ AVAILABILITY_EXCEPTION : overrides
    USER {
        int id PK
        string full_name
        string email UK
        string password_hash
        string role
    }
    EMPLOYEE {
        int id PK
        string full_name
        boolean is_active
    }
    SERVICE {
        int id PK
        string name
        int duration_minutes
        boolean is_active
    }
    WORKING_HOURS {
        int id PK
        int employee_id FK
        int weekday
        time start_time
        time end_time
    }
    AVAILABILITY_EXCEPTION {
        int id PK
        int employee_id FK
        date exception_date
        boolean is_closed
    }
    APPOINTMENT {
        int id PK
        int client_id FK
        int employee_id FK
        int service_id FK
        datetime start_at
        datetime end_at
        string status
    }
```

### Domain class diagram

```mermaid
classDiagram
    class User {
      +id: int
      +full_name: string
      +email: string
      +role: UserRole
      +is_active: bool
    }
    class Service {
      +id: int
      +name: string
      +duration_minutes: int
      +is_active: bool
    }
    class Employee {
      +id: int
      +full_name: string
      +is_active: bool
    }
    class WorkingHours {
      +weekday: int
      +start_time: time
      +end_time: time
      +is_working: bool
    }
    class AvailabilityException {
      +exception_date: date
      +is_closed: bool
      +start_time: time
      +end_time: time
    }
    class Appointment {
      +start_at: datetime
      +end_at: datetime
      +status: AppointmentStatus
    }
    User "1" --> "0..*" Appointment : books
    Employee "1" --> "0..*" Appointment : assigned to
    Service "1" --> "0..*" Appointment : selected for
    Employee "1" --> "0..*" WorkingHours : follows
    Employee "1" --> "0..*" AvailabilityException : has
```

## Planned evaluation evidence

The project can demonstrate success by creating a booking and showing it in the administrator view, rejecting an occupied start, allowing back-to-back non-overlapping starts, excluding cancelled appointments from availability, and applying regular hours and date exceptions. Functional and integration test cases should later be documented and executed against the agreed requirements.
