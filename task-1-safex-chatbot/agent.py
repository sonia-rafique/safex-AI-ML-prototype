import os
from typing import Annotated, Sequence, TypedDict

from dotenv import load_dotenv
from langchain_core.messages import BaseMessage, SystemMessage, HumanMessage, AIMessage, ToolMessage
from langchain_core.tools import tool
from langchain_chroma import Chroma
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from langchain_groq import ChatGroq  # <-- Integrated Groq here
from langchain_community.tools import DuckDuckGoSearchRun
from langchain_core.documents import Document

from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode
from langgraph.checkpoint.memory import MemorySaver

load_dotenv()

# --------------------------------------------------------------------------
# Config
# --------------------------------------------------------------------------
import streamlit as st
import os

GEMINI_API_KEY = st.secrets.get("GEMINI_API_KEY") or os.getenv("GEMINI_API_KEY")
GROQ_API_KEY = st.secrets.get("GROQ_API_KEY") or os.getenv("GROQ_API_KEY")

if not GEMINI_API_KEY:
    raise ValueError("GEMINI_API_KEY missing in Secrets/Environment")
if not GROQ_API_KEY:
    raise ValueError("GROQ_API_KEY missing in Secrets/Environment")

EMBEDDING_MODEL = "models/gemini-embedding-001"
CHAT_MODEL = "llama-3.1-8b-instant"  # <-- High performance tool-calling model on Groq
PERSIST_DIR = "./safex_db"
COLLECTION_NAME = "safex_faq"

SYSTEM_PROMPT = (
    "You are an elite, autonomous enterprise AI Assistant representing SafeX Solutions "
    "(https://safexsolutions.com), a global technology company offering cybersecurity, "
    "web development, cloud infrastructure, and digital marketing services.\n\n"
    "Your goals:\n"
    "1. Answer questions about SafeX Solutions accurately using the "
    "'query_safex_knowledge_base' tool whenever the question relates to the company, "
    "its services, pricing, process, location, or team.\n"
    "2. Use 'web_search_fallback' only for general technical/industry definitions that "
    "are NOT specific to SafeX (e.g. 'what is a firewall').\n"
    "3. If the knowledge base returns nothing useful, you may try the other tool once "
    "before answering.\n"
    "4. If neither tool has the answer, say so honestly instead of guessing. Never "
    "invent facts about SafeX Solutions (pricing, staff names, certifications).\n"
    "5. Keep answers concise, professional, and helpful — this is a customer-facing "
    "FAQ assistant, not a chat companion."
)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PERSIST_DIR = os.path.join(BASE_DIR, "safex_db")

_embeddings = GoogleGenerativeAIEmbeddings(
    model=EMBEDDING_MODEL,
    google_api_key=GEMINI_API_KEY,
)
_vector_db = Chroma(
    persist_directory=PERSIST_DIR,
    embedding_function=_embeddings,
    collection_name=COLLECTION_NAME,
)

_retriever = _vector_db.as_retriever(search_kwargs={"k": 4})


@tool
def query_safex_knowledge_base(query: str) -> str:
    """Queries the local vector store containing information scraped directly
    from safexsolutions.com. Use this for ANY question about SafeX Solutions
    itself: services, pricing, process, location, team, or policies."""
    docs = _retriever.invoke(query)
    if not docs:
        return "NO_RESULTS: nothing relevant found in the SafeX knowledge base."

    formatted = []
    for doc in docs:
        source = doc.metadata.get("source", "unknown")
        formatted.append(f"[Source: {source}]\n{doc.page_content}")
    return "\n\n---\n\n".join(formatted)


@tool
def web_search_fallback(query: str) -> str:
    """Performs a live internet search using DuckDuckGo. Use ONLY for generic
    technical/industry definitions not specific to SafeX Solutions."""
    try:
        from langchain_community.utilities import DuckDuckGoSearchAPIWrapper
        
        wrapper = DuckDuckGoSearchAPIWrapper(max_results=3)
        results = wrapper.run(query)
        
        if not results:
            return "No internet search results found for this technical query."
        return results
        
    except Exception as e:
        return f"Fallback Search Notice: Could not process live search due to environmental setup ({str(e)}). Please review system packages."


TOOLS = [query_safex_knowledge_base, web_search_fallback]
_tool_node = ToolNode(TOOLS)

# Groq Model initialization with tool binding
_model = ChatGroq(
    model=CHAT_MODEL,
    groq_api_key=GROQ_API_KEY,
    temperature=0.2,
).bind_tools(TOOLS)


# --------------------------------------------------------------------------
# Graph state + nodes
# --------------------------------------------------------------------------
class AgentState(TypedDict):
    messages: Annotated[Sequence[BaseMessage], add_messages]


def supervisor_node(state: AgentState) -> dict:
    messages = [SystemMessage(content=SYSTEM_PROMPT)] + list(state["messages"])
    response = _model.invoke(messages)
    return {"messages": [response]}


def should_continue(state: AgentState) -> str:
    last_message = state["messages"][-1]
    if getattr(last_message, "tool_calls", None):
        return "execute_tools"
    return END


# --------------------------------------------------------------------------
# Build the graph
# --------------------------------------------------------------------------
_workflow = StateGraph(AgentState)
_workflow.add_node("supervisor", supervisor_node)
_workflow.add_node("action", _tool_node)

_workflow.set_entry_point("supervisor")
_workflow.add_conditional_edges(
    "supervisor",
    should_continue,
    {
        "execute_tools": "action",
         END: END,
    },
)
_workflow.add_edge("action", "supervisor")

_checkpointer = MemorySaver()
agent_app = _workflow.compile(checkpointer=_checkpointer)


# --------------------------------------------------------------------------
# Public API used by the Streamlit frontend with Semantic Cache
# --------------------------------------------------------------------------
def get_agent_response(user_query: str, thread_id: str = "default_session") -> dict:
    # 1. Connect to Cache
    try:
        cache_vector_db = Chroma(
            persist_directory=PERSIST_DIR,
            embedding_function=_embeddings,
            collection_name="safex_faq_cache",
        )
    except Exception:
        cache_vector_db = None

    # 2. Check Cache
    if cache_vector_db:
        try:
            cached_results = cache_vector_db.similarity_search_with_score(user_query, k=1)
            if cached_results:
                cached_doc, score = cached_results[0]
                if score < 0.35:
                    import json
                    cached_data = json.loads(cached_doc.page_content)
                    return {
                        "answer": cached_data["answer"] + "\n\n*(⚡ Served instantly from local neural cache)*",
                        "sources": cached_data["sources"],
                        "tools_used": cached_data["tools_used"],
                    }
        except Exception:
            pass

    # 3. Cache Miss - Execute Groq Engine Pipeline
    config = {"configurable": {"thread_id": thread_id}}
    inputs = {"messages": [HumanMessage(content=user_query)]}

    final_state = agent_app.invoke(inputs, config=config)
    all_messages = final_state["messages"]

    raw_content = all_messages[-1].content
    
    if isinstance(raw_content, list):
        text_fragments = []
        for block in raw_content:
            if isinstance(block, str):
                text_fragments.append(block)
            elif isinstance(block, dict) and "text" in block:
                text_fragments.append(block["text"])
        answer = "".join(text_fragments)
    else:
        answer = str(raw_content)

    sources: list[str] = []
    tools_used: list[str] = []

    for msg in all_messages:
        if isinstance(msg, ToolMessage):
            tools_used.append(msg.name)
            if msg.name == "query_safex_knowledge_base":
                for line in str(msg.content).splitlines():
                    if line.startswith("[Source:"):
                        url = line.replace("[Source:", "").replace("]", "").strip()
                        if url not in sources:
                            sources.append(url)

    output_payload = {
        "answer": answer,
        "sources": sources,
        "tools_used": tools_used,
    }

    # 4. Write to cache for next identical hits
    if cache_vector_db and "Error" not in answer:
        import json
        try:
            cache_vector_db.add_documents([
                Document(
                    page_content=json.dumps(output_payload),
                    metadata={"user_query": user_query}
                )
            ])
        except Exception:
            pass

    return output_payload