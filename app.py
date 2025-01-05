from flask import Flask, request, jsonify
from flask_cors import CORS
import requests

app = Flask(__name__)

CORS(app)

# Replace with your API key
API_KEY = 'AIzaSyBQBfbhPqtL2SEKh3l_0cE6zIxwMKLTi-A'
GEMINI_API_URL = f'https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={API_KEY}'

@app.route('/ask', methods=['GET'])
def ask():
    user_question = request.args.get('question')
    
    if not user_question:
        return jsonify({"error": "No question provided"}), 400

    headers = {'Content-Type': 'application/json'}
    data = {
        "system_instruction": {
            "parts": [
                {"text": "You are Kishan Mitra, developed by EasyFarm, is an AI assistant designed to support farmers with detailed information on crops, diseases, cures, and agricultural data. It provides insights into crop varieties, disease diagnosis, soil and water management, and sustainable farming practices. Kishan Mitra also offers market trends, financial advice, and weather forecasts, delivering personalized recommendations through a user-friendly, multilingual interface. Sourcing data from credible institutions, it ensures accurate, real-time updates while adhering to strict data privacy and ethical standards. Continuous learning and user feedback drive its ongoing improvement, making it a reliable partner for farmers in enhancing productivity and sustainability."}
            ]
        },
        "contents": {
            "parts": [
                {"text": user_question}
            ]
        }
    }

    response = requests.post(GEMINI_API_URL, headers=headers, json=data)

    if response.status_code == 200:
        api_response = response.json()
        text_response = api_response.get('candidates', [{}])[0].get('content', {}).get('parts', [{}])[0].get('text', '')
        return jsonify({
            "status": 200,
            "text": text_response
        })
    else:
        return jsonify({"status": response.status_code, "error": response.text}), response.status_code

if __name__ == '__main__':
    app.run(debug=True, port=8000, host="0.0.0.0")
