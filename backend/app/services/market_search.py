import re
import asyncio
import html
from html.parser import HTMLParser
import structlog
import httpx
from typing import List, Dict, Any, Optional
from urllib.parse import parse_qs, quote, urljoin, urlparse, unquote

from app.core.config import settings
from app.services.product_identity import contains_model, model_identifiers
from app.services.product_pages import fetch_product_page, is_public_url, looks_like_product_url

logger = structlog.get_logger(__name__)

_TYPE_STOP_WORDS = {
    "для", "товар", "изделие", "средство", "моющее", "жидкое", "жидкий", "купить", "цена",
    "женский", "женская", "женское", "мужской", "мужская", "детский", "детская", "шт", "штук",
}


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


async def search_products(query: str, region: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    Search the web for a product by name + specs, optionally scoped to a region.
    Priority: Google CSE (if configured) -> DuckDuckGo -> marketplace links fallback.
    Product pages are read for characteristics and a real product photo.
    """
    results: List[Dict[str, Any]] = []

    primary_query = _primary_query(query)
    q = primary_query
    if region:
        q = f"{primary_query} купить {region}"

    try:
        if settings.GOOGLE_CSE_API_KEY and settings.GOOGLE_CSE_ID:
            google_results = await _google_cse(q, region)
            if google_results:
                results = _relevant_candidates(await enrich_product_pages(_relevant_candidates(google_results, query)[:8]), query)
                if sum(bool(row.get("is_product_page")) for row in results) >= 6:
                    return results
    except Exception as e:
        logger.warning("google_cse_search_failed", error=str(e)[:200])

    try:
        ddg = await _duckduckgo(primary_query, region)
        filtered = _relevant_candidates(ddg, query)
        if filtered:
            enriched = _relevant_candidates(await enrich_product_pages(filtered[:8]), query)
            results = _unique_results(results + enriched)
            if sum(bool(row.get("is_product_page")) for row in results) >= 6:
                return results
    except Exception as e:
        logger.warning("duckduckgo_search_failed", error=str(e)[:200])

    # Long tender prose can make generic web search return categories. A short
    # marketplace product-page query gives concrete items to inspect.
    try:
        marketplace_query = re.sub(r"моющее средство для посуды", "средство для мытья посуды", primary_query, flags=re.I)
        short_query = marketplace_query.split(";")[0][:85]
        targeted_batches = await asyncio.gather(
            _satu_search(short_query, region),
            _duckduckgo(f"{short_query} site:kaspi.kz/shop/p/", None),
            _duckduckgo(f"{short_query} site:satu.kz/p", None),
            return_exceptions=True,
        )
        concrete_urls = _unique_results([
            row
            for batch in targeted_batches
            if isinstance(batch, list)
            for row in batch
            if looks_like_product_url(row.get("url") or "")
        ])
        candidates = _relevant_candidates(await enrich_product_pages(_relevant_candidates(concrete_urls, query)[:8]), query)
        results = _unique_results(candidates + results)
    except Exception as e:
        logger.warning("targeted_product_search_failed", error_type=type(e).__name__)

    # Search pages remain discoverable links, not concrete product cards.
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


def _unique_results(results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    unique: dict[str, Dict[str, Any]] = {}
    for row in results:
        url = row.get("url") or ""
        if not url:
            continue
        previous = unique.get(url)
        # A blocked repeat lookup must not overwrite a page already read in this run.
        if previous is None or (row.get("page_verified") and not previous.get("page_verified")):
            unique[url] = row
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
    return host.endswith(".kz") or host in {"kaspi.kz", "satu.kz", "wildberries.ru"}
