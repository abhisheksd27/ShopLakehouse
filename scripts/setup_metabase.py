"""Provision local BI with a Gold-only reader and repeatable saved questions.

No emails, subscriptions, public links, or outbound notifications are created.
"""

import json
import os

import httpx
from psycopg import sql

from shoplakehouse.database import connect
from shoplakehouse.settings import ROOT, Settings


def main() -> None:
    settings = Settings()
    if settings.warehouse != "postgres":
        raise ValueError("This provisioning command targets local PostgreSQL")
    password = os.environ["BI_DB_PASSWORD"]
    email = os.getenv("METABASE_ADMIN_EMAIL", "admin@shoplakehouse.local")
    admin_password = os.environ["METABASE_ADMIN_PASSWORD"]
    with connect(settings) as conn:
        if not conn.execute("SELECT 1 FROM pg_roles WHERE rolname='shop_bi'").fetchone():
            conn.execute("CREATE ROLE shop_bi LOGIN")
        conn.execute(
            sql.SQL("ALTER ROLE shop_bi PASSWORD {} NOSUPERUSER NOCREATEDB NOCREATEROLE").format(
                sql.Literal(password)
            )
        )
        conn.execute("ALTER ROLE shop_bi SET default_transaction_read_only=on")
        conn.execute("GRANT USAGE ON SCHEMA gold TO shop_bi")
        conn.execute("GRANT SELECT ON ALL TABLES IN SCHEMA gold TO shop_bi")
        conn.execute("ALTER DEFAULT PRIVILEGES IN SCHEMA gold GRANT SELECT ON TABLES TO shop_bi")
    url = os.getenv("METABASE_URL", "http://localhost:3000")
    with httpx.Client(base_url=url, timeout=120) as client:

        def request(method, path, **kwargs):
            response = client.request(method, "/api" + path, **kwargs)
            # Do not echo request/response bodies, which can contain credentials.
            if response.is_error:
                raise RuntimeError(f"Metabase {method} {path} failed: HTTP {response.status_code}")
            return response.json() if response.content else None

        properties = request("GET", "/session/properties")
        if properties.get("setup-token"):
            request(
                "POST",
                "/setup",
                json={
                    "token": properties["setup-token"],
                    "user": {
                        "first_name": "ShopLakehouse",
                        "last_name": "Admin",
                        "email": email,
                        "password": admin_password,
                    },
                    "prefs": {
                        "site_name": "ShopLakehouse",
                        "allow_tracking": False,
                    },
                },
            )
        session = request("POST", "/session", json={"username": email, "password": admin_password})
        client.headers["X-Metabase-Session"] = session["id"]
        databases = request("GET", "/database")["data"]
        database = next((d for d in databases if d["name"] == "ShopLakehouse Gold"), None)
        if database is None:
            database = request(
                "POST",
                "/database",
                json={
                    "name": "ShopLakehouse Gold",
                    "engine": "postgres",
                    "details": {
                        "host": "analytics-postgres",
                        "port": 5432,
                        "dbname": os.getenv("ANALYTICS_DB_NAME", "shoplakehouse_analytics"),
                        "user": "shop_bi",
                        "password": password,
                        "ssl": False,
                        "schema-filters-type": "inclusion",
                        "schema-filters-patterns": "gold",
                    },
                    "is_full_sync": True,
                },
            )
        existing = {c["name"]: c for c in request("GET", "/card")}
        cards = []
        specs = json.loads((ROOT / "config/dashboards.json").read_text())
        for spec in specs:
            definition = {
                "name": spec["name"],
                "description": spec["description"],
                "display": spec["display"],
                "dataset_query": {
                    "database": database["id"],
                    "type": "native",
                    "native": {"query": (ROOT / spec["file"]).read_text(), "template-tags": {}},
                },
                "visualization_settings": spec.get("settings", {}),
            }
            card = existing.get(spec["name"])
            if card:
                card = request("PUT", f"/card/{card['id']}", json=definition)
            else:
                card = request("POST", "/card", json=definition)
            cards.append(card)
        dashboards = request("GET", "/dashboard")
        urls = {}
        groups = {
            "Executive": [0, 1, 4, 9, 12, 23],
            "Sales": [2, 3, 10, 13, 14, 16, 21],
            "Customer": [5, 6, 8, 11, 17, 22],
        }
        for title, indices in groups.items():
            name = "ShopLakehouse " + title
            dashboard = next((d for d in dashboards if d["name"] == name), None)
            if dashboard is None:
                dashboard = request("POST", "/dashboard", json={"name": name})
            current = request("GET", f"/dashboard/{dashboard['id']}")
            placed = {d["card_id"]: d for d in current.get("dashcards", [])}
            layout = []
            for i, index in enumerate(indices):
                card = cards[index]
                layout.append(
                    {
                        "id": placed.get(card["id"], {}).get("id", -(i + 1)),
                        "card_id": card["id"],
                        "row": (i // 2) * 6,
                        "col": (i % 2) * 12,
                        "size_x": 12,
                        "size_y": 6,
                        "parameter_mappings": [],
                    }
                )
            request("PUT", f"/dashboard/{dashboard['id']}", json={"dashcards": layout})
            urls[title] = f"{url}/dashboard/{dashboard['id']}"
        (ROOT / "artifacts").mkdir(exist_ok=True)
        report = {"dashboards": urls, "questions": len(cards)}
        (ROOT / "artifacts/metabase.json").write_text(json.dumps(report, indent=2))
        print(json.dumps(report))


if __name__ == "__main__":
    main()
