from flask import Flask, render_template, request, jsonify, send_file, redirect, url_for
import os
import cv2
import numpy as np
from PIL import Image, ImageDraw
import glob
import json
import time
import fcntl
import random
import string
from datetime import datetime

app = Flask(__name__)

BASE_DIR = '/home/ubuntu/runs/detect/predict8'
FRAMES_DIR = os.path.join(BASE_DIR)
LABELS_DIR = os.path.join(BASE_DIR, '3MB')
CONFIG_FILE = 'config.json'
CLASSES_IMAGES_DIR = 'class_images'
ANNOTATIONS_DIR = 'annotations'

# Default configuration
DEFAULT_CONFIG = {
    "max_frames_per_video": 10,
    "sampling_strategy": "first",
    "classes": {
        "0": "Person",
        "1": "Vehicle", 
        "2": "Animal",
        "3": "Object",
        "4": "Building",
        "5": "Other",
        "6": "Class 6",
        "7": "Class 7",
        "8": "Class 8",
        "9": "Class 9"
    },
    "class_colors": {
        "0": [255, 0, 0],
        "1": [0, 255, 0],
        "2": [0, 0, 255],
        "3": [255, 255, 0],
        "4": [255, 0, 255],
        "5": [0, 255, 255],
        "6": [128, 0, 128],
        "7": [255, 128, 0],
        "8": [128, 255, 0],
        "9": [0, 128, 255]
    }
}

def load_config():
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r') as f:
                config = json.load(f)
                for key, value in DEFAULT_CONFIG.items():
                    if key not in config:
                        config[key] = value
                return config
        except Exception as e:
            print(f"Error loading config: {e}")
    
    save_config(DEFAULT_CONFIG)
    return DEFAULT_CONFIG.copy()

def save_config(config):
    try:
        with open(CONFIG_FILE, 'w') as f:
            json.dump(config, f, indent=4)
        return True
    except Exception as e:
        print(f"Error saving config: {e}")
        return False

def ensure_directories():
    os.makedirs(ANNOTATIONS_DIR, exist_ok=True)
    os.makedirs(CLASSES_IMAGES_DIR, exist_ok=True)

def get_all_videos():
    video_dirs = [d for d in os.listdir(FRAMES_DIR) 
                 if os.path.isdir(os.path.join(FRAMES_DIR, d)) and d.endswith('_frames')]
    videos = [v.replace('_frames', '') for v in video_dirs]
    return sorted(videos)

def sample_frames(frames, max_frames, strategy="first"):
    if len(frames) <= max_frames:
        return frames
    
    if strategy == "first":
        return frames[:max_frames]
    elif strategy == "uniform":
        indices = np.linspace(0, len(frames)-1, max_frames, dtype=int)
        return [frames[i] for i in indices]
    elif strategy == "random":
        return random.sample(frames, max_frames)
    else:
        return frames[:max_frames]

def get_frames_for_video(video_name):
    config = load_config()
    frames_dir = os.path.join(FRAMES_DIR, f"{video_name}_frames")
    if not os.path.exists(frames_dir):
        return []
    
    all_frames = glob.glob(os.path.join(frames_dir, '*.jpg'))
    all_frames = sorted(all_frames, key=lambda x: int(os.path.basename(x).split('.')[0]))
    
    max_frames = config.get('max_frames_per_video', 10)
    strategy = config.get('sampling_strategy', 'first')
    
    return sample_frames(all_frames, max_frames, strategy)

def get_annotation_path(video_name, frame_number):
    annotation_file = f"{video_name}_{frame_number}.txt"
    annotation_path = os.path.join(ANNOTATIONS_DIR, annotation_file)
    return annotation_path

def get_original_label_path(video_name, frame_number):
    label_path = os.path.join(LABELS_DIR, f"{video_name}_{frame_number}.txt")
    if os.path.exists(label_path):
        return label_path
    return None

def parse_label_file(label_path):
    boxes = []
    if label_path and os.path.exists(label_path):
        try:
            with open(label_path, 'r') as f:
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
                fcntl.flock(f, fcntl.LOCK_UN)
        except Exception as e:
            print(f"Error reading label file {label_path}: {e}")
    return boxes

def load_existing_annotations(video_name, frame_number):
    annotation_path = get_annotation_path(video_name, frame_number)
    if os.path.exists(annotation_path):
        return parse_label_file(annotation_path)
    
    original_path = get_original_label_path(video_name, frame_number)
    if original_path:
        return parse_label_file(original_path)
    
    return []

def save_annotation_file(video_name, frame_number, boxes):
    annotation_path = get_annotation_path(video_name, frame_number)
    
    try:
        temp_path = f"{annotation_path}.tmp.{random_string(8)}"
        with open(temp_path, 'w') as f:
            for i, box in enumerate(boxes):
                box['id'] = i
                line = f"{box['class_id']} {box['x_center']} {box['y_center']} {box['width']} {box['height']}\n"
                f.write(line)
        
        os.rename(temp_path, annotation_path)
        return True
    except Exception as e:
        print(f"Error saving annotation file {annotation_path}: {e}")
        return False

def random_string(length):
    return ''.join(random.choice(string.ascii_letters + string.digits) for _ in range(length))

def draw_bounding_boxes(image_path, video_name, frame_number, timestamp=None):
    if not os.path.exists(image_path):
        return None, []
    
    config = load_config()
    
    img = cv2.imread(image_path)
    if img is None:
        return None, []
        
    img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
    height, width, _ = img.shape
    
    pil_img = Image.fromarray(img)
    draw = ImageDraw.Draw(pil_img)
    
    boxes = []
    parsed_boxes = load_existing_annotations(video_name, frame_number)
    
    for box in parsed_boxes:
        class_id = box['class_id']
        x_center = box['x_center'] * width
        y_center = box['y_center'] * height
        w = box['width'] * width
        h = box['height'] * height
        
        x1 = max(0, x_center - w/2)
        y1 = max(0, y_center - h/2)
        x2 = min(width, x_center + w/2)
        y2 = min(height, y_center + h/2)
        
        class_colors = config.get('class_colors', {})
        color = tuple(class_colors.get(str(class_id), [128, 128, 128]))
        
        hex_color = "#{:02x}{:02x}{:02x}".format(*color)
        
        if x2 > x1 and y2 > y1:
            draw.rectangle([x1, y1, x2, y2], outline=hex_color, width=3)
            
            class_name = config.get('classes', {}).get(str(class_id), f"Class {class_id}")
            draw.text((x1+2, y1+2), f"{class_name}", fill=hex_color)
            
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
    
    result_img = np.array(pil_img)
    result_img = cv2.cvtColor(result_img, cv2.COLOR_RGB2BGR)
    
    cache_key = timestamp if timestamp else int(time.time())
    temp_path = os.path.join('/tmp', f"{os.path.basename(image_path)}.{cache_key}.jpg")
    cv2.imwrite(temp_path, result_img)
    
    return temp_path, boxes

@app.route('/')
def index():
    videos = get_all_videos()
    config = load_config()
    return render_template('index.html', videos=videos, config=config)

@app.route('/view/<video_name>')
def view_video(video_name):
    ensure_directories()
    config = load_config()
    videos = get_all_videos()
    current_index = videos.index(video_name) if video_name in videos else 0
    
    frames = get_frames_for_video(video_name)
    if not frames:
        return "No frames found for this video", 404
    
    frame_numbers = [os.path.basename(f).split('.')[0] for f in frames]
    
    next_video = None
    if current_index < len(videos) - 1:
        next_video = videos[current_index + 1]
    
    return render_template('viewer.html', 
                          video_name=video_name, 
                          frames=frames,
                          frame_numbers=frame_numbers,
                          total_frames=len(frames),
                          next_video=next_video,
                          config=config)

@app.route('/frame/<video_name>/<frame_number>')
def get_frame(video_name, frame_number):
    frames_dir = os.path.join(FRAMES_DIR, f"{video_name}_frames")
    image_path = os.path.join(frames_dir, f"{frame_number}.jpg")
    
    timestamp = request.args.get('ts', int(time.time()))
    
    processed_image, _ = draw_bounding_boxes(image_path, video_name, frame_number, timestamp)
    
    if processed_image:
        return send_file(processed_image, mimetype='image/jpeg')
    else:
        return "Image not found", 404

@app.route('/boxes/<video_name>/<frame_number>')
def get_boxes(video_name, frame_number):
    boxes = load_existing_annotations(video_name, frame_number)
    
    frames_dir = os.path.join(FRAMES_DIR, f"{video_name}_frames")
    image_path = os.path.join(frames_dir, f"{frame_number}.jpg")
    img = cv2.imread(image_path)
    
    if img is None:
        return jsonify([])
    
    height, width, _ = img.shape
    
    for box in boxes:
        x_center = box['x_center'] * width
        y_center = box['y_center'] * height
        w = box['width'] * width
        h = box['height'] * height
        
        x1 = max(0, x_center - w/2)
        y1 = max(0, y_center - h/2)
        x2 = min(width, x_center + w/2)
        y2 = min(height, y_center + h/2)
        
        box['coords'] = {
            'x1': int(x1),
            'y1': int(y1),
            'x2': int(x2),
            'y2': int(y2)
        }
    
    return jsonify(boxes)

@app.route('/update_class', methods=['POST'])
def update_class():
    data = request.json
    video_name = data.get('video_name')
    frame_number = data.get('frame_number')
    box_id = data.get('box_id')
    new_class_id = data.get('new_class_id')
    
    boxes = load_existing_annotations(video_name, frame_number)
    
    found = False
    for box in boxes:
        if box['id'] == box_id:
            box['class_id'] = new_class_id
            found = True
            break
    
    if not found:
        return jsonify({'success': False, 'error': 'Box not found'})
    
    if save_annotation_file(video_name, frame_number, boxes):
        timestamp = int(time.time())
        return jsonify({'success': True, 'timestamp': timestamp})
    else:
        return jsonify({'success': False, 'error': 'Failed to save annotation file'})

@app.route('/add_box', methods=['POST'])
def add_box():
    data = request.json
    video_name = data.get('video_name')
    frame_number = data.get('frame_number')
    x1 = data.get('x1')
    y1 = data.get('y1')
    x2 = data.get('x2')
    y2 = data.get('y2')
    class_id = data.get('class_id', 0)
    
    frames_dir = os.path.join(FRAMES_DIR, f"{video_name}_frames")
    image_path = os.path.join(frames_dir, f"{frame_number}.jpg")
    img = cv2.imread(image_path)
    
    if img is None:
        return jsonify({'success': False, 'error': 'Image not found'})
    
    height, width, _ = img.shape
    
    # Convert to normalized coordinates
    x_center = (x1 + x2) / 2 / width
    y_center = (y1 + y2) / 2 / height
    box_width = abs(x2 - x1) / width
    box_height = abs(y2 - y1) / height
    
    boxes = load_existing_annotations(video_name, frame_number)
    
    new_box = {
        'id': len(boxes),
        'class_id': class_id,
        'x_center': x_center,
        'y_center': y_center,
        'width': box_width,
        'height': box_height
    }
    
    boxes.append(new_box)
    
    if save_annotation_file(video_name, frame_number, boxes):
        timestamp = int(time.time())
        return jsonify({'success': True, 'timestamp': timestamp, 'box_id': len(boxes)-1})
    else:
        return jsonify({'success': False, 'error': 'Failed to save annotation file'})

@app.route('/delete_box', methods=['POST'])
def delete_box():
    data = request.json
    video_name = data.get('video_name')
    frame_number = data.get('frame_number')
    box_id = data.get('box_id')
    
    boxes = load_existing_annotations(video_name, frame_number)
    
    original_count = len(boxes)
    boxes = [box for box in boxes if box['id'] != box_id]
    
    if len(boxes) == original_count:
        return jsonify({'success': False, 'error': 'Box not found'})
    
    if save_annotation_file(video_name, frame_number, boxes):
        timestamp = int(time.time())
        return jsonify({'success': True, 'timestamp': timestamp})
    else:
        return jsonify({'success': False, 'error': 'Failed to save annotation file'})

@app.route('/class_image/<class_id>')
def get_class_image(class_id):
    image_path = os.path.join(CLASSES_IMAGES_DIR, f"{class_id}.jpg")
    if os.path.exists(image_path):
        return send_file(image_path, mimetype='image/jpeg')
    else:
        return "Class image not found", 404

@app.route('/config')
def get_config():
    config = load_config()
    return jsonify(config)

@app.route('/config', methods=['POST'])
def update_config():
    try:
        new_config = request.json
        if save_config(new_config):
            return jsonify({'success': True})
        else:
            return jsonify({'success': False, 'error': 'Failed to save config'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

if __name__ == "__main__":
    ensure_directories()
    app.run(host='0.0.0.0', port=5000, debug=True)
