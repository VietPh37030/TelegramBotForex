"""
TradingView Scanner API - Giá Forex Realtime chuẩn Server
Nguồn: TradingView Scanner (FOREX.com)
Tốc độ: Realtime (theo giây)
Best for: Render, Google Cloud, VPS Linux
"""
import requests
import json
from datetime import datetime
from typing import Dict, Optional
import pandas as pd


class TradingViewScraper:
    """
    Lấy giá từ TradingView Scanner API
    - Giá XAU/USD chuẩn Forex
    - Có signal Buy/Sell từ TradingView
    - Chạy mượt trên Server (không cần bypass)
    """
    
    API_URL = "https://scanner.tradingview.com/cfd/scan"
    
    SYMBOLS = {
        'gold': 'FOREXCOM:XAUUSD',
        'gold_oanda': 'OANDA:XAUUSD',
        'gold_fxcm': 'FXCM:XAUUSD',
    }
    
    HEADERS = {
        'User-Agent': 'Mozilla/5.0 (Compatible; WyckoffBot/2.0)',
        'Content-Type': 'application/json'
    }
    
    def __init__(self, symbol: str = 'FOREXCOM:XAUUSD'):
        self.symbol = symbol
        self.last_price = None
    
    def get_realtime_price(self) -> Dict:
        """
        Lấy giá realtime từ TradingView
        
        Returns:
            Dict với price, open, high, low, change, signal
        """
        payload = {
            "symbols": {
                "tickers": [self.symbol],
                "query": {"types": []}
            },
            "columns": [
                "close",           # Giá hiện tại
                "open",            # Giá mở cửa
                "high",            # Cao nhất
                "low",             # Thấp nhất
                "change",          # Thay đổi %
                "Recommend.All"    # Signal AI TradingView
            ]
        }
        
        try:
            response = requests.post(
                self.API_URL,
                headers=self.HEADERS,
                data=json.dumps(payload),
                timeout=10
            )
            
            if response.status_code == 200:
                data = response.json()
                
                if "data" in data and data["data"]:
                    row = data["data"][0]["d"]
                    
                    # Parse signal
                    signal_value = row[5] if row[5] else 0
                    signal_text = self._parse_signal(signal_value)
                    
                    result = {
                        'price': round(float(row[0]), 2),
                        'open': round(float(row[1]), 2),
                        'high': round(float(row[2]), 2),
                        'low': round(float(row[3]), 2),
                        'change': round(float(row[4]) if row[4] else 0, 2),
                        'signal': signal_text,
                        'signal_value': signal_value,
                        'timestamp': datetime.now().isoformat(),
                        'source': 'tradingview'
                    }
                    
                    self.last_price = result
                    return result
                    
        except Exception as e:
            print(f"⚠️ TradingView API error: {e}")
        
        # Return cached if available
        if self.last_price:
            return {**self.last_price, 'warning': 'Using cached price'}
        
        return {'price': None, 'error': 'TradingView API failed'}
    
    def _parse_signal(self, value: float) -> str:
        """Parse TradingView signal value to text"""
        if value is None:
            return 'NEUTRAL'
        if value > 0.5:
            return 'STRONG_BUY'
        if value > 0.1:
            return 'BUY'
        if value < -0.5:
            return 'STRONG_SELL'
        if value < -0.1:
            return 'SELL'
        return 'NEUTRAL'
    
    def get_candles(self, timeframe: str = '15', count: int = 100) -> pd.DataFrame:
        """
        Lấy dữ liệu nến từ TradingView
        
        Args:
            timeframe: 1, 5, 15, 60, 240, D
            count: Số nến
        """
        # TradingView Scanner không hỗ trợ historical data trực tiếp
        # Fallback: tạo từ realtime data hoặc return empty
        return pd.DataFrame()
    
    def format_for_ai(self) -> str:
        """Format data cho AI analysis"""
        data = self.get_realtime_price()
        
        if not data.get('price'):
            return "Không lấy được giá từ TradingView"
        
        lines = [
            f"📊 GIÁ XAU/USD (TradingView)",
            f"━━━━━━━━━━━━━━━━━━━━━",
            f"💰 Giá hiện tại: ${data['price']:.2f}",
            f"📈 Open: ${data['open']:.2f}",
            f"📊 High: ${data['high']:.2f} | Low: ${data['low']:.2f}",
            f"📉 Change: {data['change']:.2f}%",
            f"🎯 TradingView Signal: {data['signal']}",
            f"⏰ {data['timestamp'][:19]}"
        ]
        
        return "\n".join(lines)


# Quick test
if __name__ == "__main__":
    print("=" * 50)
    print("🧪 TESTING TRADINGVIEW SCRAPER")
    print("=" * 50)
    
    tv = TradingViewScraper()
    
    print("\n📡 Fetching price...")
    result = tv.get_realtime_price()
    
    if result.get('price'):
        print(f"✅ SUCCESS!")
        print(f"   💰 Price: ${result['price']:.2f}")
        print(f"   📈 High: ${result['high']:.2f}")
        print(f"   📉 Low: ${result['low']:.2f}")
        print(f"   🎯 Signal: {result['signal']}")
        print(f"   📊 Source: {result['source']}")
    else:
        print(f"❌ Failed: {result.get('error')}")
    
    print("\n🤖 AI Format:")
    print(tv.format_for_ai())
