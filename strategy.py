# strategy.py - AI 交易策略引擎（完整版）

import yfinance as yf
import pandas as pd
from datetime import datetime, timedelta
import json
import os


class StrategyEngine:
    """AI 交易策略引擎 - 多因子评分 + 动态交易计划"""
    
    def __init__(self):
        # ============================================================
        # 策略参数配置
        # ============================================================
        
        # ----- 风险参数 -----
        self.stop_loss_pct = 0.06          # 固定止损 6%
        self.take_profit_pct = 0.12        # 止盈 12%
        self.trailing_stop_pct = 0.04      # 追踪止损 4%
        
        # ----- 评分阈值 -----
        self.strong_buy_threshold = 80     # 强烈买入阈值（A级）
        self.buy_threshold = 65            # 买入阈值（B级）
        self.watch_threshold = 50          # 观望阈值（C级）
        self.caution_threshold = 35        # 谨慎阈值（D级）
        # < 35分 = E级 坚决回避
        
        # ----- 因子权重 -----
        self.weights = {
            'ma_alignment': 25,    # 均线排列
            'price_position': 20,  # 价格位置
            'macd': 15,            # MACD
            'rsi': 10,             # RSI
            'volume': 10,          # 量能
            'momentum': 10,        # 动量
            'ma_cross': 10,        # 均线交叉（额外加分）
        }
        
        # ============================================================
        # 持仓管理
        # ============================================================
        self.positions = {}  # {symbol: {entry_price, shares, stop_loss, take_profit, entry_date}}
        
        # ============================================================
        # 交易历史
        # ============================================================
        self.trade_history = []
        self.history_file = 'trade_history.json'
        
        # ============================================================
        # 评分历史（用于趋势分析）
        # ============================================================
        self.score_history = {}
        self.score_history_file = 'score_history.json'
        
        # ============================================================
        # 加载历史数据
        # ============================================================
        self._load_history()
        self._load_score_history()
    
    
    # ============================================================
    # 核心策略函数
    # ============================================================
    
    def calculate_score(self, data):
        """
        计算综合评分 (0-100)
        
        参数:
            data: 包含 price, ma5, ma10, ma20, ma30, ma60, rsi, macd, macd_signal, macd_hist, volume_ratio, change
        
        返回:
            score: 0-100 的评分
            details: 评分明细列表
        """
        score = 0
        details = []
        
        # ============================================================
        # 1. 均线排列 (25分)
        # ============================================================
        ma_score = 0
        if data['price'] > data['ma5'] and data['ma5'] > data['ma10'] and data['ma10'] > data['ma20']:
            ma_score = 25
            details.append("✅ 完美多头排列 (MA5>MA10>MA20): +25")
        elif data['price'] > data['ma5'] and data['ma5'] > data['ma10']:
            ma_score = 15
            details.append("✅ 短期多头 (MA5>MA10): +15")
        elif data['price'] > data['ma5']:
            ma_score = 5
            details.append("✅ 站上MA5: +5")
        else:
            details.append("❌ 均线偏弱: +0")
        score += ma_score
        
        # ============================================================
        # 2. 价格位置 (20分)
        # ============================================================
        pos_score = 0
        if data['price'] > data['ma5']:
            pos_score += 10
        if data['price'] > data['ma20']:
            pos_score += 10
        details.append(f"💰 价格位置 (MA5:{data['price'] > data['ma5']}, MA20:{data['price'] > data['ma20']}): +{pos_score}")
        score += pos_score
        
        # ============================================================
        # 3. MACD (15分)
        # ============================================================
        macd_score = 0
        if data['macd_hist'] > 0:
            macd_score += 10
            details.append(f"✅ MACD柱为正 ({data['macd_hist']:.3f}): +10")
            if data['macd'] > data['macd_signal']:
                macd_score += 5
                details.append(f"✅ MACD金叉 (DIF>{data['macd_signal']:.3f}): +5")
        else:
            details.append(f"❌ MACD为负 ({data['macd_hist']:.3f}): +0")
        score += macd_score
        
        # ============================================================
        # 4. RSI (10分)
        # ============================================================
        rsi_score = 0
        if 30 < data['rsi'] < 70:
            rsi_score = 10
            details.append(f"✅ RSI健康 ({data['rsi']:.1f}): +10")
        elif data['rsi'] < 30:
            rsi_score = 5
            details.append(f"🟡 RSI超卖 ({data['rsi']:.1f}): +5")
        else:
            details.append(f"⚠️ RSI偏高 ({data['rsi']:.1f}): +0")
        score += rsi_score
        
        # ============================================================
        # 5. 量能 (10分)
        # ============================================================
        volume_score = 0
        if data['volume_ratio'] > 1.0:
            volume_score = 10
            details.append(f"✅ 放量 ({data['volume_ratio']:.2f}x): +10")
        elif data['volume_ratio'] > 0.6:
            volume_score = 5
            details.append(f"🟡 正常量能 ({data['volume_ratio']:.2f}x): +5")
        else:
            details.append(f"❌ 缩量 ({data['volume_ratio']:.2f}x): +0")
        score += volume_score
        
        # ============================================================
        # 6. 动量 (10分)
        # ============================================================
        momentum_score = 0
        if data['change'] > 2:
            momentum_score = 10
            details.append(f"✅ 强劲上涨 (+{data['change']:.2f}%): +10")
        elif data['change'] > 0:
            momentum_score = 5
            details.append(f"✅ 小幅上涨 (+{data['change']:.2f}%): +5")
        elif data['change'] > -2:
            momentum_score = 2
            details.append(f"🟡 小幅下跌 ({data['change']:.2f}%): +2")
        else:
            details.append(f"❌ 大幅下跌 ({data['change']:.2f}%): +0")
        score += momentum_score
        
        # ============================================================
        # 7. 额外加分：均线交叉信号（最多10分）
        # ============================================================
        bonus = 0
        
        # MA5 上穿 MA10（金叉）
        if data['ma5'] > data['ma10']:
            bonus += 3
            details.append("📈 MA5 > MA10 (金叉): +3")
        
        # MA10 上穿 MA20（金叉）
        if data['ma10'] > data['ma20']:
            bonus += 3
            details.append("📈 MA10 > MA20 (金叉): +3")
        
        # MA20 上穿 MA30（金叉）
        if data['ma20'] > data['ma30']:
            bonus += 2
            details.append("📈 MA20 > MA30 (金叉): +2")
        
        # MA30 上穿 MA60（金叉）
        if data['ma30'] > data['ma60']:
            bonus += 2
            details.append("📈 MA30 > MA60 (金叉): +2")
        
        score += min(bonus, 10)
        
        # ============================================================
        # 8. 额外扣分：空头信号
        # ============================================================
        penalty = 0
        
        # 价格低于 MA60（长期趋势走弱）
        if data['price'] < data['ma60']:
            penalty += 5
            details.append("⚠️ 价格低于 MA60: -5")
        
        # RSI 高于 75（严重超买）
        if data['rsi'] > 75:
            penalty += 5
            details.append("⚠️ RSI 超买 (>75): -5")
        
        score -= min(penalty, 10)
        
        # ============================================================
        # 确保分数在 0-100 之间
        # ============================================================
        score = max(0, min(100, score))
        
        return score, details
    
    
    def get_signal(self, data):
        """
        生成交易信号
        
        参数:
            data: 股票数据字典
        
        返回:
            signal: 包含评分、信号类型、交易计划等
        """
        score, details = self.calculate_score(data)
        
        # ============================================================
        # 确定信号等级
        # ============================================================
        if score >= self.strong_buy_threshold:
            signal_type = 'STRONG_BUY'
            action = '🟢 强烈买入'
            position = '15-20%'
            color = 'green'
            priority = 1
            emoji = '🔥'
        elif score >= self.buy_threshold:
            signal_type = 'BUY'
            action = '🟢 买入'
            position = '10-15%'
            color = 'lightgreen'
            priority = 2
            emoji = '📈'
        elif score >= self.watch_threshold:
            signal_type = 'WATCH'
            action = '🟡 观望等待'
            position = '5-10%'
            color = 'yellow'
            priority = 3
            emoji = '👀'
        elif score >= self.caution_threshold:
            signal_type = 'CAUTION'
            action = '🟠 谨慎/减仓'
            position = '0-5%'
            color = 'orange'
            priority = 4
            emoji = '⚠️'
        else:
            signal_type = 'AVOID'
            action = '🔴 坚决回避'
            position = '0%'
            color = 'red'
            priority = 5
            emoji = '🚫'
        
        # ============================================================
        # 计算交易计划
        # ============================================================
        
        # 买入价：使用 MA20 作为参考
        entry_price = data['ma20'] if data['ma20'] > 0 else data['price']
        
        # 根据评分动态调整止损止盈
        if score >= 85:
            stop_loss = round(entry_price * 0.92, 2)   # -8%
            take_profit = round(entry_price * 1.15, 2)  # +15%
            risk_multiplier = 1.0
        elif score >= 70:
            stop_loss = round(entry_price * 0.94, 2)   # -6%
            take_profit = round(entry_price * 1.12, 2)  # +12%
            risk_multiplier = 0.8
        elif score >= 50:
            stop_loss = round(entry_price * 0.95, 2)   # -5%
            take_profit = round(entry_price * 1.10, 2)  # +10%
            risk_multiplier = 0.6
        else:
            stop_loss = round(entry_price * 0.96, 2)   # -4%
            take_profit = round(entry_price * 1.08, 2)  # +8%
            risk_multiplier = 0.4
        
        # 计算盈亏比
        risk = entry_price - stop_loss
        reward = take_profit - entry_price
        risk_reward_ratio = round(reward / risk, 2) if risk > 0 else 0
        
        # ============================================================
        # 构建返回结果
        # ============================================================
        return {
            'score': score,
            'signal_type': signal_type,
            'action': action,
            'position': position,
            'color': color,
            'priority': priority,
            'emoji': emoji,
            'details': details,
            'entry_price': round(entry_price, 2),
            'stop_loss': stop_loss,
            'take_profit': take_profit,
            'risk_reward_ratio': risk_reward_ratio,
            'stop_loss_pct': round((1 - stop_loss/entry_price) * 100, 1) if entry_price > 0 else 0,
            'take_profit_pct': round((take_profit/entry_price - 1) * 100, 1) if entry_price > 0 else 0,
        }
    
    
    # ============================================================
    # 风险控制
    # ============================================================
    
    def check_stop_loss(self, symbol, current_price):
        """检查是否触发止损"""
        if symbol in self.positions:
            pos = self.positions[symbol]
            if current_price <= pos['stop_loss']:
                return True, 'STOP_LOSS'
        return False, None
    
    def check_take_profit(self, symbol, current_price):
        """检查是否触发止盈"""
        if symbol in self.positions:
            pos = self.positions[symbol]
            if current_price >= pos['take_profit']:
                return True, 'TAKE_PROFIT'
        return False, None
    
    def update_trailing_stop(self, symbol, current_price):
        """更新追踪止损"""
        if symbol in self.positions:
            pos = self.positions[symbol]
            new_stop = current_price * (1 - self.trailing_stop_pct)
            if new_stop > pos['stop_loss']:
                pos['stop_loss'] = round(new_stop, 2)
                return True, pos['stop_loss']
        return False, None
    
    def add_position(self, symbol, entry_price, shares):
        """添加持仓"""
        stop_loss = round(entry_price * (1 - self.stop_loss_pct), 2)
        take_profit = round(entry_price * (1 + self.take_profit_pct), 2)
        
        self.positions[symbol] = {
            'entry_price': entry_price,
            'shares': shares,
            'stop_loss': stop_loss,
            'take_profit': take_profit,
            'entry_date': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'current_price': entry_price,
            'pnl': 0,
            'pnl_pct': 0
        }
        self._save_positions()
        return self.positions[symbol]
    
    def update_position(self, symbol, current_price):
        """更新持仓价格"""
        if symbol in self.positions:
            pos = self.positions[symbol]
            pos['current_price'] = current_price
            pos['pnl'] = round((current_price - pos['entry_price']) * pos['shares'], 2)
            pos['pnl_pct'] = round((current_price / pos['entry_price'] - 1) * 100, 2)
            return pos
        return None
    
    def close_position(self, symbol, exit_price):
        """平仓"""
        if symbol in self.positions:
            pos = self.positions[symbol]
            profit = round((exit_price - pos['entry_price']) * pos['shares'], 2)
            profit_pct = round((exit_price / pos['entry_price'] - 1) * 100, 2)
            
            trade = {
                'symbol': symbol,
                'entry_price': pos['entry_price'],
                'exit_price': exit_price,
                'shares': pos['shares'],
                'profit': profit,
                'profit_pct': profit_pct,
                'entry_date': pos['entry_date'],
                'exit_date': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'holding_days': (datetime.now() - datetime.strptime(pos['entry_date'], '%Y-%m-%d %H:%M:%S')).days
            }
            self.trade_history.append(trade)
            self._save_history()
            
            del self.positions[symbol]
            self._save_positions()
            return trade
        return None
    
    def get_open_positions(self):
        """获取所有持仓"""
        return self.positions
    
    def get_position_summary(self):
        """获取持仓汇总"""
        if not self.positions:
            return {'total': 0, 'total_value': 0, 'total_pnl': 0}
        
        total_value = 0
        total_pnl = 0
        for symbol, pos in self.positions.items():
            total_value += pos['current_price'] * pos['shares']
            total_pnl += pos['pnl']
        
        return {
            'total': len(self.positions),
            'total_value': round(total_value, 2),
            'total_pnl': round(total_pnl, 2)
        }
    
    
    # ============================================================
    # 策略表现统计
    # ============================================================
    
    def get_performance(self):
        """获取策略表现统计"""
        if not self.trade_history:
            return {
                'total_trades': 0,
                'win_rate': 0,
                'total_profit': 0,
                'avg_profit': 0,
                'max_profit': 0,
                'max_loss': 0,
                'avg_holding_days': 0
            }
        
        total = len(self.trade_history)
        wins = sum(1 for t in self.trade_history if t['profit'] > 0)
        total_profit = sum(t['profit'] for t in self.trade_history)
        avg_holding = sum(t.get('holding_days', 0) for t in self.trade_history) / total if total > 0 else 0
        
        return {
            'total_trades': total,
            'win_rate': round(wins / total * 100, 1) if total > 0 else 0,
            'total_profit': round(total_profit, 2),
            'avg_profit': round(total_profit / total, 2) if total > 0 else 0,
            'max_profit': max((t['profit'] for t in self.trade_history), default=0),
            'max_loss': min((t['profit'] for t in self.trade_history), default=0),
            'avg_holding_days': round(avg_holding, 1),
        }
    
    def get_score_history(self, symbol, limit=20):
        """获取股票的评分历史"""
        if symbol in self.score_history:
            return self.score_history[symbol][-limit:]
        return []
    
    
    # ============================================================
    # 数据持久化
    # ============================================================
    
    def _load_history(self):
        """加载交易历史"""
        try:
            if os.path.exists(self.history_file):
                with open(self.history_file, 'r') as f:
                    self.trade_history = json.load(f)
        except:
            self.trade_history = []
    
    def _save_history(self):
        """保存交易历史"""
        try:
            with open(self.history_file, 'w') as f:
                json.dump(self.trade_history, f, indent=2)
        except:
            pass
    
    def _load_score_history(self):
        """加载评分历史"""
        try:
            if os.path.exists(self.score_history_file):
                with open(self.score_history_file, 'r') as f:
                    self.score_history = json.load(f)
        except:
            self.score_history = {}
    
    def _save_score_history(self):
        """保存评分历史"""
        try:
            with open(self.score_history_file, 'w') as f:
                json.dump(self.score_history, f, indent=2)
        except:
            pass
    
    def _save_positions(self):
        """保存持仓"""
        try:
            with open('positions.json', 'w') as f:
                json.dump(self.positions, f, indent=2)
        except:
            pass
    
    def add_score_record(self, symbol, score, price, signal):
        """添加评分记录"""
        if symbol not in self.score_history:
            self.score_history[symbol] = []
        self.score_history[symbol].append({
            'time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'score': score,
            'price': price,
            'signal': signal
        })
        # 只保留最近200条
        if len(self.score_history[symbol]) > 200:
            self.score_history[symbol] = self.score_history[symbol][-200:]
        self._save_score_history()
    
    
    # ============================================================
    # 工具函数
    # ============================================================
    
    def get_score_distribution(self, stocks_data):
        """获取评分分布统计"""
        if not stocks_data:
            return {}
        
        distribution = {
            'A级 (≥80)': 0,
            'B级 (65-79)': 0,
            'C级 (50-64)': 0,
            'D级 (35-49)': 0,
            'E级 (<35)': 0
        }
        
        for data in stocks_data:
            score = data.get('score', 0)
            if score >= 80:
                distribution['A级 (≥80)'] += 1
            elif score >= 65:
                distribution['B级 (65-79)'] += 1
            elif score >= 50:
                distribution['C级 (50-64)'] += 1
            elif score >= 35:
                distribution['D级 (35-49)'] += 1
            else:
                distribution['E级 (<35)'] += 1
        
        return distribution
    
    def get_top_stocks(self, stocks_data, n=10):
        """获取评分最高的N只股票"""
        sorted_stocks = sorted(stocks_data, key=lambda x: x.get('score', 0), reverse=True)
        return sorted_stocks[:n]
    
    def get_buy_signals(self, stocks_data):
        """获取所有买入信号"""
        return [s for s in stocks_data if s.get('score', 0) >= self.buy_threshold]
    
    def get_strong_buy_signals(self, stocks_data):
        """获取所有强烈买入信号"""
        return [s for s in stocks_data if s.get('score', 0) >= self.strong_buy_threshold]