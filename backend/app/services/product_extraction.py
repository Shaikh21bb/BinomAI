import re
from typing import Any, Dict, List, Optional

# Units commonly used in construction/material specs
_UNITS = (
    r"(?:м2|м³|м3|м\s?кв\.?|м\s?куб\.?|п\.?\s?м\.?|пог\.?\s?м\.?|шт\.?|компл\.?|кг|т|тн|л|л\.?|га|млн\.?\s?тенге|тенге|₸)"
)

# Rows of a spec table like: | 1 | Металлочерепица | 0,5 мм | м2 | 789,1 |
_ROW_RE = re.compile(
    r"^\|\s*(\d+)\s*\|\s*(.+?)\s*\|\s*(.*?)\s*\|\s*(" + _UNITS + r")\s*\|\s*([\d\s,\.]+)\s*\|?$",
    re.IGNORECASE,
)

# Lines like: "Металлочерепица — 0,5 мм, м2, 789,1" or "Доска обрезная 25х150 мм, 8,95 м3"
_LINE_RE = re.compile(
    r"^(.{4,120}?)[\s—–-]*(?:(\d+(?:[.,]\d+)?\s*х\s*\d+(?:[.,]\d+)?(?:\s*х\s*\d+(?:[.,]\d+)?)?\s*мм)|(\d+(?:[.,]\d+)?\s*мм)|[A-ZА-ЯЁа-яё0-9]{2,}\s*\d+[.,]\d+[^\n]{0,40})\s*(?:,\s*|\s)(" + _UNITS + r")\s*,?\s*(\d+(?:[.,]\d+)?)?\s*$",
    re.IGNORECASE,
)

# Lines containing a unit and a quantity in the middle: "... м2 ... 789,1"
_ANY_UNIT_RE = re.compile(
    r"^(.{4,140}?)(?:^|[\s,;]|—)(м2|м³|м3|п\.?\s?м\.?|шт\.?|кг|т(?:н)?)([\s,;]|$)(?=.*?(\d{2,}[\d\s,\.]*))",
    re.IGNORECASE,
)

# Quantity pattern: standalone number at line end (for tab-separated text rows)
_QTY_END_RE = re.compile(r"(\d{1,6}(?:[\s,\.]\d{1,3}){0,3})\s*$")

_STOPWORDS = {"наименование", "кол-во", "количество", "ед", "изм", "единица", "изм.", "№", "номер", "показатель"}

_RU_TENDER_FIELDS = {
    "item_number": ("Номер пункта плана",),
    "name": ("Наименование пункта плана",),
    "description": ("Описание пункта плана",),
    "short_description": ("Дополнительное описание пункта плана",),
    "quantity": ("Количество",),
    "unit": ("Единица измерения",),
    "delivery_location": ("Места поставки", "Место поставки"),
    "delivery_terms": ("Срок поставки",),
    "requirements": (
        "Описание требуемых функциональных, технических, качественных, эксплуатационных и иных характеристик закупаемого товара",
    ),
}

_KK_TENDER_FIELDS = {
    "item_number": ("Лоттың нөмірі",),
    "name": ("Лоттың атауы",),
    "description": ("Лоттың сипаттауы",),
    "short_description": ("Лоттың қысқаша сипаттауы",),
    "quantity": ("Саны, көлемі",),
    "unit": ("Өлшем бірлігі",),
    "delivery_location": ("Жеткізу орны",),
    "delivery_terms": ("Жеткізу мерзімі",),
    "requirements": (
        "Сатып алынатын тауарлардың қажетті функциональдық, техникалық, сапалық, өнімділігі мен басқа да сипаттамаларының сипатталуы",
    ),
}


def extract_products_from_text(text: str) -> List[Dict[str, Any]]:
    """
    Deterministic extraction of products/materials from tender spec text.
    Returns a list of {product_name, specs, unit, quantity, source_section}.
    """
    labeled_products = _extract_labeled_tender_products(text)
    if labeled_products:
        return labeled_products

    products: List[Dict[str, Any]] = []
    seen = set()

    def add(item: Dict[str, Any]):
        key = (item.get("product_name") or "").strip().lower()
        if not key or key in seen:
            return
        if key in _STOPWORDS or len(key) < 4:
            return
        seen.add(key)
        products.append(item)

    # 1. Table rows: | № | Name | Spec | Unit | Qty |
    for line in text.splitlines():
        m = _ROW_RE.match(line.strip())
        if m:
            add({
                "product_name": m.group(2).strip(),
                "specs": m.group(3).strip() or None,
                "unit": m.group(4).strip(),
                "quantity": _parse_qty(m.group(5)),
                "source_section": _section_of(line, text),
            })
            continue

        # 2. Table rows without №: | Name | Qty | Unit |  or  | Name | Spec | Unit | Qty |
        parts = [p.strip() for p in line.strip().strip("|").split("|")]
        if len(parts) >= 3:
            name = parts[0]
            if _looks_like_product(name):
                # Try (name, spec, unit, qty)
                if len(parts) >= 4 and re.search(_UNITS, parts[-2], re.IGNORECASE) and re.search(r"\d", parts[-1]):
                    add({
                        "product_name": name,
                        "specs": parts[1] or None,
                        "unit": parts[-2],
                        "quantity": _parse_qty(parts[-1]),
                        "source_section": _section_of(line, text),
                    })
                    continue
                # Try (name, qty, unit)
                if re.search(r"\d", parts[1]) and re.search(_UNITS, parts[2], re.IGNORECASE):
                    add({
                        "product_name": name,
                        "specs": None,
                        "unit": parts[2],
                        "quantity": _parse_qty(parts[1]),
                        "source_section": _section_of(line, text),
                    })
                    continue

        # 3. Line with unit + qty at end
        m3 = re.search(r"^(.*?)(?:м2|м³|м3|п\.?\s?м\.?|шт\.?|кг|тн?|л\.?)\s+([\d\s,\.]{2,})$", line.strip(), re.IGNORECASE)
        if m3 and _looks_like_product(m3.group(1)):
            add({
                "product_name": m3.group(1).strip(),
                "specs": None,
                "unit": _unit_of(line),
                "quantity": _parse_qty(m3.group(2)),
                "source_section": _section_of(line, text),
            })
            continue

        # 4. Line with qty then unit at end: "... 789 м2" / "... 150 м3"
        m4 = re.search(r"^(.*?)\s+([\d\s,\.]{2,})\s*(?:м2|м³|м3|п\.?\s?м\.?|шт\.?|кг|тн?|л\.?)\s*$", line.strip(), re.IGNORECASE)
        if m4 and _looks_like_product(m4.group(1)):
            add({
                "product_name": m4.group(1).strip(),
                "specs": None,
                "unit": _unit_of(line),
                "quantity": _parse_qty(m4.group(2)),
                "source_section": _section_of(line, text),
            })

    return products


def _extract_labeled_tender_products(text: str) -> List[Dict[str, Any]]:
    """Extract Kazakhstan tender line items represented as repeated label/value blocks.

    Many procurement PDFs contain the same specification in Kazakh and Russian.
    Prefer the Russian block when it is present so one bilingual item does not become
    two sourcing lines; otherwise use the Kazakh block.
    """
    normalized = _join_wrapped_tender_labels(text)
    russian = _extract_language_blocks(normalized, _RU_TENDER_FIELDS)
    if russian:
        return russian
    return _extract_language_blocks(normalized, _KK_TENDER_FIELDS)


def _join_wrapped_tender_labels(text: str) -> str:
    replacements = {
        r"(?im)^\s*Дополнительное описание\s*\n\s*пункта плана\s*:": "Дополнительное описание пункта плана:",
        r"(?ims)^\s*Описание требуемых\s+функциональных,\s*технических,\s*качественных,\s*эксплуатационных и иных\s+характеристик закупаемого\s+товара\s*:": "Описание требуемых функциональных, технических, качественных, эксплуатационных и иных характеристик закупаемого товара:",
        r"(?ims)^\s*Сатып алынатын тауарлардың\s+қажетті функциональдық,\s*техникалық,\s*сапалық,\s*өнімділігі\s+мен басқа да сипаттамаларының\s+сипатталуы\s*:": "Сатып алынатын тауарлардың қажетті функциональдық, техникалық, сапалық, өнімділігі мен басқа да сипаттамаларының сипатталуы:",
    }
    for pattern, replacement in replacements.items():
        text = re.sub(pattern, replacement, text)
    return text


def _extract_language_blocks(text: str, fields: Dict[str, tuple[str, ...]]) -> List[Dict[str, Any]]:
    item_label = re.escape(fields["item_number"][0])
    chunks = re.split(rf"(?im)(?=^\s*{item_label}\s*:)", text)
    products: List[Dict[str, Any]] = []
    seen_numbers = set()
    for chunk in chunks:
        values = _parse_labeled_values(chunk, fields)
        number_match = re.search(r"\d{5,}", values.get("item_number", ""))
        if not number_match:
            continue
        item_number = number_match.group(0)
        if item_number in seen_numbers:
            continue
        seen_numbers.add(item_number)

        product_name = values.get("short_description") or " ".join(
            part for part in (values.get("name"), values.get("description")) if part
        )
        if not values.get("quantity") or not _looks_like_product(product_name):
            continue
        spec_parts = [values.get("requirements")]
        if values.get("delivery_location"):
            spec_parts.append(f"Место поставки: {values['delivery_location']}")
        if values.get("delivery_terms"):
            spec_parts.append(f"Срок поставки: {values['delivery_terms']}")
        products.append({
            "product_name": product_name[:500],
            "specs": "; ".join(part for part in spec_parts if part) or values.get("description"),
            "unit": values.get("unit"),
            "quantity": _parse_qty(values["quantity"]) if values.get("quantity") else None,
            "source_section": f"Пункт плана № {item_number}",
        })
    return products


def _parse_labeled_values(text: str, fields: Dict[str, tuple[str, ...]]) -> Dict[str, str]:
    alias_lookup = {
        alias.casefold(): key
        for key, aliases in fields.items()
        for alias in aliases
    }
    aliases = sorted(alias_lookup, key=len, reverse=True)
    label_pattern = re.compile(
        rf"^\s*({'|'.join(re.escape(alias) for alias in aliases)})\s*:\s*(.*)$",
        re.IGNORECASE,
    )
    values: Dict[str, list[str]] = {}
    current: Optional[str] = None
    for raw_line in text.splitlines():
        line = raw_line.strip()
        match = label_pattern.match(line)
        if match:
            current = alias_lookup[match.group(1).casefold()]
            values.setdefault(current, [])
            if match.group(2).strip():
                values[current].append(match.group(2).strip())
        elif current and line:
            values[current].append(line)
    return {key: " ".join(parts).strip() for key, parts in values.items()}


def _parse_qty(raw: str):
    raw = raw.replace(" ", "").replace(",", ".")
    try:
        return float(raw)
    except ValueError:
        return None


def _unit_of(line: str) -> str:
    m = re.search(_UNITS, line, re.IGNORECASE)
    return m.group(0) if m else None


def _looks_like_product(name: str) -> bool:
    if not name or len(name) < 4:
        return False
    normalized_name = " ".join(name.lower().split())
    name_tokens = set(re.findall(r"[a-zа-яёәіңғүұқөһ]+", normalized_name))
    stopword_tokens = {word.strip(".").lower() for word in _STOPWORDS}
    if (
        (name_tokens and name_tokens.issubset(stopword_tokens))
        or normalized_name.startswith(("наименование ", "единица измерения"))
    ):
        return False
    if re.fullmatch(r"[\d\s,\.\-/:]+", name):
        return False
    return True


def _section_of(line: str, full_text: str) -> str:
    """Best-effort: name of the heading section containing the line."""
    idx = full_text.find(line)
    if idx < 0:
        return None
    before = full_text[:idx]
    matches = list(re.finditer(r"(?m)^(#{1,3}\s+|Спецификация[^\n]*|Ведомость[^\n]*|Состав работ[^\n]*|Требования к материалам[^\n]*|Технические требования[^\n]*)", before))
    if matches:
        return matches[-1].group(0).strip().lstrip("#").strip()
    return None
