CREATE TABLE rules (
    id SERIAL PRIMARY KEY,
    name TEXT,
    sensor TEXT,
    attribute TEXT,
    operator TEXT,
    threshold TEXT,
    actuator TEXT,
    action TEXT,
    enabled BOOLEAN DEFAULT true,
    last_triggered TIMESTAMPTZ
);