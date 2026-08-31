# notifier.py - 双通道通知模块（Telegram + Bark）
# 版本：v2.0 - 带自动重试机制

import requests
from datetime import datetime
import urllib.parse
import time
import re


class Notifier:
    """双通道通知器 - Telegram主通道 + Bark备用通道"""
    
    def __init__(self, config):
        self.config = config
        
        # Telegram配置
        self.telegram_token = config.get('telegram_bot_token', '')
        self.telegram_chat_id = config.get('telegram_chat_id', '')
        
        # Bark配置
        self.bark_url = config.get('bark_url', '')
        self.enable_bark = config.get('enable_bark', True)
        
        # 控制台
        self.console_print = config.get('console_print', True)
        
        # 防重复提醒
        self.last_notification = {}
    
    # ============================================================
    # 主通道：Telegram Bot（带重试机制）
    # ============================================================
    def send_telegram(self, message):
        """发送Telegram消息（主通道）- 自动重试3次"""
        if not self.telegram_token or '请填入' in self.telegram_token:
            print("⚠️ Telegram未配置")
            return False
        
        # 检查Chat ID是否已配置
        if not self.telegram_chat_id or '请填入' in self.telegram_chat_id:
            print("⚠️ Telegram Chat ID未配置")
            return False
        
        # 重试3次
        for attempt in range(1, 4):
            try:
                url = f"https://api.telegram.org/bot{self.telegram_token}/sendMessage"
                data = {
                    "chat_id": self.telegram_chat_id,
                    "text": message,
                    "parse_mode": "Markdown",
                    "disable_web_page_preview": True
                }
                # 超时时间15秒
                response = requests.post(url, json=data, timeout=15)
                
                if response.status_code == 200:
                    print("✅ Telegram通知已发送")
                    return True
                else:
                    error_msg = response.json()
                    print(f"⚠️ Telegram返回错误 (尝试 {attempt}/3): {error_msg}")
                    
                    # 如果是Chat ID错误，不重试
                    if 'chat not found' in str(error_msg):
                        print("❌ Chat ID错误！请在Telegram搜索 @userinfobot 获取正确的ID")
                        return False
                    # 如果是速率限制，等待后重试
                    if 'Too Many Requests' in str(error_msg):
                        print("⏳ 发送频率过高，等待5秒后重试...")
                        time.sleep(5)
                        continue
                    
            except requests.exceptions.Timeout:
                print(f"⚠️ Telegram超时 (尝试 {attempt}/3)")
                time.sleep(2)
                
            except requests.exceptions.ConnectionError:
                print(f"⚠️ Telegram连接错误 (尝试 {attempt}/3)")
                time.sleep(3)
                
            except Exception as e:
                print(f"⚠️ Telegram异常: {e} (尝试 {attempt}/3)")
                time.sleep(2)
        
        print("❌ Telegram发送失败，已重试3次")
        return False
    
    # ============================================================
    # 备用通道：Bark (iOS)
    # ============================================================
    def send_bark(self, title, content, url=None):
        """发送Bark推送（备用通道 - iOS专用）"""
        if not self.enable_bark:
            return False
        
        if not self.bark_url or '请填入' in self.bark_url:
            print("⚠️ Bark未配置或地址无效")
            return False
        
        try:
            # URL编码内容
            content_encoded = urllib.parse.quote(content, safe='')
            title_encoded = urllib.parse.quote(title, safe='')
            
            # 构建完整URL
            base_url = self.bark_url.rstrip('/')
            
            # 构建参数
            params = []
            params.append("sound=default")          # 默认声音
            params.append("group=AI_Trading")       # 通知分组
            params.append("level=timeSensitive")    # 时间敏感
            
            # 如果有跳转链接
            if url:
                params.append(f"url={urllib.parse.quote(url)}")
            
            # 完整URL
            full_url = f"{base_url}/{title_encoded}/{content_encoded}?{'&'.join(params)}"
            
            response = requests.get(full_url, timeout=10)
            
            if response.status_code == 200:
                print("✅ Bark通知已发送")
                return True
            else:
                print(f"❌ Bark发送失败: {response.text}")
                return False
        except Exception as e:
            print(f"❌ Bark异常: {e}")
            return False
    
    # ============================================================
    # 双通道统一发送
    # ============================================================
    def send(self, title, content, is_markdown=True, url=None):
        """双通道发送 - 同时推送到Telegram和Bark"""
        sent_count = 0
        
        # 1. 控制台打印
        if self.console_print:
            print(f"\n📢 {title}")
            print("-" * 60)
            print(content)
            print("-" * 60)
        
        # 2. 发送到Telegram（主通道）
        if self.telegram_token and '请填入' not in self.telegram_token:
            if self.telegram_chat_id and '请填入' not in self.telegram_chat_id:
                if self.send_telegram(content):
                    sent_count += 1
            else:
                print("⚠️ 跳过Telegram（Chat ID未配置）")
        else:
            print("ℹ️ 跳过Telegram（未配置）")
        
        # 3. 发送到Bark（备用通道）
        if self.enable_bark and self.bark_url and '请填入' not in self.bark_url:
            plain_content = self._strip_markdown(content)
            if self.send_bark(title, plain_content, url):
                sent_count += 1
        else:
            print("ℹ️ 跳过Bark（未配置或已禁用）")
        
        # 4. 统计结果
        if sent_count == 0:
            print("⚠️ 所有通知通道均未成功发送")
            print("📋 请检查：")
            print("   - Telegram: 检查config.py中的Token和Chat ID")
            print("   - Bark: 检查config.py中的Bark地址")
        else:
            print(f"✅ 成功发送到 {sent_count} 个通道")
        
        return sent_count > 0
    
    # ============================================================
    # 工具函数
    # ============================================================
    def _strip_markdown(self, text):
        """移除Markdown符号（Bark不支持Markdown）"""
        # 移除标题符号
        text = text.replace('#', '')
        # 移除表格符号
        text = text.replace('|', ' ')
        text = text.replace('---', '')
        # 移除加粗
        text = text.replace('**', '')
        # 移除代码块
        text = re.sub(r'```.*?```', '', text, flags=re.DOTALL)
        # 移除行内代码
        text = re.sub(r'`.*?`', '', text)
        # 移除链接
        text = re.sub(r'\[.*?\]\(.*?\)', '', text)
        # 移除多个空格
        text = re.sub(r'\s+', ' ', text)
        return text.strip()
    
    # ============================================================
    # 交易信号格式化
    # ============================================================
    def format_buy_signal(self, symbol, data, signal):
        """格式化买入信号（Telegram Markdown格式）"""
        entry_price = data['price']
        stop_loss = round(entry_price * 0.95, 2)
        take_profit = round(entry_price * 1.10, 2)
        
        msg = f"""📈 *{data['name']} ({symbol})*

*信号*: {signal['action']}
*评分*: {signal['score']}/100

📊 *当前数据*
价格: ${data['price']:.2f}
涨跌幅: {data['change']:.2f}%
MA5: ${data['ma5']:.2f}
MA10: ${data['ma10']:.2f}
RSI: {data['rsi']:.1f}

🎯 *交易计划*
仓位: {signal['position']}
止损: ${stop_loss:.2f} (-5%)
止盈: ${take_profit:.2f} (+10%)

🤖 AI Agent · {datetime.now().strftime('%Y-%m-%d %H:%M')}
"""
        return msg
    
    def send_buy_alert(self, symbol, data, signal):
        """发送买入提醒（双通道）"""
        # 防重复提醒
        key = f"{symbol}_buy"
        if key in self.last_notification and self.last_notification[key] >= signal['score']:
            return False
        
        self.last_notification[key] = signal['score']
        
        title = f"📈 买入提醒 - {data['name']} ({symbol})"
        content = self.format_buy_signal(symbol, data, signal)
        
        # Bark点击跳转链接
        url = f"https://finance.yahoo.com/quote/{symbol}"
        
        return self.send(title, content, is_markdown=True, url=url)