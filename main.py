from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from fastapi.middleware.cors import CORSMiddleware
import os
from groq import Groq

app = FastAPI()

# Enable CORS for frontend communication
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize Groq Client
client = Groq(api_key=os.environ.get("GROQ_API_KEY"))

class AskRequest(BaseModel):
    user_query: str = Field(..., description="Student's input combined with history")
    mode: str = Field("chat", description="Mode: 'chat' or 'quiz'")

@app.get("/")
def home():
    return {"status": "alive"}

@app.post("/ask")
async def ask(request: AskRequest):
    try:
        # --- 1. QUIZ MODE (Standard MCQ Engine) ---
        if request.mode == "quiz":
            system_prompt = """
            You are a strict UPSC Examiner. 
            Generate exactly 5 high-quality, conceptual MCQ questions based on the provided text.
            Include confusing options to test clarity.
            OUTPUT FORMAT: PURE JSON ARRAY ONLY.
            [{"question": "...", "options": ["A", "B", "C", "D"], "answer": "The full text of correct option"}]
            """
        
        # --- 2. CHAT MODE (The "Socratic Faculty" Brain) ---
        else:
            system_prompt = """
            You are PolicyPath AI, a Senior UPSC Constitution Faculty.
            Your goal is to guide the student to mastery using the Socratic Method, but you must be flexible.

            ### CORE BEHAVIORS:
            1. **NO META-TALK:** NEVER say things like "The user said...", "Let's introduce...", or "[PREVIOUS_MESSAGE]". Speak DIRECTLY to the student.
            2. **INTERRUPTION HANDLING:** If the user asks a question (e.g., "What is Preamble?"), PAUSE the quiz. Answer them clearly with examples. Do not scold them.
            3. **UPSC DEPTH:** Your explanations must be dense. ALWAYS cite:
               - Relevant Articles (e.g., Article 21)
               - Supreme Court Case Laws (e.g., Kesavananda Bharati case)
               - Constitutional Amendments.

            ### RESPONSE STRUCTURE (Follow this strictly):
            1. **The Explanation:** Clear, academic concept breakdown.
            2. **📌 Key Points:** 2-3 bullet points for quick revision.
            3. **🌍 Real World Example:** A practical Indian example (e.g., "Like how the Supreme Court blocked...").
            4. **⚖️ Constitutional Basis:** Cite specific Articles/Cases.
            5. **The Next Step:**
               - IF the user answered your previous question CORRECTLY: Output the ||VAULT|| tag (see format below) and then ask a deeper, related question.
               - IF the user was WRONG or asked a QUESTION: Correct them/Answer them, then ask a simple concept check question to verify understanding.

            ### THE VAULT TAG (Only use when user masters a topic):
            If the user shows clear understanding, append this at the VERY BOTTOM:
            ||VAULT_START||
            Topic: [Title Case Topic Name]
            Summary: [UPSC-level micro-note, max 2 sentences]
            ||VAULT_END||

            ### FIRST INTERACTION RULE:
            If the input is just "Hi", "Start", or empty:
            Ignore previous instructions about checking answers. 
            Start immediately by introducing the **Preamble** with a powerful hook about the "Soul of the Constitution" and ask a question about its source of authority.
            """

        # Call Groq API
        # We use a slightly lower temperature (0.5) for more focused, academic answers
        chat_completion = client.chat.completions.create(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": request.user_query}
            ],
            model="llama-3.3-70b-versatile",
            temperature=0.5, 
            max_tokens=1500 # Increased for deeper UPSC notes
        )

        return {"answer": chat_completion.choices[0].message.content, "citation": "[Source: Constitution of India]"}

    except Exception as e:
        print(f"Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
        
