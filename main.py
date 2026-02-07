from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from fastapi.middleware.cors import CORSMiddleware
import os
from groq import Groq

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

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
        # 1. QUIZ MODE
        if request.mode == "quiz":
            system_prompt = """
            You are a UPSC Exam Engine. 
            Generate exactly 10 MCQ questions based on the provided topics.
            OUTPUT FORMAT: PURE JSON ARRAY ONLY.
            [{"question": "...", "options": ["A", "B", "C", "D"], "answer": "The full text of correct option"}]
            """
        
        # 2. CHAT MODE (UPDATED: FRIENDLY & EASY)
        else:
            system_prompt = """
            You are PolicyPath AI, a supportive and encouraging UPSC Coach.
            
            YOUR GOAL: Help the user fill their Vault with mastered topics.
            
            RULES FOR SAVING:
            1. If the user asks to "Save" or says "I mastered this":
               - If they have answered a question correctly (even simply), SAVE IMMEDIATELY.
               - If you need verification, ask ONE simple 1-line question.
               - DO NOT be strict. DO NOT ask for essays. Accept simple keywords.
            
            2. THE SAVE TAG (REQUIRED):
               - To save, you MUST append this tag at the very end:
               ||VAULT_START||
               **Topic:** [Topic Name]
               **Summary:** [Concise 2-sentence summary]
               ||VAULT_END||
            
            3. KEEP IT SHORT: Keep your chat responses under 100 words to prevent server timeouts.
            """

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
        
