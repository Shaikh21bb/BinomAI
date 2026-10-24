import re
import asyncio
import html
import math
from html.parser import HTMLParser
import structlog
import httpx
from typing import List, Dict, Any, Optional
from urllib.parse import parse_qs, parse_qsl, quote, urljoin, urlparse, unquote

from app.core.config import settings
from app.services.product_identity import contains_model, model_identifiers
from app.services.product_matching import _compare_locally, _requirements, _type_check
from app.services.product_pages import _IMAGE_NOISE, fetch_product_page, is_public_url, looks_like_product_url

logger = structlog.get_logger(__name__)

_TYPE_STOP_WORDS = {
    "для", "товар", "изделие", "средство", "моющее", "жидкое", "жидкий", "купить", "цена",
    "женский", "женская", "женское", "мужской", "мужская", "детский", "детская", "шт", "штук",
}
_MAX_PAGE_READS = 24
_MAX_QUERY_VARIANTS = 6
_COMPLETE_IN_STOCK_TARGET = 3


def _word_stem(word: str) -> str:
    stem = re.sub(r"(?:ами|ями|ого|ему|ыми|ими|ая|яя|ое|ее|ые|ие|ий|ый|ой|ов|ев|ам|ям|ах|ях|ом|ем|а|я|ы|и|у|ю|е)$", "", word)
    return stem if len(stem) >= 4 else word


def _transliterate(text: str) -> str:
    # Public vendor URL slugs often become discovery titles before the page is read.
    alphabet = {
        "а": "a", "б": "b", "в": "v", "г": "g", "д": "d", "е": "e", "ё": "e",
        "ж": "zh", "з": "z", "и": "i", "й": "y", "к": "k", "л": "l", "м": "m",
        "н": "n", "о": "o", "п": "p", "р": "r", "с": "s", "т": "t", "у": "u",
        "ф": "f", "х": "kh", "ц": "ts", "ч": "ch", "ш": "sh", "щ": "shch", "ы": "y",
        "э": "e", "ю": "yu", "я": "ya", "ъ": "", "ь": "",
    }
    return "".join(alphabet.get(char, char) for char in text.casefold())


def _primary_query(query: str) -> str:
    """Keep the product type; its detailed requirements are checked after discovery."""
    if model_identifiers(query):
        return query
    short = re.split(r";|\s+(?:на|из|с|со)\s+", query, maxsplit=1, flags=re.I)[0].strip()
    return short if len(short.split()) >= 2 else query


def _search_queries(query: str, specs: str | None = None) -> list[str]:
    """Use only supplied product characteristics; never invent brands or equivalents."""
    primary = _primary_query(query)
    supplied = " ".join([query, specs or ""])
    supplied = re.split(r"(?:Место|Срок|Адрес|Условия)\s+поставки\s*:", supplied, maxsplit=1, flags=re.I)[0]
    materials = re.findall(r"\bшерст\w*", supplied, re.I)
    fasteners = re.findall(r"\bна\s+(?:молнии|замке)\b", supplied, re.I)
    # These two phrases describe the same fastening, not an invented alternative
    # material/brand. Separate queries avoid requiring every tender word in SEO.
    zipper = ["на молнии"] if any("замке" in value.casefold() for value in fasteners) else []
    if fasteners and not zipper:
        zipper = ["на замке"]
    construction = re.findall(r"(?:плотн\w*\s+)?вязк\w*|трикотаж\w*", supplied, re.I)
    measurements = re.findall(
        r"(?<![a-z0-9])\d+(?:[,.]\d+)?\s*(?:мл|кг|мм|см|кВт|Вт|литр\w*|дюйм\w*)(?!\w)",
        supplied, re.I,
    )
    qualifiers = list(dict.fromkeys(value.casefold() for value in [
        *materials, *zipper, *construction, *measurements, *fasteners,
    ]))
    # Reserve both an availability-intent query and the broad type. A long full
    # name must not consume the slot needed for an independent characteristic.
    focused = [f"{primary} {value}" for value in qualifiers if value not in primary.casefold()]
    options = focused[:_MAX_QUERY_VARIANTS - 2] + [f"{primary} в наличии", primary]
    if not specs:
        options = [primary, *focused[:_MAX_QUERY_VARIANTS - 2], f"{primary} в наличии"]
    unique: dict[str, str] = {}
    for option in options:
        value = " ".join(option.split())[:150]
        unique.setdefault(value.casefold(), value)
    return list(unique.values())[:_MAX_QUERY_VARIANTS]


def _result_quality(row: Dict[str, Any]) -> tuple:
    verified = bool(row.get("is_product_page") and row.get("page_verified"))
    stock_priority = {"InStock": 5, "LimitedAvailability": 4, None: 3, "PreOrder": 2, "BackOrder": 2, "OutOfStock": 1, "SoldOut": 1, "Discontinued": 0}
    return (
        verified,
        stock_priority.get(row.get("availability"), 3) if verified else -1,
        sum(bool(row.get(key)) for key in ("image_url", "price", "seller_phone")),
    )


def _local_requirement_states(row: Dict[str, Any], requirements: List[Dict[str, str]]) -> list[str]:
    """Pure source checks only: discovery must never call an AI for each batch."""
    if not (row.get("is_product_page") and row.get("page_verified")):
        return []
    evidence = row.get("evidence_text") or ""
    return [
        (_type_check(req["text"], evidence) if req["id"] == "type" else _compare_locally(req["text"], evidence))["status"]
        for req in requirements
    ]


def _technical_quality(row: Dict[str, Any], requirements: List[Dict[str, str]]) -> tuple:
    states = _local_requirement_states(row, requirements)
    if not states:
        rank = -1
    elif "mismatch" in states:
        rank = 0
    elif states[0] != "matched":
        rank = 1
    else:
        rank = 3 if all(state == "matched" for state in states) else 2
    return rank, _result_quality(row), states.count("matched")


def _positive_number(value: Any) -> bool:
    if isinstance(value, bool):
        return False
    try:
        number = float(value)
        return math.isfinite(number) and number > 0
    except (TypeError, ValueError, OverflowError):
        return False


def _commercially_complete_in_stock(row: Dict[str, Any]) -> bool:
    image = row.get("image_url")
    currency = row.get("currency")
    phones = row.get("seller_phones")
    phone_values = [*(phones if isinstance(phones, list) else []), row.get("seller_phone")]
    return bool(
        row.get("is_product_page") and row.get("page_verified") and is_public_url(row.get("url") or "")
        and row.get("availability") == "InStock"
        and (row.get("stock_quantity") is None or _positive_number(row["stock_quantity"]))
        and isinstance(image, str) and is_public_url(image) and not _IMAGE_NOISE.search(image)
        and _positive_number(row.get("price")) and isinstance(currency, str) and currency.strip()
        and any(isinstance(phone, str) and phone.strip() and re.search(r"\d", phone) for phone in phone_values)
    )


def _complete_in_stock(results: List[Dict[str, Any]], requirements: List[Dict[str, str]]) -> int:
    if len(requirements) < 2:
        # A confirmed type alone is not technical compliance with a tender.
        return 0
    return sum(
        bool(_commercially_complete_in_stock(row)
             and (states := _local_requirement_states(row, requirements))
             and all(state == "matched" for state in states))
        for row in results
    )


def _relevant_candidates(results: List[Dict[str, Any]], query: str) -> List[Dict[str, Any]]:
    if model_identifiers(query):
        return _matching_models(results, query)
    return [row for row in results if _relevant_result(row, query)]

# Kazakhstan marketplaces used for fallback links
MARKETPLACES = [
    {"name": "Kaspi.kz", "url": "https://kaspi.kz/shop/search/?text={q}"},
    {"name": "Satu.kz", "url": "https://satu.kz/search?search_term={q}"},
    {"name": "Alser.kz", "url": "https://alser.kz/search?q={q}"},
    {"name": "Sulpak.kz", "url": "https://www.sulpak.kz/f/{q}"},
    {"name": "Technodom.kz", "url": "https://www.technodom.kz/search?recommended_by=search&q={q}"},
    {"name": "Wildberries.kz", "url": "https://www.wildberries.kz/catalog/0/search.aspx?search={q}"},
]


async def search_products(query: str, region: Optional[str] = None, *, specs: str | None = None, closure_policy: str | None = None) -> List[Dict[str, Any]]:
    """
    Search the web for a product by name + specs, optionally scoped to a region.
    Priority: Google CSE (if configured) -> DuckDuckGo -> marketplace links fallback.
    Product pages are read for characteristics and a real product photo.
    """
    results: List[Dict[str, Any]] = []
    visited: set[tuple] = set()
    queries = _search_queries(query, specs)
    requirements = _requirements(query, specs, closure_policy=closure_policy) if closure_policy is not None else _requirements(query, specs)
    primary_query = queries[0]

    async def consume(batch: List[Dict[str, Any]], remaining_batches: int = 1) -> None:
        nonlocal results
        candidates = []
        remaining_reads = _MAX_PAGE_READS - len(visited)
        page_limit = min(8, max(1, (remaining_reads + remaining_batches - 1) // remaining_batches))
        relevant = _unique_results(_relevant_candidates(batch, query))
        for row in sorted(relevant, key=lambda row: not looks_like_product_url(row.get("url") or "")):
            key = _url_identity(row.get("url") or "")
            if key in visited or len(visited) >= _MAX_PAGE_READS:
                continue
            visited.add(key)
            candidates.append(row)
            if len(candidates) >= page_limit:
                break
        if candidates:
            enriched = _relevant_candidates(await enrich_product_pages(candidates), query)
            results = _unique_results(results + enriched)

    q = primary_query
    if region:
        q = f"{primary_query} купить {region}"

    try:
        if settings.GOOGLE_CSE_API_KEY and settings.GOOGLE_CSE_ID:
            google_results = await _google_cse(q, region)
            if google_results:
                await consume(google_results, len(queries) + 2)
    except Exception as e:
        logger.warning("google_cse_search_failed", error=str(e)[:200])

    for index, search_query in enumerate(queries):
        if _complete_in_stock(results, requirements) >= _COMPLETE_IN_STOCK_TARGET or len(visited) >= _MAX_PAGE_READS:
            break
        try:
            await consume(await _duckduckgo(search_query, region), len(queries) - index + 1)
        except Exception as e:
            logger.warning("duckduckgo_search_failed", error_type=type(e).__name__)

    # Long tender prose can make generic web search return categories. A short
    # marketplace product-page query gives concrete items to inspect.
    try:
        if _complete_in_stock(results, requirements) >= _COMPLETE_IN_STOCK_TARGET or len(visited) >= _MAX_PAGE_READS:
            return sorted(results, key=lambda row: _technical_quality(row, requirements), reverse=True)[:12]
        marketplace_query = re.sub(r"моющее средство для посуды", "средство для мытья посуды", primary_query, flags=re.I)
        short_query = marketplace_query.split(";")[0][:85]
        targeted_batches = await asyncio.gather(
            _satu_search(short_query, region),
            _duckduckgo(f"{short_query} site:kaspi.kz/shop/p/", None),
            _duckduckgo(f"{short_query} site:satu.kz/p", None),
            return_exceptions=True,
        )
        concrete_urls = [
            row
            for batch in targeted_batches
            if isinstance(batch, list)
            for row in batch
            if looks_like_product_url(row.get("url") or "")
        ]
        await consume(concrete_urls)
    except Exception as e:
        logger.warning("targeted_product_search_failed", error_type=type(e).__name__)

    # Search pages remain discoverable links, not concrete product cards.
    results = sorted(results, key=lambda row: _technical_quality(row, requirements), reverse=True)
    return results[:12] if any(row.get("is_product_page") for row in results) else results[:10] + _marketplace_links(query, region)


def _satu_product_results(markup: str, region: Optional[str] = None) -> List[Dict[str, Any]]:
    """Extract only concrete product URLs from Satu's public search results."""
    results: List[Dict[str, Any]] = []
    seen: set[str] = set()
    for href in re.findall(r'href=["\']([^"\']+)["\']', markup, flags=re.I):
        url = urljoin("https://satu.kz", href.replace("&amp;", "&"))
        parsed = urlparse(url)
        if parsed.hostname not in {"satu.kz", "www.satu.kz"} or not looks_like_product_url(url):
            continue
        canonical = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
        if canonical in seen:
            continue
        seen.add(canonical)
        slug = re.sub(r"^p\d+-|\.html$", "", parsed.path.rsplit("/", 1)[-1], flags=re.I)
        title = " ".join(part for part in slug.replace("-", " ").split() if part).strip()
        results.append({
            "title": title.capitalize() if title else "Товар на Satu.kz",
            "snippet": "Конкретная товарная страница из результатов Satu.kz",
            "price": None,
            "currency": None,
            "shop": "Satu.kz",
            "city": region,
            "url": canonical,
            "image_url": None,
        })
        if len(results) >= 12:
            break
    return results


async def _satu_search(query: str, region: Optional[str]) -> List[Dict[str, Any]]:
    """Use Satu's public search page when general search engines return no products."""
    search_query = f"{query} {region}" if region else query
    url = f"https://satu.kz/search?search_term={quote(search_query)}"
    headers = {"User-Agent": "Mozilla/5.0 (compatible; BinomProductResearch/1.0)"}
    async with httpx.AsyncClient(timeout=15.0, headers=headers, follow_redirects=True) as client:
        response = await client.get(url)
        response.raise_for_status()
        return _satu_product_results(response.text[:1_200_000], region)


def _url_identity(url: str) -> tuple:
    parsed = urlparse(url)
    query = tuple(sorted((key, value) for key, value in parse_qsl(parsed.query, keep_blank_values=True)
                         if not key.casefold().startswith("utm_") and key.casefold() not in {"gclid", "fbclid", "yclid"}))
    return (parsed.hostname or "").removeprefix("www."), parsed.path.rstrip("/"), query


def _result_identity(row: Dict[str, Any]) -> tuple:
    url = row.get("url") or ""
    host, path, query = _url_identity(url)
    if row.get("page_verified"):
        if row.get("product_sku"):
            return host, "sku", str(row["product_sku"]), query
        canonical = row.get("canonical_url")
        if canonical and not query and _url_identity(canonical)[0] == host:
            return _url_identity(canonical)
    return host, path, query


def _unique_results(results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    unique: dict[tuple, Dict[str, Any]] = {}
    by_url: dict[tuple, Dict[str, Any]] = {}
    for row in results:
        url = row.get("url") or ""
        key = _url_identity(url)
        if url and (key not in by_url or _result_quality(row) > _result_quality(by_url[key])):
            by_url[key] = row
    for row in by_url.values():
        url = row.get("url") or ""
        if not url:
            continue
        key = _result_identity(row)
        previous = unique.get(key)
        # A blocked repeat lookup must not overwrite a page already read in this run.
        if previous is None or _result_quality(row) > _result_quality(previous):
            unique[key] = row
    return list(unique.values())


def _matching_models(results: List[Dict[str, Any]], query: str) -> List[Dict[str, Any]]:
    models = model_identifiers(query)
    if not models:
        return results
    return [row for row in results if all(
        contains_model(f"{row.get('title') or ''} {unquote(row.get('url') or '')}", model)
        for model in models
    )]


async def _google_cse(q: str, region: Optional[str]) -> List[Dict[str, Any]]:
    url = "https://www.googleapis.com/customsearch/v1"
    params = {
        "key": settings.GOOGLE_CSE_API_KEY,
        "cx": settings.GOOGLE_CSE_ID,
        "q": q,
        "num": 8,
    }
    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.get(url, params=params)
        resp.raise_for_status()
        data = resp.json()

    items = data.get("items", [])
    out = []
    for it in items:
        title = it.get("title", "")
        snippet = it.get("snippet", "")
        link = it.get("link", "")
        price = _extract_price(f"{title} {snippet}")
        out.append({
            "title": title,
            "snippet": snippet,
            "price": price,
            "currency": "₸" if price else None,
            "shop": _shop_from_url(link),
            "city": region,
            "url": link,
            "image_url": None,
        })
    return out


async def _duckduckgo(query: str, region: Optional[str]) -> List[Dict[str, Any]]:

    q = query
    if region:
        q = f"{query} купить {region}"
    else:
        q = f"{query} купить Казахстан цена"
    url = "https://html.duckduckgo.com/html/"
    headers = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"}
    async with httpx.AsyncClient(timeout=15.0, headers=headers, follow_redirects=True) as client:
        resp = await client.post(url, data={"q": q})
        resp.raise_for_status()
        html_text = resp.text

    return _parse_duckduckgo_results(html_text, region)


class _DuckDuckGoParser(HTMLParser):
    """The result anchor is stable even when DDG changes its nested div layout."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.results: list[dict[str, str]] = []
        self.capture: tuple[str, str, list[str]] | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]):
        attributes = dict(attrs)
        classes = (attributes.get("class") or "").split()
        if tag == "a" and "result__a" in classes:
            link = _decode_ddg_url(attributes.get("href") or "")
            if is_public_url(link):
                self.results.append({"url": link, "title": "", "snippet": ""})
                self.capture = (tag, "title", [])
        elif "result__snippet" in classes and self.results:
            self.capture = (tag, "snippet", [])

    def handle_data(self, data: str):
        if self.capture:
            self.capture[2].append(data)

    def handle_endtag(self, tag: str):
        if self.capture and self.capture[0] == tag:
            self.results[-1][self.capture[1]] = " ".join("".join(self.capture[2]).split())
            self.capture = None


def _parse_duckduckgo_results(markup: str, region: Optional[str] = None) -> List[Dict[str, Any]]:
    parser = _DuckDuckGoParser()
    parser.feed(markup)
    if not parser.results and re.search(r'challenge-form|anomaly-modal', markup, re.I):
        logger.info("duckduckgo_search_challenged")
    results = []
    for row in parser.results[:10]:
        title, snippet, link = row["title"], row["snippet"], row["url"]
        price = _extract_price(f"{title} {snippet}")
        results.append({
            "title": title,
            "snippet": snippet[:300],
            "price": price,
            "currency": "₸" if price else None,
            "shop": _shop_from_url(link),
            "city": region,
            "url": link,
            "image_url": None,
        })
    return results


def _decode_ddg_url(href: str) -> str:
    """DuckDuckGo wraps target links; extract the real URL."""
    href = html.unescape(href)
    parsed = urlparse(urljoin("https://duckduckgo.com", href))
    if parsed.hostname in {"duckduckgo.com", "www.duckduckgo.com", "html.duckduckgo.com"}:
        target = parse_qs(parsed.query).get("uddg", [None])[0]
        if target and is_public_url(target):
            return target
        return ""
    return href


async def enrich_product_pages(results: List[Dict[str, Any]], limit: int = 8) -> List[Dict[str, Any]]:
    """Read bounded public pages; only the item's own page can supply its photo."""
    semaphore = asyncio.Semaphore(4)

    async with httpx.AsyncClient(timeout=8.0, headers={"User-Agent": "Mozilla/5.0 (compatible; BinomProductResearch/1.0)"}) as client:
        async def enrich(result: Dict[str, Any]) -> None:
            async with semaphore:
                url = result.get("url") or ""
                direct_product_candidate = looks_like_product_url(url)
                page = await fetch_product_page(url, client)
                result.update(page)
                if page.get("is_product_page") and page.get("page_verified"):
                    result["title"] = page.get("title") or result.get("title")
                    result["shop"] = page.get("seller_name") or result.get("shop")
                    result["image_url"] = page.get("image_url")
                    result["price"] = page.get("price")
                    result["currency"] = page.get("currency")
                else:
                    # A vendor may block automated reads even though the search result
                    # points to a concrete product URL. Keep it visible as an explicitly
                    # unverified candidate, without inventing price, photo, or specs.
                    result["is_product_page"] = direct_product_candidate and not page.get("page_verified")
                    result["page_verified"] = False
                    result["image_url"] = None
                    result["price"] = None
                    result["currency"] = None

        await asyncio.gather(*(enrich(result) for result in results[:limit]))
    return results


def _marketplace_links(query: str, region: Optional[str]) -> List[Dict[str, Any]]:
    results = []
    for mp in MARKETPLACES:
        url = mp["url"].format(q=quote(query))
        results.append({
            "title": f"Найти «{query}» на {mp['name']}",
            "snippet": f"Перейти к поиску на маркетплейсе {mp['name']}" + (f" ({region})" if region else ""),
            "price": None,
            "currency": None,
            "shop": mp["name"],
            "city": region,
            "url": url,
            "image_url": None,
            "is_product_page": False,
            "page_verified": False,
        })
    return results


def _extract_price(text: str) -> Optional[float]:
    """Extract a tenge price from a text snippet: 25 000 ₸, 25 000 тг, 25000тенге."""
    if not text:
        return None
    m = re.search(r"(\d[\d\s\u00a0\u202f]{1,18}?)\s*(?:₸|тенге|тг|тнг|KZT|Kzt)", text, re.IGNORECASE)
    if m:
        try:
            return float(m.group(1).replace("\u00a0", "").replace("\u202f", "").replace(" ", ""))
        except ValueError:
            return None
    # Loose: "от 18 000", "цена 18 000", "~ 12 500" — common on kz vendor sites
    m = re.search(r"(?:от|цена|стоимость|~|≈)\s*(\d[\d\s\u00a0\u202f]{1,12})", text, re.IGNORECASE)
    if m:
        try:
            v = float(m.group(1).replace("\u00a0", "").replace("\u202f", "").replace(" ", ""))
            if 100.0 <= v <= 50_000_000.0:
                return v
        except ValueError:
            pass
    return None


def _shop_from_url(url: str) -> Optional[str]:
    if not url:
        return None
    m = re.search(r"https?://(?:www\.)?([^/]+)", url)
    return m.group(1).replace("www.", "") if m else None


def _looks_like_price(match: Dict[str, Any]) -> bool:
    return bool(match.get("price"))


def _looks_like_product_page(match: Dict[str, Any]) -> bool:
    url = (match.get("url") or "").lower()
    return any(mp.split(".")[0] in url for mp in ["kaspi.kz", "satu.kz", "alser.kz", "sulpak.kz", "technodom.kz", "wildberries.kz", "flip.kz"])


def _relevant_result(match: Dict[str, Any], query: str) -> bool:
    """Price or a marketplace URL cannot substitute for the requested product type."""
    title = (match.get("title") or "").casefold()
    words = [word for word in re.findall(r"[а-яёa-z]+", query.casefold()) if len(word) >= 4 and word not in _TYPE_STOP_WORDS]
    if not words:
        return False
    primary = _word_stem(words[0])
    title_words = re.findall(r"[а-яёa-z]+", title)
    latin_primary = _transliterate(primary)
    if not any(
        _word_stem(word) == primary
        or re.fullmatch(re.escape(latin_primary) + r"(?:a|y|i|u|ov|am|ah|ami)?", _transliterate(word))
        for word in title_words
    ):
        return False
    # A cover/hanger for a jacket mentions its type, but is not that garment.
    purpose_pattern = r"\b(?:dlya|for)\s+(?:[a-z]+\s+){0,2}" + re.escape(latin_primary)
    purpose = re.search(purpose_pattern, _transliterate(title))
    requested_purpose = re.search(purpose_pattern, _transliterate(query))
    if purpose and not requested_purpose:
        return False
    if "женск" in query.casefold() and re.search(r"\b(?:мужск|детск|мальчик|девочк)", title):
        return False
    host = (urlparse(match.get("url") or "").hostname or "").casefold()
    locale_path = bool(re.match(r"^/kz(?:/|_|$)", urlparse(match.get("url") or "").path, re.I))
    return host.endswith(".kz") or host in {"kaspi.kz", "satu.kz", "wildberries.ru"} or locale_path
