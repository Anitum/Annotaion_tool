from flask import Flask, render_template_string, request, redirect, send_file
import os
from datetime import datetime
import glob
from pathlib import Path
import boto3

app = Flask(__name__)

# Configuration - Update these paths for your system
LOCAL_VIDEO_PATH = "/home/ubuntu/testWeb/Annotaion_tool/local_videos_data"  # Change this to your actual video directory
S3_BUCKET_NAME = "a2bvideos"       # Change this to your S3 bucket name
ALLOWED_EXTENSIONS = {'.mp4', '.avi', '.mov', '.mkv', '.wmv', '.flv', '.webm'}

# Initialize S3 client (configure AWS credentials separately)
try:
    s3_client = boto3.client('s3')
    S3_AVAILABLE = True
except:
    S3_AVAILABLE = False

def get_file_info(filepath):
    """Get file information from actual file"""
    try:
        stat = os.stat(filepath)
        size_mb = round(stat.st_size / (1024 * 1024), 1)
        created = datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M")
        return {
            "size": f"{size_mb}MB",
            "created": created,
            "path": filepath
        }
    except:
        return None

def scan_local_videos():
    """Scan local directory for video files"""
    videos = []
    if not os.path.exists(LOCAL_VIDEO_PATH):
        return videos
    
    try:
        for i, filepath in enumerate(glob.glob(os.path.join(LOCAL_VIDEO_PATH, "*")), 1):
            if Path(filepath).suffix.lower() in ALLOWED_EXTENSIONS:
                file_info = get_file_info(filepath)
                if file_info:
                    videos.append({
                        "id": i,
                        "filename": os.path.basename(filepath),
                        "size": file_info["size"],
                        "created": file_info["created"],
                        "path": filepath,
                        "labels": []  # You can implement label detection here
                    })
    except Exception as e:
        print(f"Error scanning local videos: {e}")
    
    return videos

def scan_s3_videos():
    """Scan S3 bucket for video files"""
    videos = []
    if not S3_AVAILABLE:
        return videos
    
    try:
        response = s3_client.list_objects_v2(Bucket=S3_BUCKET_NAME)
        if 'Contents' in response:
            for i, obj in enumerate(response['Contents'], 1):
                if Path(obj['Key']).suffix.lower() in ALLOWED_EXTENSIONS:
                    size_mb = round(obj['Size'] / (1024 * 1024), 1)
                    videos.append({
                        "id": i,
                        "filename": obj['Key'],
                        "size": f"{size_mb}MB",
                        "uploaded": obj['LastModified'].strftime("%Y-%m-%d %H:%M"),
                        "bucket": S3_BUCKET_NAME,
                        "key": obj['Key']
                    })
    except Exception as e:
        print(f"Error scanning S3 videos: {e}")
    
    return videos

# HTML Templates
BASE_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>Video Management System</title>
    <style>
        body { 
            font-family: Arial, sans-serif; 
            margin: 0; 
            padding: 20px; 
            background-color: #f5f5f5; 
        }
        .container { 
            max-width: 1200px; 
            margin: 0 auto; 
            background: white; 
            padding: 20px; 
            border-radius: 8px; 
            box-shadow: 0 2px 4px rgba(0,0,0,0.1); 
        }
        h1 { 
            color: #333; 
            border-bottom: 2px solid #007bff; 
            padding-bottom: 10px; 
        }
        h2 { 
            color: #555; 
            margin-top: 30px; 
        }
        .nav { 
            margin: 20px 0; 
            padding: 15px; 
            background-color: #e9ecef; 
            border-radius: 5px; 
        }
        .nav a { 
            display: inline-block; 
            margin-right: 15px; 
            padding: 8px 16px; 
            background-color: #007bff; 
            color: white; 
            text-decoration: none; 
            border-radius: 4px; 
        }
        .nav a:hover { 
            background-color: #0056b3; 
        }
        table { 
            width: 100%; 
            border-collapse: collapse; 
            margin: 20px 0; 
        }
        th, td { 
            border: 1px solid #ddd; 
            padding: 12px; 
            text-align: left; 
        }
        th { 
            background-color: #f8f9fa; 
            font-weight: bold; 
        }
        tr:nth-child(even) { 
            background-color: #f8f9fa; 
        }
        .status { 
            padding: 4px 8px; 
            border-radius: 4px; 
            font-size: 12px; 
        }
        .status.healthy { 
            background-color: #d4edda; 
            color: #155724; 
        }
        .status.warning { 
            background-color: #fff3cd; 
            color: #856404; 
        }
        .status.error { 
            background-color: #f8d7da; 
            color: #721c24; 
        }
        .labels { 
            font-size: 12px; 
            color: #666; 
        }
        .label-tag { 
            background-color: #e9ecef; 
            padding: 2px 6px; 
            border-radius: 3px; 
            margin-right: 4px; 
        }
        .form-group { 
            margin: 15px 0; 
        }
        label { 
            display: block; 
            margin-bottom: 5px; 
            font-weight: bold; 
        }
        input, select { 
            padding: 8px; 
            border: 1px solid #ddd; 
            border-radius: 4px; 
            width: 200px; 
        }
        button { 
            background-color: #28a745; 
            color: white; 
            padding: 10px 20px; 
            border: none; 
            border-radius: 4px; 
            cursor: pointer; 
        }
        button:hover { 
            background-color: #218838; 
        }
        .btn-danger { 
            background-color: #dc3545; 
        }
        .btn-danger:hover { 
            background-color: #c82333; 
        }
        .download-link { 
            color: #007bff; 
            text-decoration: none; 
        }
        .download-link:hover { 
            text-decoration: underline; 
        }
        .alert { 
            padding: 15px; 
            margin: 20px 0; 
            border-radius: 4px; 
        }
        .alert-info { 
            background-color: #d1ecf1; 
            color: #0c5460; 
            border: 1px solid #bee5eb; 
        }
        .alert-warning { 
            background-color: #fff3cd; 
            color: #856404; 
            border: 1px solid #ffeaa7; 
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>Video Management System</h1>
        <div class="nav">
            <a href="/">Home</a>
            <a href="/health">Health Check</a>
            <a href="/query/all">All Videos</a>
            <a href="/query/local">Local Videos</a>
            <a href="/query/s3">S3 Videos</a>
            <a href="/schedule">Schedule</a>
            <a href="/download/range">Download Range</a>
        </div>
        {% block content %}{% endblock %}
    </div>
</body>
</html>
"""

@app.route('/')
def home():
    local_count = len(scan_local_videos())
    s3_count = len(scan_s3_videos()) if S3_AVAILABLE else 0
    
    template = BASE_TEMPLATE.replace('{% block content %}{% endblock %}', f'''
        <h2>Welcome to Video Management System</h2>
        <div class="alert alert-info">
            <strong>System Status:</strong><br>
            Local Videos: {local_count} files<br>
            S3 Videos: {s3_count} files<br>
            S3 Connection: {'Available' if S3_AVAILABLE else 'Not configured'}
        </div>
        
        <p>Use the navigation above to access different features:</p>
        <ul>
            <li><strong>Health Check:</strong> System status</li>
            <li><strong>All Videos:</strong> Browse all videos (local + S3)</li>
            <li><strong>Local Videos:</strong> Browse videos stored locally</li>
            <li><strong>S3 Videos:</strong> Browse archived videos in cloud</li>
            <li><strong>Schedule:</strong> View and update upload schedule</li>
            <li><strong>Download Range:</strong> Download videos by date range</li>
        </ul>
        
        <div class="alert alert-warning">
            <strong>Configuration Required:</strong><br>
            Please update LOCAL_VIDEO_PATH in the code to point to your video directory.<br>
            Current path: {LOCAL_VIDEO_PATH}
        </div>
    ''')
    return render_template_string(template)

@app.route('/health')
def health():
    local_videos = scan_local_videos()
    s3_videos = scan_s3_videos() if S3_AVAILABLE else []
    
    local_status = "healthy" if os.path.exists(LOCAL_VIDEO_PATH) else "error"
    local_details = f"{len(local_videos)} videos available" if local_status == "healthy" else "Directory not found"
    
    s3_status = "healthy" if S3_AVAILABLE else "error"
    s3_details = f"{len(s3_videos)} videos in bucket" if S3_AVAILABLE else "S3 not configured"
    
    template = BASE_TEMPLATE.replace('{% block content %}{% endblock %}', f'''
        <h2>System Health Check</h2>
        <table>
            <tr>
                <th>Component</th>
                <th>Status</th>
                <th>Details</th>
            </tr>
            <tr>
                <td>Application</td>
                <td><span class="status healthy">Healthy</span></td>
                <td>Flask app running normally</td>
            </tr>
            <tr>
                <td>Local Storage</td>
                <td><span class="status {local_status}">{local_status.title()}</span></td>
                <td>{local_details}</td>
            </tr>
            <tr>
                <td>S3 Connection</td>
                <td><span class="status {s3_status}">{s3_status.title()}</span></td>
                <td>{s3_details}</td>
            </tr>
        </table>
    ''')
    return render_template_string(template)

@app.route('/query/all')
def query_all():
    local_videos = scan_local_videos()
    s3_videos = scan_s3_videos()
    
    all_videos_html = ""
    
    # Add local videos
    for video in local_videos:
        labels_html = " ".join([f'<span class="label-tag">{label}</span>' for label in video.get('labels', [])])
        all_videos_html += f'''
            <tr>
                <td>{video['id']}</td>
                <td>{video['filename']}</td>
                <td>{video['size']}</td>
                <td>{video['created']}</td>
                <td><span class="status healthy">Local</span></td>
                <td class="labels">{labels_html}</td>
                <td><a href="/download/local/{video['id']}" class="download-link">Download</a></td>
            </tr>
        '''
    
    # Add S3 videos
    for video in s3_videos:
        all_videos_html += f'''
            <tr>
                <td>{video['id']}</td>
                <td>{video['filename']}</td>
                <td>{video['size']}</td>
                <td>{video['uploaded']}</td>
                <td><span class="status warning">S3</span></td>
                <td>-</td>
                <td><a href="/download/s3/{video['id']}" class="download-link">Download</a></td>
            </tr>
        '''
    
    total_videos = len(local_videos) + len(s3_videos)
    
    template = BASE_TEMPLATE.replace('{% block content %}{% endblock %}', f'''
        <h2>All Videos (Local + S3)</h2>
        <p>Total videos across all storage: {total_videos} files</p>
        <table>
            <tr>
                <th>ID</th>
                <th>Filename</th>
                <th>Size</th>
                <th>Date</th>
                <th>Location</th>
                <th>Labels</th>
                <th>Action</th>
            </tr>
            {all_videos_html}
        </table>
    ''')
    return render_template_string(template)

@app.route('/query/local')
def query_local():
    videos = scan_local_videos()
    
    videos_html = ""
    for video in videos:
        labels_html = " ".join([f'<span class="label-tag">{label}</span>' for label in video.get('labels', [])])
        videos_html += f'''
            <tr>
                <td>{video['id']}</td>
                <td>{video['filename']}</td>
                <td>{video['size']}</td>
                <td>{video['created']}</td>
                <td class="labels">{labels_html}</td>
                <td><a href="/download/local/{video['id']}" class="download-link">Download</a></td>
            </tr>
        '''
    
    template = BASE_TEMPLATE.replace('{% block content %}{% endblock %}', f'''
        <h2>Local Videos</h2>
        <p>Videos stored on local system: {len(videos)} files</p>
        <p><strong>Scanning directory:</strong> {LOCAL_VIDEO_PATH}</p>
        <table>
            <tr>
                <th>ID</th>
                <th>Filename</th>
                <th>Size</th>
                <th>Created</th>
                <th>Labels</th>
                <th>Action</th>
            </tr>
            {videos_html}
        </table>
    ''')
    return render_template_string(template)

@app.route('/query/s3')
def query_s3():
    if not S3_AVAILABLE:
        template = BASE_TEMPLATE.replace('{% block content %}{% endblock %}', '''
            <h2>S3 Videos</h2>
            <div class="alert alert-warning">
                S3 is not configured. Please set up AWS credentials and update S3_BUCKET_NAME in the code.
            </div>
        ''')
        return render_template_string(template)
    
    videos = scan_s3_videos()
    
    videos_html = ""
    for video in videos:
        videos_html += f'''
            <tr>
                <td>{video['id']}</td>
                <td>{video['filename']}</td>
                <td>{video['size']}</td>
                <td>{video['uploaded']}</td>
                <td>{video['bucket']}</td>
                <td><a href="/download/s3/{video['id']}" class="download-link">Download</a></td>
            </tr>
        '''
    
    template = BASE_TEMPLATE.replace('{% block content %}{% endblock %}', f'''
        <h2>S3 Archived Videos</h2>
        <p>Videos stored in cloud: {len(videos)} files</p>
        <p><strong>Bucket:</strong> {S3_BUCKET_NAME}</p>
        <table>
            <tr>
                <th>ID</th>
                <th>Filename</th>
                <th>Size</th>
                <th>Uploaded</th>
                <th>Bucket</th>
                <th>Action</th>
            </tr>
            {videos_html}
        </table>
    ''')
    return render_template_string(template)

@app.route('/download/local/<int:video_id>')
def download_local(video_id):
    videos = scan_local_videos()
    video = next((v for v in videos if v['id'] == video_id), None)
    
    if not video:
        template = BASE_TEMPLATE.replace('{% block content %}{% endblock %}', '''
            <h2>Video Not Found</h2>
            <p>The requested video could not be found.</p>
            <a href="/query/local">Back to Local Videos</a>
        ''')
        return render_template_string(template), 404
    
    # Check if file exists
    if not os.path.exists(video['path']):
        template = BASE_TEMPLATE.replace('{% block content %}{% endblock %}', '''
            <h2>File Not Found</h2>
            <p>The video file no longer exists on disk.</p>
            <a href="/query/local">Back to Local Videos</a>
        ''')
        return render_template_string(template), 404
    
    # Serve the actual file
    try:
        return send_file(video['path'], as_attachment=True, download_name=video['filename'])
    except Exception as e:
        return f"Error downloading file: {str(e)}", 500

@app.route('/download/s3/<int:video_id>')
def download_s3(video_id):
    if not S3_AVAILABLE:
        return "S3 not configured", 500
    
    videos = scan_s3_videos()
    video = next((v for v in videos if v['id'] == video_id), None)
    
    if not video:
        template = BASE_TEMPLATE.replace('{% block content %}{% endblock %}', '''
            <h2>Video Not Found</h2>
            <p>The requested S3 video could not be found.</p>
            <a href="/query/s3">Back to S3 Videos</a>
        ''')
        return render_template_string(template), 404
    
    try:
        # Generate presigned URL for download
        url = s3_client.generate_presigned_url(
            'get_object',
            Params={'Bucket': S3_BUCKET_NAME, 'Key': video['key']},
            ExpiresIn=3600  # 1 hour
        )
        return redirect(url)
    except Exception as e:
        return f"Error downloading from S3: {str(e)}", 500

@app.route('/download/range', methods=['GET', 'POST'])
def download_range():
    if request.method == 'POST':
        start_date = request.form.get('start_date')
        end_date = request.form.get('end_date')
        source = request.form.get('source', 'all')
        
        matching_videos = []
        
        if source in ['all', 'local']:
            local_videos = scan_local_videos()
            for video in local_videos:
                video_date = video['created'].split(' ')[0]
                if start_date <= video_date <= end_date:
                    matching_videos.append({
                        'filename': video['filename'],
                        'date': video['created'],
                        'size': video['size'],
                        'location': 'Local',
                        'download_url': f"/download/local/{video['id']}"
                    })
        
        if source in ['all', 's3'] and S3_AVAILABLE:
            s3_videos = scan_s3_videos()
            for video in s3_videos:
                video_date = video['uploaded'].split(' ')[0]
                if start_date <= video_date <= end_date:
                    matching_videos.append({
                        'filename': video['filename'],
                        'date': video['uploaded'],
                        'size': video['size'],
                        'location': 'S3',
                        'download_url': f"/download/s3/{video['id']}"
                    })
        
        videos_html = ""
        total_size = 0
        for video in matching_videos:
            try:
                size_mb = float(video['size'].replace('MB', ''))
                total_size += size_mb
            except:
                pass
            
            videos_html += f'''
                <tr>
                    <td>{video['filename']}</td>
                    <td>{video['date']}</td>
                    <td>{video['size']}</td>
                    <td>{video['location']}</td>
                    <td><a href="{video['download_url']}" class="download-link">Download</a></td>
                </tr>
            '''
        
        if not matching_videos:
            videos_html = '<tr><td colspan="5">No videos found in the specified date range.</td></tr>'
        
        template = BASE_TEMPLATE.replace('{% block content %}{% endblock %}', f'''
            <h2>Download Range Results</h2>
            <p>Searching for videos between {start_date} and {end_date} (Source: {source.title()})</p>
            <p><strong>Found {len(matching_videos)} videos matching criteria (Total: {total_size:.1f}MB)</strong></p>
            <table>
                <tr><th>Filename</th><th>Date</th><th>Size</th><th>Location</th><th>Action</th></tr>
                {videos_html}
            </table>
            <a href="/download/range">New Search</a>
        ''')
        return render_template_string(template)
    
    template = BASE_TEMPLATE.replace('{% block content %}{% endblock %}', '''
        <h2>Download Videos by Date Range</h2>
        <form method="post">
            <div class="form-group">
                <label for="start_date">Start Date:</label>
                <input type="date" id="start_date" name="start_date" required>
            </div>
            <div class="form-group">
                <label for="end_date">End Date:</label>
                <input type="date" id="end_date" name="end_date" required>
            </div>
            <div class="form-group">
                <label for="source">Video Source:</label>
                <select name="source" id="source">
                    <option value="all">All (Local + S3)</option>
                    <option value="local">Local Only</option>
                    <option value="s3">S3 Only</option>
                </select>
            </div>
            <button type="submit">Search Videos</button>
        </form>
    ''')
    return render_template_string(template)

@app.route('/schedule')
def schedule():
    template = BASE_TEMPLATE.replace('{% block content %}{% endblock %}', '''
        <h2>Upload Schedule</h2>
        <div class="alert alert-info">
            This feature would integrate with your backup system to schedule automatic uploads to S3.
            Implementation depends on your specific backup requirements.
        </div>
    ''')
    return render_template_string(template)

@app.route('/upload/manual', methods=['POST'])
def upload_manual():
    template = BASE_TEMPLATE.replace('{% block content %}{% endblock %}', '''
        <h2>Manual Upload</h2>
        <div class="alert alert-info">
            Manual upload feature would be implemented here based on your S3 upload requirements.
        </div>
    ''')
    return render_template_string(template)

if __name__ == '__main__':
    print(f"Starting Video Management System...")
    print(f"Local video path: {LOCAL_VIDEO_PATH}")
    print(f"S3 bucket: {S3_BUCKET_NAME}")
    print(f"S3 available: {S3_AVAILABLE}")
    app.run(debug=True, host='0.0.0.0', port=5000)