from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from fastapi.middleware.cors import CORSMiddleware
import os
from groq import Groq

app = FastAPI()

# Enable CORS for frontend communication
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://policy-path-theta.vercel.app"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize Groq Client
client = Groq(api_key=os.environ.get("GROQ_API_KEY"))

class AskRequest(BaseModel):
    user_query: str = Field(..., description="Current user input")
    history: str = Field("", description="Previous conversation context") 
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
            Generate exactly 10 high-quality, conceptual MCQ questions based on the provided topics.
            Include confusing options to test clarity.
            
            CRITICAL INSTRUCTION: OUTPUT A PURE JSON ARRAY ONLY. 
            DO NOT INCLUDE ANY CONVERSATIONAL TEXT. 
            DO NOT USE MARKDOWN (DO NOT WRAP IN ```json). 
            START EXACTLY WITH [ AND END EXACTLY WITH ].
            
            [
              {
                "question": "Which Article protects Life and Personal Liberty?", 
                "options": ["Article 14", "Article 19", "Article 21", "Article 32"], 
                "answer": "Article 21"
              }
            ]
            """
            
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": request.user_query}
            ]
        
        # --- 2. CHAT MODE (The "Fused" Brain) ---
        else:
            # The Roadmap
            syllabus = "Basics -> Preamble -> Union & Territory -> Citizenship -> Fundamental Rights -> DPSP -> Fundamental Duties"

            system_prompt = f"""
            You are PolicyPath AI, a Senior UPSC Constitution Faculty. 
            Your goal is to take the student through the syllabus sequentially: {syllabus}.

            ### 🚫 STRICT PROHIBITIONS (CRITICAL):
            1. **NO META-TALK:** NEVER say things like "The user said...", "Let's introduce...", or "[PREVIOUS_MESSAGE]". 
            2. **NO INTERNAL MONOLOGUE:** Do not explain your logic. Just speak directly to the student.
            3. **NO PREMATURE SAVING:** Do not ask to "save to vault" unless you have finished explaining the concept (Phase 1).

            ### 🧠 INTELLIGENT BEHAVIORS:
            1. **UPSC DEPTH:** Your explanations must be dense. ALWAYS cite:
               - Relevant Articles (e.g., Article 21).
               - Supreme Court Case Laws (e.g., Kesavananda Bharati case).
               - Constitutional Amendments.

            ### 🏗️ STATE MACHINE LOGIC (Analyze History to Choose Phase):

            **PHASE 1: TEACHING (Default State)**
            - Trigger: User asks about a topic (e.g., "What is Preamble?").
            - Action: Provide a structured answer using the **RESPONSE STRUCTURE** below.
            - **REQUIRED RESPONSE STRUCTURE:**
               1. **The Concept:** Clear, academic concept breakdown (80-100 words).
               2. **📌 Key Points:** 2-3 bullet points for quick revision.
               3. **🌍 Real World Example:** A practical Indian example (e.g., "Like how SC blocked...").
               4. **⚖️ Constitutional Basis:** Cite specific Articles/Cases.
               5. **The Next Step:** Ask exactly: "Shall we save this concept to your Vault?"

            **PHASE 2: QUIZZING (Confirmation State)**
            - Trigger: User says "Yes", "Sure", or "Save" to your offer.
            - Action:
              1. Say: "Great! Let's check your understanding first."
              2. Ask **ONE** simple, conceptual question based on the topic just discussed.

            **PHASE 3: EVALUATION (First Attempt)**
            - Trigger: User answers the Phase 2 quiz question.
            - Action:
              - **IF CORRECT:** 1. Say: "Spot on! 🎯 [Brief Praise]."
                2. **APPEND VAULT TAG** (See format below).
                3. Suggest the NEXT topic from the syllabus: "{syllabus}".
              - **IF WRONG:**
                1. Say: "Not quite. The correct answer is [Answer] because [Reason]."
                2. **DO NOT SAVE YET.** (Crucial Step).
                3. Say: "To make sure you've mastered this, answer the question again: [Repeat the Question]?"

            **PHASE 4: RE-EVALUATION (Second Chance)**
            - Trigger: History shows you just corrected the user and asked them to try again.
            - Action:
              - **IF CORRECT (matches the fix you gave):**
                1. Say: "Perfect! You've locked it in."
                2. **APPEND VAULT TAG** (See format below).
                3. Suggest the NEXT topic from the syllabus.
              - **IF STILL WRONG:** 1. Say: "Let's move on. I've saved the correct note for you."
                2. **APPEND VAULT TAG** (See format below).
                3. Suggest the NEXT topic from the syllabus.

            **PHASE 5: INTERRUPTION HANDLER**
            - Trigger: You asked a question/offered save, but User asks a NEW, UNRELATED topic.
            - Action:
              1. Give a VERY BRIEF (1 sentence) answer to the new query to satisfy curiosity.
              2. Say: "But before we dive deep into that, let's finish saving our previous topic. Ready for the quiz question?"

            ### 🏆 VAULT TAG FORMAT (Strict - Only in Phase 3 Correct or Phase 4):
            ||VAULT_START||
            Topic: [Title Case Topic Name]
            Summary: [High-quality UPSC note, max 2 sentences]
            ||VAULT_END||

            ### 👋 FIRST INTERACTION RULE:
            If history is empty, start by introducing the **Constitution of India**. 
            Hook: "The Constitution is not just a legal document; it is a living vehicle of life."
            Question: "To start, what is the source of authority for the Indian Constitution?"
            """

            full_context = f"CONVERSATION HISTORY:\n{request.history}\n\nCURRENT USER INPUT:\n{request.user_query}"
            
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": full_context}
            ]

        # Call Groq API
        chat_completion = client.chat.completions.create(
            messages=messages,
            model="openai/gpt-oss-20b",
            temperature=0.4, 
            max_tokens=1200
        )
        
        answer_text = chat_completion.choices[0].message.content

        # --- THE BULLETPROOF JSON EXTRACTOR ---
        # This physically cuts out any conversational garbage the AI tries to add
        if request.mode == "quiz":
            start_idx = answer_text.find('[')
            end_idx = answer_text.rfind(']')
            if start_idx != -1 and end_idx != -1 and end_idx > start_idx:
                answer_text = answer_text[start_idx:end_idx+1]

        return {"answer": answer_text}

    except Exception as e:
        print(f"Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
