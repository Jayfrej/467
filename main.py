#!/usr/bin/env python3
"""
TradingView to MetaTrader 5 Bridge
Main entry point for the application
"""

import logging
import sys
import os
from threading import Thread
import time
import subprocess
import requests

# Add the current directory to Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.config import Config
from app.server import app, initialize_mt5

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('trading_bot.log'),
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger(__name__)

def setup_ngrok(auth_token, port):
    """Setup and run Ngrok tunnel"""
    try:
        # Set auth token
        subprocess.run(['ngrok', 'config', 'add-authtoken', auth_token], check=True)
        
        # Start tunnel
        logger.info(f"Starting Ngrok tunnel on port {port}")
        process = subprocess.Popen(['ngrok', 'http', str(port), '--log=stdout'], 
                                 stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        
        # Wait for tunnel to be ready
        time.sleep(5)
        
        # Get tunnel URL
        try:
            response = requests.get('http://localhost:4040/api/tunnels')
            if response.status_code == 200:
                tunnels = response.json().get('tunnels', [])
                if tunnels:
                    tunnel_url = tunnels[0]['public_url']
                    webhook_url = f"{tunnel_url}/trade"
                    
                    # Save webhook URL to file
                    with open('webhook_url.txt', 'w') as f:
                        f.write(webhook_url)
                    
                    logger.info(f"Ngrok tunnel active!")
                    logger.info(f"Webhook URL: {webhook_url}")
                    logger.info(f"Webhook URL saved to: webhook_url.txt")
                    
        except Exception as e:
            logger.warning(f"Could not get tunnel URL: {e}")
            logger.info("Check Ngrok dashboard at: http://localhost:4040")
            
    except subprocess.CalledProcessError as e:
        logger.error(f"Failed to setup Ngrok: {e}")
    except FileNotFoundError:
        logger.error("Ngrok not found. Please install Ngrok and add it to your PATH")
    except Exception as e:
        logger.error(f"Error setting up Ngrok: {e}")

def run_server():
    """Run the Flask server"""
    try:
        config = Config()
        
        # Validate configuration
        errors = config.validate()
        if errors:
            logger.error("Configuration errors:")
            for error in errors:
                logger.error(f"  - {error}")
            return False
        
        logger.info("Starting TradingView to MT5 Bridge...")
        logger.info(config)
        
        # Initialize MT5 connection
        logger.info("Initializing MT5 connection...")
        if not initialize_mt5():
            logger.error("Failed to initialize MT5 connection")
            return False
        
        logger.info("MT5 connection successful!")
        
        # Start Flask server
        logger.info(f"Starting Flask server on {config.SERVER_HOST}:{config.SERVER_PORT}")
        app.run(
            host=config.SERVER_HOST,
            port=config.SERVER_PORT,
            debug=config.DEBUG,
            threaded=True
        )
        
        return True
        
    except Exception as e:
        logger.error(f"Error running server: {e}")
        return False

def run_with_ngrok():
    """Run server with Ngrok tunnel"""
    try:
        config = Config()
        
        # Start Ngrok in a separate thread
        logger.info("Setting up Ngrok tunnel...")
        ngrok_thread = Thread(target=setup_ngrok, args=(config.NGROK_AUTH_TOKEN, config.SERVER_PORT))
        ngrok_thread.daemon = True
        ngrok_thread.start()
        
        # Wait a bit for Ngrok to start
        time.sleep(3)
        
        # Start the main server
        return run_server()
        
    except Exception as e:
        logger.error(f"Error running with Ngrok: {e}")
        return False

if __name__ == "__main__":
    try:
        # Check if user wants to run with Ngrok
        if len(sys.argv) > 1 and sys.argv[1] == "--no-ngrok":
            logger.info("Running without Ngrok tunnel")
            success = run_server()
        else:
            logger.info("Running with Ngrok tunnel")
            success = run_with_ngrok()
        
        if not success:
            logger.error("Application failed to start")
            sys.exit(1)
            
    except KeyboardInterrupt:
        logger.info("Application stopped by user")
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        sys.exit(1)