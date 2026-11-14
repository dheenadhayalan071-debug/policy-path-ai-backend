from typing import Optional
from fastapi import Header, HTTPException, status
from pydantic import BaseModel
from supabase import create_client, Client
from app.config import settings

# Global Supabase client instance for auth checks
supabase_client: Optional[Client] = None

if settings.SUPABASE_URL and settings.SUPABASE_ANON_KEY:
    try:
        supabase_client = create_client(settings.SUPABASE_URL, settings.SUPABASE_ANON_KEY)
    except Exception as e:
        print(f"⚠️ Failed to initialize Supabase client: {e}")


class AuthenticatedUser(BaseModel):
    user_id: Optional[str] = None
    email: Optional[str] = None
    is_guest: bool = True
    token: Optional[str] = None


async def get_current_user(
    authorization: Optional[str] = Header(None, alias="Authorization")
) -> AuthenticatedUser:
    """
    Extracts Bearer token from header and validates via Supabase.
    If no header is present or invalid, returns a Guest User object.
    """
    if not authorization or not authorization.startswith("Bearer "):
        return AuthenticatedUser(is_guest=True)

    token = authorization.split(" ")[1].strip()

    if not token or token == "undefined" or token == "null":
        return AuthenticatedUser(is_guest=True)

    # If Supabase isn't configured, default to guest safely
    if not supabase_client:
        return AuthenticatedUser(is_guest=True)

    try:
        # Verify token with Supabase Auth service
        user_res = supabase_client.auth.get_user(token)
        if user_res and user_res.user:
            return AuthenticatedUser(
                user_id=user_res.user.id,
                email=user_res.user.email,
                is_guest=False,
                token=token,
            )
    except Exception as e:
        # Token expired or tampered — fallback to guest or soft reject
        print(f"Auth verification failed: {e}")

    return AuthenticatedUser(is_guest=True)


async def require_authenticated_user(
    authorization: Optional[str] = Header(None, alias="Authorization")
) -> AuthenticatedUser:
    """
    Strict middleware for endpoints that REQUIRES a logged-in user.
    Rejects guests with 401 Unauthorized.
    """
    user = await get_current_user(authorization)
    if user.is_guest:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Aapko login karna zaroori hai is feature ke liye.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user
