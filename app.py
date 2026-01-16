from flask import Flask, request, jsonify
import requests
from flask_cors import CORS
import os
from urllib.parse import urlencode, urlparse, urlunparse

app = Flask(__name__)
CORS(app)

# --- CONFIGURATION ---
API_KEY = os.getenv("RAPIDAPI_KEY")
FALLBACK_API = os.getenv("FALLBACK_API")
INVIDIOUS_INSTANCE = 'https://yt.omada.cafe'


def replace_googlevideo_domain(url, instance):
    """Replace googlevideo.com domain with instance domain"""
    try:
        parsed_url = urlparse(url)
        parsed_instance = urlparse(instance)
        
        # Check if it's a googlevideo.com URL
        if 'googlevideo.com' in parsed_url.hostname:
            # Replace hostname and protocol
            new_url = parsed_url._replace(
                scheme=parsed_instance.scheme,
                netloc=parsed_instance.netloc
            )
            return urlunparse(new_url)
        
        return url
    except Exception as e:
        print(f'Error replacing domain: {e}')
        return url


def get_audio_from_jiosaavn(title, artist, duration):
    """Try to get audio URL from JioSaavn API (PRIMARY SOURCE)"""
    try:
        # Clean title for better matching
        clean_title = title.split('(')[0].strip()
        
        params = {
            'title': clean_title,
            'artist': artist,
            'duration': duration
        }
        url = f'https://fast-saavn.vercel.app/api?{urlencode(params)}'
        
        response = requests.get(url, timeout=8)
        
        if response.status_code == 200:
            data = response.text.strip()
            
            # Response is like: 394/d6a62165b425ee86a78da3da48aa0e4b
            if data and 'error' not in data.lower() and len(data) > 5:
                audio_url = f'https://aac.saavncdn.com/{data}_160.mp4'
                return {
                    'url': audio_url,
                    'instance': 'jiosaavn',
                    'itag': None,
                    'bitrate': 160000,  # JioSaavn uses 160kbps
                    'quality': 'AUDIO_QUALITY_MEDIUM',
                    'container': 'mp4'
                }
        
        return None
    except Exception as e:
        print(f'JioSaavn failed: {e}')
        return None


def get_audio_from_invidious(video_id):
    """Try to get audio URL from Invidious (SECONDARY SOURCE)"""
    try:
        # Get audio URL from video
        video_url = f'{INVIDIOUS_INSTANCE}/api/v1/videos/{video_id}'
        response = requests.get(video_url, timeout=10)
        
        if response.status_code == 200:
            video_data = response.json()
            
            # Filter audio formats by specific itags
            # Preferred order: 140 (m4a AAC), 251 (webm opus high), 250, 249
            preferred_itags = ['140', '251', '250', '249']
            
            audio_formats = [
                fmt for fmt in video_data.get('adaptiveFormats', [])
                if fmt.get('url') and fmt.get('itag') in preferred_itags
            ]
            
            if audio_formats:
                # Sort by preferred itag order
                def itag_priority(fmt):
                    itag = fmt.get('itag')
                    try:
                        return preferred_itags.index(itag)
                    except ValueError:
                        return 999
                
                audio_formats.sort(key=itag_priority)
                
                # Get the best format
                best_format = audio_formats[0]
                
                # Replace googlevideo.com domain with instance domain
                original_url = best_format['url']
                proxied_url = replace_googlevideo_domain(original_url, INVIDIOUS_INSTANCE)
                
                return {
                    'url': proxied_url,
                    'instance': INVIDIOUS_INSTANCE,
                    'itag': best_format.get('itag'),
                    'bitrate': best_format.get('bitrate'),
                    'quality': best_format.get('audioQuality'),
                    'container': best_format.get('container')
                }
        
        return None
    except Exception as e:
        print(f'Invidious failed: {e}')
        return None


def get_audio_from_rapidapi(video_id):
    """Try to get audio URL from RapidAPI (FINAL FALLBACK)"""
    try:
        if not API_KEY:
            print('RapidAPI: No API key configured')
            return None
        
        url = "https://youtube-mp36.p.rapidapi.com/dl"
        querystring = {"id": video_id}
        headers = {
            "x-rapidapi-key": API_KEY,
            "x-rapidapi-host": "youtube-mp36.p.rapidapi.com"    
        }

        response = requests.get(url, headers=headers, params=querystring, timeout=10)
        
        # Retry with fallback API key if primary fails
        if response.status_code != 200 and FALLBACK_API:
            print('RapidAPI: Primary key failed, trying fallback key')
            headers["x-rapidapi-key"] = FALLBACK_API
            response = requests.get(url, headers=headers, params=querystring, timeout=10)

        if response.status_code == 200:
            data = response.json()
            if data.get('link'):
                return {
                    'url': data.get('link'),
                    'instance': 'rapidapi',
                    'itag': None,
                    'bitrate': None,
                    'quality': data.get('quality', 'AUDIO_QUALITY_MEDIUM'),
                    'container': 'mp3'
                }
        
        return None
    except Exception as e:
        print(f'RapidAPI failed: {e}')
        return None


@app.route('/api', methods=['GET'])
def get_audio():
    """Main API endpoint to get audio URL"""
    
    # Get query parameters
    video_id = request.args.get('v') or request.args.get('videoId')
    title = request.args.get('title') or request.args.get('track_name')
    artist = request.args.get('artist') or request.args.get('artist_name')
    duration = request.args.get('duration')
    q = request.args.get('q')
    
    # Validation: v is REQUIRED
    if not video_id:
        return jsonify({
            'error': 'Missing required parameter "v" (video ID)'
        }), 400
    
    # Validation: Either q OR (title AND artist) is REQUIRED
    has_query = bool(q)
    has_metadata = bool(title and artist)
    
    if not has_query and not has_metadata:
        return jsonify({
            'error': 'Missing search parameters. Provide either "q" OR both "title" and "artist"'
        }), 400
    
    try:
        result = None
        
        # ==========================================
        # PHASE 1: JIOSAAVN (PRIMARY - Fastest & Free)
        # ==========================================
        if has_metadata and duration:
            print(f'[1/3] Attempting JioSaavn for: {title} - {artist}')
            result = get_audio_from_jiosaavn(title, artist, duration)
            if result:
                print(f'✓ JioSaavn success')
                return jsonify(result)
        
        # ==========================================
        # PHASE 2: INVIDIOUS (SECONDARY - Free Proxy)
        # ==========================================
        if not result:
            print(f'[2/3] Attempting Invidious for video ID: {video_id}')
            result = get_audio_from_invidious(video_id)
            if result:
                print(f'✓ Invidious success')
                return jsonify(result)
        
        # ==========================================
        # PHASE 3: RAPIDAPI (FINAL FALLBACK - Paid)
        # ==========================================
        if not result:
            print(f'[3/3] Attempting RapidAPI for video ID: {video_id}')
            result = get_audio_from_rapidapi(video_id)
            if result:
                print(f'✓ RapidAPI success')
                return jsonify(result)
        
        # ==========================================
        # ALL SOURCES FAILED
        # ==========================================
        return jsonify({
            'error': 'Could not fetch audio URL from any source'
        }), 404
    
    except Exception as e:
        print(f'Error: {e}')
        return jsonify({
            'error': 'Internal Server Error',
            'message': str(e)
        }), 500


@app.route('/health', methods=['GET'])
def health():
    """Health check endpoint"""
    return jsonify({'status': 'ok'}), 200


if __name__ == '__main__':
    app.run(debug=True, port=5000)
