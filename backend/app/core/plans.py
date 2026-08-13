from dataclasses import dataclass, field
from typing import Optional


@dataclass(frozen=True)
class Plan:
    """A subscription plan and its limits. None means unlimited."""
    key: str
    name: str
    price_monthly_kzt: int
    max_projects: Optional[int]
    max_users: Optional[int]
    max_documents: Optional[int]
    features: dict = field(default_factory=dict)


PLANS: dict[str, Plan] = {
    "trial": Plan(
        key="trial",
        name="Пробный",
        price_monthly_kzt=0,
        max_projects=2,
        max_users=3,
        max_documents=20,
        features={"ai_analysis": True, "market_search": True, "exports": True, "chat": True},
    ),
    "starter": Plan(
        key="starter",
        name="Старт",
        price_monthly_kzt=49000,
        max_projects=10,
        max_users=10,
        max_documents=100,
        features={"ai_analysis": True, "market_search": True, "exports": True, "chat": True},
    ),
    "pro": Plan(
        key="pro",
        name="Про",
        price_monthly_kzt=149000,
        max_projects=50,
        max_users=50,
        max_documents=None,
        features={"ai_analysis": True, "market_search": True, "exports": True, "chat": True},
    ),
    "enterprise": Plan(
        key="enterprise",
        name="Enterprise",
        price_monthly_kzt=0,
        max_projects=None,
        max_users=None,
        max_documents=None,
        features={"ai_analysis": True, "market_search": True, "exports": True, "chat": True},
    ),
}


def get_plan(key: Optional[str]) -> Plan:
    """Resolve a plan key to a Plan, falling back to 'trial'."""
    return PLANS.get(key or "trial", PLANS["trial"])


def plan_limits(plan_key: Optional[str]) -> dict:
    """Public serializable representation of a plan's limits."""
    plan = get_plan(plan_key)
    return {
        "max_projects": plan.max_projects,
        "max_users": plan.max_users,
        "max_documents": plan.max_documents,
        "features": plan.features,
    }
