from slowapi import Limiter
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from fastapi import Request
from fastapi.responses import JSONResponse

# Initialize SlowAPI limiter by client IP address
limiter = Limiter(key_func=get_remote_address)


def rate_limit_exceeded_handler(request: Request, exc: RateLimitExceeded):
    """
    Custom 429 response so aspirants get a friendly message instead of a raw JSON error.
    """
    return JSONResponse(
        status_code=429,
        content={
            "detail": "Thoda rukiye! 🛑 Daily focus banaye rakhne ke liye chota break zaroori hai. 1 minute baad try karein.",
            "error": "rate_limit_exceeded",
        },
    )
