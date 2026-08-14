from fastapi import APIRouter
from app.api.v1.endpoints import auth, projects, documents, analysis, health, users, chat, generation, products, admin, tender_monitor

api_router = APIRouter()

# Include infrastructure endpoints
api_router.include_router(health.router, tags=["infrastructure"])

# Core Sprint 1 endpoints
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(users.router, prefix="/users", tags=["users"])
api_router.include_router(projects.router, prefix="/projects", tags=["projects"])
api_router.include_router(documents.router, prefix="/projects", tags=["documents"])
api_router.include_router(analysis.router, prefix="/analysis", tags=["analysis"])
api_router.include_router(chat.router, tags=["chat"])
api_router.include_router(generation.router, prefix="/projects", tags=["generation"])
api_router.include_router(products.router, prefix="/projects", tags=["products"])
api_router.include_router(tender_monitor.router, prefix="/tenders", tags=["tenders"])
api_router.include_router(admin.router, tags=["admin"])
