"""Deterministic synthetic business data. Re-running a batch adds no duplicate orders."""

from __future__ import annotations

import csv
import json
import random
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from typing import Any

from faker import Faker

from .database import connect
from .settings import Settings
from .storage import Lake, json_value

CHANNELS = ("organic", "paid_search", "social", "email")


def generate_csv(settings: Settings, day: date, seed: int, inject_quality: bool = False) -> None:
    rng = random.Random(f"{seed}:{day}:csv")
    stamp = datetime.combine(day, datetime.min.time(), tzinfo=timezone.utc).isoformat()
    for entity in ("marketing", "web_traffic"):
        rows = []
        for channel in CHANNELS:
            row: dict[str, Any] = {
                "id": f"{day}:{channel}",
                "event_date": day.isoformat(),
                "channel": channel,
            }
            if entity == "marketing":
                impressions = rng.randint(1000, 20000)
                row.update(
                    spend=f"{rng.randint(10000,100000)/100:.2f}",
                    impressions=impressions,
                    clicks=rng.randint(100, 900),
                )
            else:
                sessions = rng.randint(200, 2000)
                row.update(sessions=sessions, conversions=rng.randint(5, 100))
            row["updated_at"] = stamp
            rows.append(row)
        if inject_quality and entity == "marketing":
            rows.append(dict(rows[0]))  # same key/version, dedup must account for it
            rows[1]["spend"] = "-1.00"
        directory = settings.data_dir / "csv" / entity
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / f"{day}.csv"
        temp = path.with_suffix(".tmp")
        with temp.open("w", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)
        temp.replace(path)
        if not settings.endpoint:
            Lake(settings).put(f"landing/csv/{entity}/{day}.csv", path.read_bytes())


def generate(
    settings: Settings,
    mode: str,
    day: date,
    seed: int = 27,
    orders: int = 100,
    inject_quality: bool = False,
) -> dict:
    if mode not in {"initial", "daily"} or orders < 1:
        raise ValueError("Use initial/daily mode and a positive order count")
    rng = random.Random(f"{seed}:{mode}:{day}")
    fake = Faker("en_IN")
    fake.seed_instance(seed)
    base = datetime.combine(day - timedelta(days=31), datetime.min.time(), tzinfo=timezone.utc)
    batch_key = f"{mode}:{seed}" if mode == "initial" else f"{mode}:{day}:{seed}"
    with connect(settings, True) as conn:
        conn.execute("SELECT pg_advisory_xact_lock(739202)")
        conn.execute(
            """CREATE TABLE IF NOT EXISTS public.simulation_batches(
            batch_key text PRIMARY KEY, batch_date date NOT NULL, seed integer NOT NULL,
            order_count integer NOT NULL, created_at timestamptz NOT NULL DEFAULT now())"""
        )
        prior = conn.execute(
            "SELECT * FROM public.simulation_batches WHERE batch_key=%s", (batch_key,)
        ).fetchone()
        if prior:
            if prior["batch_date"] != day or prior["order_count"] != orders:
                raise ValueError(
                    "Batch already generated with different date/count; use original parameters"
                )
            result = {"mode": mode, "orders_inserted": 0, "replayed": True}
        else:
            category_ids = []
            for name in ("Electronics", "Home", "Fashion"):
                conn.execute(
                    "INSERT INTO public.categories(name,created_at,updated_at) VALUES(%s,%s,%s) ON CONFLICT(name) DO NOTHING",
                    (name, base, base),
                )
                category_ids.append(
                    conn.execute(
                        "SELECT id FROM public.categories WHERE name=%s", (name,)
                    ).fetchone()["id"]
                )
            customer_ids = []
            addresses = {}
            for i in range(50):
                email = f"customer_{seed}_{i}@example.test"
                conn.execute(
                    """INSERT INTO public.customers(name,email,city,country,created_at,updated_at)
                    VALUES(%s,%s,%s,'IN',%s,%s) ON CONFLICT (lower(email)) DO NOTHING""",
                    (
                        fake.name(),
                        email,
                        rng.choice(["Bengaluru", "Mumbai", "Delhi", "Chennai"]),
                        base,
                        base,
                    ),
                )
                customer = conn.execute(
                    "SELECT * FROM public.customers WHERE lower(email)=lower(%s)", (email,)
                ).fetchone()
                cid = customer["id"]
                customer_ids.append(cid)
                address = conn.execute(
                    "SELECT id FROM public.addresses WHERE customer_id=%s ORDER BY id LIMIT 1",
                    (cid,),
                ).fetchone()
                if address is None:
                    address = conn.execute(
                        """INSERT INTO public.addresses(customer_id,address_line1,city,state,postal_code,created_at,updated_at)
                        VALUES(%s,%s,%s,%s,%s,%s,%s) RETURNING id""",
                        (
                            cid,
                            f"{i+1} Synthetic Street",
                            customer["city"],
                            "Synthetic State",
                            f"{560000+i:06}",
                            base,
                            base,
                        ),
                    ).fetchone()
                addresses[cid] = address["id"]
            product_ids = []
            for i in range(20):
                sku = f"SL-{seed}-{i:04}"
                conn.execute(
                    """INSERT INTO public.products(category_id,sku,name,price,stock_quantity,created_at,updated_at)
                    VALUES(%s,%s,%s,%s,1000,%s,%s) ON CONFLICT(sku) DO NOTHING""",
                    (
                        category_ids[i % 3],
                        sku,
                        f"Demo Product {i+1}",
                        Decimal((i + 1) * 125),
                        base,
                        base,
                    ),
                )
                product_ids.append(
                    conn.execute("SELECT id FROM public.products WHERE sku=%s", (sku,)).fetchone()[
                        "id"
                    ]
                )
            for i in range(orders):
                cid = rng.choice(customer_ids)
                event_day = day - timedelta(days=rng.randrange(30)) if mode == "initial" else day
                ordered_at = datetime.combine(
                    event_day, datetime.min.time(), tzinfo=timezone.utc
                ) + timedelta(hours=rng.randrange(18))
                status = rng.choices(
                    ["delivered", "cancelled", "confirmed", "shipped", "pending"],
                    [65, 10, 10, 10, 5],
                )[0]
                chosen = rng.sample(product_ids, k=rng.randint(1, 3))
                lines = []
                for pid in chosen:
                    price = conn.execute(
                        "SELECT price FROM public.products WHERE id=%s", (pid,)
                    ).fetchone()["price"]
                    quantity = rng.randint(1, 3)
                    discount = (
                        (price * quantity * Decimal("0.05")).quantize(Decimal("0.01"))
                        if rng.random() < 0.25
                        else Decimal("0")
                    )
                    lines.append((pid, quantity, price, discount))
                total = sum(
                    (quantity * price - discount for _, quantity, price, discount in lines),
                    Decimal("0"),
                )
                oid = conn.execute(
                    """INSERT INTO public.orders(customer_id,ordered_at,status,total_amount,shipping_address_id)
                    VALUES(%s,%s,%s,%s,%s) RETURNING id""",
                    (cid, ordered_at, status, total, addresses[cid]),
                ).fetchone()["id"]
                for n, (pid, quantity, price, discount) in enumerate(lines, 1):
                    conn.execute(
                        """INSERT INTO public.order_items(order_id,product_id,line_number,quantity,unit_price,discount_amount)
                        VALUES(%s,%s,%s,%s,%s,%s)""",
                        (oid, pid, n, quantity, price, discount),
                    )
                processed = ordered_at + timedelta(minutes=1)
                pay_status = "pending" if status == "pending" else "succeeded"
                conn.execute(
                    """INSERT INTO public.payments(order_id,payment_reference,payment_method,status,amount,processed_at)
                    VALUES(%s,%s,'upi',%s,%s,%s)""",
                    (
                        oid,
                        f"PAY-{batch_key}-{i}",
                        pay_status,
                        total,
                        None if pay_status == "pending" else processed,
                    ),
                )
                if status == "cancelled":
                    conn.execute(
                        """INSERT INTO public.payments(order_id,payment_reference,transaction_type,payment_method,status,amount,processed_at)
                        VALUES(%s,%s,'refund','upi','succeeded',%s,%s)""",
                        (oid, f"REF-{batch_key}-{i}", total, processed + timedelta(hours=1)),
                    )
                if status in {"shipped", "delivered"}:
                    conn.execute(
                        """INSERT INTO public.shipments(order_id,tracking_number,carrier,status,shipped_at,delivered_at)
                        VALUES(%s,%s,'Demo Logistics',%s,%s,%s)""",
                        (
                            oid,
                            f"TRACK-{batch_key}-{i}",
                            status,
                            ordered_at + timedelta(hours=2),
                            ordered_at + timedelta(days=2) if status == "delivered" else None,
                        ),
                    )
                if status == "delivered":
                    conn.execute(
                        """INSERT INTO public.reviews(customer_id,product_id,rating,review_text)
                        VALUES(%s,%s,%s,'Synthetic review') ON CONFLICT(customer_id,product_id) DO NOTHING""",
                        (cid, chosen[0], rng.randint(1, 5)),
                    )
            if mode == "daily":
                conn.execute(
                    "UPDATE public.customers SET city=%s WHERE id=%s", ("Pune", customer_ids[0])
                )
                conn.execute(
                    "UPDATE public.products SET price=price+10 WHERE id=%s", (product_ids[0],)
                )
            conn.execute(
                "INSERT INTO public.simulation_batches(batch_key,batch_date,seed,order_count) VALUES(%s,%s,%s,%s)",
                (batch_key, day, seed, orders),
            )
            result = {"mode": mode, "orders_inserted": orders, "replayed": False}
        if inject_quality:
            directory = settings.data_dir / "fixtures"
            directory.mkdir(parents=True, exist_ok=True)
            for entity, field, value in (
                ("customers", "email", "bad-email"),
                ("products", "price", "-5.00"),
            ):
                row = dict(
                    conn.execute(f"SELECT * FROM public.{entity} ORDER BY id LIMIT 1").fetchone()
                )
                row[field] = value
                row["updated_at"] = datetime.now(timezone.utc)
                (directory / f"{entity}.jsonl").write_text(
                    json.dumps(row, default=json_value) + "\n"
                )
    days = 30 if mode == "initial" else 1
    for offset in range(days):
        generate_csv(settings, day - timedelta(days=offset), seed, inject_quality and offset == 0)
    return result
