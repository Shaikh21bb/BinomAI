"""Read public product pages and retain only evidence tied to a concrete item."""

import asyncio
import html
import ipaddress
import json
import math
import re
from html.parser import HTMLParser
from typing import Any
from urllib.parse import parse_qsl, urljoin, urlparse

import httpx
from app.services.product_identity import contains_model, model_identifiers


_IMAGE_NOISE = re.compile(r"favicon|logo|sprite|placeholder|/watch/|portal-portable|base_satu|pixel", re.I)
_GENERIC_PATH = re.compile(r"/(category|search|list|catalog/0|catalog/search|shop/search)(/|$)|/f/|^/catalog/?$", re.I)
_COLLECTION_PATH = re.compile(
    r"/(?:collections?|categories)(?:/|$)|/(?:catalog|shop)/cat(?:egory)?-[^/]+(?:/|$)|"
    r"/(?:filters?|facets?)(?:/|$)",
    re.I,
)
_PRODUCT_PATH = re.compile(
    r"/p\d+[-/]|/p/[^/]+|/products?/[^/]+|/goods?/[^/]+|/catalog/\d+/detail|"
    r"/catalog/[^/]+/detail|/items?/\d+|--\d{4,}/?$",
    re.I,
)
_GENERIC_TITLE_WORDS = {"средс", "моющ", "товар", "купит", "ценам", "посуд", "коста"}
_QUANTITY_UNITS = r"(?:упаков(?:ка|ки|ок)|упак\.?|штук(?:а|и)?|шт\.?|единиц\w*|ед\.?|кг|kg|гр|г|g|мл|ml|литр\w*|л|l|м[²³23]|см|мм|м|pcs?|pieces?|meters?)"
_STOCK_TEXT = re.compile(rf"(?:в наличии|на складе|остаток)\s*:?\s*(\d+(?:[.,]\d+)?)\s*({_QUANTITY_UNITS})(?!\w)", re.I)
_MOQ_TEXT = re.compile(rf"(?:минимальн\w*\s+(?:заказ|партия)|мин\.?\s*заказ|minimum\s+order|MOQ)\s*[:—-]?\s*(?:от\s+)?(\d+(?:[.,]\d+)?)\s*({_QUANTITY_UNITS})(?!\w)", re.I)
_CERTIFICATE_TEXT = re.compile(r"сертификат|декларац|\bГОСТ\b|certificate|declaration\s+of\s+conformity", re.I)
_UNIT_CODES = {"H87": "шт", "PCE": "шт", "C62": "ед.", "KGM": "кг", "GRM": "г", "TNE": "т", "MTR": "м", "CMT": "см", "MMT": "мм", "MTK": "м2", "MTQ": "м3", "LTR": "л", "MLT": "мл"}
_SATU_PHONE = re.compile(r"PhoneDescription:(\+7\s*\(\d{3}\)\s*\d{3}[-\s]\d{2}[-\s]\d{2})", re.I)
_PHONE_TEXT = re.compile(r"(?<!\d)(?:\+7|8)\s*\(?\d{3}\)?[\s.-]*\d{3}[\s.-]*\d{2}[\s.-]*\d{2}(?!\d)")
_MARKETPLACE_HOSTS = {"satu.kz", "kaspi.kz", "ozon.kz", "wildberries.kz", "wildberries.ru"}
_VOID_TAGS = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "param", "source", "track", "wbr"}


def _price_number(value: Any) -> float | None:
    if not isinstance(value, (str, int, float)) or isinstance(value, bool):
        return None
    number = re.sub(r"\s+", "", str(value)).replace(",", ".")
    try:
        parsed = float(number)
        return parsed if math.isfinite(parsed) and 0 < parsed <= 1_000_000_000_000 else None
    except ValueError:
        return None


def _availability(value: Any) -> str | None:
    text = str(value or "").rsplit("/", 1)[-1].casefold().replace("-", "")
    return {
        "instock": "InStock", "outofstock": "OutOfStock", "soldout": "SoldOut",
        "preorder": "PreOrder", "backorder": "BackOrder", "discontinued": "Discontinued",
        "limitedavailability": "LimitedAvailability",
    }.get(text)


class _CommercialParser(HTMLParser):
    """Read only the main item's commercial fields, never cart/recommendation prices."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.stack: list[dict[str, Any]] = []
        self.main_root: dict[str, Any] | None = None
        self.heading_seen = False
        self.captures: list[dict[str, Any]] = []
        self.prices: list[str] = []
        self.stock_labels: list[str] = []
        self.root_availability: str | None = None
        self.sku: str | None = None
        self.variant_selector = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]):
        attributes = dict(attrs)
        classes = set((attributes.get("class") or "").casefold().split())
        context = " ".join(attributes.get(key) or "" for key in ("class", "id", "data-testid", "data-widget_type"))
        parent = self.stack[-1] if self.stack else {}
        ignored = parent.get("ignored", False) or tag in {"script", "style", "del", "nav", "header", "footer", "aside"} or bool(re.search(
            r"related|upsell|cross.sell|recommend|cart.totals|mini.cart|old.price|price.old|installment|monthly|credit", context, re.I,
        )) or (tag == "li" and "type-product" in classes)
        root = attributes.get("data-elementor-type") == "product" or (
            tag != "li" and "type-product" in classes
        )
        scope = parent.get("scope", False) or bool(classes & {
            "summary", "entry-summary", "product-summary", "product__info", "product-info",
        }) or "woocommerce-product-price" in (attributes.get("data-widget_type") or "")
        entry = {"tag": tag, "ignored": ignored, "root": root, "scope": scope, "classes": classes}
        if tag == "h1" and classes & {"product_title", "product-title", "product__name", "product-name", "product_name"}:
            self.heading_seen = True
            self.main_root = next((row for row in reversed(self.stack) if row["root"]), None)
            if self.main_root and not self.main_root["ignored"]:
                self.root_availability = next((state for name in self.main_root["classes"] if (state := _availability(name))), None)
        in_main = self.main_root is not None and any(row is self.main_root for row in self.stack)
        eligible = self.heading_seen and (in_main or scope) and not ignored
        kind = None
        if eligible:
            if "variations_form" in classes or (tag == "select" and re.search(r"attribute_|variant|variation|^(?:size|color|colour)$", attributes.get("name") or "", re.I)):
                self.variant_selector = True
            if "price" in classes or classes & {"product__price", "product-price", "product_price"} or attributes.get("itemprop") == "price":
                kind = "price"
            elif classes & {"stock", "availability", "product-availability", "product__availability"}:
                kind = "stock"
            elif "sku" in classes or attributes.get("itemprop") == "sku":
                kind = "sku"
        if tag not in _VOID_TAGS:
            self.stack.append(entry)
            if kind and not any(capture["kind"] == kind for capture in self.captures):
                self.captures.append({"kind": kind, "entry": entry, "text": []})

    def handle_data(self, data: str):
        if self.stack and not self.stack[-1]["ignored"]:
            for capture in self.captures:
                capture["text"].append(data)

    def handle_endtag(self, tag: str):
        index = next((i for i in range(len(self.stack) - 1, -1, -1) if self.stack[i]["tag"] == tag), None)
        if index is None:
            return
        removed = self.stack[index:]
        for capture in list(self.captures):
            if any(capture["entry"] is entry for entry in removed):
                text = _clean("".join(capture["text"]), 300)
                if capture["kind"] == "price":
                    self.prices.append(text)
                elif capture["kind"] == "stock":
                    self.stock_labels.append(text)
                elif capture["kind"] == "sku" and text:
                    self.sku = text
                self.captures.remove(capture)
        del self.stack[index:]

    def price(self) -> tuple[float | None, str | None]:
        values = []
        for text in self.prices:
            for amount, currency in re.findall(r"(\d[\d\s\u00a0\u202f]*(?:[.,]\d{1,2})?)\s*(₸|тенге|тг|KZT|руб\.?|₽|USD|\$|EUR|€)", text, re.I):
                price = _price_number(amount)
                if price:
                    code = "KZT" if currency.casefold() in {"₸", "тенге", "тг", "kzt"} else "RUB" if currency in {"₽", "руб", "руб."} else "USD" if currency in {"USD", "$"} else "EUR"
                    values.append((price, code))
        unique = list(dict.fromkeys(values))
        return unique[0] if len(unique) == 1 else (None, None)

    def availability(self) -> str | None:
        labels = " ".join(self.stock_labels).casefold()
        if re.search(r"нет\s+в\s+наличии|отсутствует|out\s+of\s+stock|sold\s+out", labels):
            return "OutOfStock"
        if re.search(r"под\s*заказ|предзаказ|pre.?order|ожидается", labels):
            return "PreOrder"
        if self.root_availability in {"OutOfStock", "SoldOut", "PreOrder", "BackOrder", "Discontinued"}:
            return self.root_availability
        if re.search(r"\bв\s+наличии\b|\bin\s+stock\b", labels):
            return "InStock"
        return self.root_availability


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


def looks_like_product_url(url: str) -> bool:
    """Identify a concrete product URL without claiming that its page was fetched."""
    if not is_public_url(url):
        return False
    path = urlparse(url).path
    return not (_GENERIC_PATH.search(path) or _COLLECTION_PATH.search(path)) and bool(_PRODUCT_PATH.search(path))


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


def _best_page_image(images: list[tuple[str, str]], page_url: str, title: str) -> str | None:
    title_words = {
        word for word in re.findall(r"[a-zа-яё0-9]+", title.casefold()) if len(word) > 3
    }
    ranked: list[tuple[int, str]] = []
    for candidate, context in images:
        url = _image_url(candidate, page_url)
        if not url:
            continue
        lowered_context = context.casefold()
        score = 20
        if any(marker in lowered_context for marker in ("gallery", "detail", "main", "product", "catalog")):
            score += 40
        score += min(60, 20 * sum(word in lowered_context for word in title_words))
        ranked.append((score, url))
    return max(ranked, default=(0, None), key=lambda row: row[0])[1]


def _quantity_number(value: Any, *, positive: bool = False) -> int | float | None:
    if isinstance(value, bool) or not isinstance(value, (str, int, float)):
        return None
    text = re.sub(r"\s+", "", str(value)).replace(",", ".")
    if not re.fullmatch(r"\d+(?:\.\d+)?", text):
        return None
    number = float(text)
    if not math.isfinite(number) or not (0 < number <= 1_000_000 if positive else 0 <= number <= 1_000_000):
        return None
    return int(number) if number.is_integer() else number


def _unit_text(value: Any) -> str | None:
    text = _clean(value, 30).casefold().rstrip(".")
    aliases = {
        "шт": "шт", "штук": "шт", "штука": "шт", "штуки": "шт", "pc": "шт", "pcs": "шт", "piece": "шт", "pieces": "шт",
        "kg": "кг", "кг": "кг", "g": "г", "гр": "г", "г": "г", "ml": "мл", "мл": "мл",
        "l": "л", "л": "л", "литр": "л", "литра": "л", "литров": "л", "м²": "м2", "м³": "м3",
        "упак": "упак", "упаковка": "упак", "упаковки": "упак", "упаковок": "упак", "meter": "м", "meters": "м",
    }
    return aliases.get(text, text) if text else None


def _quantity_unit(value: dict[str, Any]) -> str | None:
    text = _unit_text(value.get("unitText"))
    code = _UNIT_CODES.get(str(value.get("unitCode") or "").rsplit("/", 1)[-1].upper())
    # Conflicting published units cannot safely be assigned to the quantity.
    return None if text and code and text != code else text or code


def _consistent_quantity(observations: list[tuple[int | float, str | None, str]]) -> tuple[int | float | None, str | None, str | None]:
    amounts = {row[0] for row in observations}
    units = {row[1] for row in observations if row[1]}
    if len(amounts) != 1 or len(units) > 1:
        return None, None, None
    return observations[0][0], next(iter(units), None), observations[0][2][:220]


def _stock_quantity(offer: dict[str, Any], evidence: str) -> tuple[int | float | None, str | None, str | None]:
    observations = []
    for key in ("inventoryLevel", "availableQuantity"):
        level = offer.get(key)
        raw = level.get("value") if isinstance(level, dict) else level
        amount = _quantity_number(raw)
        if amount is not None:
            observations.append((amount, _quantity_unit(level if isinstance(level, dict) else offer), f"{key}: {json.dumps(level, ensure_ascii=False)}"))
    for match in _STOCK_TEXT.finditer(evidence):
        if re.search(r"\b(?:нет|не)\s*$", evidence[max(0, match.start() - 12):match.start()], re.I):
            continue
        amount = _quantity_number(match.group(1))
        if amount is not None:
            observations.append((amount, _unit_text(match.group(2)), match.group(0)))
    return _consistent_quantity(observations)


def _minimum_order(offer: dict[str, Any], evidence: str) -> tuple[int | float | None, str | None]:
    observations = []
    eligible = offer.get("eligibleQuantity")
    if isinstance(eligible, dict):
        amount = _quantity_number(eligible.get("minValue"), positive=True)
        if amount is not None:
            observations.append((amount, _quantity_unit(eligible), "eligibleQuantity.minValue"))
    for key in ("minOrderQuantity", "minimumOrderQuantity"):
        value = offer.get(key)
        amount = _quantity_number(value.get("value") if isinstance(value, dict) else value, positive=True)
        if amount is not None:
            observations.append((amount, _quantity_unit(value if isinstance(value, dict) else offer), key))
    for match in _MOQ_TEXT.finditer(evidence):
        amount = _quantity_number(match.group(1), positive=True)
        if amount is not None:
            observations.append((amount, _unit_text(match.group(2)), match.group(0)))
    amount, unit, _ = _consistent_quantity(observations)
    return amount, unit


def _url_identity(value: Any, page_url: str) -> tuple | None:
    if not isinstance(value, str) or not value.strip():
        return None
    parsed = urlparse(urljoin(page_url, value))
    query = tuple(sorted((key, val) for key, val in parse_qsl(parsed.query) if not key.casefold().startswith("utm_") and key.casefold() not in {"gclid", "fbclid"}))
    return parsed.scheme.casefold(), parsed.netloc.casefold(), parsed.path.rstrip("/"), query, parsed.fragment


def _offer_identity_conflicts(product: dict[str, Any], offer: dict[str, Any], page_url: str, visible_sku: str | None) -> bool:
    item = offer.get("itemOffered") if isinstance(offer.get("itemOffered"), dict) else {}
    page_skus = {str(value).strip() for value in (product.get("sku"), visible_sku) if value is not None and str(value).strip()}
    offer_skus = {str(value).strip() for value in (offer.get("sku"), item.get("sku")) if value is not None and str(value).strip()}
    if len(page_skus) > 1 or len(offer_skus) > 1 or (page_skus and offer_skus and page_skus != offer_skus):
        return True
    page = urlparse(page_url)
    selected = {key: value for key, value in parse_qsl(page.query) if re.fullmatch(
        r"variant(?:_?id)?|variation(?:_?id)?|sku|size|colou?r|attribute_.*", key, re.I,
    )}
    for value in (offer.get("url"), item.get("url")):
        if not isinstance(value, str):
            continue
        target = urlparse(urljoin(page_url, value))
        # A merchant's external offer/checkout URL is not a variant mismatch.
        # Only explicit contradictory selections in the same URL namespace count.
        if target.hostname == page.hostname:
            offered = dict(parse_qsl(target.query))
            if any(key in offered and offered[key] != selected_value for key, selected_value in selected.items()):
                return True
    return False


def _select_offer(product: dict[str, Any], page_url: str, visible_sku: str | None) -> tuple[dict[str, Any], str]:
    if product.get("hasVariant"):
        # A family's shared specifications cannot be silently inherited by a
        # child just because one child offer URL matches. Keep it unresolved.
        return {}, "ambiguous"
    offers = product.get("offers") or {}
    if isinstance(offers, dict) and str(offers.get("@type") or "").rsplit("/", 1)[-1].casefold() == "aggregateoffer":
        offers = offers.get("offers") or []
        if not offers:
            return {}, "ambiguous"
    if not isinstance(offers, list):
        offer = offers if isinstance(offers, dict) else {}
        return ({}, "ambiguous") if _offer_identity_conflicts(product, offer, page_url, visible_sku) else (offer, "single")
    if not offers or any(not isinstance(offer, dict) for offer in offers):
        return {}, "ambiguous"
    if len(offers) == 1:
        return ({}, "ambiguous") if _offer_identity_conflicts(product, offers[0], page_url, visible_sku) else (offers[0], "single")
    target = _url_identity(page_url, page_url)
    by_url = [offer for offer in offers if _url_identity(offer.get("url"), page_url) == target]
    sku = str(visible_sku or product.get("sku") or "").strip()
    by_sku = [offer for offer in offers if sku and str(offer.get("sku") or (offer.get("itemOffered").get("sku") if isinstance(offer.get("itemOffered"), dict) else "") or "").strip() == sku]
    selected = by_url if len(by_url) == 1 else by_sku if len(by_sku) == 1 else []
    if len(selected) == 1 and (not by_url or not by_sku or (len(by_url) == len(by_sku) == 1 and by_url[0] is by_sku[0])) and not _offer_identity_conflicts(product, selected[0], page_url, visible_sku):
        return selected[0], "selected"
    return {}, "ambiguous"


def _price_basis(offer: dict[str, Any], price: float | None, currency: str | None, visible_prices: list[str]) -> tuple[int | float | None, str | None, str]:
    observations = []
    specifications = offer.get("priceSpecification") or []
    if isinstance(specifications, dict):
        specifications = [specifications]
    for specification in specifications if isinstance(specifications, list) else []:
        if not isinstance(specification, dict) or str(specification.get("@type") or "").rsplit("/", 1)[-1] != "UnitPriceSpecification":
            continue
        if specification.get("price") is not None and _price_number(specification["price"]) != price:
            continue
        if specification.get("priceCurrency") and specification["priceCurrency"] != currency:
            continue
        reference = specification.get("referenceQuantity")
        if isinstance(reference, dict) and (amount := _quantity_number(reference.get("value"), positive=True)) is not None:
            observations.append((amount, _quantity_unit(reference), "referenceQuantity"))
    for text in visible_prices:
        for match in re.finditer(rf"(\d[\d\s\u00a0\u202f]*(?:[.,]\d{{1,2}})?)\s*(₸|KZT|тенге|тг)\s*(?:/\s*|за\s+)(?:(\d+(?:[.,]\d+)?)\s*)?({_QUANTITY_UNITS})(?!\w)", text, re.I):
            if currency == "KZT" and _price_number(match.group(1)) == price:
                amount = _quantity_number(match.group(3) or 1, positive=True)
                if amount is not None:
                    observations.append((amount, _unit_text(match.group(4)), match.group(0)))
    amount, unit, _ = _consistent_quantity(observations)
    return (amount, unit, "published") if amount is not None and unit else (None, None, "unknown")


def _certificate_documents(product: dict[str, Any], links: list[tuple[str, str]], page_url: str) -> list[dict[str, str]]:
    candidates = list(links)
    for key in ("subjectOf", "hasCertification"):
        values = product.get(key) or []
        if isinstance(values, dict):
            values = [values]
        for value in values if isinstance(values, list) else []:
            if not isinstance(value, dict):
                continue
            label = _clean(value.get("name"), 180)
            if key == "hasCertification" or _CERTIFICATE_TEXT.search(label):
                candidates.append((value.get("contentUrl") or value.get("url"), label or "Документ о соответствии"))
    documents = []
    seen = set()
    for href, label in candidates:
        if not isinstance(href, str) or not href.strip() or href.startswith("#"):
            continue
        url = urljoin(page_url, href)
        parsed = urlparse(url)
        if not is_public_url(url) or parsed.username or parsed.password or url in seen:
            continue
        seen.add(url)
        documents.append({"url": url, "label": label, "status": "unverified"})
        if len(documents) == 10:
            break
    return documents


def _wholesale_terms(evidence: str) -> str | None:
    for line in re.split(r"[\n;]|(?<=[.!?])\s+", evidence):
        if re.search(r"\b(?:оптом|оптов\w*\s+(?:цен\w*|заказ\w*|парт\w*|продаж\w*|поставк\w*)|wholesale)\b", line, re.I) and not re.search(
            r"\bне\s+(?:(?:работа\w*|прода[её]\w*|явля\w*)\s+)?(?:оптом|оптов\w*)|\bбез\s+опт\w*|\bопт\w*(?:\s+цен\w*)?\s+(?:нет|отсутств\w*|не\s+(?:указ\w*|действ\w*))|\b(?:not|no)\s+wholesale\b|\bне\s+(?:принима\w*|работа\w*|прода[её]\w*)\b", line, re.I,
        ):
            return line.strip()[:220]
    return None


class _SellerContactParser(HTMLParser):
    """Read labelled company contacts, avoiding product descriptions and reviews."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.stack: list[tuple[str, bool, bool]] = []
        self.text: list[str] = []
        self.seller_links: list[str] = []
        self.vendor_links: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]):
        attributes = dict(attrs)
        context = " ".join(attributes.get(key) or "" for key in ("class", "id", "itemprop")).casefold()
        inherited_seller = bool(self.stack and self.stack[-1][1])
        ignored = bool(self.stack and self.stack[-1][2]) or tag in {"script", "style"} or bool(
            re.search(r"description|review|comment", context)
        )
        seller_contact = inherited_seller or attributes.get("data-qaid") in {
            "company_phones", "seller_phone", "seller_phones",
        } or any(marker in context for marker in (
            "b-sidebar-contacts__phone", "b-header-phones", "b-contacts__phone", "b-drop-phones__number",
        ))
        href = attributes.get("href") or ""
        if href.casefold().startswith("tel:") and not ignored:
            self.vendor_links.append(href[4:].split(";", 1)[0])
            if seller_contact:
                self.seller_links.append(href[4:].split(";", 1)[0])
        if tag not in {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "param", "source", "track", "wbr"}:
            self.stack.append((tag, seller_contact, ignored))

    def handle_endtag(self, tag: str):
        for index in range(len(self.stack) - 1, -1, -1):
            if self.stack[index][0] == tag:
                del self.stack[index:]
                break

    def handle_data(self, data: str):
        if self.stack and self.stack[-1][1] and not self.stack[-1][2]:
            self.text.append(data)


def _seller_details(offer: dict[str, Any], markup: str, page_url: str) -> tuple[str | None, list[str]]:
    """Return only seller details explicitly published on the product page."""
    seller = offer.get("seller") or {}
    if not isinstance(seller, dict):
        seller = {}
    name = _clean(seller.get("name"), 200) or None
    contacts = _SellerContactParser()
    contacts.feed(markup)
    host = (urlparse(page_url).hostname or "").removeprefix("www.")
    marketplace = any(host == domain or host.endswith("." + domain) for domain in _MARKETPLACE_HOSTS)
    points = seller.get("contactPoint") or []
    if isinstance(points, dict):
        points = [points]
    published = seller.get("telephone")
    candidates = (published if isinstance(published, list) else [published]) + [
        point.get("telephone") for point in points if isinstance(point, dict)
    ] + contacts.seller_links + _PHONE_TEXT.findall(" ".join(contacts.text))
    if not marketplace:
        # On a store's own domain tel links belong to that storefront. On a
        # marketplace the footer phone may belong to platform support instead.
        candidates += contacts.vendor_links
    if name:
        candidates += _SATU_PHONE.findall(markup)
    phones: list[str] = []
    seen: set[str] = set()
    for candidate in candidates:
        phone = _clean(candidate, 40)
        digits = re.sub(r"\D", "", phone)
        if len(digits) not in {10, 11, 12} or digits in seen:
            continue
        seen.add(digits)
        phones.append(phone)
        if len(phones) >= 3:
            break
    return name, phones


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


def _has_collection_schema(value: Any) -> bool:
    """Only page-level graph/mainEntity types count, not a product's breadcrumbs."""
    if isinstance(value, list):
        return any(_has_collection_schema(part) for part in value)
    if not isinstance(value, dict):
        return False
    kinds = value.get("@type", [])
    kinds = kinds if isinstance(kinds, list) else [kinds]
    if any(str(kind).rsplit("/", 1)[-1].casefold() in {"collectionpage", "itemlist"} for kind in kinds):
        return True
    return any(_has_collection_schema(value[key]) for key in ("@graph", "mainEntity") if key in value)


def _own_product_identity(product: dict[str, Any], page_url: str, heading: str, product_heading: bool) -> bool:
    """A collection's featured item is not the item identified by the current URL."""
    name = _clean(product.get("name")).casefold()
    if not name or name != _clean(heading).casefold() or not (product_heading or looks_like_product_url(page_url)):
        return False
    page = urlparse(page_url)
    for key in ("url", "@id", "mainEntityOfPage"):
        target = product.get(key)
        if isinstance(target, dict):
            target = target.get("@id") or target.get("url")
        if not isinstance(target, str):
            continue
        parsed = urlparse(urljoin(page_url, target))
        if parsed.hostname == page.hostname and parsed.path.rstrip("/") == page.path.rstrip("/"):
            return True
    return False


class _ProductDetailsParser(HTMLParser):
    """Read the first item's description/specification component, not recommendations."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.stack: list[dict[str, Any]] = []
        self.heading_seen = False
        self.root_chosen = False
        self.text: list[str] = []
        self.properties: dict[str, str] = {}
        self.row: dict[str, Any] | None = None
        self.description_open = True
        self.attributes_open = True
        self.section_heading: dict[str, Any] | None = None
        self.document_section = False
        self.document_link: dict[str, Any] | None = None
        self.document_links: list[tuple[str, str]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]):
        attributes = dict(attrs)
        classes = (attributes.get("class") or "").casefold()
        context = " ".join(attributes.get(key) or "" for key in ("class", "id", "data-testid", "data-widget_type"))
        parent = self.stack[-1] if self.stack else {}
        ignored = parent.get("ignored", False) or tag in {"script", "style", "nav", "footer", "header", "aside"} or bool(
            re.search(r"related|recommend|upsell|cross.sell|recently.viewed", context, re.I)
        )
        if tag == "h1" and not ignored:
            self.heading_seen = True
        is_root = bool(set(classes.split()) & {
            "product-description", "product__description", "product-details", "product-specifications", "product-attributes",
        }) or bool(re.search(r"(?:item|product)description[\w-]*__root(?:\s|$)", classes))
        root = self.heading_seen and not self.root_chosen and is_root and not ignored
        if root:
            self.root_chosen = True
        scoped = root or parent.get("scoped", False)
        entry = {"tag": tag, "ignored": ignored, "scoped": scoped, "field": parent.get("field")}
        if scoped and not ignored:
            if tag == "a" and attributes.get("href") and (self.description_open or self.attributes_open or self.document_section):
                self.document_link = {"entry": entry, "href": attributes["href"], "text": [attributes.get("title") or ""], "section": self.document_section}
            if tag in {"h2", "h3", "h4"}:
                self.section_heading = {"entry": entry, "text": []}
            if self.attributes_open and re.search(r"(?:^|[-_\s])(?:attr|attribute|spec|property)row(?:\s|$)", classes):
                self.row = {"entry": entry, "label": [], "value": []}
            if self.row is not None:
                if re.search(r"(?:attr|attribute|spec|property)(?:label|name)(?:\s|$)", classes):
                    entry["field"] = "label"
                elif re.search(r"(?:attr|attribute|spec|property)value(?:\s|$)", classes):
                    entry["field"] = "value"
        if tag not in _VOID_TAGS:
            self.stack.append(entry)

    def handle_data(self, data: str):
        if not self.stack or self.stack[-1]["ignored"] or not self.stack[-1]["scoped"]:
            return
        if self.document_link is not None:
            self.document_link["text"].append(data)
        if self.row is not None:
            field = self.stack[-1].get("field")
            if field:
                self.row[field].append(data)
        elif self.section_heading is not None:
            self.section_heading["text"].append(data)
        elif self.description_open:
            self.text.append(data)

    def handle_endtag(self, tag: str):
        index = next((i for i in range(len(self.stack) - 1, -1, -1) if self.stack[i]["tag"] == tag), None)
        if index is None:
            return
        removed = self.stack[index:]
        if self.document_link is not None and any(self.document_link["entry"] is entry for entry in removed):
            label = _clean(" ".join(self.document_link["text"]), 180)
            if _CERTIFICATE_TEXT.search(label) or self.document_link["section"]:
                self.document_links.append((self.document_link["href"], label or "Документ о соответствии"))
            self.document_link = None
        if self.section_heading is not None and any(self.section_heading["entry"] is entry for entry in removed):
            label = _clean(" ".join(self.section_heading["text"])).casefold()
            self.document_section = bool(_CERTIFICATE_TEXT.search(label))
            self.description_open = label in {"описание", "о товаре", "description", "product description"}
            self.attributes_open = self.description_open or bool(re.search(
                r"характеристик|параметр|состав|материал|specification|product details|properties", label,
            ))
            self.section_heading = None
        if self.row is not None and any(self.row["entry"] is entry for entry in removed):
            label = _clean(" ".join(self.row["label"]), 100)
            value = _clean(" ".join(self.row["value"]), 250)
            if label and value:
                # Conflicting component rows are ambiguous, never choose the nicer one.
                previous = self.properties.get(label)
                self.properties[label] = value if previous in {None, value} else f"{previous}; {value}"
            self.row = None
        if any(entry["scoped"] for entry in removed):
            self.text.append("\n")
        del self.stack[index:]


class _PageParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.meta: dict[str, str] = {}
        self.scripts: list[str] = []
        self._script: list[str] | None = None
        self._title: list[str] | None = None
        self._heading: list[str] | None = None
        self._heading_is_product = False
        self.title = ""
        self.heading = ""
        self.product_heading = False
        self.images: list[tuple[str, str]] = []
        self._row: list[str] | None = None
        self._cell: list[str] | None = None
        self.rows: list[list[str]] = []
        self.canonical: str | None = None
        self._nodes: list[dict[str, Any]] = []
        self._section_heading: dict[str, Any] | None = None
        self._non_product_section = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]):
        attributes = dict(attrs)
        parent = self._nodes[-1] if self._nodes else {}
        context = " ".join(attributes.get(key) or "" for key in ("class", "id", "data-testid", "data-widget_type"))
        ignored = parent.get("ignored", False) or tag in {"nav", "header", "footer", "aside"} or bool(
            re.search(r"related|recommend|upsell|cross.sell|recently.viewed", context, re.I)
        )
        if tag not in _VOID_TAGS:
            self._nodes.append({"tag": tag, "ignored": ignored})
        if tag in {"h2", "h3", "h4"} and not ignored:
            self._section_heading = {"tag": tag, "text": []}
        if tag == "link" and "canonical" in (attributes.get("rel") or "").split():
            self.canonical = attributes.get("href")
        elif tag == "meta":
            key = attributes.get("property") or attributes.get("name") or attributes.get("itemprop")
            if key and attributes.get("content"):
                self.meta[key.lower()] = attributes["content"] or ""
        elif tag == "script" and "ld+json" in (attributes.get("type") or "").lower():
            self._script = []
        elif tag == "title":
            self._title = []
        elif tag == "h1" and not ignored:
            self._heading = []
            classes = (attributes.get("class") or "").split()
            self._heading_is_product = bool(set(classes) & {
                "product_title", "product-title", "product__name", "product-name", "product_name",
            })
        elif tag == "img":
            candidate = attributes.get("data-src") or attributes.get("data-lazy-src") or attributes.get("src")
            if not candidate and attributes.get("srcset"):
                candidate = attributes["srcset"].split(",")[-1].strip().split(" ")[0]
            if candidate:
                context = " ".join(
                    attributes.get(key) or "" for key in ("alt", "class", "id", "itemprop")
                )
                self.images.append((candidate, context))
        elif tag == "tr" and not ignored and not self._non_product_section:
            self._row = []
        elif tag in {"th", "td"} and self._row is not None:
            self._cell = []

    def handle_data(self, data: str):
        if self._section_heading is not None:
            self._section_heading["text"].append(data)
        if self._script is not None:
            self._script.append(data)
        if self._title is not None:
            self._title.append(data)
        if self._heading is not None:
            self._heading.append(data)
        if self._cell is not None and not (self._nodes and self._nodes[-1]["ignored"]):
            self._cell.append(data)

    def handle_endtag(self, tag: str):
        if self._section_heading is not None and self._section_heading["tag"] == tag:
            label = _clean(" ".join(self._section_heading["text"])).casefold()
            if re.search(r"доставк|возврат|оплат|delivery|returns|shipping|payment", label):
                self._non_product_section = True
            elif re.search(r"описание|характеристик|параметр|состав|материал|description|specification|product details|properties", label):
                self._non_product_section = False
            self._section_heading = None
        if tag == "script" and self._script is not None:
            self.scripts.append("".join(self._script))
            self._script = None
        elif tag == "title" and self._title is not None:
            self.title = _clean("".join(self._title))
            self._title = None
        elif tag == "h1" and self._heading is not None:
            if not self.heading:
                self.heading = _clean("".join(self._heading))
                self.product_heading = self._heading_is_product
            self._heading = None
        elif tag in {"th", "td"} and self._cell is not None:
            if self._row is not None:
                self._row.append(_clean("".join(self._cell), 250))
            self._cell = None
        elif tag == "tr" and self._row is not None:
            if len(self._row) == 2 and all(self._row):
                self.rows.append(self._row)
            self._row = None
        index = next((i for i in range(len(self._nodes) - 1, -1, -1) if self._nodes[i]["tag"] == tag), None)
        if index is not None:
            del self._nodes[index:]


def parse_product_page(markup: str, page_url: str) -> dict[str, Any]:
    parser = _PageParser()
    parser.feed(markup)
    products = []
    collection_schema = False
    for script in parser.scripts:
        try:
            structured = json.loads(script)
        except (ValueError, TypeError):
            continue
        products.extend(_product_objects(structured))
        collection_schema = collection_schema or _has_collection_schema(structured)
    product = next((item for item in products if _own_product_identity(
        item, page_url, parser.heading, parser.product_heading,
    )), products[0] if products else None)

    path = urlparse(page_url).path
    host = (urlparse(page_url).hostname or "").removeprefix("www.")
    if host == "olx.kz" and not re.match(r"/(?:d/)?obyavlenie/", path, re.I):
        # OLX category/search pages embed featured Product/Offer JSON-LD.
        return {"is_product_page": False, "page_verified": True}
    # Satu's top-level *.html pages are collections. Their JSON-LD often
    # contains an unrelated featured Product with its own photo and price.
    if (
        urlparse(page_url).hostname in {"satu.kz", "www.satu.kz"}
        and re.fullmatch(r"/[^/]+\.html", path, re.I)
        and not re.match(r"/p\d+(?:-|/)", path, re.I)
    ):
        return {"is_product_page": False, "page_verified": True}
    page_title = _clean(parser.meta.get("og:title") or parser.title)
    if re.search(r"^(?:404\b|access denied|just a moment|security check)|страниц[аы].*не найден", page_title, re.I):
        return {"is_product_page": False, "page_verified": False}
    product_name = _clean((product or {}).get("name"))
    title_words = {word[:5] for word in re.findall(r"[a-zа-яё]{5,}", page_title.casefold())} - _GENERIC_TITLE_WORDS
    product_words = {word[:5] for word in re.findall(r"[a-zа-яё]{5,}", product_name.casefold())} - _GENERIC_TITLE_WORDS
    page_models = model_identifiers(parser.heading or page_title)
    exact_name_on_page = bool(product_name and product_name.casefold() in page_title.casefold())
    name_on_page = (not page_title or not product_name or exact_name_on_page or len(title_words & product_words) >= 2) and (
        not page_models or all(contains_model(product_name, model) for model in page_models)
    )
    if product and not name_on_page:
        # Recommendations embedded beside the main item are not its evidence.
        product = None
    if (collection_schema or _COLLECTION_PATH.search(path)) and not (
        product and _own_product_identity(product, page_url, parser.heading, parser.product_heading)
    ):
        # Listing prices/stock belong to one of the listed items, not this page.
        return {"is_product_page": False, "page_verified": True}
    leaf = path.rstrip("/").rsplit("/", 1)[-1]
    concrete_catalog_leaf = bool(
        "/catalog/" in path.casefold()
        and any(character.isdigit() for character in leaf)
        and parser.heading
        and parser.images
    )
    is_product = not _GENERIC_PATH.search(path) and (
        (bool(product) and name_on_page)
        or (looks_like_product_url(page_url) and bool(parser.heading))
        or concrete_catalog_leaf
        or (parser.product_heading and bool(parser.images) and bool(parser.heading))
    )
    if not is_product:
        return {"is_product_page": False, "page_verified": True}

    product = product or {}
    name = _clean(product.get("name") or parser.meta.get("og:title") or parser.heading or parser.title)
    description = _clean(product.get("description") or parser.meta.get("og:description") or parser.meta.get("description"), 2400)
    details = _ProductDetailsParser()
    details.feed(markup)
    detailed_description = _clean(" ".join(details.text), 2400)
    if detailed_description:
        description = detailed_description
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
    for key, value in list(details.properties.items())[:50]:
        if key not in properties:
            properties[key] = value

    commercial = _CommercialParser()
    commercial.feed(markup)
    offer, variant_status = _select_offer(product, page_url, commercial.sku)
    if commercial.variant_selector and variant_status == "single":
        # A family price beside an unresolved size/colour selector is not a
        # selected variant's offer, even when JSON-LD contains one default.
        if commercial.sku and str(offer.get("sku") or "").strip() == commercial.sku:
            variant_status = "selected"
        else:
            offer, variant_status = {}, "ambiguous"
    visible_price, visible_currency = commercial.price()
    price = _price_number(offer.get("price"))
    currency = offer.get("priceCurrency") if price else None
    if price is None and variant_status == "single":
        price = _price_number(parser.meta.get("product:price:amount"))
        currency = parser.meta.get("product:price:currency") if price else None
    if price is None and variant_status == "single":
        price, currency = visible_price, visible_currency
    elif variant_status == "single" and visible_price is not None and (not currency or currency == visible_currency):
        # A scoped sale price displayed now can supersede an old JSON-LD amount.
        price, currency = visible_price, visible_currency
    image = (
        _image_url(product.get("image"), page_url)
        or _image_url(parser.meta.get("og:image"), page_url)
        or _image_url(parser.meta.get("twitter:image") or parser.meta.get("twitter:image:src"), page_url)
        or _best_page_image(parser.images, page_url, name or page_title)
    )
    evidence = "\n".join(filter(None, [name, description, *[f"{k}: {v}" for k, v in properties.items()]]))[:6500]
    commercial_evidence = "\n".join([description, *[f"{key}: {value}" for key, value in properties.items()], *commercial.stock_labels]) if variant_status == "single" else ""
    stock_quantity, stock_unit, stock_evidence = _stock_quantity(offer, commercial_evidence)
    min_order_quantity, min_order_unit = _minimum_order(offer, commercial_evidence)
    price_quantity, price_unit, price_basis_status = _price_basis(offer, price, currency, commercial.prices if variant_status == "single" else [])
    wholesale_terms = _wholesale_terms(commercial_evidence if variant_status == "single" else _clean(offer.get("description"), 2400))
    availability = _availability(offer.get("availability"))
    visible_availability = commercial.availability() if variant_status == "single" else None
    if not availability or visible_availability in {"OutOfStock", "SoldOut", "PreOrder", "BackOrder", "Discontinued"}:
        availability = visible_availability or availability
    if re.search(r"(?:^|[\n;.!?])\s*(?:наличие\s*[:—-]\s*)?(?:нет\s+в\s+наличии|out\s+of\s+stock)\b", commercial_evidence, re.I):
        availability = "OutOfStock"
    if stock_quantity == 0:
        availability = "OutOfStock"
    if variant_status == "ambiguous":
        price = currency = availability = stock_quantity = stock_unit = stock_evidence = None
        min_order_quantity = min_order_unit = price_quantity = price_unit = wholesale_terms = None
        price_basis_status = "unknown"
    seller_name, seller_phones = _seller_details(offer, markup, page_url)
    certificate_documents = _certificate_documents(product, details.document_links, page_url)
    certificate_claim = any(_CERTIFICATE_TEXT.search(line) and not re.search(
        r"\bнет\s+сертификат\w*|\bбез\s+сертификат\w*|\bне\s+(?:соответств\w*|сертифицир\w*|требу\w*)|отсутств\w*", line, re.I,
    ) for line in evidence.splitlines())
    return {
        "is_product_page": True,
        "page_verified": True,
        "title": name,
        "description": description,
        "characteristics": properties,
        "image_url": image,
        "price": price,
        "currency": currency if price else None,
        "price_quantity": price_quantity,
        "price_unit": price_unit,
        "price_basis_status": price_basis_status,
        "availability": availability,
        "canonical_url": urljoin(page_url, parser.canonical) if parser.canonical and urlparse(urljoin(page_url, parser.canonical)).hostname == urlparse(page_url).hostname else None,
        "product_sku": None if variant_status == "ambiguous" else _clean(str(offer.get("sku") or product.get("sku") or commercial.sku or ""), 120) or None,
        "variant_status": variant_status,
        "stock_quantity": stock_quantity,
        "stock_unit": stock_unit,
        "stock_evidence": stock_evidence,
        "min_order_quantity": min_order_quantity,
        "min_order_unit": min_order_unit,
        "wholesale_terms": wholesale_terms,
        "certificate_status": "document_linked" if certificate_documents else "claim_only" if certificate_claim else "missing",
        "certificate_documents": certificate_documents,
        "seller_name": seller_name,
        "seller_phone": seller_phones[0] if seller_phones else None,
        "seller_phones": seller_phones,
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
