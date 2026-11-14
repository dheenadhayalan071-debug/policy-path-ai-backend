import json
from typing import List, Dict, Any, Tuple
from groq import AsyncGroq
from app.config import settings

# Primary and Fallback Models
PRIMARY_MODEL = "openai/gpt-oss-20b"
FALLBACK_MODEL = "llama-3.1-8b-instant"

# Async Groq Client
client = AsyncGroq(api_key=settings.GROQ_API_KEY) if settings.GROQ_API_KEY else None

# Pre-compiled System Prompt (Preserved exactly as engineered)
MENTOR_SYSTEM_PROMPT = """You are PolicyPath AI, an expert, empathetic, and highly structured UPSC mentor for low-resource Indian aspirants.

Guidelines:
1. Provide structured, crisp, point-wise answers using clear markdown headings (###) and bold key terms (**term**).
2. Keep explanations easy to digest. Avoid academic jargon unless defined immediately.
3. Keep answers concise (max 3-4 key points per response).
4. Tone: Warm elder sibling/mentor. Never corporate, never robotic, never condescending. Celebrate effort.
5. Support language: If the user writes in Hinglish or requests Hindi, respond in clean, natural Hinglish. If English, respond in clear standard English.

5-Phase Response Framework:
- Teaching Phase: Explain concept clearly with relevant UPSC syllabus mapping (GS-1, GS-2, GS-3, or GS-4).
- Quick Check Phase: End with 1 interactive follow-up question to test understanding.
- Evaluation Phase: Grade their answer strictly according to UPSC standards (Content, Structure, Presentation).
- Re-Evaluation Phase: Provide actionable fixes if they missed critical facts or Articles.
- Interruption Handler: Gently guide them back to UPSC syllabus if they ask off-topic personal queries.

Hidden Note Tag (MUST INCLUDE when explaining a clear core topic/concept):
Append this EXACT tag format at the very end of your response:
||VAULT_START||
Topic: <Topic Name>
Summary: <1-line core summary>
||VAULT_END||
"""

QUIZ_SYSTEM_PROMPT = """You are a senior UPSC exam question creator. 
Generate EXACTLY 10 multiple-choice questions (MCQs) for UPSC Prelims level based on the given user topic or mixed syllabus.

Output MUST be a valid JSON object matching this structure EXACTLY:
{
  "questions": [
    {
      "id": 1,
      "question": "Question text here?",
      "options": ["Option A", "Option B", "Option C", "Option D"],
      "answer": "Option A",
      "explanation": "Detailed 2-line explanation here."
    }
  ]
}

Rules:
- Generate EXACTLY 10 questions.
- The 'answer' string MUST match one of the string elements in 'options' EXACTLY.
- Strictly output JSON only. No surrounding markdown code blocks (no ```json).
"""


def validate_quiz_json(raw_json_str: str) -> List[Dict[str, Any]]:
    """Validates and parses the AI generated quiz format."""
    data = json.loads(raw_json_str)
    questions = data.get("questions", [])

    if not isinstance(questions, list) or len(questions) != 10:
        raise ValueError(f"Expected 10 questions, got {len(questions)}")

    for i, q in enumerate(questions):
        if not all(k in q for k in ("id", "question", "options", "answer", "explanation")):
            raise ValueError(f"Missing required fields in question index {i}")

        if not isinstance(q["options"], list) or len(q["options"]) != 4:
            raise ValueError(f"Question index {i} does not have exactly 4 options")

        if q["answer"] not in q["options"]:
            raise ValueError(f"Question index {i} answer '{q['answer']}' not present in options list")

    return questions


async def call_chat_ai(
    query: str, history: List[Dict[str, str]] = None, language: str = "English"
) -> str:
    """Sends user query and dynamic chat history to Groq for mentor streaming/response."""
    if not client:
        return "System temporarily offline: Groq API Key is not configured on server."

    messages = [{"role": "system", "content": MENTOR_SYSTEM_PROMPT}]

    # Append historic conversation if provided
    if history:
        for item in history[-6:]:  # Keep last 6 context messages for memory economy
            role = item.get("role", "user")
            content = item.get("content", "")
            if role in ("user", "assistant") and content:
                messages.append({"role": role, "content": content})

    # Add primary query with explicit language directive
    user_prompt = query
    if language.lower() in ("hinglish", "hindi"):
        user_prompt += " (Kripya iska jawab Hinglish mein dein)."

    messages.append({"role": "user", "content": user_prompt})

    # Try Primary Model then Fallback
    models_to_try = [PRIMARY_MODEL, FALLBACK_MODEL]
    last_error = None

    for model_name in models_to_try:
        try:
            response = await client.chat.completions.create(
                model=model_name,
                messages=messages,
                temperature=0.4,
                max_tokens=1500,
            )
            return response.choices[0].message.content
        except Exception as e:
            print(f"⚠️ Model '{model_name}' failed: {e}. Trying fallback...")
            last_error = e

    raise Exception(f"AI Service unavailable: {last_error}")


async def call_quiz_ai(topic: str) -> List[Dict[str, Any]]:
    """Generates 10 MCQ Prelims Quiz questions strictly parsed into JSON."""
    if not client:
        raise Exception("Groq API Key is not configured on server.")

    prompt = f"Topic for UPSC Prelims MCQs: {topic if topic else 'Mixed Polity, Governance & Economy'}"

    models_to_try = [PRIMARY_MODEL, FALLBACK_MODEL]

    for model in models_to_try:
        try:
            response = await client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": QUIZ_SYSTEM_PROMPT},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.3,
                max_tokens=3000,
                response_format={"type": "json_object"},
            )
            raw_content = response.choices[0].message.content
            return validate_quiz_json(raw_content)
        except Exception as e:
            print(f"⚠️ Model '{model}' failed quiz generation: {e}")

    raise Exception("Failed to generate standard UPSC quiz after attempting all fallback models.")
