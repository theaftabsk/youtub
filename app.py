from flask import Flask, request, jsonify
import yt_dlp
import os
import logging
from datetime import datetime
import random

app = Flask(__name__)

# Enhanced logging configuration
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('yt_api.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger('YT-API')

# Configuration
DOWNLOAD_FOLDER = 'downloads'
os.makedirs(DOWNLOAD_FOLDER, exist_ok=True)

# Rotating user agents
USER_AGENTS = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/115.0'
]

def get_ytdl_opts():
    """Generate dynamic yt-dlp options with current timestamp"""
    return {
        'quiet': True,
        'no_warnings': False,
        'force_ipv4': True,
        'socket_timeout': 15,
        'extract_flat': False,
        'http_headers': {
            'User-Agent': random.choice(USER_AGENTS),
            'Accept-Language': 'en-US,en;q=0.9',
            'Referer': 'https://www.youtube.com/',
            'Origin': 'https://www.youtube.com'
        },
        'extractor_args': {
            'youtube': {
                'player_client': ['android', 'web'],
                'player_skip': ['configs'],
                'skip': ['hls', 'dash', 'translated_subs']
            }
        },
        'retries': 3,
        'retry_sleep_functions': {
            'http': lambda n: min(2 ** n, 10),
            'fragment': lambda n: min(2 ** n, 10),
        }
    }

@app.route('/info', methods=['GET'])
def get_video_info():
    url = request.args.get('url')
    if not url:
        logger.error("No URL provided")
        return jsonify({'error': 'URL parameter is required'}), 400

    # Clean URL parameters that might cause issues
    clean_url = url.split('?')[0]
    logger.info(f"Processing info request for: {clean_url}")

    try:
        ydl_opts = get_ytdl_opts()
        ydl_opts.update({'extract_flat': 'in_playlist'})

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(clean_url, download=False)

            if not info:
                logger.error(f"No info extracted for URL: {clean_url}")
                return jsonify({'error': 'Could not extract video information'}), 404

            if info.get('_type') == 'playlist':
                logger.warning(f"Playlist detected: {clean_url}")
                return jsonify({'error': 'Playlists are not supported'}), 400

            response_data = {
                'status': 'success',
                'video_id': info.get('id'),
                'title': info.get('title'),
                'duration': info.get('duration'),
                'thumbnail': info.get('thumbnail'),
                'uploader': info.get('uploader'),
                'view_count': info.get('view_count'),
                'availability': info.get('availability'),
                'formats': []
            }

            for fmt in info.get('formats', []):
                if fmt.get('url'):
                    response_data['formats'].append({
                        'format_id': fmt.get('format_id'),
                        'ext': fmt.get('ext'),
                        'resolution': fmt.get('resolution'),
                        'filesize': fmt.get('filesize')
                    })

            logger.info(f"Successfully retrieved info for: {clean_url}")
            return jsonify(response_data)

    except yt_dlp.utils.DownloadError as e:
        logger.error(f"DownloadError: {str(e)}")
        return jsonify({'error': 'YouTube download error', 'details': str(e)}), 502
    except yt_dlp.utils.ExtractorError as e:
        logger.error(f"ExtractorError: {str(e)}")
        return jsonify({'error': 'YouTube extraction error', 'details': str(e)}), 502
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}", exc_info=True)
        return jsonify({'error': 'Internal server error'}), 500

if __name__ == '__main__':
    # Verify yt-dlp version
    logger.info(f"Using yt-dlp version: {yt_dlp.version.__version__}")
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)), threaded=True)
