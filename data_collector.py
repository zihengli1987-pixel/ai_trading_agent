# data_collector.py - 数据采集模块

import yfinance as yf
import time

class DataCollector:
    """数据采集器"""
    
    def __init__(self, stock_pool):
        self.stock_pool = stock_pool
    
    def get_stock_data(self, symbol):
        """获取单只股票数据"""
        try:
            stock = yf.Ticker(symbol)
            hist = stock.history(period="6mo")
            
            if hist.empty or len(hist) < 60:
                return None
            
            current = hist['Close'].iloc[-1]
            prev_close = hist['Close'].iloc[-2] if len(hist) > 1 else current
            change = ((current - prev_close) / prev_close) * 100
            
            ma5 = hist['Close'].rolling(5).mean().iloc[-1]
            ma10 = hist['Close'].rolling(10).mean().iloc[-1]
            ma20 = hist['Close'].rolling(20).mean().iloc[-1]
            ma30 = hist['Close'].rolling(30).mean().iloc[-1]
            ma60 = hist['Close'].rolling(60).mean().iloc[-1]
            
            delta = hist['Close'].diff()
            gain = (delta.where(delta > 0, 0)).rolling(14).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
            rs = gain / loss
            rsi = 100 - (100 / (1 + rs)).iloc[-1] if loss.iloc[-1] != 0 else 50
            
            exp1 = hist['Close'].ewm(span=12, adjust=False).mean()
            exp2 = hist['Close'].ewm(span=26, adjust=False).mean()
            macd_line = exp1 - exp2
            macd_signal = macd_line.ewm(span=9, adjust=False).mean()
            macd_hist = macd_line - macd_signal
            
            avg_volume = hist['Volume'].rolling(20).mean().iloc[-1]
            volume_ratio = hist['Volume'].iloc[-1] / avg_volume if avg_volume > 0 else 0
            
            return {
                'symbol': symbol,
                'name': self.stock_pool.get(symbol, symbol),
                'price': round(current, 2),
                'change': round(change, 2),
                'high': round(hist['High'].iloc[-1], 2),
                'low': round(hist['Low'].iloc[-1], 2),
                'volume': int(hist['Volume'].iloc[-1]),
                'ma5': round(ma5, 2),
                'ma10': round(ma10, 2),
                'ma20': round(ma20, 2),
                'ma30': round(ma30, 2),
                'ma60': round(ma60, 2),
                'rsi': round(rsi, 2),
                'macd': round(macd_line.iloc[-1], 3),
                'macd_signal': round(macd_signal.iloc[-1], 3),
                'macd_hist': round(macd_hist.iloc[-1], 3),
                'volume_ratio': round(volume_ratio, 2),
                'prev_close': round(prev_close, 2)
            }
        except Exception as e:
            print(f"⚠️ 获取 {symbol} 数据失败")
            return None
    
    def get_all_data(self):
        """获取所有股票数据"""
        results = {}
        print(f"\n📊 正在采集 {len(self.stock_pool)} 只股票数据...")
        
        for i, symbol in enumerate(self.stock_pool.keys()):
            data = self.get_stock_data(symbol)
            if data:
                results[symbol] = data
            time.sleep(0.5)
            
            if (i + 1) % 10 == 0:
                print(f"  进度: {i+1}/{len(self.stock_pool)}")
        
        print(f"✅ 采集完成: {len(results)}/{len(self.stock_pool)} 只")
        return results