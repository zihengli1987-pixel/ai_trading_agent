# app.py - 添加 WebSocket 实时推送

from flask import Flask, render_template, jsonify, request
from flask_socketio import SocketIO, emit
import yfinance as yf
import pandas as pd
from datetime import datetime
import time
import threading
from strategy import StrategyEngine

app = Flask(__name__)
app.config['SECRET_KEY'] = 'secret!'
socketio = SocketIO(app, cors_allowed_origins="*")

# ===== 初始化策略引擎 =====
strategy = StrategyEngine()

# ============================================================
# 股票池
# ============================================================
STOCKS = [
    'TSLA', 'DOCU', 'NOW', 'AI', 'APD', 'HAL', 'DASH', 'DPZ', 'AFRM',
    'ABNB', 'TEAM', 'A', 'TGT', 'CRCL', 'ELF', 'CAH', 'VG', 'CHA',
    'AAPL', 'MSFT', 'GOOGL', 'AMZN', 'META', 'NVDA', 'JPM', 'BAC',
    'WMT', 'HD', 'MCD', 'NKE', 'PFE', 'JNJ', 'PG', 'KO', 'PEP',
    'IBM', 'ORCL', 'CRM', 'PANW', 'OXY', 'VZ', 'ADBE', 'HOOD',
    'ALL', 'GILD', 'HSAI', 'DJT', 'MDLN', 'GM', 'TAL', 'DKNG'
]


def get_stock_data(symbol):
    """获取股票数据"""
    try:
        stock = yf.Ticker(symbol)
        hist = stock.history(period="6mo")
        if hist.empty or len(hist) < 10:
            return None
        
        current = hist['Close'].iloc[-1]
        prev_close = hist['Close'].iloc[-2] if len(hist) > 1 else current
        
        ma5 = hist['Close'].rolling(5).mean().iloc[-1]
        ma10 = hist['Close'].rolling(10).mean().iloc[-1]
        ma20 = hist['Close'].rolling(20).mean().iloc[-1]
        ma30 = hist['Close'].rolling(30).mean().iloc[-1]
        ma60 = hist['Close'].rolling(60).mean().iloc[-1]
        
        delta = hist['Close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
        rsi = 100 - (100 / (1 + gain/loss)).iloc[-1] if loss.iloc[-1] != 0 else 50
        
        exp1 = hist['Close'].ewm(span=12, adjust=False).mean()
        exp2 = hist['Close'].ewm(span=26, adjust=False).mean()
        macd_line = exp1 - exp2
        macd_signal = macd_line.ewm(span=9, adjust=False).mean()
        macd_hist = macd_line - macd_signal
        
        avg_volume = hist['Volume'].rolling(20).mean().iloc[-1]
        volume_ratio = hist['Volume'].iloc[-1] / avg_volume if avg_volume > 0 else 0
        
        return {
            'symbol': symbol,
            'name': stock.info.get('longName', symbol)[:25],
            'price': round(current, 2),
            'change': round(((current - prev_close) / prev_close) * 100, 2),
            'high': round(hist['High'].iloc[-1], 2),
            'low': round(hist['Low'].iloc[-1], 2),
            'volume': int(hist['Volume'].iloc[-1]),
            'ma5': round(ma5, 2),
            'ma10': round(ma10, 2),
            'ma20': round(ma20, 2),
            'ma30': round(ma30, 2),
            'ma60': round(ma60, 2),
            'rsi': round(rsi, 1),
            'macd': round(macd_line.iloc[-1], 3),
            'macd_signal': round(macd_signal.iloc[-1], 3),
            'macd_hist': round(macd_hist.iloc[-1], 3),
            'volume_ratio': round(volume_ratio, 2),
            'prev_close': round(prev_close, 2),
        }
    except Exception as e:
        return None


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/api/stocks')
def get_stocks():
    """获取所有股票数据"""
    results = []
    for symbol in STOCKS:
        data = get_stock_data(symbol)
        if data:
            signal = strategy.get_signal(data)
            data.update(signal)
            results.append(data)
    
    results.sort(key=lambda x: x['score'], reverse=True)
    
    return jsonify({
        'total': len(results),
        'update_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'stocks': results,
        'performance': strategy.get_performance()
    })


@app.route('/api/kline/<symbol>')
def get_kline(symbol):
    """获取K线数据"""
    period = request.args.get('period', '6mo')
    try:
        stock = yf.Ticker(symbol)
        hist = stock.history(period=period)
        if hist.empty:
            return jsonify({'error': 'No data'}), 404
        
        data = []
        for date, row in hist.iterrows():
            data.append({
                'date': date.strftime('%Y-%m-%d'),
                'open': round(row['Open'], 2),
                'high': round(row['High'], 2),
                'low': round(row['Low'], 2),
                'close': round(row['Close'], 2),
                'volume': int(row['Volume']),
            })
        
        closes = hist['Close']
        ma5 = closes.rolling(5).mean().tolist()
        ma10 = closes.rolling(10).mean().tolist()
        ma20 = closes.rolling(20).mean().tolist()
        ma60 = closes.rolling(60).mean().tolist()
        
        return jsonify({
            'symbol': symbol,
            'data': data,
            'ma5': [round(x, 2) if pd.notna(x) else None for x in ma5],
            'ma10': [round(x, 2) if pd.notna(x) else None for x in ma10],
            'ma20': [round(x, 2) if pd.notna(x) else None for x in ma20],
            'ma60': [round(x, 2) if pd.notna(x) else None for x in ma60],
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ============================================================
# 🆕 WebSocket 实时推送
# ============================================================

@socketio.on('connect')
def handle_connect():
    print('✅ 客户端已连接')
    emit('connected', {'data': 'Connected to AI Agent'})


@socketio.on('subscribe')
def handle_subscribe(data):
    """客户端订阅实时数据"""
    symbol = data.get('symbol', 'TSLA')
    print(f'📊 订阅实时数据: {symbol}')
    
    # 启动后台线程推送数据
    def push_data():
        while True:
            stock_data = get_stock_data(symbol)
            if stock_data:
                signal = strategy.get_signal(stock_data)
                stock_data.update(signal)
                emit('stock_update', stock_data)
            time.sleep(5)  # 每5秒推送一次
    
    thread = threading.Thread(target=push_data)
    thread.daemon = True
    thread.start()


if __name__ == '__main__':
    print("=" * 60)
    print("🌐 AI Agent 实时交易系统 (WebSocket)")
    print("=" * 60)
    print("📍 访问地址: http://127.0.0.1:5000")
    print("📊 评分实时更新: 每5秒自动刷新")
    print("=" * 60)
    socketio.run(app, debug=True, host='0.0.0.0', port=5000)