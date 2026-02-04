from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(
    title="PolicyPath AI – Backend PoC",
    description="Proof of Concept API for frontend-backend integration",
    version="0.1.0"
)


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],                    # ← or ["http://localhost:3000", "http://127.0.0.1:3000"]
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class ChatRequest(BaseModel):
    user_query: str = Field(
        ...,
        example="What are the Fundamental Rights in India?",
        description="The question asked by the user"
    )

class ChatResponse(BaseModel):
    answer: str
    source: str
    status: str

@app.post("/chat", response_model=ChatResponse)
def chat(request: ChatRequest):
    if not request.user_query.strip():
        raise HTTPException(status_code=400, detail="user_query cannot be empty")

   
    return {
        "answer": (
            "The Fundamental Rights are defined in Part III of the Constitution of India "
            "(Articles 12 to 35). They guarantee civil liberties to all citizens and protect "
            "them against any arbitrary actions by the State. Key rights include equality, "
            "freedom of speech & expression, protection against exploitation, freedom of "
            "religion, cultural & educational rights, and right to constitutional remedies."
        ),
        "source": "Constitution of India, Part III (Articles 12–35)",
        "status": "success"
    }