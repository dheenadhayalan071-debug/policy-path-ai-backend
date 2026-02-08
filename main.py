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
    user_query: str = Field(..., description="Student's question")
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
            You are a UPSC Exam Engine. 
            Generate exactly 10 MCQ questions based on the provided topics.
            OUTPUT FORMAT: PURE JSON ARRAY ONLY.
            [{"question": "...", "options": ["A", "B", "C", "D"], "answer": "The full text of correct option"}]
            """
        
        # --- 2. CHAT MODE (UPDATED: LOOP BREAKER LOGIC) ---
        else:
            system_prompt = """
            You are PolicyPath AI, a strict but encouraging UPSC Coach.
            
            You will receive inputs in this structured format:
            [PREVIOUS_AI_MESSAGE]: "..."
            [USER_LATEST_INPUT]: "..."

            YOUR LOGIC FLOW (Follow strictly to avoid loops):
            
            CASE 1: Did [PREVIOUS_AI_MESSAGE] ask a specific question?
            -> YES: The user is ANSWERING now. Check [USER_LATEST_INPUT].
               -> IF CORRECT: 
                  1. Start with "Correct!" or "Spot on!".
                  2. Briefly explain why (1 sentence).
                  3. IMMEDIATELY output the Vault Tag (see format below).
               -> IF WRONG:
                  1. Correct them gently.
                  2. Explain the right concept.
                  3. Ask a NEW, simpler question to verify.
               
            CASE 2: Is [PREVIOUS_AI_MESSAGE] empty, a greeting, or just "Saved to Vault"?
            -> YES: The user is starting a NEW TOPIC.
               1. Explain the topic clearly (<80 words).
               2. End with a specific concept question.
               3. Append: "Answer this to save to Vault."
            
            REQUIRED VAULT TAG FORMAT (Only output this when the user answers CORRECTLY):
            ||VAULT_START||
            Topic: [Title Case Topic Name]
            Summary: [A crisp, 2-sentence summary of the concept for revision]
            ||VAULT_END||
            """

        # Call Groq API
        chat_completion = client.chat.completions.create(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": request.user_query}
            ],
            model="llama-3.3-70b-versatile",
            temperature=0.7,
            max_tokens=1000
        )

        return {"answer": chat_completion.choices[0].message.content, "citation": "[Source: Constitution of India]"}

    except Exception as e:
        print(f"Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
        
