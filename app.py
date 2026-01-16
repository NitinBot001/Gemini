from flask import Flask, request, jsonify
import requests
from flask_cors import CORS
import os
from urllib.parse import urlencode, urlparse, urlunparse

app = Flask(__name__)
CORS(app)

# --- CONFIGURATION ---
API_KEY = os.getenv("RAPIDAPI_KEY","")
FALLBACK_API = os.getenv("FALLBACK_API","")
INVIDIOUS_INSTANCE = 'https://yt.omada.cafe'

# --- HELPER 1: JIOSAAVN ---
def get_audio_from_jiosaavn(title, artist, duration):
    try:
        if not title or not artist:
            return None
        
        # Clean title for better matching
        clean_title = title.split('(')[0].strip()
        params = {'title': clean_title, 'artist': artist, 'duration': duration}
        url = f'https://fast-saavn.vercel.app/api?{urlencode(params)}'
        
        response = requests.get(url, timeout=5)
        if response.status_code == 200:
            data = response.text.strip()
            if data and 'error' not in data.lower() and len(data) > 5:
                return f'https://aac.saavncdn.com/{data}_160.mp4'
        return None
    except Exception as e:
        print(f'JioSaavn Error: {e}')
        return None

# --- HELPER 2: INVIDIOUS ---
def replace_googlevideo_domain(url, instance):
    try:
        parsed_url = urlparse(url)
        parsed_instance = urlparse(instance)
        if 'googlevideo.com' in parsed_url.hostname:
            new_url = parsed_url._replace(
                scheme=parsed_instance.scheme,
                netloc=parsed_instance.netloc
            )
            return urlunparse(new_url)
        return url
    except:
        return url

def get_audio_from_invidious(video_id):
    """Scrapes audio using a specific Video ID"""
    try:
        url = f'{INVIDIOUS_INSTANCE}/api/v1/videos/{video_id}'
        response = requests.get(url, timeout=8)
        
        if response.status_code == 200:
            video_data = response.json()
            preferred_itags = ['140', '251', '250', '249']
            
            audio_formats = [
                fmt for fmt in video_data.get('adaptiveFormats', [])
                if fmt.get('url') and fmt.get('itag') in preferred_itags
            ]
            
            if audio_formats:
                audio_formats.sort(key=lambda x: preferred_itags.index(x['itag']) if x['itag'] in preferred_itags else 999)
                best_format = audio_formats[0]
                proxied_url = replace_googlevideo_domain(best_format['url'], INVIDIOUS_INSTANCE)
                
                return {
                    "link": proxied_url,
                    "quality": best_format.get('audioQuality'),
                    "title": video_data.get('title', 'Unknown')
                }
        return None
    except Exception as e:
        print(f'Invidious Audio Error: {e}')
        return None

# --- MAIN ROUTE ---
@app.route('/api', methods=['GET'])
def get_audio_url():
    # 1. Capture Inputs
    video_id = request.args.get('videoId')
    q = request.args.get('q')
    title = request.args.get('title')
    artist = request.args.get('artist')
    duration = request.args.get('duration')

    # 2. NEW VALIDATION: v is REQUIRED, then q OR (title AND artist) is REQUIRED
    if not video_id:
        return jsonify({
            "error": "Missing required parameter 'v' (video ID)"
        }), 400
    
    # Check if we have either q OR both title and artist
    has_query = bool(q)
    has_metadata = bool(title and artist)
    
    if not has_query and not has_metadata:
        return jsonify({
            "error": "Missing search parameters. Provide either 'q' OR both 'title' and 'artist'"
        }), 400

    # Determine a Search Query for display purposes
    search_query = q if q else f"{title} {artist}"

    # ==========================================
    # PHASE 1: JIOSAAVN (Fastest)
    # ==========================================
    # Only runs if we have explicit metadata
    if has_metadata:
        print(f"Step 1: JioSaavn for '{title}'")
        saavn_url = get_audio_from_jiosaavn(title, artist, duration)
        if saavn_url:
            return jsonify({
                "status": "ok",
                "link": saavn_url,
                "source": "jiosaavn",
                "videoId": video_id
            })

    # ==========================================
    # PHASE 2: INVIDIOUS (Search + Proxy)
    # ==========================================
    print(f"Step 2: Invidious fetch for ID: {video_id}")
    invidious_data = get_audio_from_invidious(video_id)
    if invidious_data:
        return jsonify({
            "status": "ok",
            "link": invidious_data['link'],
            "source": "invidious",
            "videoId": video_id,
            "title": invidious_data['title']
        })
    
    # ==========================================
    # PHASE 3: RAPIDAPI (Fallback)
    # ==========================================
    if API_KEY:
        print(f"Step 3: RapidAPI for ID: {video_id}")
        try:
            url = "https://youtube-mp36.p.rapidapi.com/dl"
            querystring = {"id": video_id}
            headers = {
                "x-rapidapi-key": API_KEY,
                "x-rapidapi-host": "youtube-mp36.p.rapidapi.com"    
            }

            response = requests.get(url, headers=headers, params=querystring)
            
            # Retry with fallback API
            if response.status_code != 200 and FALLBACK_API:
                headers["x-rapidapi-key"] = FALLBACK_API
                response = requests.get(url, headers=headers, params=querystring)

            if response.status_code == 200:
                data = response.json()
                if data.get('link'):
                    data['source'] = 'rapidapi'
                    data['videoId'] = video_id
                    return jsonify(data)

        except Exception as e:
            print(f"RapidAPI Error: {e}")

    return jsonify({
        "error": "Audio not found", 
        "videoId": video_id,
        "searchQuery": search_query
    }), 404

if __name__ == '__main__':
    app.run(debug=True, port=5000)
