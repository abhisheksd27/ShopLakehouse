-- Run everything as one transaction (all or nothing)
BEGIN;

-- Create the customers table if it doesn't exist
CREATE TABLE IF NOT EXISTS public.customers (
    id          bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,  -- auto-generated unique ID
    name        varchar(120) NOT NULL,                            -- customer name
    email       varchar(254) NOT NULL,                            -- customer email
    city        varchar(100) NOT NULL,                            -- customer city
    country     char(2)      NOT NULL DEFAULT 'IN',               -- 2-letter country code
    created_at  timestamptz  NOT NULL DEFAULT now(),              -- when the row was created
    updated_at  timestamptz  NOT NULL DEFAULT now(),              -- when the row was last changed

    -- name can't be empty or only spaces
    CONSTRAINT customers_name_not_blank CHECK (length(trim(name)) > 0),
    -- country must be 2 capital letters (e.g. IN, US)
    CONSTRAINT customers_country_format CHECK (country ~ '^[A-Z]{2}$'),
    -- updated_at can't be earlier than created_at
    CONSTRAINT customers_timestamp_order CHECK (updated_at >= created_at)
);

-- Emails must be unique, ignoring upper/lower case
CREATE UNIQUE INDEX IF NOT EXISTS customers_email_lower_key
    ON public.customers (lower(email));

-- Speeds up queries that sort or filter by updated_at
CREATE INDEX IF NOT EXISTS idx_customers_updated_at
    ON public.customers (updated_at, id);

-- Function: sets updated_at to the current time
CREATE OR REPLACE FUNCTION public.set_updated_at()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    NEW.updated_at = clock_timestamp();
    RETURN NEW;
END;
$$;

-- Trigger: runs the function before every UPDATE on customers
CREATE OR REPLACE TRIGGER trg_customers_updated_at
BEFORE UPDATE ON public.customers
FOR EACH ROW
EXECUTE FUNCTION public.set_updated_at();

-- Save the changes
COMMIT;