# main.py - 主程序

import time
from datetime import datetime
import schedule
import sys

from config import *
from data_collector import DataCollector
from ai_engine import AIEngine
from notifier import Notifier

class AITradingSystem:
    """AI Agent 自动交易系统"""
    
    def __init__(self):
        print("""
╔═══════════════════════════════════════════════════════════╗
║                                                           ║
║   🤖 AI Agent 自动交易提醒系统 v1.0                      ║
║                                                           ║
║   系统启动中...                                          ║
║                                                           ║
╚═══════════════════════════════════════════════════════════╝
        """)
        
        self.collector = DataCollector(STOCK_POOL)
        self.engine = AIEngine(SCORE_THRESHOLDS, RISK_CONFIG)
        self.notifier = Notifier(NOTIFICATION_CONFIG)
        self.alert_history = {}
    
    def run_analysis(self):
        """执行一次分析"""
        print(f"\n{'='*70}")
        print(f"⏰ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print('='*70)
        
        all_data = self.collector.get_all_data()
        if not all_data:
            print("⚠️ 未获取到数据")
            return
        
        buy_list = []
        watch_list = []
        avoid_list = []
        
        for symbol, data in all_data.items():
            signal = self.engine.get_signal(data)
            data['score'] = signal['score']
            data['action'] = signal['action']
            
            if signal['signal'] in ['STRONG_BUY', 'BUY']:
                buy_list.append((symbol, data, signal))
            elif signal['signal'] == 'WATCH':
                watch_list.append((symbol, data, signal))
            else:
                avoid_list.append((symbol, data, signal))
        
        buy_list.sort(key=lambda x: x[2]['score'], reverse=True)
        
        self.print_results(buy_list, watch_list, avoid_list)
        self.send_alerts(buy_list)
    
    def print_results(self, buy_list, watch_list, avoid_list):
        """打印结果"""
        print(f"\n📊 分析结果:")
        print('-'*70)
        
        if buy_list:
            print(f"\n🟢 买入信号 ({len(buy_list)}只):")
            print("  排名 | 股票 | 评分 | 价格 | 信号")
            print("  " + "-"*55)
            for i, (symbol, data, signal) in enumerate(buy_list[:10], 1):
                print(f"  {i:2}. | {data['name']:10} | {signal['score']:3} | ${data['price']:7.2f} | {signal['action']}")
        else:
            print("\n🟢 暂无买入信号")
        
        if watch_list:
            print(f"\n🟡 观望 ({len(watch_list)}只):")
            for symbol, data, signal in watch_list[:5]:
                print(f"  {data['name']} ({symbol}) | 评分:{signal['score']} | ${data['price']:.2f}")
        
        if avoid_list:
            print(f"\n🔴 回避 ({len(avoid_list)}只):")
            for symbol, data, signal in avoid_list[:5]:
                print(f"  {data['name']} ({symbol}) | 评分:{signal['score']} | {signal['action']}")
        
        print(f"\n{'='*70}")
        print(f"📊 汇总: 买入{len(buy_list)}只 | 观望{len(watch_list)}只 | 回避{len(avoid_list)}只")
    
    def send_alerts(self, buy_list):
        """发送提醒"""
        for symbol, data, signal in buy_list[:5]:
            key = f"{symbol}_buy"
            if key not in self.alert_history:
                self.notifier.send_buy_alert(symbol, data, signal)
                self.alert_history[key] = signal['score']
                time.sleep(1)
    
    def run_scheduled(self):
        """定时运行"""
        print(f"📅 定时任务: {', '.join(SCHEDULE_CONFIG['times'])}")
        print(f"📊 监控股票: {len(STOCK_POOL)} 只")
        print("\n💡 按 Ctrl+C 停止系统\n")
        
        self.run_analysis()
        
        for t in SCHEDULE_CONFIG['times']:
            schedule.every().day.at(t).do(self.run_analysis)
        
        try:
            while True:
                schedule.run_pending()
                time.sleep(30)
        except KeyboardInterrupt:
            print("\n🛑 系统已停止")

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == '--once':
        system = AITradingSystem()
        system.run_analysis()
    else:
        system = AITradingSystem()
        system.run_scheduled()