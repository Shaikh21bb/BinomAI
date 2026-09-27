"""Read public product pages and retain only evidence tied to a concrete item."""

import asyncio
import html
import ipaddress
import json
import re
from html.parser import HTMLParser
from typing import Any
from urllib.parse import urljoin, urlparse

import httpx


_IMAGE_NOISE = re.compile(r"favicon|logo|sprite|placeholder|/watch/|portal-portable|base_satu|pixel", re.I)
_GENERIC_PATH = re.compile(r"/(category|search|list|catalog/0|catalog/search|shop/search)(/|$)|/f/", re.I)
_PRODUCT_PATH = re.compile(r"/p\d+[-/]|/p/[^/]+|/product/|/catalog/\d+/detail|/catalog/[^/]+/detail|/item/\d+", re.I)
_GENERIC_TITLE_WORDS = {"средс", "моющ", "товар", "купит", "ценам", "посуд", "коста"}
_STOCK_TEXT = re.compile(r"(?:в наличии|на складе|остаток)\s*:?\s*(\d{1,6})\s*(шт\.?|штук|ед\.?|единиц|упак\.?|упаковок)\b", re.I)


def is_public_url(url: str) -> bool:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        return False
    host = parsed.hostname.rstrip(".").lower()
    if host == "localhost" or host.endswith((".localhost", ".local", ".internal")):
        return False
    try:
        return ipaddress.ip_address(host).is_global
    except ValueError:
        return "." in host


async def _resolves_publicly(url: str) -> bool:
    parsed = urlparse(url)
    if not is_public_url(url):
        return False
    try:
        addresses = await asyncio.get_running_loop().getaddrinfo(parsed.hostname, parsed.port or 443)
        return bool(addresses) and all(ipaddress.ip_address(row[4][0]).is_global for row in addresses)
    except (OSError, ValueError):
        return False


def _clean(value: Any, limit: int = 600) -> str:
    if not isinstance(value, str):
        return ""
    return " ".join(html.unescape(re.sub(r"<[^>]+>", " ", value)).split())[:limit]


def _image_url(value: Any, page_url: str) -> str | None:
    if isinstance(value, list):
        value = next((part for part in value if isinstance(part, (str, dict))), None)
    if isinstance(value, dict):
        value = value.get("url") or value.get("contentUrl")
    if not isinstance(value, str):
        return None
    url = urljoin(page_url, html.unescape(value.strip()))
    return url if is_public_url(url) and not _IMAGE_NOISE.search(url) else None


def _stock_quantity(offer: dict[str, Any], description: str, properties: dict[str, str]) -> tuple[int | None, str | None]:
    level = offer.get("inventoryLevel")
    if level is None:
        level = offer.get("availableQuantity")
    unit = "ед."
    if isinstance(level, dict):
        unit = _clean(level.get("unitText") or "ед.", 20)
        level = level.get("value")
    if level is not None:
        try:
            amount = int(str(level).strip())
            if 0 <= amount <= 1_000_000:
                return amount, unit
        except (ValueError, TypeError):
            pass
    evidence = "\n".join([description, *[f"{key}: {value}" for key, value in properties.items()]])
    match = _STOCK_TEXT.search(evidence)
    if match:
        return int(match.group(1)), match.group(2)
    return None, None


def _product_objects(value: Any):
    if isinstance(value, list):
        for part in value:
            yield from _product_objects(part)
    elif isinstance(value, dict):
        kind = value.get("@type", "")
        kinds = kind if isinstance(kind, list) else [kind]
        if any(str(item).lower().endswith("product") for item in kinds):
            yield value
        for key in ("@graph", "mainEntity"):
            if key in value:
                yield from _product_objects(value[key])


class _PageParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.meta: dict[str, str] = {}
        self.scripts: list[str] = []
        self._script: list[str] | None = None
        self._title: list[str] | None = None
        self.title = ""
        self._row: list[str] | None = None
        self._cell: list[str] | None = None
        self.rows: list[list[str]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]):
        attributes = dict(attrs)
        if tag == "meta":
            key = attributes.get("property") or attributes.get("name") or attributes.get("itemprop")
            if key and attributes.get("content"):
                self.meta[key.lower()] = attributes["content"] or ""
        elif tag == "script" and "ld+json" in (attributes.get("type") or "").lower():
            self._script = []
        elif tag == "title":
            self._title = []
        elif tag == "tr":
            self._row = []
        elif tag in {"th", "td"} and self._row is not None:
            self._cell = []

    def handle_data(self, data: str):
        if self._script is not None:
            self._script.append(data)
        if self._title is not None:
            self._title.append(data)
        if self._cell is not None:
            self._cell.append(data)

    def handle_endtag(self, tag: str):
        if tag == "script" and self._script is not None:
            self.scripts.append("".join(self._script))
            self._script = None
        elif tag == "title" and self._title is not None:
            self.title = _clean("".join(self._title))
            self._title = None
        elif tag in {"th", "td"} and self._cell is not None:
            if self._row is not None:
                self._row.append(_clean("".join(self._cell), 250))
            self._cell = None
        elif tag == "tr" and self._row is not None:
            if len(self._row) == 2 and all(self._row):
                self.rows.append(self._row)
            self._row = None


def parse_product_page(markup: str, page_url: str) -> dict[str, Any]:
    parser = _PageParser()
    parser.feed(markup)
    product = None
    for script in parser.scripts:
        try:
            product = next(_product_objects(json.loads(script)), None)
        except (ValueError, TypeError):
            continue
        if product:
            break

    path = urlparse(page_url).path
    # Satu's top-level *.html pages are collections. Their JSON-LD often
    # contains an unrelated featured Product with its own photo and price.
    if urlparse(page_url).hostname in {"satu.kz", "www.satu.kz"} and re.fullmatch(r"/[^/]+\.html", path, re.I):
        return {"is_product_page": False, "page_verified": True}
    page_title = _clean(parser.meta.get("og:title") or parser.title)
    product_name = _clean((product or {}).get("name"))
    title_words = {word[:5] for word in re.findall(r"[a-zа-яё]{5,}", page_title.casefold())} - _GENERIC_TITLE_WORDS
    product_words = {word[:5] for word in re.findall(r"[a-zа-яё]{5,}", product_name.casefold())} - _GENERIC_TITLE_WORDS
    name_on_page = not page_title or not product_name or len(title_words & product_words) >= 2
    is_product = not _GENERIC_PATH.search(path) and (
        (bool(product) and name_on_page) or bool(_PRODUCT_PATH.search(path))
    )
    if not is_product:
        return {"is_product_page": False, "page_verified": True}

    product = product or {}
    name = _clean(product.get("name") or parser.meta.get("og:title") or parser.title)
    description = _clean(product.get("description") or parser.meta.get("og:description") or parser.meta.get("description"), 2400)
    properties: dict[str, str] = {}
    for prop in product.get("additionalProperty") or []:
        if isinstance(prop, dict):
            key = _clean(prop.get("name"), 100)
            value = _clean(str(prop.get("value") or ""), 160)
            if key and value:
                properties[key] = value
    for key, value in parser.rows[:50]:
        if key not in properties and len(key) < 100:
            properties[key] = value

    offer = product.get("offers") or {}
    if isinstance(offer, list):
        offer = offer[0] if offer else {}
    if not isinstance(offer, dict):
        offer = {}
    price = offer.get("price") or offer.get("lowPrice")
    try:
        price = float(str(price).replace(" ", "").replace(",", ".")) if price else None
    except ValueError:
        price = None
    image = _image_url(product.get("image"), page_url) or _image_url(parser.meta.get("og:image"), page_url)
    stock_quantity, stock_unit = _stock_quantity(offer, description, properties)
    evidence = "\n".join(filter(None, [name, description, *[f"{k}: {v}" for k, v in properties.items()]]))[:6500]
    return {
        "is_product_page": True,
        "page_verified": True,
        "title": name,
        "description": description,
        "characteristics": properties,
        "image_url": image,
        "price": price,
        "currency": offer.get("priceCurrency") if price else None,
        "availability": str(offer.get("availability") or "").rsplit("/", 1)[-1] or None,
        "stock_quantity": stock_quantity,
        "stock_unit": stock_unit,
        "evidence_text": evidence,
    }


async def fetch_product_page(url: str, client: httpx.AsyncClient, redirects_left: int = 2) -> dict[str, Any]:
    """Fetch at most one public page, bounded in time and size."""
    if not await _resolves_publicly(url):
        return {"is_product_page": False, "page_verified": False}
    try:
        async with client.stream("GET", url, follow_redirects=False) as response:
            if response.status_code in {301, 302, 303, 307, 308}:
                redirect = urljoin(url, response.headers.get("location", ""))
                if redirects_left <= 0 or redirect == url or not await _resolves_publicly(redirect):
                    return {"is_product_page": False, "page_verified": False}
                return await fetch_product_page(redirect, client, redirects_left - 1)
            if response.status_code != 200 or "html" not in response.headers.get("content-type", ""):
                return {"is_product_page": False, "page_verified": False}
            chunks = bytearray()
            async for chunk in response.aiter_bytes():
                chunks.extend(chunk)
                if len(chunks) > 1_200_000:
                    break
            return parse_product_page(chunks.decode(response.encoding or "utf-8", errors="replace"), str(response.url))
    except (httpx.HTTPError, UnicodeError):
        return {"is_product_page": False, "page_verified": False}
