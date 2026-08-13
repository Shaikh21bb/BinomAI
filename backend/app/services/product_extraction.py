import re
from typing import List, Dict, Any

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


def extract_products_from_text(text: str) -> List[Dict[str, Any]]:
    """
    Deterministic extraction of products/materials from tender spec text.
    Returns a list of {product_name, specs, unit, quantity, source_section}.
    """
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
    if any(w in name.lower() for w in _STOPWORDS):
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
