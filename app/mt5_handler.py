import MetaTrader5 as mt5
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

class MT5Handler:
    def __init__(self, account, password, server, path, symbol_suffix=""):
        self.account = account
        self.password = password
        self.server = server
        self.path = path
        self.symbol_suffix = symbol_suffix
        self.connected = False
        
    def connect(self):
        """Connect to MT5"""
        try:
            if not mt5.initialize(self.path):
                logger.error(f"Failed to initialize MT5: {mt5.last_error()}")
                return False
                
            if not mt5.login(self.account, self.password, self.server):
                logger.error(f"Failed to login to MT5: {mt5.last_error()}")
                return False
                
            self.connected = True
            logger.info("Successfully connected to MT5")
            return True
            
        except Exception as e:
            logger.error(f"Error connecting to MT5: {e}")
            return False
    
    def disconnect(self):
        """Disconnect from MT5"""
        mt5.shutdown()
        self.connected = False
        logger.info("Disconnected from MT5")
    
    def get_symbol_with_suffix(self, symbol):
        """Add suffix to symbol if configured"""
        return symbol + self.symbol_suffix
    
    def get_positions(self, symbol=None):
        """Get current positions"""
        if not self.connected:
            return []
            
        try:
            if symbol:
                symbol = self.get_symbol_with_suffix(symbol)
                positions = mt5.positions_get(symbol=symbol)
            else:
                positions = mt5.positions_get()
                
            return list(positions) if positions else []
            
        except Exception as e:
            logger.error(f"Error getting positions: {e}")
            return []
    
    def close_all_positions_by_type(self, symbol, position_type):
        """Close all positions of specific type (buy/sell) for a symbol"""
        symbol = self.get_symbol_with_suffix(symbol)
        positions = self.get_positions(symbol)
        
        closed_positions = []
        for position in positions:
            if position.type == position_type:
                try:
                    # Create close request
                    request = {
                        "action": mt5.TRADE_ACTION_DEAL,
                        "symbol": symbol,
                        "volume": position.volume,
                        "type": mt5.ORDER_TYPE_SELL if position.type == mt5.ORDER_TYPE_BUY else mt5.ORDER_TYPE_BUY,
                        "position": position.ticket,
                        "price": mt5.symbol_info_tick(symbol).bid if position.type == mt5.ORDER_TYPE_BUY else mt5.symbol_info_tick(symbol).ask,
                        "deviation": 20,
                        "magic": 0,
                        "comment": "Close position",
                        "type_time": mt5.ORDER_TIME_GTC,
                        "type_filling": mt5.ORDER_FILLING_IOC,
                    }
                    
                    result = mt5.order_send(request)
                    if result.retcode == mt5.TRADE_RETCODE_DONE:
                        closed_positions.append(position.ticket)
                        logger.info(f"Closed position {position.ticket}")
                    else:
                        logger.error(f"Failed to close position {position.ticket}: {result.comment}")
                        
                except Exception as e:
                    logger.error(f"Error closing position {position.ticket}: {e}")
        
        return closed_positions
    
    def close_position_by_volume(self, symbol, volume, position_type=None):
        """Close positions by specified volume (partial or full)"""
        symbol = self.get_symbol_with_suffix(symbol)
        positions = self.get_positions(symbol)
        
        if position_type is not None:
            positions = [p for p in positions if p.type == position_type]
        
        remaining_volume = volume
        closed_positions = []
        
        for position in positions:
            if remaining_volume <= 0:
                break
                
            close_volume = min(position.volume, remaining_volume)
            
            try:
                request = {
                    "action": mt5.TRADE_ACTION_DEAL,
                    "symbol": symbol,
                    "volume": close_volume,
                    "type": mt5.ORDER_TYPE_SELL if position.type == mt5.ORDER_TYPE_BUY else mt5.ORDER_TYPE_BUY,
                    "position": position.ticket,
                    "price": mt5.symbol_info_tick(symbol).bid if position.type == mt5.ORDER_TYPE_BUY else mt5.symbol_info_tick(symbol).ask,
                    "deviation": 20,
                    "magic": 0,
                    "comment": f"Close {close_volume} lots",
                    "type_time": mt5.ORDER_TIME_GTC,
                    "type_filling": mt5.ORDER_FILLING_IOC,
                }
                
                result = mt5.order_send(request)
                if result.retcode == mt5.TRADE_RETCODE_DONE:
                    closed_positions.append(position.ticket)
                    remaining_volume -= close_volume
                    logger.info(f"Closed {close_volume} lots from position {position.ticket}")
                else:
                    logger.error(f"Failed to close position {position.ticket}: {result.comment}")
                    
            except Exception as e:
                logger.error(f"Error closing position {position.ticket}: {e}")
        
        return closed_positions
    
    def place_order(self, symbol, action, volume, stop_loss=None, take_profit=None):
        """Place order with new logic"""
        if not self.connected:
            logger.error("Not connected to MT5")
            return None
            
        symbol = self.get_symbol_with_suffix(symbol)
        
        # Get symbol info
        symbol_info = mt5.symbol_info(symbol)
        if symbol_info is None:
            logger.error(f"Symbol {symbol} not found")
            return None
        
        # Get current tick
        tick = mt5.symbol_info_tick(symbol)
        if tick is None:
            logger.error(f"Failed to get tick for {symbol}")
            return None
        
        try:
            if action.lower() == "buy":
                # ถ้าเป็นคำสั่งซื้อ และมีโพซิชั่นขายอยู่ ให้ปิดโพซิชั่นขายทั้งหมดก่อน
                sell_positions = [p for p in self.get_positions(symbol) if p.type == mt5.ORDER_TYPE_SELL]
                if sell_positions:
                    logger.info(f"Closing all sell positions for {symbol} before opening buy")
                    self.close_all_positions_by_type(symbol, mt5.ORDER_TYPE_SELL)
                
                # เปิดโพซิชั่นซื้อใหม่
                order_type = mt5.ORDER_TYPE_BUY
                price = tick.ask
                
            elif action.lower() == "sell":
                # ถ้าเป็นคำสั่งขาย และมีโพซิชั่นซื้ออยู่ ให้ปิดโพซิชั่นซื้อทั้งหมดก่อน
                buy_positions = [p for p in self.get_positions(symbol) if p.type == mt5.ORDER_TYPE_BUY]
                if buy_positions:
                    logger.info(f"Closing all buy positions for {symbol} before opening sell")
                    self.close_all_positions_by_type(symbol, mt5.ORDER_TYPE_BUY)
                
                # เปิดโพซิชั่นขายใหม่
                order_type = mt5.ORDER_TYPE_SELL
                price = tick.bid
                
            elif action.lower() == "close":
                # ปิดโพซิชั่นตาม volume ที่ระบุ
                logger.info(f"Closing {volume} lots for {symbol}")
                closed = self.close_position_by_volume(symbol, volume)
                return {"action": "close", "closed_positions": closed, "volume": volume}
                
            else:
                logger.error(f"Unknown action: {action}")
                return None
            
            # สร้างคำสั่งซื้อ/ขาย
            request = {
                "action": mt5.TRADE_ACTION_DEAL,
                "symbol": symbol,
                "volume": float(volume),
                "type": order_type,
                "price": price,
                "deviation": 20,
                "magic": 0,
                "comment": f"{action.upper()} order",
                "type_time": mt5.ORDER_TIME_GTC,
                "type_filling": mt5.ORDER_FILLING_IOC,
            }
            
            # เพิ่ม stop loss และ take profit ถ้ามี
            if stop_loss:
                request["sl"] = float(stop_loss)
            if take_profit:
                request["tp"] = float(take_profit)
            
            # ส่งคำสั่ง
            result = mt5.order_send(request)
            
            if result.retcode == mt5.TRADE_RETCODE_DONE:
                logger.info(f"Order executed successfully: {action.upper()} {volume} {symbol} at {price}")
                return {
                    "action": action,
                    "symbol": symbol,
                    "volume": volume,
                    "price": price,
                    "ticket": result.order,
                    "success": True
                }
            else:
                logger.error(f"Order failed: {result.comment}")
                return {
                    "action": action,
                    "symbol": symbol,
                    "volume": volume,
                    "success": False,
                    "error": result.comment
                }
                
        except Exception as e:
            logger.error(f"Error placing order: {e}")
            return None
    
    def get_account_info(self):
        """Get account information"""
        if not self.connected:
            return None
            
        try:
            account_info = mt5.account_info()
            if account_info:
                return {
                    "login": account_info.login,
                    "balance": account_info.balance,
                    "equity": account_info.equity,
                    "margin": account_info.margin,
                    "free_margin": account_info.margin_free,
                    "profit": account_info.profit
                }
            return None
            
        except Exception as e:
            logger.error(f"Error getting account info: {e}")
            return None