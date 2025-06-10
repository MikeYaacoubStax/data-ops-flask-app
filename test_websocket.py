#!/usr/bin/env python3
"""
Simple test script to verify WebSocket status updates are working
"""

import socketio
import time
import json

# Create a Socket.IO client
sio = socketio.Client()

@sio.event
def connect():
    print("✅ Connected to WebSocket")

@sio.event
def disconnect():
    print("❌ Disconnected from WebSocket")

@sio.event
def status_update(data):
    infrastructure = data.get('infrastructure', {})
    ready = infrastructure.get('ready', False)
    vm_status = infrastructure.get('victoriametrics', {}).get('status', 'unknown')
    grafana_status = infrastructure.get('grafana', {}).get('status', 'unknown')
    
    print(f"📊 Status Update: Infrastructure Ready={ready}, VM={vm_status}, Grafana={grafana_status}")

def main():
    try:
        print("🔌 Connecting to Flask app WebSocket...")
        sio.connect('http://localhost:5000')
        
        print("⏳ Listening for status updates for 10 seconds...")
        time.sleep(10)
        
    except Exception as e:
        print(f"❌ Error: {e}")
    finally:
        sio.disconnect()
        print("👋 Test completed")

if __name__ == "__main__":
    main()
