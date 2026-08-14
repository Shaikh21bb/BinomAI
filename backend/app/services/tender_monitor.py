import re
import httpx
import structlog
from datetime import datetime, timedelta
from decimal import Decimal, InvalidOperation
from typing import Dict, Optional
from urllib.parse import urlparse
from zoneinfo import ZoneInfo

logger = structlog.get_logger(__name__)

ALLOWED_TENDER_HOSTS = {
    "goszakup.gov.kz",
    "www.goszakup.gov.kz",
    "zakupki.sk.kz",
    "www.zakupki.sk.kz",
}

FETCH_TIMEOUT = 35.0
USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0 Safari/537.36"
)

ALMATY_TZ = ZoneInfo("Asia/Almaty")

# Labels found on goszakup.gov.kz lot pages (label -> field)
LABEL_MAP = {
    "Лот №": "lot_number",
    "Номер лота": "lot_number",
    "Статус лота": "status",
    "Дата начала приема заявок": "start_date",
    "Дата окончания приема заявок": "deadline_at",
    "БИН заказчика": "customer_bin",
    "Наименование заказчика": "customer_name",
    "Код ТРУ": "tru_code",
    "Наименование ТРУ": "name",
    "Краткая характеристика": "description",
    "Дополнительная характеристика": "description",
    "Запланированная сумма": "amount",
}


class TenderParseError(Exception):
    """Raised when a lot page cannot be fetched or parsed."""


def _clean(value: str) -> str:
    value = re.sub(r"<[^>]+>", "", value)
    value = re.sub(r"\s+", " ", value).strip()
    return value


def _parse_amount(value: str) -> Optional[Decimal]:
    try:
        return Decimal(re.sub(r"[^\d.]", "", value.replace(",", ".")))
    except (InvalidOperation, ValueError):
        return None


def _parse_dt(value: str) -> Optional[datetime]:
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%d.%m.%Y %H:%M:%S", "%d.%m.%Y"):
        try:
            return datetime.strptime(value.strip(), fmt).replace(tzinfo=ALMATY_TZ)
        except ValueError:
            continue
    return None


def parse_lot_page(html: str) -> Dict[str, object]:
    """Extract lot fields from a public lot page (label/value table rows)."""
    fields: Dict[str, str] = {}
    # Capture pairs regardless of exact row markup (gov portal uses <tr><td>label</td><td>value</td></tr>)
    for row in re.findall(r"<tr[^>]*>(.*?)</tr>", html, re.S):
        cells = re.findall(r"<t[hd][^>]*>(.*?)</t[hd]>", row, re.S)
        if len(cells) < 2:
            continue
        label = _clean(cells[0])
        value = _clean(cells[1])
        if label and value:
            fields.setdefault(label, value)

    if not fields:
        raise TenderParseError("Не удалось найти данные лота на странице (таблица не распознана)")

    result: Dict[str, object] = {}
    for label, field in LABEL_MAP.items():
        if field not in result and label in fields:
            result[field] = fields[label]

    lot_number = str(result.get("lot_number", "")).strip()
    name = str(result.get("name", "")).strip()
    if not lot_number and not name:
        raise TenderParseError("На странице не найден номер или наименование лота")

    if "amount" in result:
        parsed = _parse_amount(str(result["amount"]))
        result["amount"] = parsed
    for key in ("start_date", "deadline_at"):
        if key in result:
            parsed = _parse_dt(str(result[key]))
            result[key] = parsed
    return result


def fetch_lot_page(url: str) -> Dict[str, object]:
    """Fetch and parse a public lot page. Validates the host (SSRF guard)."""
    host = urlparse(url).hostname or ""
    if host not in ALLOWED_TENDER_HOSTS:
        raise TenderParseError(
            f"Разрешены только страницы: {', '.join(sorted(ALLOWED_TENDER_HOSTS))}"
        )
    if not url.startswith("https://"):
        raise TenderParseError("URL должен начинаться с https://")

    try:
        resp = httpx.get(
            url,
            timeout=FETCH_TIMEOUT,
            follow_redirects=True,
            headers={
                "User-Agent": USER_AGENT,
                "Accept-Language": "ru,kk;q=0.9",
            },
        )
        resp.raise_for_status()
    except httpx.HTTPError as e:
        raise TenderParseError(f"Не удалось загрузить страницу: {e}") from e

    data = parse_lot_page(resp.text)
    data["source_host"] = host
    return data


def deadline_reminder_label(deadline_at: Optional[datetime], now: Optional[datetime] = None) -> Optional[str]:
    """Return a human label when the deadline is approaching."""
    if not deadline_at:
        return None
    now = now or datetime.now(ALMATY_TZ)
    delta = deadline_at - now
    if delta.total_seconds() < 0:
        return "Дедлайн прошёл"
    if delta <= timedelta(days=1):
        return "Менее 1 дня"
    if delta <= timedelta(days=3):
        return f"{delta.days} дн."
    return None
