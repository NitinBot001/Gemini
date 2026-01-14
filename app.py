from flask import Flask, request, jsonify
import requests
from urllib.parse import urlencode, urlparse, urlunparse
from datetime import datetime, timedelta
import random

app = Flask(__name__)

# Cache for instances
cached_instances = None
cache_timestamp = None
CACHE_DURATION = timedelta(hours=1)


def get_invidious_instances():
    """Fetch and cache Invidious instances from GitHub"""
    global cached_instances, cache_timestamp
    
    now = datetime.now()
    
    # Return cached instances if still valid
    if cached_instances and cache_timestamp and (now - cache_timestamp) < CACHE_DURATION:
        return cached_instances
    
    try:
        response = requests.get(
            'https://raw.githubusercontent.com/n-ce/Uma/refs/heads/main/iv.json',
            timeout=10
        )
        response.raise_for_status()
        cached_instances = response.json()
        cache_timestamp = now
        return cached_instances
    except Exception as e:
        print(f'Error fetching instances: {e}')
        return [['https://yt.omada.cafe']]


def get_random_instance(instances):
    """Get a random instance based on current month"""
    current_month = datetime.now().month - 1  # 0-11
    instance_group = instances[current_month] if current_month < len(instances) else instances[0]
    return random.choice(instance_group)


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
    """Try to get audio URL from Invidious instances"""
    try:
        instances = get_invidious_instances()
        final_video_id = video_id
        used_instance = ''
        
        # Search if no video_id provided
        if not final_video_id:
            for attempt in range(3):
                instance = get_random_instance(instances)
                try:
                    search_url = f'{instance}/api/v1/search?{urlencode({"q": query, "type": "video"})}'
                    response = requests.get(search_url, timeout=10)
                    
                    if response.status_code == 200:
                        results = response.json()
                        if results and len(results) > 0:
                            final_video_id = results[0]['videoId']
                            used_instance = instance
                            break
                except Exception as err:
                    print(f'Search failed on {instance}: {err}')
        
        if not final_video_id:
            return None
        
        # Get audio URL from video
        for attempt in range(3):
            instance = used_instance if used_instance else get_random_instance(instances)
            try:
                video_url = f'{instance}/api/v1/videos/{final_video_id}'
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
                        proxied_url = replace_googlevideo_domain(original_url, instance)
                        
                        return {
                            'url': proxied_url,
                            'instance': instance
                        }
            except Exception as err:
                print(f'Video fetch failed on {instance}: {err}')
                used_instance = ''
        
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
