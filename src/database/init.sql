CREATE TABLE rules (
    id SERIAL PRIMARY KEY,
    sensor TEXT,
    operator TEXT,
    threshold INT,
    actuator TEXT,
    action TEXT
);