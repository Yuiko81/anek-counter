-- Примерный шаблон создания таблицы, отредактируйте под свои нужды
CREATE TABLE IF NOT EXISTS users (
    id BIGINT PRIMARY KEY,
    username TEXT,
    first_name TEXT NOT NULL,
    joined_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS types (
    id SMALLSERIAL PRIMARY KEY,
    code TEXT NOT NULL UNIQUE,
    title TEXT NOT NULL
);

INSERT INTO types (code, title) VALUES
    ('joke', 'Анекдот'),
    ('story', 'Кулстори')
ON CONFLICT (code) DO NOTHING;

CREATE TABLE IF NOT EXISTS events (
    id BIGSERIAL PRIMARY KEY,
    type_id SMALLINT NOT NULL REFERENCES types(id),
    user_id BIGINT NOT NULL REFERENCES users(id),
    spent_minutes INT NOT NULL CHECK (spent_minutes > 0),
    rating SMALLINT NOT NULL CHECK (rating BETWEEN 1 AND 5),
    happened_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_events_user ON events (user_id, happened_at DESC);
CREATE INDEX IF NOT EXISTS idx_events_type ON events (type_id, happened_at DESC);
