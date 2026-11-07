BEGIN;

CREATE TABLE public.orders (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    customer_id bigint NOT NULL,
    ordered_at timestamptz NOT NULL DEFAULT now(),
    status varchar(20) NOT NULL DEFAULT 'pending',
    currency char(3) NOT NULL DEFAULT 'INR',
    total_amount numeric(18,2) NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),

    CONSTRAINT orders_customer_id_fk
        FOREIGN KEY (customer_id)
        REFERENCES public.customers (id)
        ON DELETE RESTRICT,

    CONSTRAINT orders_status_valid
        CHECK (
            status IN (
                'pending', 'confirmed', 'shipped',
                'delivered', 'cancelled'
            )
        ),

    CONSTRAINT orders_currency_valid
        CHECK (currency = 'INR'),

    CONSTRAINT orders_total_amount_valid
        CHECK (
            total_amount >= 0
            AND total_amount <> 'NaN'::numeric
        ),

    CONSTRAINT orders_timestamp_order
        CHECK (updated_at >= created_at)
);

CREATE TABLE public.order_items (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    order_id bigint NOT NULL,
    product_id bigint NOT NULL,
    line_number integer NOT NULL,
    quantity integer NOT NULL,
    unit_price numeric(18,2) NOT NULL,
    discount_amount numeric(18,2) NOT NULL DEFAULT 0,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),

    CONSTRAINT order_items_order_id_fk
        FOREIGN KEY (order_id)
        REFERENCES public.orders (id)
        ON DELETE RESTRICT,

    CONSTRAINT order_items_product_id_fk
        FOREIGN KEY (product_id)
        REFERENCES public.products (id)
        ON DELETE RESTRICT,

    CONSTRAINT order_items_order_line_unique
        UNIQUE (order_id, line_number),

    CONSTRAINT order_items_line_number_positive
        CHECK (line_number > 0),

    CONSTRAINT order_items_quantity_positive
        CHECK (quantity > 0),

    CONSTRAINT order_items_unit_price_valid
        CHECK (
            unit_price >= 0
            AND unit_price <> 'NaN'::numeric
        ),

    CONSTRAINT order_items_discount_valid
        CHECK (
            discount_amount >= 0
            AND discount_amount <> 'NaN'::numeric
            AND discount_amount <= quantity * unit_price
        ),

    CONSTRAINT order_items_timestamp_order
        CHECK (updated_at >= created_at)
);

-- Support incremental extraction of new and changed rows.
CREATE INDEX idx_orders_updated_at
    ON public.orders (updated_at, id);

CREATE INDEX idx_order_items_updated_at
    ON public.order_items (updated_at, id);

-- Support customer and product lookups.
CREATE INDEX idx_orders_customer_id
    ON public.orders (customer_id);

CREATE INDEX idx_order_items_product_id
    ON public.order_items (product_id);

-- UNIQUE (order_id, line_number) already creates an index
-- that supports lookups by order_id.

CREATE OR REPLACE TRIGGER trg_orders_updated_at
BEFORE UPDATE ON public.orders
FOR EACH ROW
EXECUTE FUNCTION public.set_updated_at();

CREATE OR REPLACE TRIGGER trg_order_items_updated_at
BEFORE UPDATE ON public.order_items
FOR EACH ROW
EXECUTE FUNCTION public.set_updated_at();

COMMIT;