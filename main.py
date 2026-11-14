import json
import logging
import os
import re
from typing import Any, Optional

from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from groq import Groq
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

# ---------------------------------------------------------------------------
# Sentry Crash Reporting Setup
# ---------------------------------------------------------------------------
import sentry_sdk
from sentry_sdk.integrations.fastapi import FastApiIntegration

SENTRY_DSN = os.environ.get("SENTRY_DSN")

if SENTRY_DSN:
    sentry_sdk.init(
        dsn=SENTRY_DSN,
        integrations=[FastApiIntegration()],
        # Set traces_sample_rate to 1.0 to capture 100% of transactions for performance monitoring.
        traces_sample_rate=0.2,
        # Capture 100% of errors
        sample_rate=1.0,
        environment=os.environ.get("ENVIRONMENT", "production"),
    )
    logging.info("⚡ Sentry monitoring active.")
else:
    logging.warning("⚠️ SENTRY_DSN is not set. Error tracking disabled.")

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Rate limiter
# ---------------------------------------------------------------------------
limiter = Limiter(key_func=get_remote_address)

# ---------------------------------------------------------------------------
# App + CORS
# ---------------------------------------------------------------------------
app = FastAPI(title="PolicyPath AI API", version="2.0.0")
app.state.limiter = limiter

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://policy-path-theta.vercel.app",
        "https://policypath.in",
        "https://www.policypath.in",
        "http://localhost:5173",
        "http://localhost:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _rate_limit_handler(request: Request, exc: RateLimitExceeded):
    return JSONResponse(
        status_code=429,
        content={
            "detail": (
                "Thoda rukiye! 🛑 Daily focus banaye rakhne ke liye chota break "
                "zaroori hai. 1 minute baad try karein."
            ),
            "error": "rate_limit_exceeded",
        },
    )


app.add_exception_handler(RateLimitExceeded, _rate_limit_handler)

# ---------------------------------------------------------------------------
# Groq client
# ---------------------------------------------------------------------------
_groq_api_key = os.environ.get("GROQ_API_KEY")
client = Groq(api_key=_groq_api_key) if _groq_api_key else None
if not _groq_api_key:
    logger.warning(
        "GROQ_API_KEY is not set; /ask requests cannot reach Groq until it is configured."
    )

# ---------------------------------------------------------------------------
# Supabase auth (optional — guests still allowed)
# ---------------------------------------------------------------------------
_supabase_url = os.environ.get("SUPABASE_URL", "")
_supabase_anon_key = os.environ.get("SUPABASE_ANON_KEY", "")
_supabase = None
if _supabase_url and _supabase_anon_key:
    try:
        from supabase import create_client

        _supabase = create_client(_supabase_url, _supabase_anon_key)
        logger.info("Supabase auth client initialized")
    except Exception as exc:
        logger.warning("Supabase client init failed: %s", exc)


class AuthUser:
    def __init__(
        self,
        user_id: Optional[str] = None,
        email: Optional[str] = None,
        is_guest: bool = True,
    ):
        self.user_id = user_id
        self.email = email
        self.is_guest = is_guest


async def get_current_user(
    authorization: Optional[str] = Header(None, alias="Authorization"),
) -> AuthUser:
    """
    Read Bearer token from Authorization header.
    Valid Supabase JWT → logged-in user.
    Missing / invalid → guest (still allowed, tighter rate limit possible later).
    """
    if not authorization or not authorization.startswith("Bearer "):
        return AuthUser(is_guest=True)

    token = authorization.split(" ", 1)[1].strip()
    if not token or token in ("undefined", "null"):
        return AuthUser(is_guest=True)

    if _supabase is None:
        return AuthUser(is_guest=True)

    try:
        result = _supabase.auth.get_user(token)
        if result and result.user:
            return AuthUser(
                user_id=result.user.id,
                email=result.user.email,
                is_guest=False,
            )
    except Exception as exc:
        logger.info("Auth token verification failed: %s", exc)

    return AuthUser(is_guest=True)


# ---------------------------------------------------------------------------
# Input sanitization (prompt-injection + length guard)
# ---------------------------------------------------------------------------
_INJECTION_PATTERNS = [
    re.compile(p, re.IGNORECASE)
    for p in [
        r"ignore (all )?previous instructions",
        r"system prompt",
        r"you are now an? (unrestricted|dan|jailbroken)",
        r"reveal (your|the) (system|hidden) (prompt|instructions)",
        r"forget your (rules|instructions)",
    ]
]
MAX_QUERY_LENGTH = 2000


def sanitize_query(text: str) -> str:
    if not text or not text.strip():
        raise HTTPException(status_code=400, detail="user_query must not be blank.")

    text = text.strip()
    if len(text) > MAX_QUERY_LENGTH:
        raise HTTPException(
            status_code=400,
            detail=f"Sawaal bahut lamba hai. Kripya {MAX_QUERY_LENGTH} characters se kam rakhein.",
        )

    for pattern in _INJECTION_PATTERNS:
        if pattern.search(text):
            raise HTTPException(
                status_code=400,
                detail="Aapka sawaal PolicyPath AI safety guidelines ke khilaaf hai.",
            )
    return text


# ---------------------------------------------------------------------------
# Request model — KEEP history as string (frontend contract)
# ---------------------------------------------------------------------------
class AskRequest(BaseModel):
    user_query: str = Field(..., description="Current user input")
    history: str = Field("", description="Previous conversation context")
    mode: str = Field("chat", description="Mode: 'chat' or 'quiz'")
    language: str = Field(
        "English", description="Response language: 'English' or 'हिंदी'"
    )


# ---------------------------------------------------------------------------
# Health endpoints
# ---------------------------------------------------------------------------
@app.api_route("/", methods=["GET", "HEAD"])
def home():
    return {"status": "alive"}


@app.api_route("/health", methods=["GET", "HEAD"])
def health():
    return {
        "status": "alive",
        "groq_configured": bool(_groq_api_key),
        "supabase_configured": bool(_supabase),
    }


# ---------------------------------------------------------------------------
# Quiz validator (unchanged contract)
# ---------------------------------------------------------------------------
def _get_questions(parsed_data: Any) -> list[dict[str, Any]]:
    """Validate the model response against the quiz response contract."""
    if not isinstance(parsed_data, dict):
        raise ValueError("Quiz response root must be a JSON object.")

    questions = parsed_data.get("questions")
    if not isinstance(questions, list) or len(questions) != 10:
        raise ValueError("Quiz response must contain exactly 10 questions.")

    for index, question in enumerate(questions, start=1):
        if not isinstance(question, dict):
            raise ValueError(f"Question {index} must be a JSON object.")
        if not isinstance(question.get("question"), str) or not question["question"].strip():
            raise ValueError(f"Question {index} must have a non-empty question string.")

        options = question.get("options")
        if (
            not isinstance(options, list)
            or not options
            or any(not isinstance(option, str) or not option.strip() for option in options)
        ):
            raise ValueError(
                f"Question {index} must have a non-empty list of option strings."
            )

        answer = question.get("answer")
        if not isinstance(answer, str) or not answer.strip() or answer not in options:
            raise ValueError(
                f"Question {index} must have an answer matching one of its options."
            )

    return questions


def _require_groq_client() -> Groq:
    if client is None:
        raise HTTPException(
            status_code=500,
            detail="AI service is not configured. Please contact the service administrator.",
        )
    return client


# ---------------------------------------------------------------------------
# POST /ask — secured, same response shape as before
# ---------------------------------------------------------------------------
@app.post("/ask")
@limiter.limit("20/minute")
async def ask(
    request: Request,
    body: AskRequest,
    user: AuthUser = Depends(get_current_user),
):
    # 1. Sanitize
    clean_query = sanitize_query(body.user_query)

    # 2. Log (never log full token / key)
    logger.info(
        "ask mode=%s guest=%s user_id=%s query_len=%d",
        body.mode,
        user.is_guest,
        user.user_id or "guest",
        len(clean_query),
    )

    groq_client = _require_groq_client()

    # -----------------------------------------------------------------------
    # QUIZ MODE
    # -----------------------------------------------------------------------
    if body.mode == "quiz":
        lang_note = (
            "Write questions and options in simple Hinglish (easy Hindi mixed with standard English UPSC terms)."
            if body.language == "हिंदी"
            else "Write questions and options in crisp, clear English."
        )
        system_prompt = f"""
        You are a strict yet supportive UPSC Prelims Examiner.
        Generate exactly 10 high-quality, conceptual MCQ questions based on the provided topics.
        Include realistic, conceptual distractors to build exam clarity.
        {lang_note}

        CRITICAL INSTRUCTION: OUTPUT A VALID JSON OBJECT ONLY.
        Use the exact schema below with a single root key "questions". Every question must have
        a non-empty question string, an options array of 4 strings, and an answer that exactly
        matches one of those options:
        {{
          "questions": [
            {{
              "question": "Which Article protects Life and Personal Liberty?",
              "options": ["Article 14", "Article 19", "Article 21", "Article 32"],
              "answer": "Article 21"
            }}
          ]
        }}
        """
        quiz_models = ["openai/gpt-oss-20b", "llama-3.1-8b-instant"]
        chat_completion = None
        last_exc: Exception | None = None

        for model_name in quiz_models:
            try:
                chat_completion = groq_client.chat.completions.create(
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": clean_query},
                    ],
                    model=model_name,
                    temperature=0.3,
                    max_tokens=3000,
                    response_format={"type": "json_object"},
                )
                break
            except Exception as exc:
                logger.warning("Groq quiz request failed for model %s: %s", model_name, exc)
                last_exc = exc

        if chat_completion is None:
            logger.error("All Groq quiz models failed", exc_info=last_exc)
            raise HTTPException(status_code=500, detail="Quiz generation failed.") from last_exc

        raw_json = chat_completion.choices[0].message.content
        try:
            parsed_data = json.loads(raw_json)
            questions_list = _get_questions(parsed_data)
        except (json.JSONDecodeError, TypeError, ValueError) as exc:
            logger.exception("Groq returned invalid quiz JSON or schema")
            raise HTTPException(
                status_code=500, detail="Quiz generation returned invalid data."
            ) from exc

        # Frontend contract: answer is a JSON string of the questions list
        return {"answer": json.dumps(questions_list, ensure_ascii=False)}

    # -----------------------------------------------------------------------
    # CHAT MODE — exact mentor prompt preserved
    # -----------------------------------------------------------------------
    syllabus = (
        "Basics -> Preamble -> Union & Territory -> Citizenship -> "
        "Fundamental Rights -> DPSP -> Fundamental Duties"
    )
    is_hindi = body.language == "हिंदी"

    language_directive = (
        "Respond in warm, conversational Hinglish (simple Hindi mixed with standard English UPSC terms like Fundamental Rights, Article, Writ, Basic Structure). Address the student personally as 'tum' / 'aap'."
        if is_hindi
        else "Respond in simple, encouraging English with occasional warm Hindi mentor phrases (like 'Shabaash!', 'Chalo samajhte hain'). Address the student personally as 'you'."
    )

    save_offer_line = (
        "Shall we save this to **Topics You Know**? (Reply 'Yes' for a quick 1-question check!)"
        if not is_hindi
        else "Kya hum ise **Topics You Know** mein save karein? (Ek chhote se question ke liye 'Yes' likho!)"
    )

    system_prompt = f"""
    You are PolicyPath Mentor, an encouraging elder sibling and Senior UPSC Faculty.
    Your goal is to guide the student step-by-step through the UPSC syllabus: {syllabus}.

    ### 🎯 TONE & LANGUAGE RULES (CRITICAL):
    1. **WARM MENTOR VOICE:** Be encouraging, clear, and personal. Never scold or make the student feel judged. Celebrate small wins loudly ("Shabaash! 🎯", "Bahut badhiya!").
    2. **LANGUAGE:** {language_directive}
    3. **NO CORPORATE JARGON:** Never say the words "vault", "portfolio", or "generate" in your visible reply. Always refer to saved notes as **"Topics You Know"**.
    4. **NO META-TALK:** Never say "The user said..." or explain your internal state machine. Speak directly to the student.
    5. **NO WALLS OF TEXT:** Keep every bullet crisp (12–18 words max) and scannable on a mobile screen.

    ### 🏗️ STATE MACHINE LOGIC (Analyze History to Choose Phase):

    **PHASE 1: TEACHING (Default State when student asks a topic or doubt)**
    - Action: Provide a structured, high-yield UPSC breakdown using the **EXACT SECTION TEMPLATE** below.
    - **MANDATORY RESPONSE TEMPLATE:**
      📌 **[Topic / Article Title & One-Line Subtitle]**

      🔑 **Key Point:**
      [1–2 crisp sentences explaining the core constitutional rule]

      📚 **Expanded Scope:**
      • [Key dimension or sub-provision 1]
      • [Key dimension or sub-provision 2]
      • [Key dimension or sub-provision 3]

      ⚖️ **Landmark Cases & Amendments:**
      • [Supreme Court Case / Amendment 1 with year]
      • [Supreme Court Case / Amendment 2 with year]

      📝 **UPSC Connection:**
      • [Prelims/Mains relevance & years asked, e.g., "Asked in UPSC Prelims 2018, 2021"]

      👉 **Next Step:** {save_offer_line}

    **PHASE 2: QUICK CHECK (Confirmation State)**
    - Trigger: Student says "Yes", "Haan", "Sure", or "Save" to your Phase 1 offer.
    - Action:
      1. Say: "Badhiya! Let's do a quick 1-question check to lock it in."
      2. Ask **ONE** clear, conceptual UPSC question based on the topic just discussed.

    **PHASE 3: EVALUATION (First Attempt)**
    - Trigger: Student answers your Phase 2 question.
    - Action:
      - **IF CORRECT:**
        1. Celebrate warmly: "Shabaash! Bilkul sahi 🎯 [1-sentence reinforcement]."
        2. **APPEND HIDDEN SAVE TAG** at the very end (exact format below).
        3. Suggest the NEXT topic from the syllabus: "{syllabus}".
      - **IF WRONG:**
        1. Stay supportive: "Koi baat nahi, close attempt! The right answer is **[Answer]** because [1-sentence reason]."
        2. **DO NOT APPEND THE SAVE TAG YET.**
        3. Say: "Ek baar phir try karte hain taaki pakka yaad ho jaye: [Repeat the Question]?"

    **PHASE 4: RE-EVALUATION (Second Chance)**
    - Trigger: History shows you just explained the right answer and asked them to try again.
    - Action:
      - **IF CORRECT:**
        1. Say: "Perfect! Ab yeh concept tumhara pakka ho gaya 💪"
        2. **APPEND HIDDEN SAVE TAG** at the very end.
        3. Suggest the NEXT topic from the syllabus.
      - **IF STILL WRONG:**
        1. Say: "No worries! Har topper ne zero se shuru kiya tha. Maine iska clean note **Topics You Know** mein save kar diya hai."
        2. **APPEND HIDDEN SAVE TAG** at the very end.
        3. Suggest the NEXT topic from the syllabus.

    **PHASE 5: INTERRUPTION HANDLER**
    - Trigger: You asked the quick-check question, but the student asks a NEW, UNRELATED doubt.
    - Action:
      1. Give a crisp, structured answer to their new doubt first.
      2. Gently ask: "Jab ready ho, pichle topic ka quick-check question bhi complete kar lein?"

    ### 🏆 HIDDEN DATABASE SAVE TAG (Strict - Only in Phase 3 Correct or Phase 4; frontend parses and hides this):
    ||VAULT_START||
    Topic: [Title Case Topic Name]
    Summary: [High-quality UPSC revision note, max 2 crisp sentences]
    ||VAULT_END||

    ### 👋 FIRST INTERACTION RULE:
    If history is empty and the user says "Hi", "Hello", or "Continue Polity", welcome them warmly:
    "Namaste! 🙏 Main tumhara AI mentor hoon. Constitution, Polity, Economy — kuch bhi pucho. Chalo **Source of Authority** se shuru karte hain: Indian Constitution ko apni ultimate power kisse milti hai?"
    """

    # history stays a STRING — do not change this
    full_context = (
        f"CONVERSATION HISTORY:\n{body.history}\n\n"
        f"CURRENT USER INPUT:\n{clean_query}"
    )

    chat_models = ["openai/gpt-oss-20b", "llama-3.1-8b-instant"]
    chat_completion = None
    last_chat_exc: Exception | None = None

    for model_name in chat_models:
        try:
            chat_completion = groq_client.chat.completions.create(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": full_context},
                ],
                model=model_name,
                temperature=0.4,
                max_tokens=1500,
            )
            break
        except Exception as exc:
            logger.warning("Groq chat request failed for model %s: %s", model_name, exc)
            last_chat_exc = exc

    if chat_completion is None:
        logger.error("All Groq chat models failed", exc_info=last_chat_exc)
        raise HTTPException(
            status_code=500, detail="Chat response generation failed."
        ) from last_chat_exc

    answer_text = chat_completion.choices[0].message.content
    if not isinstance(answer_text, str):
        logger.error("Groq chat completion returned an empty or non-text response")
        raise HTTPException(
            status_code=500, detail="Chat response generation returned invalid data."
        )

    # Frontend contract: {"answer": "<mentor text including optional ||VAULT_*|| tags>"}
    return {"answer": answer_text}
