CREATE TABLE rules (
    id SERIAL PRIMARY KEY,
    sensor TEXT,
    attribute TEXT,
    operator TEXT,
    threshold TEXT,
    actuator TEXT,
    action TEXT
);