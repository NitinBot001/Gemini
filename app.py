from flask import Flask, request, jsonify
import google.generativeai as genai
import os
from flask-cors import CORS
import requests

# Load API key from environment variable
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    raise ValueError("Gemini API Key is missing. Set it in environment variables.")

# Configure the Gemini AI client
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel(model_name="gemini-1.5-flash")

# Read the context file
CONTEXT_FILE = "context.txt"
try:
    with open(CONTEXT_FILE, "r", encoding="utf-8") as file:
        CONTEXT_DATA = file.read()
except FileNotFoundError:
    CONTEXT_DATA = "No context available."

# System instruction for Hal (AI Assistant)
SYSTEM_INSTRUCTION = """
You are Hal, an AI assistant created to help farmers.
Your goal is to analyze the crop data provided in the context file and assist farmers by answering their queries and solving their problems.

Response Rules:
1. Use the context file to answer farmer-related questions.
2. Do not share any personal information (such as names, addresses, phone numbers, or emails).
3. Provide only the information available in the context file.
4. If the required information is not found in the context file, generate a helpful response based on agricultural knowledge.
5. Keep responses simple, clear, and useful for farmers.
"""

# Initialize Flask app
app = Flask(__name__)
CORS(app)

@app.route("/chat", methods=["POST"])
def chat():
    try:
        data = request.get_json()
        user_message = data.get("message")
        target_lang = data.get("lang", "en")  # Default to English if no language is given

        if not user_message:
            return jsonify({"error": "Message is required"}), 400

        # AI Processing with system instruction
        prompt = [
            SYSTEM_INSTRUCTION,
            f"Context Data:\n{CONTEXT_DATA}",
            f"User Query: {user_message}"
        ]
        ai_response = model.generate_content(prompt).text.strip()

        # Translation (if necessary)
        if target_lang and target_lang.lower() != "en":
            ai_response = translate_text(ai_response, target_lang)

        return jsonify({"response": ai_response})

    except Exception as e:
        return jsonify({"error": str(e)}), 500

# Run API
if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)
