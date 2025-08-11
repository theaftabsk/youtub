from flask import Flask, request, jsonify
from flask_cors import CORS
import yt_dlp
import os
import uuid
from werkzeug.utils import secure_filename

app = Flask(__name__)
CORS(app)  # Enable CORS for frontend communication

# Configuration
DOWNLOAD_FOLDER = 'downloads'
ALLOWED_EXTENSIONS = {'mp4', 'webm', 'mp3', 'm4a'}
os.makedirs(DOWNLOAD_FOLDER, exist_ok=True)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route('/download', methods=['POST'])
def download_video():
    # Validate input
    if not request.is_json:
        return jsonify({'error': 'Request must be JSON'}), 400
        
    url = request.json.get('url')
    if not url:
        return jsonify({'error': 'No URL provided'}), 400
    
    # Get optional parameters
    format_type = request.json.get('format', 'best')
    audio_only = request.json.get('audio_only', False)
    
    # Configure download options
    ydl_opts = {
        'outtmpl': os.path.join(DOWNLOAD_FOLDER, f'{str(uuid.uuid4())}_%(title)s.%(ext)s'),
        'quiet': True,
        'no_warnings': True,
        'restrictfilenames': True,
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
            filename = ydl.prepare_filename(info)
            
            # Handle post-processing for audio downloads
            if audio_only and 'entries' not in info:
                filename = os.path.splitext(filename)[0] + '.mp3'
            
            # Secure the filename before returning it
            safe_filename = secure_filename(os.path.basename(filename))
            
        return jsonify({
            'message': 'Download successful',
            'filename': safe_filename,
            'title': info.get('title'),
            'duration': info.get('duration'),
            'thumbnail': info.get('thumbnail')
        })
        
    except yt_dlp.utils.DownloadError as e:
        return jsonify({'error': f'Download failed: {str(e)}'}), 400
    except yt_dlp.utils.ExtractorError as e:
        return jsonify({'error': f'URL extraction failed: {str(e)}'}), 400
    except Exception as e:
        return jsonify({'error': f'An unexpected error occurred: {str(e)}'}), 500

@app.route('/info', methods=['GET'])
def get_video_info():
    url = request.args.get('url')
    if not url:
        return jsonify({'error': 'No URL provided'}), 400
    
    try:
        with yt_dlp.YoutubeDL({'quiet': True}) as ydl:
            info = ydl.extract_info(url, download=False)
            
            # Simplify the info for response
            response_info = {
                'title': info.get('title'),
                'duration': info.get('duration'),
                'thumbnail': info.get('thumbnail'),
                'formats': [],
                'uploader': info.get('uploader'),
                'view_count': info.get('view_count'),
                'webpage_url': info.get('webpage_url')
            }
            
            # Add available formats
            if 'formats' in info:
                for fmt in info['formats']:
                    if fmt.get('ext') and fmt.get('url'):
                        response_info['formats'].append({
                            'format_id': fmt.get('format_id'),
                            'ext': fmt.get('ext'),
                            'resolution': fmt.get('resolution'),
                            'note': fmt.get('format_note'),
                            'filesize': fmt.get('filesize')
                        })
            
        return jsonify(response_info)
    except Exception as e:
        return jsonify({'error': str(e)}), 400

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
