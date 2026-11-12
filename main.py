import json
import logging
import os
import traceback
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from groq import Groq


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://policy-path-theta.vercel.app",
        "http://localhost:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Keep health endpoints available even when deployment configuration is incomplete.
_groq_api_key = os.environ.get("GROQ_API_KEY")
client = Groq(api_key=_groq_api_key) if _groq_api_key else None
if not _groq_api_key:
    logger.warning("GROQ_API_KEY is not set; /ask requests cannot reach Groq until it is configured.")


class AskRequest(BaseModel):
    user_query: str = Field(..., description="Current user input")
    history: str = Field("", description="Previous conversation context")
    mode: str = Field("chat", description="Mode: 'chat' or 'quiz'")


@app.get("/")
def home():
    return {"status": "alive"}


@app.get("/health")
def health():
    return {"status": "alive"}


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
            raise ValueError(f"Question {index} must have a non-empty list of option strings.")

        answer = question.get("answer")
        if not isinstance(answer, str) or not answer.strip() or answer not in options:
            raise ValueError(f"Question {index} must have an answer matching one of its options.")

    return questions


def _require_groq_client() -> Groq:
    if client is None:
        raise HTTPException(
            status_code=500,
            detail="AI service is not configured. Please contact the service administrator.",
        )
    return client


@app.post("/ask")
async def ask(request: AskRequest):
    if not request.user_query.strip():
        raise HTTPException(status_code=400, detail="user_query must not be blank.")

    groq_client = _require_groq_client()

    if request.mode == "quiz":
        system_prompt = """
        You are a strict UPSC Examiner.
        Generate exactly 10 high-quality, conceptual MCQ questions based on the provided topics.
        Include confusing options to test clarity.

        CRITICAL INSTRUCTION: OUTPUT A VALID JSON OBJECT ONLY.
        Use the exact schema below with a single root key "questions". Every question must have
        a non-empty question string, an options array of strings, and an answer that exactly
        matches one of those options:
        {
          "questions": [
            {
              "question": "Which Article protects Life and Personal Liberty?",
              "options": ["Article 14", "Article 19", "Article 21", "Article 32"],
              "answer": "Article 21"
            }
          ]
        }
        """
        try:
            chat_completion = groq_client.chat.completions.create(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": request.user_query.strip()},
                ],
                model="llama-3.3-70b-versatile",
                temperature=0.3,
                max_tokens=3000,
                response_format={"type": "json_object"},
            )
        except Exception as exc:
            logger.exception("Groq quiz completion request failed")
            raise HTTPException(status_code=500, detail="Quiz generation failed.") from exc

        raw_json = chat_completion.choices[0].message.content
        try:
            parsed_data = json.loads(raw_json)
            questions_list = _get_questions(parsed_data)
        except (json.JSONDecodeError, TypeError, ValueError) as exc:
            logger.exception("Groq returned invalid quiz JSON or schema")
            raise HTTPException(status_code=500, detail="Quiz generation returned invalid data.") from exc

        return {"answer": json.dumps(questions_list, ensure_ascii=False)}

    syllabus = "Basics -> Preamble -> Union & Territory -> Citizenship -> Fundamental Rights -> DPSP -> Fundamental Duties"
    system_prompt = f"""
    You are PolicyPath AI, a Senior UPSC Constitution Faculty.
    Your goal is to take the student through the syllabus sequentially: {syllabus}.

    ### 🚫 STRICT PROHIBITIONS (CRITICAL):
    1. **NO META-TALK:** NEVER say things like "The user said...", "Let's introduce...", or "[PREVIOUS_MESSAGE]".
    2. **NO INTERNAL MONOLOGUE:** Do not explain your logic. Just speak directly to the student.
    3. **NO PREMATURE SAVING:** Do not ask to "save to vault" unless you have finished explaining the concept (Phase 1).

    ### 🧠 INTELLIGENT BEHAVIORS:
    1. **UPSC DEPTH:** Your explanations must be dense. ALWAYS cite:
       - Relevant Articles (e.g., Article 21).
       - Supreme Court Case Laws (e.g., Kesavananda Bharati case).
       - Constitutional Amendments.

    ### 🏗️ STATE MACHINE LOGIC (Analyze History to Choose Phase):

    **PHASE 1: TEACHING (Default State)**
    - Trigger: User asks about a topic (e.g., "What is Preamble?").
    - Action: Provide a structured answer using the **RESPONSE STRUCTURE** below.
    - **REQUIRED RESPONSE STRUCTURE:**
       1. **The Concept:** Clear, academic concept breakdown (80-100 words).
       2. **📌 Key Points:** 2-3 bullet points for quick revision.
       3. **🌍 Real World Example:** A practical Indian example (e.g., "Like how SC blocked...").
       4. **⚖️ Constitutional Basis:** Cite specific Articles/Cases.
       5. **The Next Step:** Ask exactly: "Shall we save this concept to your Vault?"

    **PHASE 2: QUIZZING (Confirmation State)**
    - Trigger: User says "Yes", "Sure", or "Save" to your offer.
    - Action:
      1. Say: "Great! Let's check your understanding first."
      2. Ask **ONE** simple, conceptual question based on the topic just discussed.

    **PHASE 3: EVALUATION (First Attempt)**
    - Trigger: User answers the Phase 2 quiz question.
    - Action:
      - **IF CORRECT:** 1. Say: "Spot on! 🎯 [Brief Praise]."
        2. **APPEND VAULT TAG** (See format below).
        3. Suggest the NEXT topic from the syllabus: "{syllabus}".
      - **IF WRONG:**
        1. Say: "Not quite. The correct answer is [Answer] because [Reason]."
        2. **DO NOT SAVE YET.** (Crucial Step).
        3. Say: "To make sure you've mastered this, answer the question again: [Repeat the Question]?"

    **PHASE 4: RE-EVALUATION (Second Chance)**
    - Trigger: History shows you just corrected the user and asked them to try again.
    - Action:
      - **IF CORRECT (matches the fix you gave):**
        1. Say: "Perfect! You've locked it in."
        2. **APPEND VAULT TAG** (See format below).
        3. Suggest the NEXT topic from the syllabus.
      - **IF STILL WRONG:** 1. Say: "Let's move on. I've saved the correct note for you."
        2. **APPEND VAULT TAG** (See format below).
        3. Suggest the NEXT topic from the syllabus.

    **PHASE 5: INTERRUPTION HANDLER**
    - Trigger: You asked a question/offered save, but User asks a NEW, UNRELATED topic.
    - Action:
      1. Give a VERY BRIEF (1 sentence) answer to the new query to satisfy curiosity.
      2. Say: "But before we dive deep into that, let's finish saving our previous topic. Ready for the quiz question?"

    ### 🏆 VAULT TAG FORMAT (Strict - Only in Phase 3 Correct or Phase 4):
    ||VAULT_START||
    Topic: [Title Case Topic Name]
    Summary: [High-quality UPSC note, max 2 sentences]
    ||VAULT_END||

    ### 👋 FIRST INTERACTION RULE:
    If history is empty, start by introducing the **Constitution of India**.
    Hook: "The Constitution is not just a legal document; it is a living vehicle of life."
    Question: "To start, what is the source of authority for the Indian Constitution?"
    """
    full_context = (
        f"CONVERSATION HISTORY:\n{request.history}\n\nCURRENT USER INPUT:\n{request.user_query.strip()}"
    )

    try:
        chat_completion = groq_client.chat.completions.create(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": full_context},
            ],
            model="openai/gpt-oss-20b",
            temperature=0.4,
            max_tokens=1500,
        )
    except Exception as exc:
        logger.exception("Groq chat completion request failed")
        raise HTTPException(status_code=500, detail="Chat response generation failed.") from exc

    answer_text = chat_completion.choices[0].message.content
    if not isinstance(answer_text, str):
        logger.error("Groq chat completion returned an empty or non-text response")
        raise HTTPException(status_code=500, detail="Chat response generation returned invalid data.")
    return {"answer": answer_text}
