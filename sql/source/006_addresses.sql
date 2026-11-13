BEGIN;
CREATE TABLE public.addresses (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    customer_id bigint NOT NULL REFERENCES public.customers(id) ON DELETE RESTRICT,
    address_line1 varchar(255) NOT NULL CHECK (length(trim(address_line1)) > 0),
    address_line2 varchar(255),
    city varchar(100) NOT NULL,
    state varchar(100) NOT NULL,
    postal_code varchar(12) NOT NULL CHECK (postal_code ~ '^[0-9]{6}$'),
    country char(2) NOT NULL DEFAULT 'IN' CHECK (country = 'IN'),
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE(id,customer_id),
    CHECK (updated_at >= created_at)
);
ALTER TABLE public.orders ADD COLUMN shipping_address_id bigint;
ALTER TABLE public.orders ADD CONSTRAINT orders_shipping_address_owner_fk
    FOREIGN KEY (shipping_address_id,customer_id) REFERENCES public.addresses(id,customer_id)
    ON DELETE RESTRICT;
CREATE INDEX idx_addresses_customer_id ON public.addresses(customer_id);
CREATE INDEX idx_addresses_updated_at ON public.addresses(updated_at,id);
CREATE INDEX idx_orders_shipping_address ON public.orders(shipping_address_id,customer_id);
CREATE TRIGGER trg_addresses_updated_at BEFORE UPDATE ON public.addresses
FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();
COMMENT ON TABLE public.addresses IS 'Address versions: create a new row for a changed delivery address; retain addresses referenced by historical orders.';
COMMIT;
