from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from fastapi.middleware.cors import CORSMiddleware
import os
from groq import Groq

# 1. SETUP & CONFIGURATION
app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

client = Groq(api_key=os.environ.get("GROQ_API_KEY"))

# 2. DATA MODELS
class AskRequest(BaseModel):
    user_query: str = Field(..., description="Student's question")
    mode: str = Field("chat", description="Mode: 'chat' or 'quiz'")

class AskResponse(BaseModel):
    answer: str
    citation: str
    is_refusal: bool = False

# 3. THE BRAIN (SYSTEM PROMPT LOGIC)
def get_system_prompt(mode: str):
    if mode == "quiz":
        return """
        You are an Exam Engine. Generate 5 MCQ questions based on the user's mastered topics.
        Format: JSON Array only. No text.
        """
    
    # CHAT MODE - The "Socratic Professor" Persona
    return """
    You are 'PolicyPath AI', a Strict Socratic Mentor for UPSC Civil Services (Indian Polity).
    
    CORE BEHAVIORS:
    1. **STRICT GUARDRAILS:** If the user asks about anything other than Indian Constitution/Polity (e.g., Python, Cricket, Movies), REFUSE immediately. Say: "I am your Polity Mentor. Let's stick to the Constitution."
    
    2. **SOCRATIC METHOD:** - If the user is WRONG, DO NOT give the answer immediately. 
       - Challenge them: "That is incorrect. Article 21 talks about Life. Which Article actually covers [Topic]? Try again."
       - EXCEPTION: If the user says "I don't know", "Tell me", or "Give up", STOP Socratic mode and provide the full answer immediately.

    3. **EXAM-STYLE FORMATTING:**
       - NEVER write big blocks of text.
       - Use HEADINGS (e.g., "### Constitutional Provision").
       - Use BULLET POINTS for key details.
    
    4. **ADAPTABILITY:**
       - If user says "Explain like I'm 5", simplify your language temporarily, then link back to legal terms.

    5. **CONCEPTUAL SYLLABUS JUMPING:**
       - At the end, suggest the next *Logical Concept* (not just the next number).
       - Ex: Rights (Art 12-35) -> DPSP (Art 36-51).
       - Ex: President -> Governor (Comparative).

    6. **SMART VAULT SUMMARY:**
       - If the explanation is useful for revision, append a summary box at the very bottom using this EXACT format:
       ||VAULT_START||
       **📌 SAVED TO VAULT:**
       *Topic: [Topic Name]*
       *Summary: [1-line rigorous definition]*
       ||VAULT_END||

    7. **CITATION:**
       - Be Specific. Use: [Source: Constitution of India, Part X, Article Y].
    """

# 4. API ENDPOINT
@app.post("/ask", response_model=AskResponse)
async def ask(request: AskRequest):
    
    if not request.user_query.strip():
        raise HTTPException(status_code=400, detail="Query cannot be empty")

    try:
        # --- 1. Socratic Logic Check ---
        # If user is giving up, we prepend a system instruction to "Yield"
        final_query = request.user_query
        if any(w in request.user_query.lower() for w in ["don't know", "tell me", "give up", "answer is"]):
             final_query = f"[SYSTEM: User has yielded. Provide the full answer now.] {request.user_query}"
        elif "explain like" in request.user_query.lower():
             final_query = f"[SYSTEM: Switch to Simple Analogy Mode.] {request.user_query}"

        # --- 2. The AI Call ---
        chat_completion = client.chat.completions.create(
            messages=[
                {"role": "system", "content": get_system_prompt(request.mode)},
                {"role": "user", "content": final_query}
            ],
            model="llama-3.3-70b-versatile",
            temperature=0.6, # Lower temp for more academic accuracy
            max_tokens=800
        )

        ai_text = chat_completion.choices[0].message.content

        # --- 3. Guardrail Check ---
        is_refusal = "let's stick to the constitution" in ai_text.lower()

        return AskResponse(
            answer=ai_text,
            citation="[Source: Constitution of India / Laxmikanth]", # Fallback citation
            is_refusal=is_refusal
        )

    except Exception as e:
        print(f"ERROR: {str(e)}")
        raise HTTPException(status_code=500, detail="Brain Freeze. Please retry.")
        
