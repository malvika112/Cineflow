-- Sample data for local development and the digital twin

INSERT INTO menu_items (id, name, description, price_paise, category, is_active) VALUES
    (1, 'Large Popcorn',      'Classic salted popcorn, large tub',     25000, 'snacks',    1),
    (2, 'Regular Popcorn',    'Classic salted popcorn, regular tub',   18000, 'snacks',    1),
    (3, 'Nachos & Cheese',    'Crispy nachos with cheese dip',         22000, 'snacks',    1),
    (4, 'Coca-Cola (L)',      'Large fountain coke',                   15000, 'beverages', 1),
    (5, 'Coca-Cola (R)',      'Regular fountain coke',                 11000, 'beverages', 1),
    (6, 'Combo: Popcorn+Coke','Large popcorn + large coke',            35000, 'combos',    1),
    (7, 'Hot Dog',            'Classic grilled hot dog',                18000, 'snacks',    1),
    (8, 'Choco Bar',          'Chocolate ice cream bar',                 9000, 'desserts',  1);

INSERT INTO stock (item_id, quantity) VALUES
    (1, 40),
    (2, 60),
    (3, 25),
    (4, 50),
    (5, 70),
    (6, 30),
    (7, 20),
    (8, 35);

INSERT INTO offers (id, code, discount_type, discount_value, min_order_paise, max_uses, per_user_cap, valid_from, valid_until, stackable) VALUES
    ('off-welcome10', 'WELCOME10', 'percent', 10, 10000, 1000, 1, '2026-01-01T00:00:00', '2026-12-31T23:59:59', 0),
    ('off-flat50',    'FLAT50',    'flat',    5000, 30000, 500,  1, '2026-01-01T00:00:00', '2026-12-31T23:59:59', 0),
    ('off-combo-extra','COMBOLOVE','percent', 5,  0,     5000, 3, '2026-01-01T00:00:00', '2026-12-31T23:59:59', 1);
