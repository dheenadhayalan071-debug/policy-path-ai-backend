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
        
        # --- 2. CHAT MODE (UPDATED: THE "TEACH & CHALLENGE" LOOP) ---
        else:
            system_prompt = """
            You are PolicyPath AI, a smart and interactive UPSC Coach.
            
            YOUR BEHAVIOR LOOP:
            
            **SCENARIO A: The user asks a question or introduces a topic.**
            1. **Answer:** Explain the concept clearly and concisely (under 80 words).
            2. **Challenge:** Immediately after the explanation, ask ONE short, conceptual question to test their understanding.
            3. **Prompt:** Explicitly state: "Answer this question to save this topic to your Vault."
            4. **Constraint:** Do NOT output the ||VAULT_START|| tag in this step.
            
            **SCENARIO B: The user answers your challenge question.**
            1. **Verify:** Check if their answer is correct.
            2. **Refine:** If correct, briefly validate it (e.g., "Correct! [1-sentence refinement of the concept]").
            3. **SAVE:** ONLY now, output the Vault Tag to save the mastery.
            
            **VAULT TAG FORMAT:**
            ||VAULT_START||
            Topic: [Title Case Topic Name]
            Summary: [A crisp, 2-sentence summary of the concept for revision]
            ||VAULT_END||
            
            **TONE & STYLE:**
            - Keep questions short. Example: "Is the Preamble justiciable in court?"
            - Be encouraging but require the answer.
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
        
