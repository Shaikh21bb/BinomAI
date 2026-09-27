import uuid
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import HTTPException

from app.api.v1.endpoints.sourcing import create_offer_from_discovery
from app.db.models.product_search import ProductSearchItem
from app.db.models.project import Project
from app.db.models.sourcing import SupplierOffer
from app.db.models.user import User
from app.schemas.sourcing import DiscoveryOfferCreate


PROJECT_ID = uuid.UUID("33333333-3333-3333-3333-333333333333")
COMPANY_ID = uuid.UUID("11111111-1111-1111-1111-111111111111")
USER_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")
ITEM_ID = uuid.UUID("44444444-4444-4444-4444-444444444444")
SOURCE_URL = "https://vendor.example/products/cable-100"


def scalar_first(value):
    result = MagicMock()
    result.scalars.return_value.first.return_value = value
    return result


def make_project():
    return Project(id=PROJECT_ID, company_id=COMPANY_ID, created_by=USER_ID, name="Тендер")


def make_item(*, verified: bool = True, price=1250):
    return ProductSearchItem(
        id=ITEM_ID,
        project_id=PROJECT_ID,
        company_id=COMPANY_ID,
        product_name="Кабель ВВГнг 3×2,5",
        unit="м",
        quantity=100,
        status="ready",
        results=[{
            "url": SOURCE_URL,
            "title": "Кабель ВВГнг-LS 3×2,5",
            "shop": "Vendor KZ",
            "price": price,
            "currency": "₸",
            "stock_quantity": 120,
            "characteristics": {"Сечение": "3×2,5 мм²"},
            "is_product_page": True,
            "page_verified": verified,
            "match_status": "partial",
            "checks": [{
                "requirement": "Сечение 3×2,5 мм²",
                "status": "matched",
                "evidence": "3×2,5 мм²",
            }],
        }],
    )


def make_db(*results):
    db = AsyncMock()
    db.add = MagicMock()
    db.execute = AsyncMock(side_effect=[scalar_first(value) for value in results])
    db.flush = AsyncMock()
    return db


@pytest.mark.asyncio
async def test_create_offer_from_verified_discovery_card():
    item = make_item()
    db = make_db(make_project(), item, None)
    user = User(id=USER_ID, company_id=COMPANY_ID, role="admin")

    offer = await create_offer_from_discovery(
        PROJECT_ID,
        ITEM_ID,
        DiscoveryOfferCreate(source_url=SOURCE_URL),
        db,
        user,
    )

    assert isinstance(offer, SupplierOffer)
    assert offer.item_id == ITEM_ID
    assert offer.supplier_name == "Vendor KZ"
    assert offer.unit_price == Decimal("1250")
    assert offer.currency == "KZT"
    assert offer.available_quantity == Decimal("120")
    assert offer.compliance_status == "partial"
    assert offer.source_type == "discovery"
    assert offer.source_url == SOURCE_URL
    assert "Сечение 3×2,5 мм²: подтверждено" in offer.compliance_notes
    db.add.assert_called_once_with(offer)
    db.flush.assert_awaited_once()


@pytest.mark.asyncio
async def test_create_offer_from_discovery_rejects_duplicate_url():
    item = make_item()
    duplicate = SupplierOffer(source_url=SOURCE_URL)
    db = make_db(make_project(), item, duplicate)
    user = User(id=USER_ID, company_id=COMPANY_ID, role="admin")

    with pytest.raises(HTTPException) as exc:
        await create_offer_from_discovery(
            PROJECT_ID,
            ITEM_ID,
            DiscoveryOfferCreate(source_url=SOURCE_URL),
            db,
            user,
        )

    assert exc.value.status_code == 409
    db.add.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.parametrize("verified,price", [(False, 1250), (True, None)])
async def test_create_offer_from_discovery_requires_verified_card_with_price(verified, price):
    item = make_item(verified=verified, price=price)
    db = make_db(make_project(), item)
    user = User(id=USER_ID, company_id=COMPANY_ID, role="admin")

    with pytest.raises(HTTPException) as exc:
        await create_offer_from_discovery(
            PROJECT_ID,
            ITEM_ID,
            DiscoveryOfferCreate(source_url=SOURCE_URL),
            db,
            user,
        )

    assert exc.value.status_code == 422
    db.add.assert_not_called()
