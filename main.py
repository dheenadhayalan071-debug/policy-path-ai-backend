from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(
    title="PolicyPath AI Backend",
    description="FastAPI backend for frontend integration",
    version="0.1.0"
)

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # or ["http://localhost:3000"]
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# -------- Request Model --------
class AskRequest(BaseModel):
    user_query: str = Field(
        ...,
        example="What are the Fundamental Rights in India?",
        description="The question asked by the user"
    )

# -------- Response Model --------
class AskResponse(BaseModel):
    answer: str
    citation: str
    progress_boost: int

# -------- Endpoint --------
@app.post("/ask", response_model=AskResponse)
def ask(request: AskRequest):
    if not request.user_query.strip():
        raise HTTPException(status_code=400, detail="user_query cannot be empty")

    return {
        "answer": (
            "The Fundamental Rights are defined in Part III of the Constitution of India "
            "(Articles 12 to 35). They guarantee basic freedoms and equality to citizens."
        ),
        "citation": "Constitution of India, Part III (Articles 12–35)",
        "progress_boost": 5
    }
