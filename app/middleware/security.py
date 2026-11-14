import re
from fastapi import HTTPException, status

# Suspicious patterns common in LLM jailbreaks
SUSPICIOUS_PATTERNS = [
    r"ignore (all )?previous instructions",
    r"system prompt",
    r"you are now an? (unrestricted|dan|jailbroken)",
    r"reveal (your|the) (system|hidden) (prompt|instructions)",
    r"forget your (rules|instructions)",
]

COMPILED_PATTERNS = [re.compile(p, re.IGNORECASE) for p in SUSPICIOUS_PATTERNS]


def sanitize_user_input(text: str, max_chars: int = 2000) -> str:
    """
    Sanitizes user input:
    1. Trims leading/trailing whitespace.
    2. Checks max length.
    3. Blocks malicious prompt injection attempts.
    """
    if not text:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Poochne ke liye text khali nahi ho sakta."
        )

    text = text.strip()

    if len(text) > max_chars:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Sawaal bahut lamba hai. Kripya {max_chars} characters se kam rakhein."
        )

    # Check for injection attacks
    for pattern in COMPILED_PATTERNS:
        if pattern.search(text):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Aapka sawaal PolicyPath AI safety guidelines ke khilaaf hai."
            )

    return text
