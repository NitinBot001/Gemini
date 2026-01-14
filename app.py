from flask import Flask, request, jsonify
import requests
from urllib.parse import urlencode, urlparse, urlunparse

app = Flask(__name__)

# Fixed Invidious instance
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
    """Try to get audio URL from JioSaavn API"""
    try:
        params = {
            'title': title,
            'artist': artist,
            'duration': duration
        }
        url = f'https://fast-saavn.vercel.app/api?{urlencode(params)}'
        
        response = requests.get(url, timeout=8)
        
        if response.status_code == 200:
            data = response.text.strip()
            
            # Response is like: 394/d6a62165b425ee86a78da3da48aa0e4b
            if data and 'error' not in data.lower():
                audio_url = f'https://aac.saavncdn.com/{data}_160.mp4'
                return audio_url
        
        return None
    except Exception as e:
        print(f'JioSaavn failed: {e}')
        return None


def get_audio_from_invidious(query, video_id=None):
    """Try to get audio URL from Invidious"""
    try:
        final_video_id = video_id
        
        # Search if no video_id provided
        if not final_video_id:
            try:
                search_url = f'{INVIDIOUS_INSTANCE}/api/v1/search?{urlencode({"q": query, "type": "video"})}'
                response = requests.get(search_url, timeout=10)
                
                if response.status_code == 200:
                    results = response.json()
                    if results and len(results) > 0:
                        final_video_id = results[0]['videoId']
            except Exception as err:
                print(f'Search failed: {err}')
                return None
        
        if not final_video_id:
            return None
        
        # Get audio URL from video
        try:
            video_url = f'{INVIDIOUS_INSTANCE}/api/v1/videos/{final_video_id}'
            response = requests.get(video_url, timeout=10)
            
            if response.status_code == 200:
                video_data = response.json()
                
                # Filter audio formats
                audio_formats = [
                    fmt for fmt in video_data.get('adaptiveFormats', [])
                    if fmt.get('url') and fmt.get('container') in ['m4a', 'webm']
                ]
                
                if audio_formats:
                    # Sort by bitrate (highest first)
                    audio_formats.sort(
                        key=lambda x: int(x.get('bitrate', 0)),
                        reverse=True
                    )
                    
                    # Replace googlevideo.com domain with instance domain
                    original_url = audio_formats[0]['url']
                    proxied_url = replace_googlevideo_domain(original_url, INVIDIOUS_INSTANCE)
                    
                    return {
                        'url': proxied_url,
                        'instance': INVIDIOUS_INSTANCE
                    }
        except Exception as err:
            print(f'Video fetch failed: {err}')
        
        return None
    except Exception as e:
        print(f'Invidious failed: {e}')
        return None


@app.route('/api', methods=['GET'])
def get_audio():
    """Main API endpoint to get audio URL"""
    
    # Get query parameters
    title = request.args.get('title')
    artist = request.args.get('artist')
    duration = request.args.get('duration')
    q = request.args.get('q')
    video_id = request.args.get('videoId')
    
    # Determine search query
    if q:
        query = q
    elif title and artist:
        query = f'{title} {artist}'
    else:
        return jsonify({
            'error': 'Missing required parameters. Provide either "q" or "title" with "artist"'
        }), 400
    
    try:
        audio_url = None
        source = ''
        instance = ''
        
        # Try JioSaavn first (if title, artist, duration provided)
        if title and artist and duration:
            print('Attempting JioSaavn...')
            audio_url = get_audio_from_jiosaavn(title, artist, duration)
            if audio_url:
                source = 'jiosaavn'
        
        # Fallback to Invidious if JioSaavn failed or wasn't attempted
        if not audio_url:
            print('Attempting Invidious...')
            invidious_result = get_audio_from_invidious(query, video_id)
            
            if invidious_result:
                audio_url = invidious_result['url']
                instance = invidious_result['instance']
                source = 'invidious'
        
        # If both failed
        if not audio_url:
            return jsonify({
                'error': 'Could not fetch audio URL from any source',
                'query': query,
                'attemptedSources': ['jiosaavn', 'invidious']
            }), 404
        
        return jsonify({
            'success': True,
            'query': query,
            'audioUrl': audio_url,
            'source': source,
            'instance': instance if source == 'invidious' else 'N/A',
            'metadata': {
                'title': title,
                'artist': artist,
                'duration': duration
            }
        }), 200, {
            'Cache-Control': 's-maxage=3600, stale-while-revalidate'
        }
    
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
