BEGIN;
CREATE TABLE public.reviews (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    customer_id bigint NOT NULL REFERENCES public.customers(id) ON DELETE RESTRICT,
    product_id bigint NOT NULL REFERENCES public.products(id) ON DELETE RESTRICT,
    rating smallint NOT NULL CHECK (rating BETWEEN 1 AND 5),
    review_text text,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE(customer_id,product_id),
    CHECK (updated_at >= created_at)
);
CREATE INDEX idx_reviews_product_id ON public.reviews(product_id);
CREATE INDEX idx_reviews_updated_at ON public.reviews(updated_at,id);
CREATE TRIGGER trg_reviews_updated_at BEFORE UPDATE ON public.reviews
FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();
COMMIT;
