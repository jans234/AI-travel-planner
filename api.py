from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware
from typing import List
from app import chatbot, retrieve_all_threads, delete_thread_from_db, get_thread_by_id
from fastapi.responses import FileResponse
import os

# ✅ Initialize FastAPI app
app = FastAPI(title="Travel Chatbot API", version="1.0")

# Path to your index.html
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
INDEX_PATH = os.path.join(BASE_DIR, "interface", "index.html")

# ✅ Enable CORS (allow frontend to call API)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],        # 👈 For local dev, allow all origins (frontend can connect)
    allow_credentials=True,
    allow_methods=["*"],        # 👈 Allow GET, POST, DELETE, OPTIONS
    allow_headers=["*"],        # 👈 Allow all headers
)

# ✅ Pydantic models
class ChatRequest(BaseModel):
    thread_id: str
    destination: str
    budget: float
    dates: str
    preferences: str   # typo fixed (kept consistent)


class ChatResponse(BaseModel):
    thread_id: str
    plan: str
    cost_breakdown: dict
    search_result: str


@app.post("/chat", response_model=ChatResponse)
def chat_with_bot(request: ChatRequest):
    """Send user input to the travel chatbot and get full itinerary at once."""

    initial_state = {
        "destination": request.destination,
        "budget": request.budget,
        "dates": request.dates,
        "preferences": request.preferences,
        "search_result": "",
        "plan": "",
        "cost_breakdown": {},
        "history": []   # we'll fill this later
    }

    try:
        final_state = chatbot.invoke(
            initial_state,
            config={"configurable": {"thread_id": request.thread_id}}
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    # ✅ Append conversation to history (user + bot)
    conversation_turn = [
        {"role": "user", "content": f"Plan a trip to {request.destination} with budget {request.budget}, dates {request.dates}, preferences {request.preferences}"},
        {"role": "assistant", "content": final_state["plan"]}
    ]

    # If previous history exists, keep it
    final_state["history"].extend(conversation_turn)

    return ChatResponse(
        thread_id=request.thread_id,
        plan=final_state["plan"],
        cost_breakdown=final_state["cost_breakdown"],
        search_result=final_state["search_result"],
    )

# ✅ Thread management
@app.get("/threads", response_model=List)
def list_threads():
    """Get all saved conversation thread IDs."""
    return retrieve_all_threads()


@app.get("/thread/chats")
def fetch_thread_chats(thread_id: str):
    """Fetch chats of a specific thread (newest → oldest)."""
    chats = get_thread_by_id(thread_id)
    if not chats:
        raise HTTPException(status_code=404, detail="Thread not found or no chats available")
    return chats


@app.delete("/threads/{thread_id}")
def delete_thread(thread_id: str):
    """Delete a conversation thread from DB."""
    try:
        delete_thread_from_db(thread_id)
        return {"message": f"Thread {thread_id} deleted successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/")
async def serve_index():
    return FileResponse(INDEX_PATH)
