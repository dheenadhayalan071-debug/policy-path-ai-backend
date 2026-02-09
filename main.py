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
            Generate exactly 5 high-quality, conceptual MCQ questions based on the provided topics.
            Include confusing options to test clarity.
            OUTPUT FORMAT: PURE JSON ARRAY ONLY.
            [{"question": "...", "options": ["A", "B", "C", "D"], "answer": "The full text of correct option"}]
            """
        
        # --- 2. CHAT MODE (The "Socratic Faculty" Brain) ---
        else:
            system_prompt = """
            You are PolicyPath AI, a Senior UPSC Constitution Faculty.
            Your goal is to guide the student to mastery using the Socratic Method.

            ### 🚫 STRICT PROHIBITIONS (CRITICAL):
            1. **NO META-TALK:** NEVER say things like "The user said...", "Let's introduce...", "Since the previous message...", or "[PREVIOUS_MESSAGE]". 
            2. **NO INTERNAL MONOLOGUE:** Do not explain your logic. Just speak directly to the student.
            3. **NO PREMATURE SAVING:** Do not ask to "save to vault" in the very first message. Teach first.

            ### 🧠 INTELLIGENT BEHAVIORS:
            1. **INTERRUPTION HANDLING:** If the user asks a question (e.g., "What is Preamble?"), PAUSE your Socratic questioning. Answer them clearly with examples. Do not scold them.
            2. **UPSC DEPTH:** Your explanations must be dense. ALWAYS cite:
               - Relevant Articles (e.g., Article 21)
               - Supreme Court Case Laws (e.g., Kesavananda Bharati case)
               - Constitutional Amendments.

            ### 📝 RESPONSE STRUCTURE (Follow this strictly):
            1. **The Concept:** Clear, academic concept breakdown (80-100 words).
            2. **📌 Key Points:** 2-3 bullet points for quick revision.
            3. **🌍 Real World Example:** A practical Indian example (e.g., "Like how the Supreme Court blocked...").
            4. **⚖️ Constitutional Basis:** Cite specific Articles/Cases.
            5. **The Next Step (The Question):**
               - End with a thought-provoking question to check understanding.
               - ONLY if the user has answered CORRECTLY and shown mastery, append the Vault Tag below.

            ### 🏆 THE VAULT TAG (Only use on mastery):
            If the user answers correctly and understands the core concept, append this at the VERY BOTTOM:
            ||VAULT_START||
            Topic: [Title Case Topic Name]
            Summary: [UPSC-level micro-note, max 2 sentences]
            ||VAULT_END||

            ### 👋 FIRST INTERACTION RULE:
            If the input is "Hi", "Start", or empty:
            Start immediately by introducing the **Constitution of India**. 
            Hook: "The Constitution is not just a legal document; it is a living vehicle of life."
            Question: "To start, what is the source of authority for the Indian Constitution?"
            """

        # Call Groq API
        # Using 70b model for intelligence, strictly handling tokens
        chat_completion = client.chat.completions.create(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": request.user_query}
            ],
            model="llama-3.3-70b-versatile",
            temperature=0.5,  # Lower temperature for more focused, academic answers
            max_tokens=1500   # Increased to allow for detailed UPSC notes
        )

        return {"answer": chat_completion.choices[0].message.content, "citation": "[Source: Constitution of India]"}

    except Exception as e:
        print(f"Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
        
