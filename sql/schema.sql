-- Public portfolio schema. Personal identifiers are intentionally excluded.

CREATE TABLE orders (
    order_id       VARCHAR(50) PRIMARY KEY,
    customer_id    VARCHAR(50) NOT NULL,
    order_status   VARCHAR(20) NOT NULL,
    store_id       INT NOT NULL,
    order_time     DATETIME NOT NULL,
    total_amount   DECIMAL(10,2) NOT NULL,
    INDEX idx_customer (customer_id),
    INDEX idx_order_time (order_time),
    INDEX idx_store (store_id)
);

CREATE TABLE order_items (
    item_id        BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    order_id       VARCHAR(50) NOT NULL,
    product_name   VARCHAR(100) NOT NULL,
    quantity       INT NOT NULL,
    unit_price     DECIMAL(10,2) NOT NULL,
    INDEX idx_order_id (order_id),
    CONSTRAINT fk_order_items_order
        FOREIGN KEY (order_id) REFERENCES orders(order_id)
        ON DELETE CASCADE ON UPDATE CASCADE
);
