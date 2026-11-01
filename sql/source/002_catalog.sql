BEGIN;

create table if not exists public.categories(
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    name varchar(255) not null unique,
    created_at timestamp not null default current_timestamp,
    updated_at timestamp not null default current_timestamp,

    constraint categories_name_bot_blank check (length(trim(name)) > 0),

    constraint categories_timestamp_order check (updated_at >= created_at)

);


create table if not exists public.products(
    id bigint generated always as identity primary key,
    category_id bigint not null,
    sku varchar(255) not null unique,
    name varchar(255) not null,
    price numeric(18,2) not null ,
    stock_quantity integer not null default 0,
    created_at timestamp not null default current_timestamp,
    updated_at timestamp not null default current_timestamp,

    constraint products_category_id_fk foreign key (category_id) references public.categories(id) on delete cascade,

    constraint products_sku_not_blank check (length(trim(sku)) > 0),

    constraint products_name_not_blank check (length(trim(name)) > 0),

    constraint products_price_positive check (price >= 0),

    constraint products_timestamp_order check (updated_at >= created_at)
    


);


-- Support incremental extraction.
CREATE INDEX IF NOT EXISTS idx_categories_updated_at
    ON public.categories (updated_at, id);

CREATE INDEX IF NOT EXISTS idx_products_updated_at
    ON public.products (updated_at, id);

-- Support product lookups by category.
CREATE INDEX IF NOT EXISTS idx_products_category_id
    ON public.products (category_id);

-- Reuse the function created in 001_customers.sql.
CREATE OR REPLACE TRIGGER trg_categories_updated_at
    BEFORE UPDATE ON public.categories
    FOR EACH ROW
    EXECUTE FUNCTION public.set_updated_at();

CREATE OR REPLACE TRIGGER trg_products_updated_at
    BEFORE UPDATE ON public.products
    FOR EACH ROW
    EXECUTE FUNCTION public.set_updated_at();

COMMIT;