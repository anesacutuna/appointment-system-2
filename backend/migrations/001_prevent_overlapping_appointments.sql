CREATE EXTENSION IF NOT EXISTS btree_gist;

ALTER TABLE appointments
    ADD CONSTRAINT exclude_overlapping_active_appointments
    EXCLUDE USING gist (
        employee_id WITH =,
        tstzrange(start_at, end_at, '[)') WITH &&
    )
    WHERE (status <> 'cancelled');
