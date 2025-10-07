from langgraph.checkpoint.sqlite import SqliteSaver
import sqlite3
from pydantic import BaseModel


conn = sqlite3.connect(database='travel_memory.db', check_same_thread=False)
checkpointer = SqliteSaver(conn=conn)


def get_thread_by_id(thread_id):
    class Trip(BaseModel):
        destination: str
        budget: float
        dates: str
        preferences : str
        plan: str
        cost_breakdown:dict
        timestamp:str


    chats = []
    for chat in checkpointer.get_tuple({"configurable": {"thread_id": thread_id}}):
        
        if "channel_values" in chat:
            timestamp = chat['ts']
            trip_chat = Trip(
                destination=chat["channel_values"]["destination"],
                budget=chat["channel_values"]["budget"],
                dates=chat["channel_values"]["dates"],
                preferences=chat["channel_values"]["preferences"],
                plan=chat["channel_values"]["plan"],
                cost_breakdown=chat["channel_values"]["cost_breakdown"],
                timestamp=timestamp
            )
            chats.append(trip_chat.model_dump_json())
    
    return chats


print(get_thread_by_id("1234567890"))

