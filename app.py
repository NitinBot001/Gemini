from flask import Flask, request, jsonify
import requests

app = Flask(__name__)

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
        "contents": [{
            "parts": [{"text": user_question}]
        }]
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
