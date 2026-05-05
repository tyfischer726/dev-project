CREATE TABLE IF NOT EXISTS messages (
    id         SERIAL PRIMARY KEY,
    message    TEXT,
    response   TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
