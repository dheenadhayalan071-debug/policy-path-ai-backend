from fastapi import APIRouter
from app.config import settings

router = APIRouter(tags=["Health"])


@router.get("/")
@router.head("/")
async def root():
    return {
        "status": "online",
        "app": settings.APP_NAME,
        "environment": settings.ENVIRONMENT,
        "docs": "/docs",
    }


@router.get("/health")
@router.head("/health")
async def health_check():
    return {
        "status": "healthy",
        "groq_configured": bool(settings.GROQ_API_KEY),
        "supabase_configured": bool(settings.SUPABASE_URL),
    }
