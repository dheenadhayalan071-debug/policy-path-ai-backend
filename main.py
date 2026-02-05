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
    allow_origins=["*"],  # Allows all origins
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
            # --- UPDATED BRAIN LOGIC ---
    system_prompt = """
    You are 'PolicyPath AI', an expert UPSC Civil Services Mentor for Indian Polity.

    STRICT RULES:
    1. CONCISE: Keep answers under 150 words. Use bullet points.
    2. CONTEXT IS KING: 
       - Look at the [Context] provided in the user's message.
       - If the user asks "What next?", suggest the IMMEDIATE NEXT TOPIC after the one in the context.
       - EXAMPLES:
         * Context="Article 21" -> Suggest "Article 21A (Right to Education)" or "Article 22".
         * Context="Preamble" -> Suggest "Union & Territory (Art 1-4)".
         * Context="President" -> Suggest "Vice-President".
    3. TONE: Encouraging coach.
    4. CITATION: Always end with [Source: Constitution of India].
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

    except Exception as e:
        print(f"SERVER ERROR: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
        
