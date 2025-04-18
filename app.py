from flask import Flask, render_template, request, send_file, jsonify
import os
import uuid
from kokoro import KPipeline
import soundfile as sf
import traceback

app = Flask(__name__)

# Create output directory if it doesn't exist
os.makedirs('output', exist_ok=True)

# Dictionary of language codes
KOKORO_LANGUAGE_CODES = {
    'English (US)': 'a',
    'English (UK)': 'b',
    'Spanish': 'e',
    'French': 'f',
    'Italian': 'i',
    'Portuguese (Brazil)': 'p'
}

# List of voice choices
KOKORO_VOICE_CHOICES = [
    # US English (a) Voices
    ("KOKORO US Fenrir", "am_fenrir", "m"),
    ("KOKORO US Nicole", "af_nicole", "f"),
    ("KOKORO US Jessica", "af_jessica", "f"),
    ("KOKORO US River", "af_river", "f"),
    ("KOKORO US Eric", "am_eric", "m"),
    ("KOKORO US Adam", "am_adam", "m"),
    ("KOKORO US Alloy", "af_alloy", "f"),
    ("KOKORO US Heart", "af_heart", "f"),
    ("KOKORO US Onyx", "am_onyx", "m"),
    ("KOKORO US Bella", "af_bella", "f"),
    ("KOKORO US Aoede", "af_aoede", "f"),
    ("KOKORO US Santa", "am_santa", "m"),
    ("KOKORO US Sky", "af_sky", "f"),
    ("KOKORO US Puck", "am_puck", "m"),
    ("KOKORO US Nova", "af_nova", "f"),
    ("KOKORO US Liam", "am_liam", "m"),
    ("KOKORO US Sarah", "af_sarah", "f"),
    ("KOKORO US Kore", "af_kore", "f"),
    ("KOKORO US Echo", "am_echo", "m"),
    ("KOKORO US Michael", "am_michael", "m"),
    # UK English (b) Voices
    ("KOKORO GB Alice", "bf_alice", "f"),
    ("KOKORO GB George", "bm_george", "m"),
    ("KOKORO GB Fable", "bm_fable", "m"),
    ("KOKORO GB Lily", "bf_lily", "f"),
    ("KOKORO GB Emma", "bf_emma", "f"),
    ("KOKORO GB Isabella", "bf_isabella", "f"),
    ("KOKORO GB Lewis", "bm_lewis", "m"),
    ("KOKORO GB Daniel", "bm_daniel", "m"),
    # Portuguese (p) Voices
    ("KOKORO PT Dora", "pf_dora", "f"),
    ("KOKORO PT Alex", "pm_alex", "m"),
    ("KOKORO PT Santa", "pm_santa", "m"),
    # Italian (i) Voices
    ("KOKORO IT Nicola", "im_nicola", "m"),
    ("KOKORO IT Sara", "if_sara", "f"),
    # French (f) Voices
    ("KOKORO FR Siwis", "ff_siwis", "f"),
    # Spanish (e) Voices
    ("KOKORO ES Dora", "ef_dora", "f"),
    ("KOKORO ES Alex", "em_alex", "m"),
    ("KOKORO ES Santa", "em_santa", "m")
]

# Group voices by language
voices_by_language = {}
for name, code, gender in KOKORO_VOICE_CHOICES:
    lang_code = code[0]
    lang_name = next((k for k, v in KOKORO_LANGUAGE_CODES.items() if v == lang_code), "Unknown")
    if lang_name not in voices_by_language:
        voices_by_language[lang_name] = []
    voices_by_language[lang_name].append({
        "name": name,
        "code": code,
        "gender": gender
    })

# Initialize pipelines dictionary (will be created on demand)
pipelines = {}

@app.route('/')
def index():
    return render_template('index.html', voices_by_language=voices_by_language)

@app.route('/generate', methods=['POST'])
def generate_speech():
    data = request.json
    text = data.get('text', '')
    voice_code = data.get('voice', 'af_heart')
    
    if not text:
        return jsonify({"error": "Text is required"}), 400
    
    # Get language code from voice code (first character)
    lang_code = voice_code[0]
    
    try:
        # Create pipeline if not exists for this language
        if lang_code not in pipelines:
            pipelines[lang_code] = KPipeline(lang_code=lang_code)
        
        pipeline = pipelines[lang_code]
        
        # Generate a unique filename - FIX: Use correct output path
        filename = f"output/{uuid.uuid4()}.wav"

        # Generate speech
        generator = pipeline(text, voice=voice_code)
        
        # We're only saving the last segment for simplicity
        last_segment = 0
        for i, (gs, ps, audio) in enumerate(generator):
            sf.write(filename, audio, 24000)
            last_segment = i
        
        # Return the URL to the generated audio file
        return jsonify({
            "success": True,
            "filename": filename,
            "segments": last_segment + 1
        })
    except Exception as e:
        app.logger.error(f"Error generating speech: {str(e)}")
        app.logger.error(traceback.format_exc())
        return jsonify({"error": str(e)}), 500

@app.route('/audio/<path:filename>')
def get_audio(filename):
    # Only get the basename to prevent directory traversal
    safe_filename = os.path.basename(filename)
    file_path = os.path.join('output', safe_filename)
    
    # Check if file exists
    if not os.path.exists(file_path):
        return jsonify({"error": "Audio file not found"}), 404
        
    return send_file(file_path)

if __name__ == '__main__':
    app.run(debug=True)