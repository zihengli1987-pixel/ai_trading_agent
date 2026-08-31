# ai_engine.py - AI分析引擎

class AIEngine:
    """AI分析引擎"""
    
    def __init__(self, thresholds, risk_config):
        self.thresholds = thresholds
        self.risk_config = risk_config
    
    def calculate_score(self, data):
        """计算综合评分"""
        score = 0
        details = []
        
        # 1. 均线排列 (25分)
        if data['price'] > data['ma5'] and data['ma5'] > data['ma10'] and data['ma10'] > data['ma20']:
            score += 25
            details.append(f"✅ 完美多头排列: +25")
        elif data['price'] > data['ma5'] and data['ma5'] > data['ma10']:
            score += 15
            details.append(f"✅ 短期多头: +15")
        elif data['price'] > data['ma5']:
            score += 5
            details.append(f"✅ 站上MA5: +5")
        else:
            details.append(f"❌ 均线偏弱: +0")
        
        # 2. 价格位置 (20分)
        if data['price'] > data['ma5']:
            score += 10
        if data['price'] > data['ma20']:
            score += 10
        details.append(f"💰 价格位置: +{10 + (10 if data['price'] > data['ma20'] else 0)}")
        
        # 3. MACD (15分)
        if data['macd_hist'] > 0:
            score += 10
            details.append(f"✅ MACD柱为正: +10")
            if data['macd'] > data['macd_signal']:
                score += 5
                details.append(f"✅ MACD金叉: +5")
        else:
            details.append(f"❌ MACD为负: +0")
        
        # 4. RSI (10分)
        if 30 < data['rsi'] < 70:
            score += 10
            details.append(f"✅ RSI健康({data['rsi']:.1f}): +10")
        elif data['rsi'] < 30:
            score += 5
            details.append(f"🟡 RSI超卖({data['rsi']:.1f}): +5")
        else:
            details.append(f"⚠️ RSI偏高({data['rsi']:.1f}): +0")
        
        # 5. 量能 (10分)
        if data['volume_ratio'] > 1.0:
            score += 10
            details.append(f"✅ 放量({data['volume_ratio']:.2f}x): +10")
        elif data['volume_ratio'] > 0.6:
            score += 5
            details.append(f"🟡 正常量能({data['volume_ratio']:.2f}x): +5")
        else:
            details.append(f"❌ 缩量({data['volume_ratio']:.2f}x): +0")
        
        # 6. 动量 (10分)
        if data['change'] > 2:
            score += 10
            details.append(f"✅ 强劲上涨(+{data['change']:.2f}%): +10")
        elif data['change'] > 0:
            score += 5
            details.append(f"✅ 小幅上涨(+{data['change']:.2f}%): +5")
        elif data['change'] > -2:
            score += 2
            details.append(f"🟡 小幅下跌({data['change']:.2f}%): +2")
        else:
            details.append(f"❌ 大幅下跌({data['change']:.2f}%): +0")
        
        return min(score, 100), details
    
    def get_signal(self, data):
        """生成交易信号"""
        score, details = self.calculate_score(data)
        
        if score >= self.thresholds['STRONG_BUY']:
            signal_type = 'STRONG_BUY'
            action = '🟢 强烈买入'
            position = '15%'
        elif score >= self.thresholds['BUY']:
            signal_type = 'BUY'
            action = '🟢 买入'
            position = '10%'
        elif score >= self.thresholds['WATCH']:
            signal_type = 'WATCH'
            action = '🟡 观望等待'
            position = '0%'
        elif score >= self.thresholds['CAUTION']:
            signal_type = 'CAUTION'
            action = '🟠 谨慎/减仓'
            position = '减仓'
        else:
            signal_type = 'AVOID'
            action = '🔴 坚决回避'
            position = '0%'
        
        return {
            'score': score,
            'signal': signal_type,
            'action': action,
            'position': position,
            'details': details
        }