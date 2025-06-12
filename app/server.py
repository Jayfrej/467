import logging
import threading
import json
from .mt5_handler import MT5Handler
from .utils import parse_tradingview_webhook
from .config import FLASK_HOST, FLASK_PORT, DEBUG, DEFAULT_VOLUME
from flask import Flask, request, jsonify

logger = logging.getLogger(__name__)

def create_app(mt5_handler=None):
    """
    Create and configure the Flask application
    
    Args:
        mt5_handler (MT5Handler, optional): MT5 handler instance. Creates new one if None.
        
    Returns:
        Flask: Configured Flask application
    """
    app = Flask(__name__)
    
    # Create MT5 handler if not provided
    if mt5_handler is None:
        mt5_handler = MT5Handler()

    def validate_volume(volume):
        """Validate volume/lot size parameter"""
        try:
            # Handle string inputs
            if isinstance(volume, str):
                volume = volume.strip()
                if not volume:
                    return False, "Volume cannot be empty"
            
            vol = float(volume)
            
            # Check minimum lot size
            if vol <= 0:
                return False, "Lot size must be positive (greater than 0)"
            
            # Check maximum lot size (configurable)
            max_lots = 100  # ปรับได้ตามต้องการ
            if vol > max_lots:
                return False, f"Lot size too large (maximum {max_lots} lots allowed)"
            
            # Check lot size precision (most brokers allow 0.01 minimum)
            # Round to 2 decimal places for standard lot sizes
            vol = round(vol, 2)
            
            # Check minimum lot size (standard is 0.01)
            min_lots = 0.01
            if vol < min_lots:
                return False, f"Lot size too small (minimum {min_lots} lots)"
                
            return True, vol
            
        except (ValueError, TypeError) as e:
            return False, f"Invalid lot size format: {str(e)}"

    @app.route('/symbols', methods=['GET'])
    def get_symbols():
        """Endpoint to get all available symbols"""
        try:
            symbols = mt5_handler.list_available_symbols()
            
            # Filter by query if provided
            query = request.args.get('q', '').upper()
            if query:
                symbols = [s for s in symbols if query in s.upper()]
            
            return jsonify({
                "success": True,
                "count": len(symbols),
                "symbols": symbols
            }), 200
            
        except Exception as e:
            logger.error(f"Error getting symbols: {str(e)}", exc_info=True)
            return jsonify({"success": False, "message": f"Error: {str(e)}"}), 500

    @app.route('/', methods=['GET'])
    def index():
        """Root endpoint with basic information"""
        return jsonify({
            "name": "TradingView to MT5 Integration",
            "version": "1.0.0",
            "status": "running",
            "mt5_connected": mt5_handler.connected,
            "endpoints": {
                "/": "This information page (GET)",
                "/trade": "Endpoint for TradingView alerts (POST)",
                "/health": "Health check endpoint (GET)",
                "/positions": "List open positions (GET)",
                "/position/<id>/close": "Close a specific position (POST)",
                "/symbols": "List available symbols (GET)",
                "/symbols?q=EUR": "Search for symbols (GET)"
            },
            "webhook_format": {
                "symbol": "EURUSD (required)",
                "action": "BUY/SELL/LONG/SHORT (required)",
                "volume": "0.01-100.0 (optional, default from config)",
                "lots": "Alternative field name for volume",
                "lot_size": "Alternative field name for volume", 
                "size": "Alternative field name for volume",
                "comment": "Optional comment for the trade",
                "close_existing": "true/false (optional, close existing positions first)"
            },
            "examples": {
                "basic_trade": {
                    "symbol": "EURUSD",
                    "action": "BUY",
                    "volume": 0.1
                },
                "advanced_trade": {
                    "symbol": "GBPUSD", 
                    "action": "SELL",
                    "lots": 0.5,
                    "comment": "TradingView Signal - RSI Oversold",
                    "close_existing": True
                }
            }
        })

    @app.route('/health', methods=['GET'])
    def health_check():
        """Health check endpoint to verify the server is running"""
        return jsonify({
            "status": "ok", 
            "mt5_connected": mt5_handler.connected,
            "timestamp": str(import_datetime().now())
        })

    @app.route('/trade', methods=['POST'])
    def webhook():
        """Endpoint to receive TradingView alerts"""
        # Log every request attempt
        logger.info(f"=== TRADE REQUEST START ===")
        logger.info(f"Remote address: {request.remote_addr}")
        logger.info(f"Method: {request.method}")
        logger.info(f"URL: {request.url}")
        logger.info(f"Content-Type: {request.content_type}")
        logger.info(f"Content-Length: {request.content_length}")
        logger.info(f"Headers: {dict(request.headers)}")
        logger.info(f"Raw data: {request.data}")
        logger.info(f"Raw data (decoded): {request.data.decode('utf-8', errors='ignore') if request.data else 'None'}")
        
        try:
            # Check if request has data
            if not request.data:
                logger.error("ERROR: Empty request body")
                return jsonify({
                    "success": False, 
                    "message": "Empty request body",
                    "debug_info": {
                        "content_type": request.content_type,
                        "content_length": request.content_length,
                        "headers": dict(request.headers)
                    }
                }), 400
            
            # Try to get JSON data with better error handling
            data = None
            try:
                logger.info(f"Checking if request is JSON: {request.is_json}")
                if request.is_json:
                    data = request.get_json()
                    logger.info(f"Got JSON data via request.get_json(): {data}")
                else:
                    # Try to parse as JSON even if content-type is not set correctly
                    try:
                        raw_text = request.data.decode('utf-8')
                        logger.info(f"Trying to parse raw text as JSON: {raw_text}")
                        data = json.loads(raw_text)
                        logger.info(f"Successfully parsed raw text as JSON: {data}")
                    except json.JSONDecodeError as jde:
                        logger.error(f"JSON decode error: {str(jde)}")
                        # Try to parse as form data or plain text
                        raw_data = request.data.decode('utf-8')
                        logger.error(f"Non-JSON data received: {raw_data}")
                        return jsonify({
                            "success": False, 
                            "message": f"Request must be valid JSON format. Received: {raw_data[:100]}...",
                            "json_error": str(jde),
                            "debug_info": {
                                "is_json": request.is_json,
                                "content_type": request.content_type,
                                "raw_data_preview": raw_data[:200]
                            }
                        }), 400
            except Exception as json_error:
                logger.error(f"Unexpected JSON parsing error: {str(json_error)}", exc_info=True)
                return jsonify({
                    "success": False, 
                    "message": f"Invalid JSON format: {str(json_error)}",
                    "debug_info": {
                        "is_json": request.is_json,
                        "content_type": request.content_type,
                        "error_type": type(json_error).__name__
                    }
                }), 400
            
            if not data:
                logger.error("ERROR: No JSON data found in request")
                return jsonify({
                    "success": False, 
                    "message": "No valid JSON data found in request",
                    "debug_info": {
                        "is_json": request.is_json,
                        "content_type": request.content_type,
                        "data_received": request.data.decode('utf-8', errors='ignore') if request.data else None
                    }
                }), 400
            
            logger.info(f"SUCCESS: Parsed webhook data: {data}")
            logger.info(f"Data type: {type(data)}")
            logger.info(f"Data keys: {list(data.keys()) if isinstance(data, dict) else 'Not a dict'}")
        
        except Exception as e:
            logger.error(f"FATAL ERROR in webhook processing: {str(e)}", exc_info=True)
            return jsonify({
                "success": False, 
                "message": f"Fatal error processing request: {str(e)}",
                "error_type": type(e).__name__,
                "debug_info": {
                    "content_type": request.content_type,
                    "has_data": bool(request.data),
                    "data_length": len(request.data) if request.data else 0
                }
            }), 500
        
        # Continue with validation (moved outside of try-catch for main parsing)
        try:
            
            # Validate required fields with detailed error messages
            missing_fields = []
            if 'symbol' not in data or not data['symbol']:
                missing_fields.append('symbol')
            if 'action' not in data or not data['action']:
                missing_fields.append('action')
            
            if missing_fields:
                error_msg = f"Missing required fields: {', '.join(missing_fields)}"
                logger.warning(error_msg)
                return jsonify({
                    "success": False, 
                    "message": error_msg,
                    "required_fields": ["symbol", "action"],
                    "received_fields": list(data.keys()) if isinstance(data, dict) else []
                }), 400
            
            # Validate data types
            if not isinstance(data['symbol'], str):
                return jsonify({
                    "success": False, 
                    "message": "Symbol must be a string"
                }), 400
            
            if not isinstance(data['action'], str):
                return jsonify({
                    "success": False, 
                    "message": "Action must be a string"
                }), 400
            
            symbol = data['symbol'].strip().upper()
            action = data['action'].strip().upper()
            
            # Validate symbol is not empty after stripping
            if not symbol:
                return jsonify({
                    "success": False, 
                    "message": "Symbol cannot be empty"
                }), 400
            
            # Validate action
            valid_actions = ['BUY', 'SELL', 'LONG', 'SHORT']
            if action not in valid_actions:
                return jsonify({
                    "success": False, 
                    "message": f"Invalid action '{action}'. Must be one of: {', '.join(valid_actions)}"
                }), 400
            
            # Get and validate lot size (support multiple field names)
            # Support 'volume', 'lots', 'lot_size', 'size' for flexibility
            volume = (data.get('volume') or 
                     data.get('lots') or 
                     data.get('lot_size') or 
                     data.get('size') or 
                     DEFAULT_VOLUME)
            
            logger.info(f"Volume from webhook: {volume} (type: {type(volume)})")
            
            is_valid, validated_volume = validate_volume(volume)
            if not is_valid:
                return jsonify({
                    "success": False, 
                    "message": f"Lot size validation failed: {validated_volume}",
                    "received_volume": volume,
                    "supported_fields": ["volume", "lots", "lot_size", "size"]
                }), 400
            
            # Get optional parameters with validation
            comment = data.get('comment', 'TradingView Signal')
            if comment and not isinstance(comment, str):
                comment = str(comment)
            
            close_existing = data.get('close_existing', True)
            
            # Convert close_existing to boolean if it's a string
            if isinstance(close_existing, str):
                close_existing = close_existing.lower() in ['true', '1', 'yes', 'on']
            elif not isinstance(close_existing, bool):
                try:
                    close_existing = bool(close_existing)
                except:
                    close_existing = True
            
            logger.info(f"Processed trade params - Symbol: {symbol}, Action: {action}, "
                      f"Volume: {validated_volume}, Close existing: {close_existing}, Comment: {comment}")
            
            # Check MT5 connection before placing trade
            if not mt5_handler.connected:
                logger.error("MT5 is not connected")
                return jsonify({
                    "success": False, 
                    "message": "MT5 connection is not available"
                }), 500
            
            # Place the trade
            result = mt5_handler.place_trade(
                symbol=symbol,
                order_type=action,
                volume=validated_volume,
                comment=comment,
                close_existing=close_existing
            )
            
            # Return the result
            if result['success']:
                logger.info(f"Trade executed successfully: {result['message']}")
                return jsonify(result), 200
            else:
                logger.error(f"Trade execution failed: {result['message']}")
                return jsonify(result), 500
        
        except Exception as e:
            logger.error(f"VALIDATION/EXECUTION ERROR: {str(e)}", exc_info=True)
            return jsonify({
                "success": False, 
                "message": f"Error in trade processing: {str(e)}",
                "error_type": type(e).__name__
            }), 500
        
        finally:
            logger.info(f"=== TRADE REQUEST END ===")
    
    # Add a simple test endpoint to verify server is working
    @app.route('/test', methods=['GET', 'POST'])
    def test():
        """Test endpoint to verify server functionality"""
        if request.method == 'GET':
            return jsonify({
                "message": "Server is working",
                "method": "GET",
                "timestamp": str(import_datetime().now())
            }), 200
        else:  # POST
            try:
                data = request.get_json() if request.is_json else None
                return jsonify({
                    "message": "POST test successful",
                    "received_data": data,
                    "content_type": request.content_type,
                    "is_json": request.is_json,
                    "raw_data": request.data.decode('utf-8', errors='ignore') if request.data else None
                }), 200
            except Exception as e:
                return jsonify({
                    "message": "POST test failed",
                    "error": str(e),
                    "content_type": request.content_type
                }), 400
    
    @app.route('/positions', methods=['GET'])
    def get_positions():
        """Endpoint to get all open positions"""
        try:
            # Get symbol from query string if provided
            symbol = request.args.get('symbol')
            
            # Get positions
            positions = mt5_handler.get_positions(symbol)
            
            return jsonify({
                "success": True,
                "positions": positions,
                "count": len(positions)
            }), 200
            
        except Exception as e:
            logger.error(f"Error getting positions: {str(e)}", exc_info=True)
            return jsonify({"success": False, "message": f"Error: {str(e)}"}), 500

    @app.route('/positions/close', methods=['POST'])
    def close_all_positions():
        """Endpoint to close all positions for a symbol"""
        try:
            data = request.json if request.is_json else {}
            symbol = data.get('symbol') if data else request.args.get('symbol')
            
            # Close all positions for the symbol
            result = mt5_handler.close_all_positions(symbol)
            
            # Return the result
            if result['success']:
                logger.info(f"Positions closed successfully: {result['message']}")
                return jsonify(result), 200
            else:
                logger.error(f"Close positions failed: {result['message']}")
                return jsonify(result), 500
                
        except Exception as e:
            logger.error(f"Error closing positions: {str(e)}", exc_info=True)
            return jsonify({"success": False, "message": f"Error: {str(e)}"}), 500
    
    @app.route('/position/<int:position_id>/close', methods=['POST'])
    def close_position(position_id):
        """Endpoint to close a specific position"""
        try:
            # Close the position
            result = mt5_handler.close_position(position_id)
            
            # Return the result
            if result['success']:
                logger.info(f"Position closed successfully: {result['message']}")
                return jsonify(result), 200
            else:
                logger.error(f"Position close failed: {result['message']}")
                return jsonify(result), 500
            
        except Exception as e:
            logger.error(f"Error closing position: {str(e)}", exc_info=True)
            return jsonify({"success": False, "message": f"Error: {str(e)}"}), 500
    
    @app.errorhandler(400)
    def bad_request(e):
        """Handle 400 errors"""
        logger.warning(f"Bad request: {str(e)}")
        return jsonify({
            "success": False, 
            "message": "Bad request - please check your request format and data"
        }), 400
    
    @app.errorhandler(404)
    def not_found(e):
        """Handle 404 errors"""
        return jsonify({"success": False, "message": "Endpoint not found"}), 404
    
    @app.errorhandler(405)
    def method_not_allowed(e):
        """Handle 405 errors"""
        return jsonify({"success": False, "message": "Method not allowed"}), 405
    
    @app.errorhandler(500)
    def server_error(e):
        """Handle 500 errors"""
        logger.error(f"Server error: {str(e)}")
        return jsonify({"success": False, "message": "Internal server error"}), 500
    
    return app

def import_datetime():
    """Import datetime to avoid circular imports"""
    from datetime import datetime
    return datetime

def run_server(mt5_handler=None):
    """
    Run the Flask server
    
    Args:
        mt5_handler (MT5Handler, optional): MT5 handler instance
    """
    # Setup logging before creating app
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler('trade_api.log'),
            logging.StreamHandler()
        ]
    )
    
    logger.info("=== SERVER STARTING ===")
    
    app = create_app(mt5_handler)
    
    # Force logging for all requests
    @app.before_request
    def log_request_info():
        logger.info('=== REQUEST START ===')
        logger.info(f'Endpoint: {request.endpoint}')
        logger.info(f'Method: {request.method}')
        logger.info(f'Path: {request.path}')
        logger.info(f'Headers: {dict(request.headers)}')
        logger.info(f'Body: {request.get_data()}')
    
    @app.after_request
    def log_response_info(response):
        logger.info(f'Response Status: {response.status_code}')
        logger.info(f'Response Headers: {dict(response.headers)}')
        logger.info('=== REQUEST END ===')
        return response
    
    # When running in a thread, we need to disable the reloader
    use_reloader = DEBUG and threading.current_thread() is threading.main_thread()
    
    logger.info(f"Starting server on {FLASK_HOST}:{FLASK_PORT}")
    app.run(host=FLASK_HOST, port=FLASK_PORT, debug=DEBUG, use_reloader=use_reloader)