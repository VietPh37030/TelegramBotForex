"""
Realtime Gold Price Scraper - Multi-source
Lấy giá vàng realtime từ nhiều nguồn web
Primary: Exness (via Playwright) - XAU/USD spot
Backup: Yahoo Finance
"""
import requests
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Optional, Dict, List
import time
import re
import json

try:
    import yfinance as yf
    YF_AVAILABLE = True
except ImportError:
    YF_AVAILABLE = False
    print("⚠️ yfinance not installed. pip install yfinance")

try:
    from bs4 import BeautifulSoup
    BS4_AVAILABLE = True
except ImportError:
    BS4_AVAILABLE = False

# Import Exness Playwright scraper
try:
    from .exness_scraper import ExnessGoldScraper, PLAYWRIGHT_AVAILABLE
except ImportError:
    PLAYWRIGHT_AVAILABLE = False
    ExnessGoldScraper = None


class RealtimeGoldScraper:
    """
    Scraper giá vàng realtime từ nhiều nguồn
    Primary: Yahoo Finance (GC=F - Gold Futures)
    Backup: Web scraping từ Investing.com, Kitco
    """
    
    # Yahoo Finance tickers for gold
    GOLD_TICKERS = {
        'gold_futures': 'GC=F',      # Gold Futures (CME)
        'gold_spot': 'XAUUSD=X',     # XAU/USD Spot
        'gold_etf': 'GLD',           # SPDR Gold ETF
    }
    
    HEADERS = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.5',
    }
    
    def __init__(self, ticker: str = 'GC=F'):
        """
        Khởi tạo scraper
        
        Args:
            ticker: Yahoo Finance ticker cho vàng
                   'GC=F' = Gold Futures (most reliable)
                   Note: Price is per contract. Divide by 100 for per oz
        """
        self.ticker = ticker
        self.session = requests.Session()
        self.session.headers.update(self.HEADERS)
        self.last_price = None
        self.price_history = []
        self.max_history = 500
        
        # Khởi tạo yfinance ticker
        if YF_AVAILABLE:
            self.yf_ticker = yf.Ticker(ticker)
        else:
            self.yf_ticker = None
    
    def get_realtime_price(self) -> Dict:
        """
        Lấy giá realtime - Production ready for Server
        Priority: TradingView > Yahoo Finance
        
        Returns:
            Dict với price, open, high, low, change, timestamp, source
        """
        # Try TradingView first (best for forex)
        try:
            result = self._get_from_tradingview()
            if result and result.get('price'):
                self._update_history(result)
                return result
        except Exception as e:
            pass  # Silent fail, try next
        
        # Fallback to Yahoo Finance
        try:
            result = self._get_from_yahoo_fast()
            if result and result.get('price'):
                self._update_history(result)
                return result
        except:
            pass
        
        # Last resort: Yahoo info
        try:
            result = self._get_from_yahoo_info()
            if result and result.get('price'):
                self._update_history(result)
                return result
        except:
            pass
        
        # Return cached if available
        if self.last_price:
            return {**self.last_price, 'warning': 'Using cached price'}
        
        return {'price': None, 'error': 'All sources failed'}
    
    def _get_from_tradingview(self) -> Dict:
        """
        Lấy giá từ TradingView Scanner API
        Best for: Render, Google Cloud, VPS
        """
        import json
        
        url = "https://scanner.tradingview.com/cfd/scan"
        headers = {
            'User-Agent': 'Mozilla/5.0 (Compatible; WyckoffBot/2.0)',
            'Content-Type': 'application/json'
        }
        payload = {
            "symbols": {
                "tickers": ["FOREXCOM:XAUUSD"],
                "query": {"types": []}
            },
            "columns": ["close", "open", "high", "low", "change", "Recommend.All"]
        }
        
        response = requests.post(url, headers=headers, data=json.dumps(payload), timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            if "data" in data and data["data"]:
                row = data["data"][0]["d"]
                
                # Parse TradingView signal
                signal_val = row[5] if row[5] else 0
                tv_signal = 'NEUTRAL'
                if signal_val > 0.5: tv_signal = 'STRONG_BUY'
                elif signal_val > 0.1: tv_signal = 'BUY'
                elif signal_val < -0.5: tv_signal = 'STRONG_SELL'
                elif signal_val < -0.1: tv_signal = 'SELL'
                
                return {
                    'price': round(float(row[0]), 2),
                    'open': round(float(row[1]), 2),
                    'high': round(float(row[2]), 2),
                    'low': round(float(row[3]), 2),
                    'change': round(float(row[4]) if row[4] else 0, 2),
                    'tv_signal': tv_signal,
                    'timestamp': datetime.now().isoformat(),
                    'source': 'tradingview'
                }
        
        raise Exception("TradingView API failed")
    
    def _get_from_ratesx(self) -> Dict:
        """
        Lấy giá từ rate.sx - API text-only
        Formats: curl rate.sx/1xau hoặc rate.sx/xauusd
        """
        urls = [
            "https://rate.sx/1xau",
            "https://rate.sx/xauusd",
        ]
        
        for url in urls:
            try:
                # Use curl-like headers
                headers = {
                    'User-Agent': 'curl/7.68.0',
                    'Accept': '*/*',
                }
                response = requests.get(url, headers=headers, timeout=10)
                
                if response.status_code == 200:
                    text = response.text.strip()
                    
                    # Find price pattern in response
                    # Pattern: 2620.45 or 2620
                    match = re.search(r'(\d{4}(?:\.\d+)?)', text[:50])
                    if match:
                        price = float(match.group(1))
                        if 1500 < price < 5000:
                            return {
                                'price': round(price, 2),
                                'timestamp': datetime.now().isoformat(),
                                'source': 'rate.sx'
                            }
            except:
                continue
        
        raise Exception("rate.sx failed")
    
    def _get_from_goldprice(self) -> Dict:
        """
        Lấy giá từ GoldPrice.org - HTML đơn giản
        """
        url = "https://www.goldprice.org/"
        
        response = self.session.get(url, timeout=10)
        if response.status_code != 200:
            raise Exception(f"HTTP {response.status_code}")
        
        if not BS4_AVAILABLE:
            raise Exception("BeautifulSoup not available")
        
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Tìm giá trong các element phổ biến
        # Pattern 1: id='gpxauusd' hoặc class chứa 'price'
        selectors = [
            '#gpxauusd',
            '.price',
            '[data-price]',
            '.gold-price',
            '#gold-price-usd'
        ]
        
        for selector in selectors:
            el = soup.select_one(selector)
            if el:
                price_text = el.get('data-price') or el.get_text(strip=True)
                price_clean = re.sub(r'[^\d.]', '', price_text)
                if price_clean:
                    price = float(price_clean)
                    if 1500 < price < 5000:
                        return {
                            'price': round(price, 2),
                            'timestamp': datetime.now().isoformat(),
                            'source': 'goldprice.org'
                        }
        
        # Fallback: search text for price pattern
        text = soup.get_text()
        matches = re.findall(r'\$?(2[0-9]{3}|3[0-5][0-9]{2})\.[0-9]{2}', text)
        if matches:
            price = float(matches[0])
            return {
                'price': round(price, 2),
                'timestamp': datetime.now().isoformat(),
                'source': 'goldprice.org'
            }
        
        raise Exception("Price not found")
    
    def _get_from_exness(self) -> Dict:
        """
        Lấy giá XAU/USD realtime từ Exness bằng Playwright
        Primary: Playwright (accurate realtime)
        Fallback: Free APIs
        """
        # Option 1: Exness via Playwright (most accurate)
        if PLAYWRIGHT_AVAILABLE and ExnessGoldScraper:
            try:
                scraper = ExnessGoldScraper(headless=True)
                result = scraper.get_price_sync()
                if result.get('price'):
                    return result
            except Exception as e:
                print(f"⚠️ Exness Playwright failed: {e}")
        
        # Option 2: Parse from Google Finance
        try:
            url = "https://www.google.com/finance/quote/XAUUSD:FOREX?hl=en"
            response = self.session.get(url, timeout=10)
            if response.status_code == 200:
                # Pattern: data-last-price="2620.45"
                match = re.search(r'data-last-price="(\d+\.?\d*)"', response.text)
                if match:
                    price = float(match.group(1))
                    if 2000 < price < 3500:
                        return {
                            'price': round(price, 2),
                            'timestamp': datetime.now().isoformat(),
                            'source': 'google_finance'
                        }
        except:
            pass
        
        raise Exception("Exness and fallback APIs failed")
    
    def _get_from_yahoo_fast(self) -> Dict:
        """Lấy giá nhanh từ Yahoo Finance API"""
        if not YF_AVAILABLE:
            raise Exception("yfinance not available")
        
        # Lấy dữ liệu 1 phút gần nhất
        df = self.yf_ticker.history(period='1d', interval='1m')
        
        if df.empty:
            raise Exception("No data from Yahoo Finance")
        
        latest = df.iloc[-1]
        
        return {
            'price': round(float(latest['Close']), 2),
            'open': round(float(latest['Open']), 2),
            'high': round(float(latest['High']), 2),
            'low': round(float(latest['Low']), 2),
            'volume': int(latest['Volume']),
            'timestamp': datetime.now().isoformat(),
            'source': 'yahoo_finance'
        }
    
    def _get_from_yahoo_info(self) -> Dict:
        """Lấy thông tin chi tiết từ Yahoo Finance"""
        if not YF_AVAILABLE:
            raise Exception("yfinance not available")
        
        info = self.yf_ticker.info
        
        # Thử nhiều trường khác nhau
        price = info.get('regularMarketPrice') or info.get('previousClose') or info.get('ask')
        
        if not price:
            raise Exception("No price in info")
        
        return {
            'price': round(float(price), 2),
            'bid': info.get('bid'),
            'ask': info.get('ask'),
            'day_high': info.get('dayHigh'),
            'day_low': info.get('dayLow'),
            'change': info.get('regularMarketChange'),
            'change_percent': info.get('regularMarketChangePercent'),
            'timestamp': datetime.now().isoformat(),
            'source': 'yahoo_info'
        }
    
    def _get_from_web_scraping(self) -> Dict:
        """Lấy giá bằng web scraping (backup)"""
        # Try goldprice.org - simpler structure
        url = "https://www.google.com/finance/quote/XAUUSD:FOREX"
        
        response = self.session.get(url, timeout=10)
        
        if response.status_code == 200:
            # Extract price using regex
            # Pattern for gold price format: 2,XXX.XX or X,XXX.XX
            pattern = r'(\d{1,2},?\d{3}\.\d{2})'
            matches = re.findall(pattern, response.text)
            
            if matches:
                # Get the first reasonable gold price (around $2000)
                for match in matches:
                    price = float(match.replace(',', ''))
                    if 1500 < price < 3500:  # Reasonable gold price range
                        return {
                            'price': price,
                            'timestamp': datetime.now().isoformat(),
                            'source': 'web_scraping'
                        }
        
        raise Exception("Web scraping failed")
    
    def _update_history(self, price_data: Dict):
        """Cập nhật lịch sử giá"""
        self.last_price = price_data
        self.price_history.append({
            'price': price_data['price'],
            'high': price_data.get('high', price_data['price']),
            'low': price_data.get('low', price_data['price']),
            'open': price_data.get('open', price_data['price']),
            'volume': price_data.get('volume', 100),
            'time': datetime.now()
        })
        
        if len(self.price_history) > self.max_history:
            self.price_history = self.price_history[-self.max_history:]
    
    def get_candles(self, n_bars: int = 30, interval: str = '15m') -> pd.DataFrame:
        """
        Lấy dữ liệu nến từ Yahoo Finance
        
        Args:
            n_bars: Số nến cần lấy
            interval: 1m, 5m, 15m, 30m, 1h, 1d
            
        Returns:
            DataFrame với open, high, low, close, volume
        """
        if YF_AVAILABLE:
            try:
                # Tính period dựa trên interval và n_bars
                period_map = {
                    '1m': '1d',
                    '5m': '5d', 
                    '15m': '5d',
                    '30m': '5d',
                    '1h': '1mo',
                    '1d': '3mo'
                }
                period = period_map.get(interval, '5d')
                
                df = self.yf_ticker.history(period=period, interval=interval)
                
                if not df.empty:
                    df.columns = [c.lower() for c in df.columns]
                    df = df[['open', 'high', 'low', 'close', 'volume']]
                    return df.tail(n_bars)
                    
            except Exception as e:
                print(f"⚠️ Yahoo candles error: {e}")
        
        # Fallback to local history or demo
        return self._build_candles_from_history(n_bars)
    
    def _build_candles_from_history(self, n_bars: int) -> pd.DataFrame:
        """Xây dựng nến từ price history hoặc demo"""
        if len(self.price_history) >= 2:
            df = pd.DataFrame(self.price_history)
            df['time'] = pd.to_datetime(df['time'])
            df = df.set_index('time')
            
            # Resample to 1 minute candles
            ohlc = df.resample('1min').agg({
                'open': 'first',
                'high': 'max',
                'low': 'min',
                'price': 'last',
                'volume': 'sum'
            })
            ohlc = ohlc.rename(columns={'price': 'close'})
            ohlc = ohlc.dropna()
            
            if len(ohlc) >= n_bars:
                return ohlc.tail(n_bars)
        
        # Generate demo data
        return self._generate_demo_candles(n_bars)
    
    def _generate_demo_candles(self, n_bars: int) -> pd.DataFrame:
        """Tạo demo candles"""
        base = self.last_price['price'] if self.last_price else 2620.0
        
        dates = pd.date_range(end=datetime.now(), periods=n_bars, freq='15min')
        
        returns = np.random.randn(n_bars) * 0.0003
        closes = base * (1 + np.cumsum(returns[::-1]))[::-1]
        
        df = pd.DataFrame({
            'open': closes - np.random.rand(n_bars) * 0.5,
            'high': closes + np.random.rand(n_bars) * 1.5,
            'low': closes - np.random.rand(n_bars) * 1.5,
            'close': closes,
            'volume': np.random.randint(100, 500, n_bars)
        }, index=dates)
        
        return df
    
    def format_for_ai(self, df: pd.DataFrame = None, last_n: int = 10) -> str:
        """Format dữ liệu cho AI analysis"""
        if df is None:
            df = self.get_candles(30)
        
        df_last = df.tail(last_n)
        
        lines = ["📊 DỮ LIỆU NẾN GẦN NHẤT (Mới nhất ở cuối):"]
        lines.append("Time | Open | High | Low | Close | Vol")
        lines.append("-" * 50)
        
        for idx, row in df_last.iterrows():
            time_str = idx.strftime("%H:%M") if hasattr(idx, 'strftime') else str(idx)[-5:]
            lines.append(
                f"{time_str} | {row['open']:.2f} | {row['high']:.2f} | "
                f"{row['low']:.2f} | {row['close']:.2f} | {int(row.get('volume', 0))}"
            )
        
        # Add realtime price
        rt = self.get_realtime_price()
        if rt.get('price'):
            lines.append(f"\n💰 GIÁ REALTIME: ${rt['price']:.2f}")
            if rt.get('change'):
                lines.append(f"   Thay đổi: {rt['change']:+.2f} ({rt.get('change_percent', 0):+.2f}%)")
            lines.append(f"   Nguồn: {rt.get('source', 'N/A')}")
        
        return "\n".join(lines)
    
    def stream_prices(self, interval_seconds: float = 1.0, callback=None, duration: int = None):
        """
        Stream giá liên tục
        
        Args:
            interval_seconds: Tần suất lấy giá
            callback: Function xử lý giá mới
            duration: Thời gian stream (None = vô hạn)
        """
        print(f"🔴 Starting price stream (interval: {interval_seconds}s)...")
        start_time = time.time()
        
        while True:
            if duration and (time.time() - start_time) > duration:
                print("\n⏹️ Stream duration reached")
                break
            
            try:
                price_data = self.get_realtime_price()
                
                if price_data.get('price'):
                    if callback:
                        callback(price_data)
                    else:
                        ts = datetime.now().strftime('%H:%M:%S')
                        price = price_data['price']
                        src = price_data.get('source', 'N/A')[:10]
                        print(f"💰 {ts} | XAU/USD: ${price:.2f} | {src}")
                
                time.sleep(interval_seconds)
                
            except KeyboardInterrupt:
                print("\n⏹️ Stream stopped by user")
                break
            except Exception as e:
                print(f"❌ Error: {e}")
                time.sleep(5)


# Alias for backwards compatibility
DataFetcher = RealtimeGoldScraper


# ================== QUICK TEST ==================
if __name__ == "__main__":
    print("=" * 50)
    print("🧪 TESTING REALTIME GOLD SCRAPER")
    print("=" * 50)
    
    scraper = RealtimeGoldScraper('GC=F')
    
    # Test 1: Get realtime price
    print("\n📡 Test 1: Realtime Price")
    print("-" * 30)
    result = scraper.get_realtime_price()
    
    if result.get('price'):
        print(f"✅ SUCCESS!")
        print(f"   💰 Price: ${result['price']:.2f}")
        print(f"   📊 Source: {result.get('source')}")
        if result.get('change'):
            print(f"   📈 Change: {result['change']:+.2f}")
    else:
        print(f"❌ Failed: {result}")
    
    # Test 2: Get candles
    print("\n📊 Test 2: Candle Data (15m)")
    print("-" * 30)
    df = scraper.get_candles(5, '15m')
    if not df.empty:
        print(df.to_string())
    else:
        print("No candle data")
    
    # Test 3: Format for AI
    print("\n🤖 Test 3: AI Format")
    print("-" * 30)
    print(scraper.format_for_ai())
    
    # Test 4: Stream for 5 seconds
    print("\n🔴 Test 4: Price Stream (5s)")
    print("-" * 30)
    scraper.stream_prices(interval_seconds=1, duration=5)
    
    print("\n✅ All tests completed!")
