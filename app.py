from flask import Flask, request, jsonify
import yt_dlp
import os
import uuid
import logging
from werkzeug.utils import secure_filename
from datetime import datetime

app = Flask(__name__)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('youtube_dl_api.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Configuration
DOWNLOAD_FOLDER = 'downloads'
ALLOWED_EXTENSIONS = {'mp4', 'webm', 'mp3', 'm4a'}
os.makedirs(DOWNLOAD_FOLDER, exist_ok=True)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def get_user_agent():
    """Return a rotating user agent to help prevent blocking"""
    agents = [
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:89.0) Gecko/20100101 Firefox/89.0'
    ]
    return agents[int(datetime.now().timestamp()) % len(agents)]

@app.route('/info', methods=['GET'])
def get_video_info():
    url = request.args.get('url')
    if not url:
        logger.error("No URL provided in info request")
        return jsonify({'error': 'No URL provided'}), 400
    
    logger.info(f"Processing info request for URL: {url}")
    
    ydl_opts = {
        'quiet': True,
        'no_warnings': False,
        'extract_flat': False,
        'force_ipv4': True,
        'socket_timeout': 10,
        'http_headers': {'User-Agent': get_user_agent()},
        'ignoreerrors': True,
        'retries': 3,
        'extractor_args': {
            'youtube': {
                'skip': ['hls', 'dash', 'translated_subs']
            }
        }
    }
    
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            
            if info is None:
                logger.error(f"Failed to extract info for URL: {url}")
                return jsonify({'error': 'Failed to extract video information'}), 400
            
            if 'entries' in info:
                # This is a playlist or multi-video entry
                logger.warning(f"Playlist detected for URL: {url}")
                return jsonify({'error': 'Playlists are not supported, please provide a single video URL'}), 400
            
            # Simplify the info for response
            response_info = {
                'title': info.get('title'),
                'duration': info.get('duration'),
                'thumbnail': info.get('thumbnail'),
                'uploader': info.get('uploader'),
                'view_count': info.get('view_count'),
                'webpage_url': info.get('webpage_url'),
                'available_formats': []
            }
            
            # Add available formats
            if 'formats' in info:
                for fmt in info['formats']:
                    if fmt.get('ext') and fmt.get('url'):
                        response_info['available_formats'].append({
                            'format_id': fmt.get('format_id'),
                            'ext': fmt.get('ext'),
                            'resolution': fmt.get('resolution'),
                            'filesize': fmt.get('filesize'),
                            'format_note': fmt.get('format_note')
                        })
            
            logger.info(f"Successfully retrieved info for URL: {url}")
            return jsonify(response_info)
            
    except yt_dlp.utils.DownloadError as e:
        logger.error(f"DownloadError for URL {url}: {str(e)}")
        return jsonify({'error': 'Failed to retrieve video information (DownloadError)'}), 400
    except yt_dlp.utils.ExtractorError as e:
        logger.error(f"ExtractorError for URL {url}: {str(e)}")
        return jsonify({'error': 'Failed to retrieve video information (ExtractorError)'}), 400
    except Exception as e:
        logger.error(f"Unexpected error for URL {url}: {str(e)}", exc_info=True)
        return jsonify({'error': 'An unexpected error occurred while processing your request'}), 500

@app.route('/download', methods=['POST'])
def download_video():
    if not request.is_json:
        logger.error("Request is not JSON")
        return jsonify({'error': 'Request must be JSON'}), 400
        
    url = request.json.get('url')
    if not url:
        logger.error("No URL provided in download request")
        return jsonify({'error': 'No URL provided'}), 400
    
    logger.info(f"Processing download request for URL: {url}")
    
    # Get optional parameters
    format_type = request.json.get('format', 'bestvideo+bestaudio/best')
    audio_only = request.json.get('audio_only', False)
    
    # Configure download options
    ydl_opts = {
        'outtmpl': os.path.join(DOWNLOAD_FOLDER, f'{str(uuid.uuid4())}_%(title)s.%(ext)s'),
        'quiet': True,
        'no_warnings': False,
        'restrictfilenames': True,
        'force_ipv4': True,
        'socket_timeout': 30,
        'http_headers': {'User-Agent': get_user_agent()},
        'retries': 3,
        'extractor_args': {
            'youtube': {
                'skip': ['hls', 'dash', 'translated_subs']
            }
        }
    }
    
    # Set format based on user preference
    if audio_only:
        ydl_opts.update({
            'format': 'bestaudio/best',
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192',
            }],
        })
    else:
        ydl_opts['format'] = format_type
    
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            
            if info is None:
                logger.error(f"Failed to extract info for download URL: {url}")
                return jsonify({'error': 'Failed to extract video information'}), 400
            
            if 'entries' in info:
                logger.warning(f"Playlist detected in download request for URL: {url}")
                return jsonify({'error': 'Playlists are not supported, please provide a single video URL'}), 400
            
            filename = ydl.prepare_filename(info)
            
            # Handle post-processing for audio downloads
            if audio_only and 'entries' not in info:
                filename = os.path.splitext(filename)[0] + '.mp3'
            
            # Secure the filename before returning it
            safe_filename = secure_filename(os.path.basename(filename))
            
            logger.info(f"Successfully downloaded content from URL: {url} as {safe_filename}")
            
            return jsonify({
                'message': 'Download successful',
                'filename': safe_filename,
                'title': info.get('title'),
                'duration': info.get('duration'),
                'thumbnail': info.get('thumbnail')
            })
            
    except yt_dlp.utils.DownloadError as e:
        logger.error(f"DownloadError for URL {url}: {str(e)}")
        return jsonify({'error': f'Download failed: {str(e)}'}), 400
    except yt_dlp.utils.ExtractorError as e:
        logger.error(f"ExtractorError for URL {url}: {str(e)}")
        return jsonify({'error': f'URL extraction failed: {str(e)}'}), 400
    except Exception as e:
        logger.error(f"Unexpected error during download for URL {url}: {str(e)}", exc_info=True)
        return jsonify({'error': f'An unexpected error occurred: {str(e)}'}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)), debug=False)
