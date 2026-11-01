import csv
import json
import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"

# Descriptions that contradict the product name or specs (see README).
UNRELIABLE_DESCRIPTIONS = {135, 136, 137, 139, 140, 142, 144}


def normalize(text: str) -> str:
    stripped = "".join(c for c in unicodedata.normalize("NFKD", text) if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9]+", " ", stripped.lower()).strip()


def digits(phone: str) -> str:
    only = re.sub(r"\D", "", phone)
    return only[2:] if len(only) in (12, 13) and only.startswith("55") else only


def _rows(table: str) -> list[dict]:
    with open(DATA_DIR / f"desafio_tecnico_ai_eng - {table}.csv", encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


@dataclass(frozen=True)
class Store:
    products: dict[int, dict]
    customers: dict[int, dict]
    orders: dict[int, dict]
    items: dict[int, list[dict]]
    promotions: dict[int, dict]


def load_store() -> Store:
    categories = {int(c["category_id"]): c["name"] for c in _rows("categories")}

    promotions: dict[int, dict] = {}
    for p in _rows("promotions"):
        if p["is_active"] == "1":
            promotions[int(p["product_id"])] = {
                "percent": float(p["discount_percent"]),
                "name": p["description"],
            }

    products: dict[int, dict] = {}
    for p in _rows("products"):
        pid = int(p["product_id"])
        category = categories[int(p["category_id"])]
        reliable = pid not in UNRELIABLE_DESCRIPTIONS
        products[pid] = {
            "id": pid,
            "name": p["name"],
            "category": category,
            "price": float(p["price_brl"]),
            "stock": int(p["stock_quantity"]),
            "status": p["status"],
            "description": p["description"] if reliable else None,
            "specs": json.loads(p["specs"]),
            "search_name": normalize(p["name"]),
            "search_category": normalize(category),
            "search_all": normalize(f"{p['name']} {category} {p['description'] if reliable else ''}"),
        }

    customers = {
        int(c["customer_id"]): {
            "name": c["name"],
            "phone": digits(c["phone"]),
            "email": c["email"].strip().lower(),
        }
        for c in _rows("customers")
    }
    orders = {int(o["order_id"]): o | {"customer_id": int(o["customer_id"])} for o in _rows("orders")}

    items: dict[int, list[dict]] = {}
    for i in _rows("order_items"):
        items.setdefault(int(i["order_id"]), []).append(
            {"product_id": int(i["product_id"]), "quantity": int(i["quantity"])}
        )
    return Store(products, customers, orders, items, promotions)


def load_policies() -> dict[str, str]:
    text = (ROOT / "knowledge" / "policies.md").read_text(encoding="utf-8")
    sections = re.split(r"^## (\w+)\n", text, flags=re.MULTILINE)[1:]
    return {sections[i]: sections[i + 1].strip() for i in range(0, len(sections), 2)}
