import os
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from fastapi.middleware.cors import CORSMiddleware
from groq import Groq  # <--- Importing the new Brain

# 1. SETUP THE CLIENT
# We initialize Groq using the key from your Render Environment
client = Groq(
    api_key=os.environ.get("GROQ_API_KEY"),
)

app = FastAPI()

# 2. SECURITY (CORS)
# This allows your Replit Frontend to talk to this Backend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 3. DATA MODELS
# This defines what the backend expects to receive
class AskRequest(BaseModel):
    user_query: str = Field(..., description="The student's question")

class AskResponse(BaseModel):
    answer: str
    citation: str
    progress_boost: int

# 4. THE API ENDPOINT
@app.post("/ask", response_model=AskResponse)
async def ask(request: AskRequest):
    # Safety Check: Is the question empty?
    if not request.user_query.strip():
        raise HTTPException(status_code=400, detail="Query cannot be empty")

    try:
        # THE AI CALL (The Brain Transplant)
        # We use 'llama-3.3-70b-versatile' (Smart & Fast)
        chat_completion = client.chat.completions.create(
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are an expert UPSC Tutor for Indian Polity. "
                        "Answer clearly, strictly based on the Constitution of India. "
                        "Keep answers concise (under 100 words) for a chat interface."
                    )
                },
                {
                    "role": "user",
                    "content": request.user_query,
                }
            ],
            model="llama-3.3-70b-versatile",
        )

        # Extract the text answer
        ai_text = chat_completion.choices[0].message.content

        return {
            "answer": ai_text,
            "citation": "Source: Llama 3 (via Groq)",
            "progress_boost": 10
        }

    except Exception as e:
        # If something breaks, print the real error to Render logs
        print(f"Groq Error: {e}")
        return {
            "answer": "I am currently upgrading my neural pathways. Please try again in a moment.",
            "citation": "System Maintenance",
            "progress_boost": 0
        }
        
