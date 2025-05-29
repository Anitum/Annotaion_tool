from flask import Flask, render_template, request, jsonify, send_file, redirect, url_for
import os
import cv2
import numpy as np
from PIL import Image, ImageDraw
import glob
import json
import time
import fcntl  # For file locking to handle concurrent updates
import random
import string

app = Flask(__name__)

BASE_DIR = '/home/ubuntu/runs/detect/predict8'
FRAMES_DIR = os.path.join(BASE_DIR)
LABELS_DIR = os.path.join(BASE_DIR, '3MB')

# Define colors for different classes (0-5)
CLASS_COLORS = {
    0: (255, 0, 0),    # Red
    1: (0, 255, 0),    # Green
    2: (0, 0, 255),    # Blue
    3: (255, 255, 0),  # Yellow
    4: (255, 0, 255),  # Magenta
    5: (0, 255, 255),  # Cyan
}

def get_all_videos():
    """Get all video folders that have _frames suffix"""
    video_dirs = [d for d in os.listdir(FRAMES_DIR) 
                 if os.path.isdir(os.path.join(FRAMES_DIR, d)) and d.endswith('_frames')]
    # Remove the _frames suffix
    videos = [v.replace('_frames', '') for v in video_dirs]
    return sorted(videos)

def get_frames_for_video(video_name):
    """Get all frame paths for a specific video"""
    frames_dir = os.path.join(FRAMES_DIR, f"{video_name}_frames")
    if not os.path.exists(frames_dir):
        return []
    
    frames = glob.glob(os.path.join(frames_dir, '*.jpg'))
    return sorted(frames, key=lambda x: int(os.path.basename(x).split('.')[0]))

def get_label_path(video_name, frame_number):
    """Get path to label file for a specific frame"""
    label_path = os.path.join(LABELS_DIR, f"{video_name}_{frame_number}.txt")
    if os.path.exists(label_path):
        return label_path
    return None

def parse_label_file(label_path):
    """Parse label file and return list of bounding boxes"""
    boxes = []
    if label_path and os.path.exists(label_path):
        try:
            with open(label_path, 'r') as f:
                # Acquire a shared lock for reading
                fcntl.flock(f, fcntl.LOCK_SH)
                for i, line in enumerate(f):
                    parts = line.strip().split()
                    if len(parts) >= 5:
                        box = {
                            'id': i,
                            'class_id': int(parts[0]),
                            'x_center': float(parts[1]),
                            'y_center': float(parts[2]),
                            'width': float(parts[3]),
                            'height': float(parts[4])
                        }
                        boxes.append(box)
                # Release the lock
                fcntl.flock(f, fcntl.LOCK_UN)
        except Exception as e:
            print(f"Error reading label file {label_path}: {e}")
    return boxes

def save_label_file(label_path, boxes):
    """Save updated boxes to label file with proper locking for multi-user safety"""
    # Maximum number of retries if file is locked
    max_retries = 5
    retry_delay = 0.2  # seconds
    
    for attempt in range(max_retries):
        try:
            # Write to a temporary file first
            temp_path = f"{label_path}.tmp.{random_string(8)}"
            with open(temp_path, 'w') as f:
                # Acquire an exclusive lock
                fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
                
                for box in boxes:
                    line = f"{box['class_id']} {box['x_center']} {box['y_center']} {box['width']} {box['height']}\n"
                    f.write(line)
                
                # Flush to disk before releasing lock
                f.flush()
                os.fsync(f.fileno())
                fcntl.flock(f, fcntl.LOCK_UN)
                
            # Atomically replace the old file with the new file
            os.rename(temp_path, label_path)
            return True
            
        except IOError as e:
            if e.errno == 11:  # Resource temporarily unavailable (would block)
                print(f"File {label_path} is locked, retrying... (attempt {attempt+1}/{max_retries})")
                time.sleep(retry_delay)
                continue
            else:
                print(f"Error saving label file {label_path}: {e}")
                # Clean up the temp file if it exists
                if os.path.exists(temp_path):
                    try:
                        os.remove(temp_path)
                    except:
                        pass
                return False
                
        except Exception as e:
            print(f"Error saving label file {label_path}: {e}")
            # Clean up the temp file if it exists
            if os.path.exists(temp_path):
                try:
                    os.remove(temp_path)
                except:
                    pass
            return False
    
    # If we've exhausted all retries
    print(f"Failed to save {label_path} after {max_retries} attempts")
    return False

def random_string(length):
    """Generate a random string for temporary files"""
    return ''.join(random.choice(string.ascii_letters + string.digits) for _ in range(length))

def draw_bounding_boxes(image_path, label_path, timestamp=None):
    """Draw bounding boxes from label file onto image"""
    if not os.path.exists(image_path):
        return None, []
    
    # Read the image
    img = cv2.imread(image_path)
    if img is None:
        return None, []
        
    img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
    height, width, _ = img.shape
    
    # Convert to PIL Image for drawing
    pil_img = Image.fromarray(img)
    draw = ImageDraw.Draw(pil_img)
    
    boxes = []
    
    # If label exists, draw bounding boxes
    if label_path and os.path.exists(label_path):
        parsed_boxes = parse_label_file(label_path)
        
        for box in parsed_boxes:
            class_id = box['class_id']
            x_center = box['x_center'] * width
            y_center = box['y_center'] * height
            w = box['width'] * width
            h = box['height'] * height
            
            # Calculate box coordinates
            x1 = x_center - w/2
            y1 = y_center - h/2
            x2 = x_center + w/2
            y2 = y_center + h/2
            
            # Get color for this class
            color = CLASS_COLORS.get(class_id, (128, 128, 128))  # Default to gray if class not in colors
            
            # Convert color tuple to hex for PIL
            hex_color = "#{:02x}{:02x}{:02x}".format(*color)
            
            # Draw rectangle
            draw.rectangle([x1, y1, x2, y2], outline=hex_color, width=3)
            
            # Display class ID
            font_size = max(12, int(h/10))
            try:
                from PIL import ImageFont
                font = ImageFont.truetype("arial.ttf", font_size)
            except:
                font = None
                
            draw.text((x1+2, y1+2), f"Class {class_id}", fill=hex_color, font=font)
            
            # Store box info for frontend
            boxes.append({
                'id': box['id'],
                'class_id': class_id,
                'coords': {
                    'x1': int(x1),
                    'y1': int(y1),
                    'x2': int(x2),
                    'y2': int(y2)
                }
            })
    
    # Convert back to numpy array
    result_img = np.array(pil_img)
    
    # Convert back to BGR for cv2.imwrite
    result_img = cv2.cvtColor(result_img, cv2.COLOR_RGB2BGR)
    
    # Use timestamp in filename to avoid browser caching
    cache_key = timestamp if timestamp else int(time.time())
    temp_path = os.path.join('/tmp', f"{os.path.basename(image_path)}.{cache_key}.jpg")
    cv2.imwrite(temp_path, result_img)
    
    return temp_path, boxes

@app.route('/')
def index():
    videos = get_all_videos()
    return render_template('index.html', videos=videos)

@app.route('/view/<video_name>')
def view_video(video_name):
    videos = get_all_videos()
    current_index = videos.index(video_name) if video_name in videos else 0
    
    frames = get_frames_for_video(video_name)
    if not frames:
        return "No frames found for this video", 404
    
    frame_numbers = [os.path.basename(f).split('.')[0] for f in frames]
    
    # Get next video for auto-progression
    next_video = None
    if current_index < len(videos) - 1:
        next_video = videos[current_index + 1]
    
    return render_template('viewer.html', 
                          video_name=video_name, 
                          frames=frames,
                          frame_numbers=frame_numbers,
                          total_frames=len(frames),
                          next_video=next_video,
                          class_colors=CLASS_COLORS)

@app.route('/frame/<video_name>/<frame_number>')
def get_frame(video_name, frame_number):
    """Get frame image with bounding boxes drawn on it"""
    frames_dir = os.path.join(FRAMES_DIR, f"{video_name}_frames")
    image_path = os.path.join(frames_dir, f"{frame_number}.jpg")
    label_path = get_label_path(video_name, frame_number)
    
    # Add timestamp to prevent browser caching
    timestamp = request.args.get('ts', int(time.time()))
    
    # Draw boxes on image
    processed_image, _ = draw_bounding_boxes(image_path, label_path, timestamp)
    
    if processed_image:
        return send_file(processed_image, mimetype='image/jpeg')
    else:
        return "Image not found", 404

@app.route('/boxes/<video_name>/<frame_number>')
def get_boxes(video_name, frame_number):
    """Get bounding box data for a frame"""
    label_path = get_label_path(video_name, frame_number)
    boxes = parse_label_file(label_path)
    
    # Get image dimensions to calculate absolute coordinates
    frames_dir = os.path.join(FRAMES_DIR, f"{video_name}_frames")
    image_path = os.path.join(frames_dir, f"{frame_number}.jpg")
    img = cv2.imread(image_path)
    
    if img is None:
        return jsonify([])
    
    height, width, _ = img.shape
    
    # Add pixel coordinates for frontend
    for box in boxes:
        x_center = box['x_center'] * width
        y_center = box['y_center'] * height
        w = box['width'] * width
        h = box['height'] * height
        
        box['coords'] = {
            'x1': int(x_center - w/2),
            'y1': int(y_center - h/2),
            'x2': int(x_center + w/2),
            'y2': int(y_center + h/2)
        }
    
    return jsonify(boxes)

@app.route('/update_class', methods=['POST'])
def update_class():
    """Update class ID for a bounding box"""
    data = request.json
    video_name = data.get('video_name')
    frame_number = data.get('frame_number')
    box_id = data.get('box_id')
    new_class_id = data.get('new_class_id')
    
    label_path = get_label_path(video_name, frame_number)
    if not label_path:
        return jsonify({'success': False, 'error': 'Label file not found'})
    
    # Parse label file
    boxes = parse_label_file(label_path)
    
    # Update class for the specified box
    found = False
    for box in boxes:
        if box['id'] == box_id:
            box['class_id'] = new_class_id
            found = True
            break
    
    if not found:
        return jsonify({'success': False, 'error': 'Box not found'})
    
    # Save updated label file
    if save_label_file(label_path, boxes):
        # Return a timestamp for cache-busting the image
        timestamp = int(time.time())
        return jsonify({'success': True, 'timestamp': timestamp})
    else:
        return jsonify({'success': False, 'error': 'Failed to save label file'})

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5000, debug=True)
