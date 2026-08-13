import re
import json
import asyncio
import structlog
import httpx
from typing import List, Dict, Any, Optional

from app.core.config import settings

logger = structlog.get_logger(__name__)

# Kazakhstan marketplaces used for fallback links
MARKETPLACES = [
    {"name": "Kaspi.kz", "url": "https://kaspi.kz/shop/search/?text={q}"},
    {"name": "Satu.kz", "url": "https://satu.kz/search?search_term={q}"},
    {"name": "Alser.kz", "url": "https://alser.kz/search?q={q}"},
    {"name": "Sulpak.kz", "url": "https://www.sulpak.kz/f/{q}"},
    {"name": "Technodom.kz", "url": "https://www.technodom.kz/katatalog/search/?q={q}"},
    {"name": "Wildberries.kz", "url": "https://www.wildberries.kz/catalog/0/search.aspx?search={q}"},
]


async def search_products(query: str, region: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    Search the web for a product by name + specs, optionally scoped to a region.
    Priority: Google CSE (if configured) -> DuckDuckGo -> marketplace links fallback.
    Returns a list of matches:
      {title, price, currency, shop, city, url, image_url, snippet}
    """
    results: List[Dict[str, Any]] = []

    q = query
    if region:
        q = f"{query} купить {region}"

    try:
        if settings.GOOGLE_CSE_API_KEY and settings.GOOGLE_CSE_ID:
            results = await _google_cse(q, region)
            if results:
                return await _enrich_images(results[:10])
    except Exception as e:
        logger.warning("google_cse_search_failed", error=str(e)[:200])

    try:
        ddg = await _duckduckgo(query, region)
        results = [r for r in ddg if _looks_like_price(r) or _looks_like_product_page(r) or _relevant_result(r, query)]
        if len(results) >= 2:
            return await _enrich_images(results[:10])
    except Exception as e:
        logger.warning("duckduckgo_search_failed", error=str(e)[:200])

    # Last resort: guaranteed-available marketplace search links
    return _marketplace_links(query, region)


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
        page_map = it.get("pagemap", {})
        img = None
        if page_map:
            for kind in ("cse_image", "imageobject", "thumbnail"):
                arr = page_map.get(kind) or []
                if arr and arr[0].get("src"):
                    img = arr[0]["src"]
                    break
        price = _extract_price(f"{title} {snippet}")
        out.append({
            "title": title,
            "snippet": snippet,
            "price": price,
            "currency": "₸" if price else None,
            "shop": _shop_from_url(link),
            "city": region,
            "url": link,
            "image_url": img,
        })
    return out


async def _duckduckgo(query: str, region: Optional[str]) -> List[Dict[str, Any]]:
    import html as html_mod

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

    results = []
    # DuckDuckGo HTML results: <a class="result__a" href="...">title</a> ... <a class="result__snippet">...
    for block in re.findall(r'<div class="result[^"]*".*?</div>\s*</div>\s*</div>', html_text, re.S)[:10]:
        a = re.search(r'class="result__a"[^>]*href="([^"]*)"[^>]*>(.*?)</a>', block, re.S)
        if not a:
            continue
        link = _decode_ddg_url(a.group(1))
        title = re.sub(r"<[^>]+>", "", a.group(2)).strip()
        snip_m = re.search(r'class="result__snippet"[^>]*>(.*?)</a>', block, re.S)
        snippet = re.sub(r"<[^>]+>", "", snip_m.group(1)).strip() if snip_m else ""
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
    if href.startswith("http") or href.startswith("https"):
        return href
    m = re.search(r"uddg=([^&]+)", href)
    if m:
        from urllib.parse import unquote
        return unquote(m.group(1))
    return href


async def _enrich_images(results: List[Dict[str, Any]], limit: int = 6) -> List[Dict[str, Any]]:
    """Fetch og:image for results that lack a product image (top N, in parallel)."""
    from urllib.parse import urljoin, urlparse

    to_fetch = [r for r in results if not r.get("image_url") and r.get("url")][:limit]

    async def fetch_one(r: Dict[str, Any]) -> Optional[str]:
        url = r["url"]
        try:
            async with httpx.AsyncClient(timeout=6.0, follow_redirects=True) as client:
                resp = await client.get(url)
                if resp.status_code != 200:
                    return None
                text = resp.text[:400_000]
        except Exception:
            return None
        for pat in (
            r'<meta[^>]+property=["\']og:image["\'][^>]+content=["\']([^"\']+)["\']',
            r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+property=["\']og:image["\']',
            r'<meta[^>]+property=["\']og:image:url["\'][^>]+content=["\']([^"\']+)["\']',
        ):
            m = re.search(pat, text, re.IGNORECASE)
            if m and not m.group(1).startswith("data:"):
                return urljoin(url, m.group(1).strip())
        m = re.search(r'<img[^>]+src=["\']([^"\']+)["\']', text, re.IGNORECASE)
        if m and not m.group(1).startswith("data:"):
            return urljoin(url, m.group(1).strip())
        return None

    async def favicon_of(r: Dict[str, Any]) -> Optional[str]:
        try:
            host = urlparse(r["url"]).netloc
            return f"https://www.google.com/s2/favicons?domain={host}&sz=128"
        except Exception:
            return None

    images = await asyncio.gather(*(fetch_one(r) for r in to_fetch))
    favicons = await asyncio.gather(*(favicon_of(r) for r in to_fetch))
    for r, img, fav in zip(to_fetch, images, favicons):
        r["image_url"] = img or fav
    return results


def _marketplace_links(query: str, region: Optional[str]) -> List[Dict[str, Any]]:
    from urllib.parse import quote
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
    """Keep a result when the title carries the query and the site looks like a vendor."""
    title = (match.get("title") or "").lower()
    words = [w.lower() for w in re.findall(r"[а-яёa-z0-9]+", query) if len(w) > 2]
    if not words or not any(w in title for w in words):
        return False
    url = (match.get("url") or "").lower()
    return ".kz" in url or any(k in url for k in ["kaspi", "satu", "alser", "sulpak", "technodom", "wildberries"])
