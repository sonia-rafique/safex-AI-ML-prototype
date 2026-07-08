import uuid
import time
import streamlit as st
import base64
from agent import get_agent_response
import sys
import asyncio
import os
import base64

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

st.set_page_config(
    page_title="SAFEX Solutions | AI FAQ Engine",
    layout="wide",
    initial_sidebar_state="expanded",
)

SUGGESTED_QUESTIONS = [
    "What services does SAFEX Solutions offer?",
    "Where is SAFEX Solutions located?",
    "How can I get a quote for a project?",
    "Does SAFEX Solutions offer cybersecurity services?",
]

def get_image_base64(path: str) -> str:
    try:
        with open(path, "rb") as image_file:
            return base64.b64encode(image_file.read()).decode()
    except Exception:
        return ""

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
LOGO_PATH = os.path.join(BASE_DIR, "safex-logo.png")

LOGO_BASE64 = get_image_base64(LOGO_PATH)

USER_AVATAR = "data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHdpZHRoPSI0MCIgaGVpZ2h0PSI0MCIgdmlld0JveD0iMCAwIDQwIDQwIj4KPGNpcmNsZSBjeD0iMjAiIGN5PSIyMCIgcj0iMTkiIGZpbGw9IiNmZmZmZmYiIHN0cm9rZT0iIzAwNzdiNiIgc3Ryb2tlLXdpZHRoPSIyIi8+CjxwYXRoIGZpbGw9IiMwMDc3YjYiIGQ9Ik0yMCAyMGMzLjMxIDAgNi0yLjY5IDYtNnMtMi42OS02LTYtNi02IDIuNjktNiA2IDIuNjkgNiA2IDZ6bTAgM2MtNCAwLTEyIDIuMDEtMTIgNnYzaDI0di0zYzAtMy45OS04LTYtMTItNnoiLz4KPC9zdmc+"
BOT_AVATAR = "data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHdpZHRoPSI0MCIgaGVpZ2h0PSI0MCIgdmlld0JveD0iMCAwIDQwIDQwIj4KPGNpcmNsZSBjeD0iMjAiIGN5PSIyMCIgcj0iMTkiIGZpbGw9IiNmZmZmZmYiIHN0cm9rZT0iIzAwYjRkOCIgc3Ryb2tlLXdpZHRoPSIyIi8+CjxwYXRoIGZpbGw9IiMwMGI0ZDgiIGQ9Ik0yOCAxNnYtMmMwLTEuNjYtMS4zNC0zLTMtM2gtNGMwLTEuNjYtMS4zNC0zLTMtM3MtMyAxLjM0LTMgM2gtNGMtMS42NiAwLTMgMS4zNC0zIDN2MmMtMS42NiAwLTMgMS4zNC0zIDNzMS4zNCAzIDMgM3Y1YzAgMS42NiAxLjM0IDMgMyAzaDE0YzEuNjYgMCAzLTEuMzQgMy0zdi01YzEuNjYgMCAzLTEuMzQgMy0zcy0xLjM0LTMtMy0zek0xNS41IDIwLjVjMC0xLjEuOS0yIDItMnMyIC45IDIgMi0uOSAyLTIgMi0yLS45LTItMnptMTAgNi41Yy0xLjIgMS0zLjIgMS44LTUuNSAxLjhzLTQuMy0uOC01LjUtMS44Yy0uNS0uNC0uMi0xLjIuNS0xLjJoMTBjLjcgMCAxIC44LjUgMS4yem0tMS00LjVjLTEuMSAwLTItLjktMi0ycy45LTIgMi0yIDIgLjkgMiAyLS45IDItMiAyeiIvPgo8L3N2Zz4="

def get_avatar(role: str) -> str:
    return USER_AVATAR if role == "user" else BOT_AVATAR

CUSTOM_CSS = f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&family=Inter:wght@300;400;500;600&display=swap');

:root {{
    --safex-cyan: #00b4d8;
    --safex-navy: #0077b6;
    --safex-dark-blue: #0b2545;
    --text-dark: #0f172a !important; 
    --text-muted: #64748b !important;
    --border-light: #e2e8f0;
}}

.stApp {{
    background: #f8fafc !important; 
    color: var(--text-dark) !important;
    font-family: 'Inter', sans-serif !important;
}}

div[data-testid="stMainSpaceBlock"] {{
    padding-top: 10px !important;
}}

header[data-testid="stHeader"], div[data-testid="stDecoration"] {{
    background-color: transparent !important;
    background: transparent !important;
    border-bottom: 0px none !important;
    height: 0px !important;
}}

section[data-testid="stSidebar"] {{
    background-color: var(--safex-dark-blue) !important;
    border-right: none !important;
}}

section[data-testid="stSidebar"] h2,
section[data-testid="stSidebar"] h4,
section[data-testid="stSidebar"] p,
section[data-testid="stSidebar"] span,
section[data-testid="stSidebar"] div,
section[data-testid="stSidebar"] label,
section[data-testid="stSidebar"] caption,
section[data-testid="stSidebar"] .stMarkdown p {{
    color: #ffffff !important;
}}

section[data-testid="stSidebar"] hr {{
    border-color: rgba(255, 255, 255, 0.15) !important;
}}

.brand-container {{
    display: flex;
    flex-direction: row;
    align-items: center;
    justify-content: center;
    text-align: left;
    padding: 0px 0px 15px 0px;
    margin-bottom: 20px;
    gap: 24px;
    width: 100%;
    border-bottom: 1px dashed var(--border-light);
}}

.logo-animation {{
    max-height: 160px; 
    transition: transform 0.4s cubic-bezier(0.16, 1, 0.3, 1);
}}

.brand-text-block {{
    display: flex;
    flex-direction: column;
    justify-content: center;
}}

.brand-title-text {{
    font-family: 'Plus Jakarta Sans', sans-serif !important;
    font-size: 32px !important; 
    font-weight: 800 !important;
    letter-spacing: -0.03em !important;
    margin: 0;
    background: linear-gradient(135deg, #0056b3 0%, #00b4d8 50%, #0077b6 100%);
    background-size: 200% auto;
    -webkit-background-clip: text !important;
    -webkit-text-fill-color: transparent !important;
    animation: textShine 4s ease infinite;
}}

@keyframes textShine {{
    0% {{ background-position: 0% 50%; }}
    50% {{ background-position: 100% 50%; }}
    100% {{ background-position: 0% 50%; }}
}}

.brand-subtitle-text {{
    margin: 6px 0 0 0;
    color: var(--text-muted) !important;
    font-size: 15px;
    font-weight: 500;
    line-height: 1.4;
    font-family: 'Plus Jakarta Sans', sans-serif !important;
    letter-spacing: -0.01em;
    max-width: 650px;
}}

div.stButton > button {{
    background: rgba(255, 255, 255, 0.08) !important;
    color: #ffffff !important;
    border: 1px solid rgba(255, 255, 255, 0.15) !important;
    border-radius: 20px !important;
    padding: 12px 18px !important;
    text-align: left !important;
    font-size: 13.5px !important;
    font-weight: 500 !important;
    transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1) !important;
}}

div.stButton > button:hover {{
    background: #0077b6 !important;
    border-color: #00b4d8 !important;
    color: #ffffff !important;
    transform: translateY(-2px) !important;
    box-shadow: 0 4px 12px rgba(0, 180, 216, 0.3) !important;
}}

div[data-testid="stSidebar"] div.stButton > button[key^="reset_"] {{
    border-radius: 12px !important;
    text-align: center !important;
    background: transparent !important;
    border: 1px solid rgba(255, 255, 255, 0.3) !important;
}}

div[data-testid="stSidebar"] div.stButton > button[key^="reset_"]:hover {{
    background: #ef4444 !important;
    border-color: #f87171 !important;
}}

/* ===== AVATAR STYLING ===== */
/* We now pass real image avatars (blue SVGs) directly to st.chat_message(avatar=...),
   so Streamlit renders an <img> instead of its own colored-square default emoji avatar.
   This just makes sure that image renders as a clean, consistently-sized circle. */
[data-testid="stChatMessageAvatarContainer"] {{
    background: transparent !important;
    border-radius: 50% !important;
    width: 40px !important;
    height: 40px !important;
    overflow: hidden !important;
}}

[data-testid="stChatMessageAvatarContainer"] img {{
    width: 100% !important;
    height: 100% !important;
    border-radius: 50% !important;
    object-fit: cover !important;
}}

div[data-testid="stChatMessage"] {{
    padding: 6px 0px !important; 
    margin-bottom: 2px !important;
    border: none !important;
    background-color: transparent !important;
    background: transparent !important;
    box-shadow: none !important;
}}

div[data-testid="stChatMessage"]:nth-child(even),
div[data-testid="stChatMessage"]:nth-child(odd) {{
    background-color: transparent !important;
    background: transparent !important;
    border: none !important;
}}

div[data-testid="stChatMessage"] p, 
div[data-testid="stChatMessage"] span, 
div[data-testid="stChatMessage"] li,
div[data-testid="stChatMessage"] div {{
    color: var(--text-dark) !important;
    line-height: 1.5;
}}

div[data-testid="stChatInput"] {{
    border: 1px solid #cbd5e1 !important;
    border-radius: 12px !important;
    box-shadow: none !important;
}}

div[data-testid="stChatInput"]:focus-within {{
    border-color: #0077b6 !important;
    box-shadow: 0 0 0 2px rgba(0,119,182,.2) !important;
    outline: none !important;
}}

div[data-testid="stChatInput"] textarea,
div[data-testid="stChatInput"] textarea:focus {{
    outline: none !important;
    box-shadow: none !important;
}}

div[data-testid="stChatInputContainer"] button {{
   background: #0077b6 !important;
    border: none !important;
    color: white !important;
}}

div[data-testid="stChatInputContainer"] button:hover {{
    background: #0056b3 !important;
}}

div[data-testid="stChatInputContainer"] button:focus,
div[data-testid="stChatInputContainer"] button:focus-visible {{
    outline: none !important;
    box-shadow: 0 0 0 2px rgba(0,119,182,.3) !important;
}}

div[data-testid="stChatInputContainer"] button svg {{
    fill: white !important;
    color: white !important;
}}

.safex-link-container {{
    text-align: center;
    font-size: 12px;
    padding-top: 10px;
    margin-top: 15px;
}}
</style>
"""
st.markdown(CUSTOM_CSS, unsafe_allow_html=True)

def init_session_state() -> None:
    if "messages" not in st.session_state:
        st.session_state.messages = []
    if "thread_id" not in st.session_state:
        st.session_state.thread_id = str(uuid.uuid4())
    if "pending_question" not in st.session_state:
        st.session_state.pending_question = None

def render_header() -> None:
    if LOGO_BASE64:
        logo_html = f'<img src="data:image/png;base64,{LOGO_BASE64}" class="logo-animation" alt="SAFEX Logo"/>'
    else:
        logo_html = '<div style="font-size:24px; font-weight:700; color:#0077b6;">[SAFEX]</div>'

    st.markdown(
        f"""
        <div class="brand-container">
            {logo_html}
            <div class="brand-text-block">
                <div class="brand-title-text">WELCOME TO SAFEX AI ASSISTANT</div>
                <div class="brand-subtitle-text">
                    Get instant, accurate answers about our services, solutions, technologies, and company information using our AI-powered knowledge base.
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

def render_sidebar() -> None:
    with st.sidebar:
        st.markdown("<div style='padding-top: 25px;'></div>", unsafe_allow_html=True)
        st.markdown("<h2 style='margin-top:0; font-size:22px; font-family:\"Plus Jakarta Sans\"; font-weight:700;'>SAFEX Portal Engine</h2>", unsafe_allow_html=True)
        st.caption("SAFEX Cognitive Core Interface v2.5")
        st.markdown("---")

        st.markdown("#### Popular FAQ Prompts")
        for q in SUGGESTED_QUESTIONS:
            if st.button(q, use_container_width=True, key=f"suggested_{q}"):
                st.session_state.pending_question = q

        st.markdown("---")
        if st.button("Reset Chat Engine State", use_container_width=True, key="reset_engine"):
            st.session_state.messages = []
            st.session_state.thread_id = str(uuid.uuid4())
            st.rerun()

        st.markdown("---")
        st.caption("Secure Portal: [safexsolutions.com](https://safexsolutions.com)")

def render_message(msg: dict, index: int) -> None:
    role = msg["role"]
    with st.chat_message(role, avatar=get_avatar(role)):
        st.markdown(msg["content"])

def handle_new_query(query: str) -> None:
    st.session_state.messages.append({"role": "user", "content": query})
    with st.chat_message("user", avatar=get_avatar("user")):
        st.markdown(query)

    with st.chat_message("assistant", avatar=get_avatar("assistant")):
        placeholder = st.empty()
        
        with st.spinner("Processing..."):
            try:
                result = get_agent_response(query, thread_id=st.session_state.thread_id)
                answer = result["answer"]
            except Exception as exc:
                answer = "System Exception: Unable to safely complete data computation node."
                st.error(f"Trace stack failure: {exc}")

        typed = ""
        for word in answer.split(" "):
            typed += word + " "
            placeholder.markdown(typed + "|")
            time.sleep(0.010)
        placeholder.markdown(typed)

    st.session_state.messages.append({
        "role": "assistant",
        "content": answer
    })

def render_footer_links() -> None:
    st.markdown(
        '<div class="safex-link-container">'
        '<a href="https://safexsolutions.com/contact" style="color:#0077b6; font-weight:600; text-decoration:none;">Corporate Request Node</a>'
        '</div>',
        unsafe_allow_html=True,
    )

def main() -> None:
    init_session_state()
    render_header()
    render_sidebar()
    
    for i, msg in enumerate(st.session_state.messages):
        render_message(msg, i)

    if st.session_state.pending_question:
        q = st.session_state.pending_question
        st.session_state.pending_question = None
        handle_new_query(q)

    user_input = st.chat_input("💬Ask a question about SAFEX SOLUTIONS...")
    if user_input:
        handle_new_query(user_input)

    render_footer_links()

if __name__ == "__main__":
    main()