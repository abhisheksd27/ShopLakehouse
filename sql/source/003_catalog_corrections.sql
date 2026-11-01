BEGIN;

SET LOCAL TIME ZONE 'UTC';

-- Existing timestamps were recorded using the UTC server timezone.
ALTER TABLE public.categories
    ALTER COLUMN created_at TYPE TIMESTAMPTZ
        USING created_at AT TIME ZONE 'UTC',
    ALTER COLUMN updated_at TYPE TIMESTAMPTZ
        USING updated_at AT TIME ZONE 'UTC';

ALTER TABLE public.products
    ALTER COLUMN created_at TYPE TIMESTAMPTZ
        USING created_at AT TIME ZONE 'UTC',
    ALTER COLUMN updated_at TYPE TIMESTAMPTZ
        USING updated_at AT TIME ZONE 'UTC';

-- Prevent deleting categories that still have products.
ALTER TABLE public.products
    DROP CONSTRAINT products_category_id_fk,
    ADD CONSTRAINT products_category_id_fk
        FOREIGN KEY (category_id)
        REFERENCES public.categories (id)
        ON DELETE RESTRICT;

-- Enforce valid prices and stock quantities.
ALTER TABLE public.products
    DROP CONSTRAINT IF EXISTS products_price_positive,
    DROP CONSTRAINT IF EXISTS products_price_valid,
    DROP CONSTRAINT IF EXISTS products_stock_nonnegative,

    ADD CONSTRAINT products_price_valid
        CHECK (price >= 0 AND price <> 'NaN'::numeric),

    ADD CONSTRAINT products_stock_nonnegative
        CHECK (stock_quantity >= 0);

COMMIT;