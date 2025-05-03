from flask import Flask, render_template, request, jsonify, send_file
from gtts import gTTS
import os
import datetime
import requests
import google.generativeai as genai
from flask import Flask, render_template, request, jsonify, send_file
from gtts import gTTS
import os
import datetime
import requests
import google.generativeai as genai
from google.cloud import vision
from PIL import Image
import language_tool_python 
import io
from transformers import pipeline
from dotenv import load_dotenv 

import torch

app = Flask(__name__)
app.config['STATIC_FOLDER'] = os.path.join(os.getcwd(), 'static')

API_KEY = os.getenv('API_KEY')

# Initialize Gemini AI with your API key from .env file
genai.configure(api_key=API_KEY)

# Use Gemini 1.5 Flash model consistently for all text and vision tasks
gemini_model = genai.GenerativeModel('gemini-1.5-flash')

# Ensure static folder exists
if not os.path.exists(app.config['STATIC_FOLDER']):
    os.makedirs(app.config['STATIC_FOLDER'])

@app.route('/')
def home():
    return render_template('home.html')

@app.route('/get_historic_day')
def get_historic_day():
    today = datetime.datetime.now().strftime('%m-%d')
    events = {
        "02-01": "சுதந்திர நாள்",
        "12-05": "கலைஞர் கலைநிதி பிறந்த நாள்"
    }
    return jsonify({"event": events.get(today, "No historic events today.")})

@app.route('/get_popularity_data')
def get_popularity_data():
    url = 'https://ta.wikipedia.org/w/api.php'
    params = {
        'action': 'query',
        'list': 'mostviewed',
        'format': 'json',
        'pvimlimit': 10
    }
    response = requests.get(url, params=params)
    data = response.json()
    return jsonify(data)

@app.route('/plugin_store')
def plugin_store():
    plugins = [
        {"name": "Grammar Checker", "url": "https://plugin1.com"},
        {"name": "Template Maker", "url": "https://plugin2.com"},
    ]
    return jsonify(plugins)

@app.route('/suggest_missing_content', methods=['POST'])
def suggest_missing_content():
    data = request.get_json()
    content = data.get("content", "")

    if not content.strip():
        return jsonify({"suggestion": "உள்ளடக்கம் வழங்கப்படவில்லை."})

    try:
        prompt = f"""நீ ஒரு தமிழ் விக்கிப்பீடியா ஆசிரியர். கீழ்க்காணும் உள்ளடக்கத்தின் அடிப்படையில், விரிவாக எழுத ஒரு பரிந்துரை/பொருளடக்கம் உருவாக்கவும்:
        
        உள்ளடக்கம்: {content}
        
        புதிய பரிந்துரை:"""

        response = gemini_model.generate_content(prompt)
        suggestion = response.text.strip()

        return jsonify({"suggestion": suggestion})
    except Exception as e:
        return jsonify({"suggestion": f"பிழை: {str(e)}"}), 500

@app.route('/create_article.html')
def create_article():
    return render_template('create_article.html')

@app.route('/speak_text', methods=['GET'])
def speak_text():
    text = request.args.get('text', 'சிலப்பதிகாரம் ஒரு தமிழ் இலக்கியம்')
    try:
        tts = gTTS(text, lang='ta')
        audio_file = os.path.join(app.config['STATIC_FOLDER'], 'output.mp3')
        tts.save(audio_file)
        return jsonify({'audio_url': '/static/output.mp3'})
    except Exception as e:
        return jsonify({'error': str(e)})

@app.route('/static/<filename>')
def serve_audio(filename):
    return send_file(os.path.join(app.config['STATIC_FOLDER'], filename))

@app.route('/generate_tamil_from_image', methods=['POST'])
def generate_tamil_from_image():
    try:
        # Check if image file exists in the request
        if 'image' not in request.files:
            return jsonify({'error': 'No image file provided'}), 400
            
        image_file = request.files['image']
        if image_file.filename == '':
            return jsonify({'error': 'Empty image file name'}), 400
            
        # Get requested number of lines
        lines = int(request.form.get('lines', 5))

        # Read image bytes
        image_bytes = image_file.read()
        image = Image.open(io.BytesIO(image_bytes))
        
        # Create a more detailed Tamil prompt
        prompt = f"""இந்த படத்தை விரிவாக பார்த்து தமிழில் {lines} வரிகளில் விளக்கம் தரவும். 
        படத்தில் உள்ள விவரங்களை துல்லியமாக குறிப்பிடவும். 
        எளிய, தெளிவான தமிழில் விளக்கம் அளிக்கவும்."""

        # Send to Gemini model with explicit language preference
        response = gemini_model.generate_content([
            prompt, 
            image
        ])
        
        # Debug information
        print(f"Generated caption: {response.text}")
        
        return jsonify({'caption': response.text.strip()})

    except Exception as e:
        print(f"Error in image caption generation: {str(e)}")
        return jsonify({'error': str(e)}), 500


@app.route('/chatbot', methods=['POST'])
def chatbot():
    try:
        # Get the user message from the request
        data = request.get_json()
        if not data or 'message' not in data:
            return jsonify({'error': 'No message provided'}), 400
            
        user_message = data['message']
        
        # Add Tamil context to improve responses
        prompt = f"""நான் தமிழ் விக்கிப்பீடியா பற்றிய ஒரு உதவியாளர். 
        கீழே உள்ள கேள்விக்கு தமிழில் பதிலளிக்கவும்:
        
        கேள்வி: {user_message}
        
        பதில்:"""
        
        # Generate response using Gemini 1.5 Flash
        response = gemini_model.generate_content(prompt)
        
        # Log response for debugging
        print(f"User: {user_message}")
        print(f"Bot: {response.text}")
        
        return jsonify({'response': response.text.strip()})
    except Exception as e:
        print(f"Chatbot error: {str(e)}")
        return jsonify({'error': str(e), 'response': 'பதில் பெற முடியவில்லை. மீண்டும் முயற்சிக்கவும்.'}), 500


@app.route('/check-grammar', methods=['POST'])
def check_grammar():
    # Get the text from the request
    text_to_check = request.json.get('text', '')

    if not text_to_check:
        return jsonify({'error': 'No text provided'}), 400
    
    try:
        # Assuming 'generate_content' is the correct method to use
        prompt = f"Correct the following Tamil text for grammar: {text_to_check}"
        
        # Sending the prompt to the Gemini model for correction
        response = gemini_model.generate_content(prompt)

        # Assuming the response contains the corrected text
        corrected_text = response.text.strip()

        # Return the corrected content
        return jsonify({'corrected_text': corrected_text})

    except Exception as e:
        return jsonify({'error': str(e)}), 500


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))  # 5000 for local dev
    app.run(host='0.0.0.0', port=port, debug=True)
