from langgraph.graph import StateGraph, START, END
from langchain_core.messages import messages_from_dict
from typing import TypedDict, Annotated
from datetime import datetime
from langchain_core.messages import HumanMessage
from langchain_groq import ChatGroq
from langchain.prompts import ChatPromptTemplate
from pydantic import BaseModel
from langgraph.checkpoint.sqlite import SqliteSaver
from tavily import TavilyClient
from dotenv import load_dotenv
import operator
import os
import sqlite3

load_dotenv()

# ✅ Model
groq_model = os.environ["GROQ_MODEL"]
model = ChatGroq(model=groq_model)

# ✅ Tools
tavily_client = TavilyClient(api_key=os.getenv("TAVILY_API_KEY"))

# ✅ TravelState definition
class TravelState(TypedDict):
    destination: str
    budget: float
    dates: str
    preferences: str
    search_result: str
    plan: str
    cost_breakdown: dict
    history: Annotated[list[str], operator.add]

# ✅ Nodes
def web_search(state: TravelState) -> TravelState:
    query = (
        f"Travel option for {state['destination']} within budget {state['budget']} "
        f"for dates {state['dates']} with preferences {state['preferences']}"
    )
    try:
        result = tavily_client.search(query)
        state['search_result'] = str(result)
    except Exception as e:
        state['search_result'] = f"⚠️ API Error: {str(e)}"
    return state


def budget_allocator(state: TravelState) -> TravelState:
    total_budget = state["budget"]
    state['cost_breakdown'] = {
        "Travel": total_budget * 0.4,
        "Accommodation": total_budget * 0.3,
        "Attractions": total_budget * 0.2,
        "Food and activities": total_budget * 0.3,
    }
    return state


def budget_check(state: TravelState) -> TravelState:
    if not isinstance(state["budget"], (int, float)) or state["budget"] <= 0:
        raise ValueError("Budget must be a positive number.")

    total = state["budget"]
    if total < 500:
        state["plan"] = (
            f"⚠️ Your budget of ${total} seems too low for {state['destination']}.\n\n"
            f"👉 Suggestions:\n"
            f"- Consider a closer/cheaper destination.\n"
            f"- Shorten your trip (dates: {state['dates']}).\n"
            f"- Stay in hostels or budget stays.\n"
            f"- Look for off-season travel deals."
        )
        state["search_result"] = "Skipped due to low budget."
        state["skip_itinerary"] = True
    else:
        state["skip_itinerary"] = False
    return state


def itinerary_generator(state: TravelState) -> TravelState:
    prompt = ChatPromptTemplate.from_template("""
    You are a travel assistant. Based on the details, create a detailed day-by-day itinerary.
    Include travel, accommodation, food, and activities only.
    Destination: {destination}
    Dates: {dates}
    Preferences: {preferences}
    Web Search Results: {search_result}
    Budget Breakdown: {cost_breakdown}
    """)
    response = model.invoke(prompt.format_messages(**state))
    state["plan"] = response.content
    return state

# Building workflow
# Creates a SQLite DB file "travel_memory.db" to store chat state
conn = sqlite3.connect(database='travel_memory.db', check_same_thread=False)
checkpointer = SqliteSaver(conn=conn)

# ✅ Build Graph
graph = StateGraph(TravelState)
graph.add_node("search", web_search)
graph.add_node("budget", budget_allocator)
graph.add_node("check_budget", budget_check)
graph.add_node("generate_itinerary", itinerary_generator)

graph.add_edge(START, "search")
graph.add_edge("search", "budget")
graph.add_edge("budget", "check_budget")
graph.add_edge("check_budget", "generate_itinerary")
graph.add_edge("generate_itinerary", END)

chatbot = graph.compile(checkpointer=checkpointer)


def get_thread_by_id(thread_id):
    class Trip(BaseModel):
        thread_id:str
        destination: str
        budget: float
        dates: str
        preferences : str
        plan: str
        cost_breakdown: dict
        timestamp: str


    chats = []
    for chat in checkpointer.get_tuple({"configurable": {"thread_id": thread_id}}):
        if "channel_values" in chat:
            timestamp = chat["ts"]
            trip_chat = Trip(
                thread_id=thread_id,
                destination=chat["channel_values"]["destination"],
                budget=chat["channel_values"]["budget"],
                dates=chat["channel_values"]["dates"],
                preferences=chat["channel_values"]["preferences"],
                plan=chat["channel_values"]["plan"],
                cost_breakdown=chat["channel_values"]["cost_breakdown"],
                timestamp=timestamp

            )
            chats.append(trip_chat.model_dump())
    
    return chats



def retrieve_all_threads():
    all_threads = set()
    threads_list_with_names = []

    for checkpoint in checkpointer.list(None):
        all_threads.add(checkpoint.config['configurable']['thread_id'])

    thread_list = list(all_threads)

    for thread in thread_list:
        data = get_thread_by_id(thread)
        thread_name = f"{data[0]['destination']} from {data[0]['dates']}"

        ts_str = data[0]["timestamp"]  # e.g. "2025-10-01T10:16:46.304782+00:00"
        ts_obj = datetime.fromisoformat(ts_str)  # ✅ works for ISO format with timezone

        threads_list_with_names.append({
            "thread_id": thread,
            "thread_name": thread_name,
            "timestamp": ts_str,
            "ts_obj":ts_obj
        })

    # ✅ Sort newest first
    threads_list_with_names.sort(key=lambda x: x["ts_obj"], reverse=True)

    # (Optional) remove helper key before returning
    for t in threads_list_with_names:
        t.pop("ts_obj")

    return threads_list_with_names


def delete_thread_from_db(thread_id: str):
    cursor = conn.cursor()
    cursor.execute(
        "DELETE FROM checkpoints WHERE thread_id = ?",
        (str(thread_id),)
    )
    conn.commit()





# initial_state = {
#     "destination": "Naran",
#     "budget": 60000,
#     "dates": "10-15 October",
#     "preferences": "Culture, food, budget-friendly",  # match TypedDict spelling
#     "search_result": "",   # match TypedDict key
#     "plan": "",
#     "cost_breakdown": {},
#     "history": []
# }

# final_state = chatbot.invoke(
#     initial_state,
#     config={"configurable": {"thread_id": "trip-1"}}  # ✅ Required for MemorySaver
# )
# print(final_state)