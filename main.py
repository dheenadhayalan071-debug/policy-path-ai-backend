from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from fastapi.middleware.cors import CORSMiddleware
import os
from groq import Groq

# 1. SETUP
app = FastAPI()

# Add CORS so Vercel can talk to Render
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize Groq Client
client = Groq(
    api_key=os.environ.get("GROQ_API_KEY")
)

# 2. DATA MODELS
class AskRequest(BaseModel):
    user_query: str = Field(..., description="The student's question")

class AskResponse(BaseModel):
    answer: str
    citation: str
    progress_boost: int

# 3. THE API ENDPOINT
@app.post("/ask", response_model=AskResponse)
async def ask(request: AskRequest):
    
    # Safety Check
    if not request.user_query.strip():
        raise HTTPException(status_code=400, detail="Query cannot be empty")

    try:
        #  ⬇️ LOOK HERE! I pushed all this code to the right ⬇️
        system_prompt = """
        You are 'PolicyPath AI', an expert UPSC Civil Services Mentor for Indian Polity.
        Your Goal: Guide the student to mastery.

        STRICT RULES:
        1. CONCISE: Keep answers under 150 words. Use bullet points.
        2. CONTEXT AWARE: If the user asks "What next?", DO NOT explain the previous topic.
           - Instead, suggest the NEXT logical topic in the syllabus.
           - Sequence: Preamble -> Union & Territory (Art 1-4) -> Citizenship (Art 5-11) -> Fundamental Rights (Art 12-35).
        3. TONE: Encouraging but strict coach.
        4. CITATION: Always end with a source (e.g., [Source: Constitution of India]).
        """

        # --- THE AI CALL ---
        chat_completion = client.chat.completions.create(
            messages=[
                {
                    "role": "system",
                    "content": system_prompt
                },
                {
                    "role": "user",
                    "content": request.user_query
                }
            ],
            model="llama-3.3-70b-versatile",
            temperature=0.7
        )

        # Extract the text
        ai_text = chat_completion.choices[0].message.content

        return AskResponse(
            answer=ai_text,
            citation="Source: Constitution of India / Laxmikanth",
            progress_boost=5
        )
        # ⬆️ END OF INDENTED BLOCK ⬆️

    except Exception as e:
        print(f"SERVER ERROR: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
        
