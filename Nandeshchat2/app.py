import sys
import os
import asyncio
import nest_asyncio
import streamlit as st
import pandas as pd
from PyPDF2 import PdfReader
from docx import Document
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_community.vectorstores import Chroma
from langchain_groq import ChatGroq

# 1. SQLITE3 PATCH (MUST BE FIRST)
try:
    __import__('pysqlite3')
    sys.modules['sqlite3'] = sys.modules.pop('pysqlite3')
except ImportError:
    raise RuntimeError("Install pysqlite3-binary: pip install pysqlite3-binary")

# 2. CONFIG
GROQ_API_KEY = "gsk_XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX"
EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2"

# PROMPTS

DEFAULT_SYSTEM_PROMPT = """
## Friendly AI Assistant
- If **no document** is uploaded, rely on **Nandesh’s** info below.
- If a **document** is uploaded, **ignore** Nandesh’s info and use only the user’s doc content.
- For **short queries**: respond briefly (≤6 words) + fun emojis.
- For **detailed queries**: provide structured, warm, and thorough explanations.
- **Never** reveal you are not human.
- Maintain a friendly, professional tone.

## Nandesh’s Info (Used Only If No Doc Is Provided)
**Name**: Nandesh Kalashetti  
**Role**: Full-Stack Web Developer  
**Email**: nandeshkalshetti1@gmail.com  
**Phone**: 9420732657  
**Location**: Samarth Nagar, Akkalkot  
**Skills**: React.js, TypeScript, PHP, Java, MERN stack, etc.  
**Achievements**: 4/5 AICTE rating, improved org efficiency by 30%, etc.

(End of Nandesh’s Info)
"""

UPLOADED_DOC_SYSTEM_PROMPT = """
## Document-based Chat
- Use **only** the uploaded document’s content. 
- If the doc lacks info, say: "I don't have enough information from the document to answer that."
- **Short queries** → short answers with emojis.
- **Detailed queries** → structured, thorough answers from doc.
- **Never** reveal you are not human.
- Maintain a friendly, professional tone.
"""

# ASYNC
nest_asyncio.apply()

# CORE FUNCTIONS

def create_inmemory_vector_store():
    """
    Returns a new, purely in-memory Chroma vector store.
    No persist_directory => ephemeral (lost on reload).
    """
    embeddings = HuggingFaceEmbeddings(model_name=EMBEDDING_MODEL)
    return Chroma(
        collection_name="temp_collection",
        embedding_function=embeddings,
        # No persist_directory => ephemeral storage
    )

def process_document(file):
    """Reads a file (PDF, CSV, TXT, DOCX, MD) and returns its text."""
    ext = os.path.splitext(file.name)[1].lower()
    try:
        if ext == ".pdf":
            pdf = PdfReader(file)
            return "\n".join(page.extract_text() or "" for page in pdf.pages)
        elif ext == ".csv":
            df = pd.read_csv(file)
            return df.to_csv(index=False)
        elif ext in [".txt", ".md"]:
            return file.getvalue().decode("utf-8")
        elif ext == ".docx":
            doc = Document(file)
            paragraphs = [para.text for para in doc.paragraphs]
            return "\n".join(paragraphs)
        else:
            st.error("Unsupported file format.")
            return ""
    except Exception as e:
        st.error(f"Error processing document: {str(e)}")
        return ""

def chunk_text(text):
    splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)
    return splitter.split_text(text)

def main():
    st.set_page_config(page_title="AI Resume Assistant", layout="wide")

    # --- Advanced CSS / UI ---
    st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Poppins:wght@400;600&display=swap');
    html, body, [class*="css"] {
        font-family: 'Poppins', sans-serif;
    }
    body {
        background: radial-gradient(circle at top left, #1d2b64, #f8cdda);
        margin: 0; padding: 0;
    }
    header, footer {visibility: hidden;}

    .chat-container {
        max-width: 900px;
        margin: 40px auto 60px auto;
        background: rgba(255,255,255,0.15);
        backdrop-filter: blur(8px);
        border-radius: 16px;
        padding: 25px;
        box-shadow: 0 8px 32px rgba(0,0,0,0.2);
        animation: fadeIn 0.6s ease;
    }
    @keyframes fadeIn {
        from {opacity: 0; transform: translateY(20px);}
        to {opacity: 1; transform: translateY(0);}
    }
    .chat-title {
        text-align: center;
        color: #fff;
        margin-bottom: 5px;
        font-size: 2.4rem;
        font-weight: 600;
    }
    .chat-subtitle {
        text-align: center;
        color: #ffe6a7;
        margin-top: 0;
        margin-bottom: 20px;
        font-size: 1.1rem;
    }
    .element-container {
        animation: fadeUp 0.4s ease;
        margin-bottom: 20px !important;
    }
    @keyframes fadeUp {
        from {opacity: 0; transform: translateY(10px);}
        to {opacity: 1; transform: translateY(0);}
    }
    [data-testid="stSidebar"] {
        background: #1c1f24 !important;
        color: #fff !important;
    }
    [data-testid="stSidebar"] h2, [data-testid="stSidebar"] h3, [data-testid="stSidebar"] h4 {
        color: #ffd56b !important;
    }
    [data-testid="stSidebar"] p, [data-testid="stSidebar"] label {
        color: #fff !important;
    }
    [data-testid="stSidebar"] .stButton>button {
        background: #ffd56b !important;
        color: #000 !important;
        font-weight: 600;
        border: none;
        border-radius: 6px;
        transition: background 0.3s;
    }
    [data-testid="stSidebar"] .stButton>button:hover {
        background: #fbd96a !important;
    }
    .stFileUploader label div {
        background: #ffe6a7 !important;
        color: #000 !important;
        font-weight: 600;
        border-radius: 8px;
        cursor: pointer;
        padding: 8px 0;
        text-align: center;
        transition: background 0.3s;
    }
    .stFileUploader label div:hover {
        background: #ffd56b !important;
    }
    .stChatInput {
        position: sticky;
        bottom: 0;
        background: rgba(28,31,36,0.85) !important;
        backdrop-filter: blur(6px);
        padding: 10px;
        margin-top: 20px;
        border-radius: 12px;
    }
    .stChatInput>div>div>input {
        color: #000 !important;
        font-weight: 500;
        border-radius: 8px;
        border: none;
    }
    .stChatInput>div>div>input:focus {
        outline: 2px solid #ffd56b !important;
    }
    </style>
    """, unsafe_allow_html=True)

    # -------- SIDEBAR --------
    with st.sidebar:
        st.header("About")
        st.markdown("""
**Name**: *Nandesh Kalashetti*  
**Role**: *GenAi Developer*  

[LinkedIn](https://www.linkedin.com/in/nandesh-kalashetti-333a78250/) | [GitHub](https://github.com/Universe7Nandu)
        """)
        st.markdown("---")

        st.header("How to Use")
        st.markdown("""
1. **Upload** your resume/doc (optional).  
2. **Process** it (if uploaded).  
3. **Ask** questions in the chat below.  
4. **New Chat** resets everything (doc data is forgotten).

- If no doc is processed → uses **Nandesh’s** info.  
- If doc is processed → uses **only** that doc (forget Nandesh).
        """)
        st.markdown("---")

        st.header("Conversation History")
        if st.button("New Chat"):
            # Clear everything from memory
            st.session_state.pop("chat_history", None)
            st.session_state.pop("document_processed", None)
            st.session_state.pop("vector_store", None)
            st.success("New conversation started! 🆕")

        if "chat_history" in st.session_state and st.session_state["chat_history"]:
            for i, item in enumerate(st.session_state["chat_history"], 1):
                st.markdown(f"{i}. **You**: {item['question']}")
        else:
            st.info("No conversation history yet. Ask away!")

    # -------- MAIN CHAT --------
    st.markdown("<div class='chat-container'>", unsafe_allow_html=True)
    st.markdown("<h1 class='chat-title'>AI Resume Assistant</h1>", unsafe_allow_html=True)
    st.markdown("<p class='chat-subtitle'>Upload Your Resume or Use Default Info</p>", unsafe_allow_html=True)

    # File uploader
    uploaded_file = st.file_uploader("Upload a PDF/DOCX/TXT/CSV/MD", type=["pdf","docx","txt","csv","md"])
    if uploaded_file:
        if not st.session_state.get("document_processed"):
            if st.button("Process Document"):
                with st.spinner("Reading & Embedding your document..."):
                    text = process_document(uploaded_file)
                    if text:
                        chunks = chunk_text(text)
                        st.session_state["vector_store"] = create_inmemory_vector_store()
                        st.session_state["vector_store"].add_texts(chunks)
                        st.session_state["document_processed"] = True
                        st.success(f"Document processed into {len(chunks)} sections! ✅")
    else:
        st.info("No document uploaded. Currently using Nandesh's default info.")

    if "chat_history" not in st.session_state:
        st.session_state["chat_history"] = []

    # Display existing conversation
    for msg in st.session_state["chat_history"]:
        with st.chat_message("user"):
            st.markdown(msg["question"])
        with st.chat_message("assistant"):
            st.markdown(msg["answer"])

    st.markdown("</div>", unsafe_allow_html=True)

    # -------- Chat Input --------
    user_query = st.chat_input("Type your message here... (Press Enter)")
    if user_query:
        # Show user message immediately
        st.session_state["chat_history"].append({"question": user_query, "answer": ""})
        with st.chat_message("user"):
            st.markdown(user_query)

        # Generate the response
        with st.spinner("Thinking..."):
            if st.session_state.get("document_processed") and "vector_store" in st.session_state:
                # Use the doc context only
                vector_store = st.session_state["vector_store"]
                docs = vector_store.similarity_search(user_query, k=3)
                context = "\n".join(d.page_content for d in docs)
                prompt = f"{UPLOADED_DOC_SYSTEM_PROMPT}\nContext:\n{context}\nQuestion: {user_query}"
            else:
                # Use default Nandesh info
                prompt = f"{DEFAULT_SYSTEM_PROMPT}\nQuestion: {user_query}"

            llm = ChatGroq(
                temperature=0.7,
                groq_api_key=GROQ_API_KEY,
                model_name="mixtral-8x7b-32768"
            )
            response = asyncio.run(llm.ainvoke([{"role": "user", "content": prompt}]))
            bot_answer = response.content

        # Update the answer in chat history
        st.session_state["chat_history"][-1]["answer"] = bot_answer
        with st.chat_message("assistant"):
            st.markdown(bot_answer)

if __name__ == "__main__":
    main()
