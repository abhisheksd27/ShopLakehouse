"""Synthetic catalog API with keyset pagination and opt-in fault injection."""

from __future__ import annotations

import hmac
import os
import random
import time
from collections import deque
from datetime import datetime, timezone

from fastapi import Depends, FastAPI, Header, HTTPException, Query

from .database import connect
from .settings import Settings

app = FastAPI(title="ShopLakehouse synthetic catalog", version="1.0")
requests: deque[float] = deque()


def authorize(authorization: str = Header(default="")) -> None:
    token = Settings().api_token
    if not token or not hmac.compare_digest(authorization, f"Bearer {token}"):
        raise HTTPException(401, "Invalid API token")
    now = time.monotonic()
    while requests and requests[0] < now - 60:
        requests.popleft()
    if len(requests) >= int(os.getenv("API_RATE_LIMIT", "120")):
        raise HTTPException(429, "Rate limit exceeded", headers={"Retry-After": "5"})
    requests.append(now)
    if random.random() < float(os.getenv("API_FAILURE_RATE", "0")):
        raise HTTPException(500, "Injected synthetic failure")


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.get("/products", dependencies=[Depends(authorize)])
def products(
    after_id: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    updated_since: datetime = datetime(1970, 1, 1, tzinfo=timezone.utc),
    as_of: datetime | None = None,
) -> dict:
    upper = as_of or datetime.now(timezone.utc)
    if updated_since.tzinfo is None or upper.tzinfo is None:
        raise HTTPException(422, "Timezone-aware timestamps required")
    with connect(Settings(), True) as conn:
        conn.execute("SET TRANSACTION READ ONLY")
        rows = list(
            conn.execute(
                """SELECT id,sku,updated_at FROM public.products
            WHERE id>%s AND updated_at>=%s AND updated_at<=%s ORDER BY id LIMIT %s""",
                (after_id, updated_since, upper, limit + 1),
            )
        )
    page = rows[:limit]
    items = [
        dict(
            row,
            brand=f"Demo Brand {row['id']%4}",
            material=("metal", "fabric", "plastic")[row["id"] % 3],
        )
        for row in page
    ]
    return {"items": items, "next_after_id": page[-1]["id"] if len(rows) > limit else None}
