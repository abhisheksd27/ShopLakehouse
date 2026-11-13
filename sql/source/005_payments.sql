BEGIN;
CREATE TABLE public.payments (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    order_id bigint NOT NULL REFERENCES public.orders(id) ON DELETE RESTRICT,
    payment_reference varchar(100) NOT NULL UNIQUE CHECK (length(trim(payment_reference)) > 0),
    transaction_type varchar(10) NOT NULL DEFAULT 'payment' CHECK (transaction_type IN ('payment','refund')),
    payment_method varchar(20) NOT NULL CHECK (payment_method IN ('card','upi','netbanking','wallet','cash_on_delivery')),
    status varchar(12) NOT NULL DEFAULT 'pending' CHECK (status IN ('pending','succeeded','failed')),
    amount numeric(18,2) NOT NULL CHECK (amount > 0 AND amount <> 'NaN'::numeric),
    currency char(3) NOT NULL DEFAULT 'INR' CHECK (currency = 'INR'),
    processed_at timestamptz,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    CHECK ((status = 'pending' AND processed_at IS NULL) OR (status IN ('succeeded','failed') AND processed_at IS NOT NULL)),
    CHECK (updated_at >= created_at)
);
CREATE INDEX idx_payments_order_id ON public.payments(order_id);
CREATE INDEX idx_payments_updated_at ON public.payments(updated_at,id);
CREATE TRIGGER trg_payments_updated_at BEFORE UPDATE ON public.payments
FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();
COMMIT;
