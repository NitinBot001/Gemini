from flask import Flask, request, jsonify, render_template
from flask_cors import CORS
from googletrans import Translator
from langchain.document_loaders import TextLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.vectorstores import FAISS
from langchain.chains import RetrievalQA
from langchain.prompts import PromptTemplate
from langchain_google_genai import ChatGoogleGenerativeAI, GoogleGenerativeAIEmbeddings
import os

# Load API key from environment variable
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    raise ValueError("GEMINI_API_KEY environment variable not set")

# File paths
STATIC_FOLDER = os.path.join(os.path.dirname(__file__), "static")
CONTEXT_FILE = os.path.join(STATIC_FOLDER, "context.txt")
INDEX_PATH = "faiss_context_index"

# Load and process context
loader = TextLoader(CONTEXT_FILE)
documents = loader.load()

text_splitter = RecursiveCharacterTextSplitter(chunk_size=800, chunk_overlap=100)
chunks = text_splitter.split_documents(documents)

# Create or load FAISS vector store
embeddings = GoogleGenerativeAIEmbeddings(
    model="models/embedding-001",
    google_api_key=GEMINI_API_KEY
)

if os.path.exists(INDEX_PATH):
    vector_store = FAISS.load_local(INDEX_PATH, embeddings, allow_dangerous_deserialization=True)
else:
    vector_store = FAISS.from_documents(chunks, embeddings)
    vector_store.save_local(INDEX_PATH)

# Gemini LLM setup
llm = ChatGoogleGenerativeAI(
    model="gemini-1.5-flash",
    google_api_key=GEMINI_API_KEY,
    temperature=0.5,
    max_tokens=512
)

# Prompt template
SYSTEM_INSTRUCTION = """
You are Hal, an AI assistant created to help farmers.
Your goal is to analyze the crop data provided in the context file and assist farmers by answering their queries and solving their problems.

Response Rules:
1. Use the context file to answer farmer-related questions.
2. Do not share any personal information.
3. Provide only the information available in the context file.
4. If not found, generate helpful answers from agricultural knowledge.
5. Keep responses simple, clear, and useful.
"""

prompt_template = PromptTemplate(
    input_variables=["context", "question"],
    template=SYSTEM_INSTRUCTION + "\n\nContext:\n{context}\n\nUser Query: {question}"
)

qa_chain = RetrievalQA.from_chain_type(
    llm=llm,
    chain_type="stuff",
    retriever=vector_store.as_retriever(search_kwargs={"k": 5}),
    chain_type_kwargs={"prompt": prompt_template},
    return_source_documents=False
)

# Flask app
app = Flask(__name__, template_folder="templates", static_folder="static")
CORS(app)

translator = Translator()

def translate_text(text, target_lang):
    try:
        translated = translator.translate(text, dest=target_lang)
        return translated.text
    except Exception as e:
        return f"Translation error: {str(e)}"

@app.route("/", methods=["GET"])
def home():
    return render_template("index.html")

@app.route("/chat", methods=["POST"])
def chat():
    try:
        data = request.get_json()
        user_message = data.get("message")
        target_lang = data.get("lang", "en")

        if not user_message:
            return jsonify({"error": "Message is required"}), 400

        # Use vector-based QA
        result = qa_chain(user_message)
        ai_response = result.strip()

        if target_lang.lower() != "en":
            ai_response = translate_text(ai_response, target_lang)

        return jsonify({"response": ai_response})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000, threaded=True)
