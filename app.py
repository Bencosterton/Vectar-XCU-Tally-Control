from flask import Flask, render_template, jsonify, request
import requests
from requests.auth import HTTPDigestAuth
import xml.etree.ElementTree as ET
from datetime import datetime
import threading
import time
import subprocess
import os
import json

app = Flask(__name__)

# Configuration
VECTAR_IP = "INSERT-YOUR-VECTAR-IP-HERE"
SWITCHER_URL = f"http://{VECTAR_IP}/v1/dictionary?key=switcher"
TALLY_URL = f"http://{VECTAR_IP}/v1/dictionary?key=tally"
UPDATE_INTERVAL = 1 

# Path to the camera-to-XCU mapping file
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_FILE = os.path.join(SCRIPT_DIR, "camera_mapping.json")

# Default Camera to XCU mapping
DEFAULT_CAMERA_TO_XCU = {
    'input1': 'XCU-01',
    'input2': 'XCU-02',
    'input3': 'XCU-03',
    'input4': 'XCU-04',
    'input5': 'XCU-05',
    'input6': 'XCU-06',
    'input7': 'XCU-07',
    'input8': 'XCU-08',
}

# Load camera mapping from the json
def load_camera_mapping():
    global CAMERA_TO_XCU
    try:
        if os.path.exists(CONFIG_FILE):
            with open(CONFIG_FILE, 'r') as f:
                CAMERA_TO_XCU = json.load(f)
            print(f"Loaded camera mapping from {CONFIG_FILE}: {CAMERA_TO_XCU}")
        else:
            CAMERA_TO_XCU = DEFAULT_CAMERA_TO_XCU
            # Save default mapping to the json file
            with open(CONFIG_FILE, 'w') as f:
                json.dump(CAMERA_TO_XCU, f, indent=4)
            print(f"Created default camera mapping file: {CONFIG_FILE}")
    except Exception as e:
        print(f"Error loading camera mapping: {e}")
        CAMERA_TO_XCU = DEFAULT_CAMERA_TO_XCU

# load mapping
CAMERA_TO_XCU = {}

# Authentication credentials
VECTAR_USER = 'admin'
VECTAR_PASS = 'password'

# Cauth with Digest Authentication
auth = HTTPDigestAuth(VECTAR_USER, VECTAR_PASS)

# Headers
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
    'Accept': 'application/xml'
}

# Global variables to store the current state
current_state = {
    'program': [],  # List of program sources
    'preview': None,  # Single preview source
    'last_update': None,
    'status': 'Not Connected'
}

# Track tally states (Global Variables)
tally_states = {}

# Path to gv_tally_control.py
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
GV_TALLY_SCRIPT = os.path.join(SCRIPT_DIR, "gv_tally_control.py")

def send_tally_command(xcu, tally_type, state):
    """
    Send tally command to a specific XCU using gv_tally_control.py
    
    Args:
        xcu: XCU identifier (e.g., XCU-09)
        tally_type: Type of tally (red, green, yellow)
        state: Tally state (True for on, False for off)
    """
    if not xcu:
        print(f"No XCU specified for tally command")
        return
    
    # Convert boolean to on/off string
    state_str = "on" if state else "off"
    
    cmd = [
        "python", 
        GV_TALLY_SCRIPT,
        f"--xcu", xcu,
        f"--{tally_type}", state_str
    ]
    
    # Log command
    print(f"Sending {tally_type} tally {state_str} command to {xcu}")
    
    try:
        # Execute command
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=True
        )
        print(f"Successfully sent {tally_type} tally {state_str} to {xcu}")
        return True
    except subprocess.CalledProcessError as e:
        print(f"Error sending tally command: {e.stderr}")
        return False

def get_source_labels(session):
    """Get the friendly names for all inputs from switcher endpoint"""
    try:
        response = session.get(SWITCHER_URL, auth=auth, headers=HEADERS, timeout=5)
        if response.status_code == 200:
            root = ET.fromstring(response.text)
            labels = {}
            
            # Process inputs
            for input_elem in root.findall('.//physical_input'):
                input_num = input_elem.get('physical_input_number').lower()  # word styles etc.
                label = input_elem.get('iso_label')
                labels[input_num] = label
                
            return labels
        else:
            print(f"Error getting labels: HTTP {response.status_code}")
            return {}
    except Exception as e:
        print(f"Error getting labels: {e}")
        return {}

def get_tally_state(session, labels):
    """Get the current tally state from tally endpoint"""
    try:
        response = session.get(TALLY_URL, auth=auth, headers=HEADERS, timeout=5)
        if response.status_code == 200:
            root = ET.fromstring(response.text)
            
            # Find all sources that are on program or preview
            program_sources = []
            preview_source = None
            
            for column in root.findall('.//column'):
                name = column.get('name')
                on_pgm = column.get('on_pgm') == 'true'
                on_prev = column.get('on_prev') == 'true'
                
                # Get friendly name if someone has been kind enough to put them anywhere
                friendly_name = labels.get(name, name)
                
                if on_pgm:
                    program_sources.append({
                        'source': name,
                        'label': friendly_name
                    })
                if on_prev:
                    preview_source = {
                        'source': name,
                        'label': friendly_name
                    }
            
            return program_sources, preview_source
        else:
            print(f"Error getting tally: HTTP {response.status_code}")
            return [], None
    except Exception as e:
        print(f"Error getting tally: {e}")
        return [], None

def initialize_tally_states():
    """Initialize the tally states dictionary based on current camera mapping"""
    global tally_states
    tally_states = {}
    for camera in CAMERA_TO_XCU:
        tally_states[camera] = {
            'red': False,
            'green': False
        }

def update_tally_state():
    """Fetch and parse the XML data from Vectar"""
    global tally_states
    
    # initialize tally states dictionary
    initialize_tally_states()
    
    while True:
        try:
            # all the coockies
            session = requests.Session()
            
            # get labels then telly state
            labels = get_source_labels(session)
            program_sources, preview_source = get_tally_state(session, labels)
            
            # update global state
            current_state['program'] = program_sources
            current_state['preview'] = preview_source
            current_state['last_update'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            current_state['status'] = 'Connected'
            
            # Ddbug output
            print("\nCurrent State:")
            print(f"Program Sources: {[p['label'] for p in program_sources]}")
            print(f"Preview Source: {preview_source['label'] if preview_source else 'None'}")
            
            # Update tally lights based on program and preview sources
            # Extract source names from program_sources
            program_source_names = [p['source'] for p in program_sources]
            preview_source_name = preview_source['source'] if preview_source else None
            
            # Process each camera
            for camera, xcu in CAMERA_TO_XCU.items():
                should_be_red = camera in program_source_names
                should_be_green = camera == preview_source_name
                
                # Check if rtally is red, does it need change
                if tally_states[camera]['red'] != should_be_red:
                    send_tally_command(xcu, 'red', should_be_red)
                    tally_states[camera]['red'] = should_be_red
                
                # here is green data also becuase a function exists... don't know if I want it...
                if tally_states[camera]['green'] != should_be_green:
                    send_tally_command(xcu, 'green', should_be_green)
                    tally_states[camera]['green'] = should_be_green
                
        except Exception as e:
            print(f"Error updating state: {e}")
            current_state['status'] = f'Error: {str(e)}'
        
        # patience.....
        time.sleep(UPDATE_INTERVAL)

@app.route('/')
def index():
    return render_template('index.html', state=current_state)

@app.route('/status')
def status():
    return jsonify(current_state)

@app.route('/camera-mapping')
def get_camera_mapping():
    """Get the current camera-to-XCU mapping"""
    return jsonify(CAMERA_TO_XCU)

@app.route('/camera-mapping', methods=['POST'])
def update_camera_mapping():
    """Update the camera-to-XCU mapping"""
    global CAMERA_TO_XCU
    try:
        # Get the updated mapping from request
        new_mapping = request.json
    
        for key, value in new_mapping.items():
            if not isinstance(key, str) or not isinstance(value, str):
                return jsonify({'status': 'error', 'message': 'Invalid mapping format'}), 400
            if not key.startswith('input'):
                return jsonify({'status': 'error', 'message': 'Input keys must start with "input"'}), 400
            if not value.startswith('XCU-'):
                return jsonify({'status': 'error', 'message': 'XCU values must start with "XCU-"'}), 400
        
        # update mapping
        CAMERA_TO_XCU = new_mapping
        
        # save mapping
        with open(CONFIG_FILE, 'w') as f:
            json.dump(CAMERA_TO_XCU, f, indent=4)
        
        # update tally states with new mapping
        initialize_tally_states()
        
        return jsonify({'status': 'success', 'message': 'Camera mapping updated successfully'})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

if __name__ == '__main__':
    # load camera mapping from the json
    load_camera_mapping()
    
    # start the background thread for updating tally state
    update_thread = threading.Thread(target=update_tally_state, daemon=True)
    update_thread.start()
    
    app.run(host='0.0.0.0', port=5000, debug=True)
