BEGIN;
CREATE TABLE public.shipments (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    order_id bigint NOT NULL REFERENCES public.orders(id) ON DELETE RESTRICT,
    tracking_number varchar(100) NOT NULL UNIQUE CHECK (length(trim(tracking_number)) > 0),
    carrier varchar(100) NOT NULL,
    status varchar(20) NOT NULL DEFAULT 'pending' CHECK (status IN ('pending','shipped','delivered','returned')),
    shipped_at timestamptz,
    delivered_at timestamptz,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    CHECK (status = 'pending' OR shipped_at IS NOT NULL),
    CHECK (status <> 'delivered' OR delivered_at IS NOT NULL),
    CHECK (delivered_at IS NULL OR (shipped_at IS NOT NULL AND delivered_at >= shipped_at)),
    CHECK (updated_at >= created_at)
);
CREATE INDEX idx_shipments_order_id ON public.shipments(order_id);
CREATE INDEX idx_shipments_updated_at ON public.shipments(updated_at,id);
CREATE TRIGGER trg_shipments_updated_at BEFORE UPDATE ON public.shipments
FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();
COMMIT;
