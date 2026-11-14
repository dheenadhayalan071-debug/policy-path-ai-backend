from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field

from app.auth.supabase_auth import get_current_user, AuthenticatedUser
from app.middleware.security import sanitize_user_input
from app.middleware.rate_limit import limiter
from app.services.groq_service import call_chat_ai, call_quiz_ai
from app.config import settings

router = APIRouter(tags=["AI Mentor"])


class AskRequest(BaseModel):
    user_query: str = Field(..., max_length=2000, description="User question or quiz topic")
    history: Optional[List[Dict[str, str]]] = Field(default=[], description="Chat context")
    mode: str = Field(default="chat", description="'chat' or 'quiz'")
    language: str = Field(default="English", description="'English' or 'Hinglish'")


@router.post("/ask")
@limiter.limit(settings.DEFAULT_RATE_LIMIT)
async def ask_mentor(
    request: Request,
    payload: AskRequest,
    user: AuthenticatedUser = Depends(get_current_user),
):
    """
    Main AI endpoint supporting Chat and Quiz modes with auto rate-limiting and auth detection.
    """
    # 1. Sanitize user text input
    clean_query = sanitize_user_input(payload.user_query, max_chars=settings.MAX_QUERY_LENGTH)

    # 2. Process Quiz Mode
    if payload.mode.lower() == "quiz":
        questions = await call_quiz_ai(clean_query)
        return {
            "mode": "quiz",
            "is_guest": user.is_guest,
            "questions": questions,
        }

    # 3. Process Chat Mode
    ai_response = await call_chat_ai(
        query=clean_query,
        history=payload.history,
        language=payload.language,
    )

    return {
        "mode": "chat",
        "is_guest": user.is_guest,
        "response": ai_response,
    }
