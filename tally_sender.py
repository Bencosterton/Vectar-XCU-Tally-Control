#!/usr/bin/env python3
"""
TallySender - Handles sending tally commands to camera control units
"""

import threading
import time
import requests
import logging
import subprocess
import os
import sys
from datetime import datetime

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('tally_sender')

class TallySender:
    """Handles sending tally commands to camera control units"""
    
    def __init__(self, controllers=None):
        """
        Initialize the TallySender
        
        Args:
            controllers: List of controller configurations
        """
        self.controllers = controllers or []
        self.camera_to_xcu = {}
        self.monitor_thread = None
        self.running = False
        self.current_program_sources = []
        self.current_preview_source = None
        
        # Track which XCUs have tally on to avoid duplicate commands
        self.xcu_tally_state = {}  # Format: {'XCU-09': {'red': True, 'green': False}}
        
        logger.info(f"TallySender initialized with {len(self.controllers)} controllers")
    
    def start_monitoring(self, status_url, interval=1):
        """
        Start monitoring the status URL for tally changes
        
        Args:
            status_url: URL to fetch status from
            interval: Polling interval in seconds
        """
        if self.monitor_thread and self.monitor_thread.is_alive():
            logger.warning("Monitor thread already running")
            return
        
        self.running = True
        self.monitor_thread = threading.Thread(
            target=self._monitor_status,
            args=(status_url, interval),
            daemon=True
        )
        self.monitor_thread.start()
        logger.info(f"Started monitoring {status_url} every {interval} seconds")
    
    def stop_monitoring(self):
        """Stop the monitoring thread"""
        self.running = False
        if self.monitor_thread:
            self.monitor_thread.join(timeout=5)
            logger.info("Stopped monitoring")
    
    def _monitor_status(self, status_url, interval):
        """
        Monitor the status URL and update tally state
        
        Args:
            status_url: URL to fetch status from
            interval: Polling interval in seconds
        """
        while self.running:
            try:
                response = requests.get(status_url, timeout=5)
                if response.status_code == 200:
                    data = response.json()
                    
                    # Get program and preview sources
                    program_sources = [p['source'] for p in data.get('program', [])]
                    preview_source = data.get('preview', {}).get('source') if data.get('preview') else None
                    
                    # Check if anything changed
                    if (program_sources != self.current_program_sources or 
                            preview_source != self.current_preview_source):
                        
                        logger.info(f"Tally state changed: Program={program_sources}, Preview={preview_source}")
                        
                        # Update stored state
                        self.current_program_sources = program_sources
                        self.current_preview_source = preview_source
                        
                        # Send tally commands
                        self.update_tally_state(program_sources, preview_source)
                
            except Exception as e:
                logger.error(f"Error monitoring status: {e}")
            
            time.sleep(interval)
    
    def update_tally_state(self, program_sources, preview_source):
        """
        Update tally state based on program and preview sources
        
        Args:
            program_sources: List of sources currently on program
            preview_source: Source currently on preview
        """
        # Track which XCUs should have tally on
        target_state = {}
        
        # Process program sources (red tally)
        for source in program_sources:
            if source in self.camera_to_xcu:
                xcu = self.camera_to_xcu[source]
                if xcu not in target_state:
                    target_state[xcu] = {'red': True, 'green': False}
                else:
                    target_state[xcu]['red'] = True
        
        # Process preview source (green tally)
        if preview_source and preview_source in self.camera_to_xcu:
            xcu = self.camera_to_xcu[preview_source]
            if xcu not in target_state:
                target_state[xcu] = {'red': False, 'green': True}
            else:
                target_state[xcu]['green'] = True
        
        # Compare with current state and send commands for changes
        for xcu, state in target_state.items():
            # Initialize XCU state if not present
            if xcu not in self.xcu_tally_state:
                self.xcu_tally_state[xcu] = {'red': False, 'green': False}
            
            # Check if red tally state changed
            if state['red'] != self.xcu_tally_state[xcu]['red']:
                self.send_tally_command(xcu, 'red', state['red'])
                self.xcu_tally_state[xcu]['red'] = state['red']
            
            # Check if green tally state changed
            if state['green'] != self.xcu_tally_state[xcu]['green']:
                self.send_tally_command(xcu, 'green', state['green'])
                self.xcu_tally_state[xcu]['green'] = state['green']
        
        # Turn off tally for XCUs not in target_state
        for xcu in list(self.xcu_tally_state.keys()):
            if xcu not in target_state:
                # Turn off red tally if it was on
                if self.xcu_tally_state[xcu]['red']:
                    self.send_tally_command(xcu, 'red', False)
                    self.xcu_tally_state[xcu]['red'] = False
                
                # Turn off green tally if it was on
                if self.xcu_tally_state[xcu]['green']:
                    self.send_tally_command(xcu, 'green', False)
                    self.xcu_tally_state[xcu]['green'] = False
    
    def send_tally_command(self, xcu, tally_type, state):
        """
        Send tally command to a specific XCU
        
        Args:
            xcu: XCU identifier (e.g., XCU-09)
            tally_type: Type of tally (red, green)
            state: Tally state (True for on, False for off)
        """
        state_str = "on" if state else "off"
        logger.info(f"Sending {tally_type} tally {state_str} command to {xcu}")
        
        # Build command
        script_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "gv_tally_control.py")
        command = [
            sys.executable,  # Use the same Python interpreter
            script_path,
            "--xcu", xcu,
            f"--{tally_type}", state_str
        ]
        
        # Execute command
        try:
            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                check=False  # Don't raise exception on non-zero exit
            )
            
            if result.returncode == 0:
                logger.info(f"Successfully sent {tally_type} tally {state_str} to {xcu}")
            else:
                logger.error(f"Error sending tally command: {result.stderr}")
                
        except Exception as e:
            logger.error(f"Exception sending tally command: {e}")
