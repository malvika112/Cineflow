-- CinemaFlo schema
-- All monetary values stored as integer paise (1 INR = 100 paise) to avoid
-- floating point rounding errors.

PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS menu_items (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    name            TEXT NOT NULL,
    description     TEXT NOT NULL DEFAULT '',
    price_paise     INTEGER NOT NULL CHECK (price_paise >= 0),
    category        TEXT NOT NULL DEFAULT 'general',
    is_active       INTEGER NOT NULL DEFAULT 1 CHECK (is_active IN (0, 1))
);

CREATE TABLE IF NOT EXISTS stock (
    item_id         INTEGER PRIMARY KEY REFERENCES menu_items(id),
    quantity        INTEGER NOT NULL DEFAULT 0 CHECK (quantity >= 0),
    last_updated    TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS orders (
    id              TEXT PRIMARY KEY,
    session_id      TEXT NOT NULL,
    seat_number     TEXT NOT NULL,
    status          TEXT NOT NULL DEFAULT 'placed'
                        CHECK (status IN ('placed','preparing','ready','delivered','cancelled')),
    discount_paise  INTEGER NOT NULL DEFAULT 0,
    offer_code      TEXT,
    created_at      TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at      TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS order_items (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    order_id            TEXT NOT NULL REFERENCES orders(id),
    item_id             INTEGER NOT NULL REFERENCES menu_items(id),
    item_name           TEXT NOT NULL,
    quantity            INTEGER NOT NULL CHECK (quantity > 0),
    unit_price_paise    INTEGER NOT NULL CHECK (unit_price_paise >= 0)
);

CREATE TABLE IF NOT EXISTS offers (
    id                  TEXT PRIMARY KEY,
    code                TEXT NOT NULL UNIQUE,
    discount_type       TEXT NOT NULL CHECK (discount_type IN ('flat','percent')),
    discount_value      INTEGER NOT NULL CHECK (discount_value >= 0),
    min_order_paise     INTEGER NOT NULL DEFAULT 0,
    max_uses            INTEGER NOT NULL DEFAULT 1000000,
    per_user_cap        INTEGER NOT NULL DEFAULT 1,
    valid_from          TEXT NOT NULL,
    valid_until         TEXT NOT NULL,
    stackable           INTEGER NOT NULL DEFAULT 0 CHECK (stackable IN (0, 1))
);

CREATE TABLE IF NOT EXISTS offer_redemptions (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    offer_id        TEXT NOT NULL REFERENCES offers(id),
    session_id      TEXT NOT NULL,
    order_id        TEXT NOT NULL REFERENCES orders(id),
    applied_at      TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_orders_status ON orders(status);
CREATE INDEX IF NOT EXISTS idx_order_items_order_id ON order_items(order_id);
CREATE INDEX IF NOT EXISTS idx_redemptions_offer ON offer_redemptions(offer_id);
CREATE INDEX IF NOT EXISTS idx_redemptions_session ON offer_redemptions(session_id);
