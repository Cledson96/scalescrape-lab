from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP
from pathlib import PurePosixPath
from urllib.parse import urlparse


RATING_VALUES = {
    "One": 1,
    "Two": 2,
    "Three": 3,
    "Four": 4,
    "Five": 5,
}


def parse_books_price(price_text: str, gbp_to_brl_rate: float) -> dict:
    amount = Decimal(price_text.strip().replace("£", "").replace(",", ""))
    rate = Decimal(str(gbp_to_brl_rate))
    brl_amount = (amount * rate).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    return {
        "currency": "GBP",
        "amount": float(amount),
        "formatted": f"£{amount:.2f}",
        "brl_currency": "BRL",
        "brl_amount": float(brl_amount),
        "brl_formatted": format_brl(brl_amount),
        "exchange_rate": float(rate),
    }


def format_brl(amount: Decimal) -> str:
    formatted = f"{amount:.2f}".replace(".", ",")
    return f"R$ {formatted}"


def parse_rating_class(class_text: str) -> dict:
    tokens = class_text.split()
    label = next((token for token in tokens if token in RATING_VALUES), "Unknown")
    return {"label": label, "value": RATING_VALUES.get(label, 0)}


def extract_book_external_id(detail_url: str) -> str:
    path = PurePosixPath(urlparse(detail_url).path)
    if path.name == "index.html":
        return path.parent.name
    return path.stem


def extract_books_category(category_url: str) -> str:
    category_segment = PurePosixPath(urlparse(category_url).path).parent.name
    if "_" not in category_segment:
        return category_segment
    return category_segment.rsplit("_", 1)[0]


def build_books_record_payload(
    *,
    title: str,
    category: str,
    detail_url: str,
    price_text: str,
    rating_class: str,
    description: str,
    availability: str,
    gbp_to_brl_rate: float,
) -> dict:
    return {
        "source": "books-to-scrape",
        "category": category,
        "title": title,
        "detail_url": detail_url,
        "price": parse_books_price(price_text, gbp_to_brl_rate),
        "rating": parse_rating_class(rating_class),
        "description": description.strip(),
        "availability": availability.strip(),
    }
