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

@app.post("/ask")
async def ask(request: AskRequest):
    try:
        # SYSTEM PROMPTS
        if request.mode == "quiz":
            system_prompt = """
            You are a UPSC Exam Engine. 
            Generate exactly 10 tough MCQ questions based on the provided topics.
            OUTPUT FORMAT: PURE JSON ARRAY. No text before/after.
            [{"question": "...", "options": ["A", "B", "C", "D"], "answer": "The full text of correct option"}]
            """
        else:
            system_prompt = """
            You are 'PolicyPath AI', a strict UPSC Mentor.
            RULES:
            1. Use Bullet points.
            2. If user masters a topic, append this HIDDEN TAG at the end:
               ||VAULT_START||
               **Topic:** [Topic Name]
               **Summary:** [Deep concise revision note of 50 words]
               ||VAULT_END||
            3. CHALLENGE the user. Don't just answer.
            """

        chat_completion = client.chat.completions.create(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": request.user_query}
            ],
            model="llama-3.3-70b-versatile",
            temperature=0.5,
            max_tokens=1500
        )

        return {"answer": chat_completion.choices[0].message.content, "citation": "[Source: Constitution of India]"}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
        
