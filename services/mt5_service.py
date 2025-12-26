"""
MetaTrader 5 Integration - Giá Realtime + Lịch Kinh Tế
Cách "chính đạo" nhất để lấy data Forex
"""
import MetaTrader5 as mt5
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
import pandas as pd


@dataclass
class MT5Price:
    """Giá từ MT5"""
    symbol: str
    bid: float
    ask: float
    spread: float
    time: datetime
    
    @property
    def mid(self) -> float:
        return (self.bid + self.ask) / 2


@dataclass
class MT5News:
    """Tin tức từ MT5 Calendar"""
    time: datetime
    currency: str
    importance: int  # 1=Low, 2=Medium, 3=High
    name: str
    forecast: str
    previous: str
    actual: str


class MT5Service:
    """
    Kết nối MetaTrader 5 để lấy:
    - Giá realtime (tick-by-tick)
    - Lịch kinh tế
    - OHLC data
    """
    
    GOLD_SYMBOLS = ['XAUUSD', 'GOLD', 'XAUUSDm', 'GOLDm', 'XAU/USD']
    
    def __init__(self):
        """Khởi tạo và kết nối MT5"""
        self.connected = False
        self.gold_symbol = None
        
        if self._connect():
            self._find_gold_symbol()
    
    def _connect(self) -> bool:
        """Kết nối MT5"""
        try:
            if not mt5.initialize():
                print(f"⚠️ MT5 initialize failed: {mt5.last_error()}")
                print("   Hãy mở MT5 và đăng nhập trước khi chạy bot!")
                return False
            
            # Get account info
            account = mt5.account_info()
            if account:
                print(f"✅ MT5 Connected: {account.name} ({account.server})")
                print(f"   Balance: ${account.balance:.2f}")
                self.connected = True
                return True
            else:
                print("⚠️ MT5: Không lấy được thông tin tài khoản")
                return False
                
        except Exception as e:
            print(f"❌ MT5 error: {e}")
            return False
    
    def _find_gold_symbol(self):
        """Tìm symbol Gold trên sàn"""
        if not self.connected:
            return
        
        for sym in self.GOLD_SYMBOLS:
            info = mt5.symbol_info(sym)
            if info is not None:
                self.gold_symbol = sym
                print(f"   Gold symbol: {sym}")
                return
        
        # Search in all symbols
        symbols = mt5.symbols_get()
        if symbols:
            for s in symbols:
                if 'XAU' in s.name.upper() or 'GOLD' in s.name.upper():
                    self.gold_symbol = s.name
                    print(f"   Gold symbol: {s.name}")
                    return
        
        print("⚠️ Không tìm thấy symbol Gold!")
    
    def get_realtime_price(self, symbol: str = None) -> Optional[MT5Price]:
        """
        Lấy giá realtime tick-by-tick
        
        Args:
            symbol: Symbol (mặc định XAUUSD)
        
        Returns:
            MT5Price với bid, ask, spread
        """
        if not self.connected:
            return None
        
        sym = symbol or self.gold_symbol
        if not sym:
            return None
        
        tick = mt5.symbol_info_tick(sym)
        if tick:
            return MT5Price(
                symbol=sym,
                bid=tick.bid,
                ask=tick.ask,
                spread=round(tick.ask - tick.bid, 2),
                time=datetime.fromtimestamp(tick.time)
            )
        
        return None
    
    def get_candles(self, symbol: str = None, timeframe: str = 'M15', count: int = 100) -> pd.DataFrame:
        """
        Lấy dữ liệu nến OHLC
        
        Args:
            symbol: Symbol
            timeframe: M1, M5, M15, M30, H1, H4, D1
            count: Số nến
        
        Returns:
            DataFrame với open, high, low, close, volume
        """
        if not self.connected:
            return pd.DataFrame()
        
        sym = symbol or self.gold_symbol
        if not sym:
            return pd.DataFrame()
        
        # Map timeframe string to MT5 constant
        tf_map = {
            'M1': mt5.TIMEFRAME_M1,
            'M5': mt5.TIMEFRAME_M5,
            'M15': mt5.TIMEFRAME_M15,
            'M30': mt5.TIMEFRAME_M30,
            'H1': mt5.TIMEFRAME_H1,
            'H4': mt5.TIMEFRAME_H4,
            'D1': mt5.TIMEFRAME_D1,
        }
        tf = tf_map.get(timeframe.upper(), mt5.TIMEFRAME_M15)
        
        rates = mt5.copy_rates_from_pos(sym, tf, 0, count)
        
        if rates is not None and len(rates) > 0:
            df = pd.DataFrame(rates)
            df['time'] = pd.to_datetime(df['time'], unit='s')
            df = df.set_index('time')
            df = df.rename(columns={'tick_volume': 'volume'})
            return df[['open', 'high', 'low', 'close', 'volume']]
        
        return pd.DataFrame()
    
    def get_calendar(self, hours_ahead: int = 24, currency: str = 'USD', 
                     min_importance: int = 2) -> List[MT5News]:
        """
        Lấy lịch kinh tế từ MT5
        
        Args:
            hours_ahead: Số giờ tới cần lấy tin
            currency: Lọc theo currency (USD, EUR, etc)
            min_importance: Mức quan trọng tối thiểu (1-3)
        
        Returns:
            List tin tức quan trọng
        """
        if not self.connected:
            return []
        
        start = datetime.now()
        end = start + timedelta(hours=hours_ahead)
        
        try:
            # Lấy events từ MT5
            events = mt5.calendar_events(
                login=None,
                time_from=start,
                time_to=end
            )
            
            if not events:
                return []
            
            news_list = []
            for e in events:
                # Lọc theo importance và currency
                if e.importance >= min_importance:
                    if currency.upper() in e.currency_code.upper():
                        news_list.append(MT5News(
                            time=e.time,
                            currency=e.currency_code,
                            importance=e.importance,
                            name=e.name,
                            forecast=str(e.forecast_value) if e.forecast_value else '',
                            previous=str(e.prev_value) if e.prev_value else '',
                            actual=str(e.actual_value) if e.actual_value else ''
                        ))
            
            return news_list
            
        except Exception as e:
            print(f"⚠️ MT5 calendar error: {e}")
            return []
    
    def get_high_impact_news(self) -> List[MT5News]:
        """Lấy tin 3 sao (High Impact) cho USD"""
        return self.get_calendar(hours_ahead=24, currency='USD', min_importance=3)
    
    def should_pause_trading(self, minutes_before: int = 30) -> Tuple[bool, Optional[MT5News]]:
        """
        Kiểm tra có nên tạm dừng trading không
        
        Returns:
            (should_pause, upcoming_news)
        """
        high_impact = self.get_high_impact_news()
        now = datetime.now()
        
        for news in high_impact:
            time_diff = (news.time - now).total_seconds() / 60
            
            if 0 <= time_diff <= minutes_before:
                return True, news
        
        return False, None
    
    def format_price_for_ai(self, df: pd.DataFrame = None) -> str:
        """Format data cho AI analysis"""
        if df is None:
            df = self.get_candles(count=30)
        
        if df.empty:
            return "Không có dữ liệu"
        
        df_last = df.tail(10)
        
        lines = [f"📊 DỮ LIỆU NẾN {self.gold_symbol} (Mới nhất ở cuối):"]
        lines.append("Time | Open | High | Low | Close | Vol")
        lines.append("-" * 50)
        
        for idx, row in df_last.iterrows():
            time_str = idx.strftime("%H:%M") if hasattr(idx, 'strftime') else str(idx)[-5:]
            lines.append(
                f"{time_str} | {row['open']:.2f} | {row['high']:.2f} | "
                f"{row['low']:.2f} | {row['close']:.2f} | {int(row.get('volume', 0))}"
            )
        
        # Realtime price
        rt = self.get_realtime_price()
        if rt:
            lines.append(f"\n💰 GIÁ REALTIME:")
            lines.append(f"   Bid: ${rt.bid:.2f}")
            lines.append(f"   Ask: ${rt.ask:.2f}")
            lines.append(f"   Spread: {rt.spread:.2f}")
        
        return "\n".join(lines)
    
    def shutdown(self):
        """Đóng kết nối MT5"""
        if self.connected:
            mt5.shutdown()
            self.connected = False
            print("MT5 disconnected")


# Quick test
if __name__ == "__main__":
    print("=" * 50)
    print("🧪 TESTING MT5 SERVICE")
    print("=" * 50)
    
    mt5_service = MT5Service()
    
    if mt5_service.connected:
        # Test realtime price
        print("\n📡 Realtime Price:")
        price = mt5_service.get_realtime_price()
        if price:
            print(f"   {price.symbol}: Bid ${price.bid:.2f} | Ask ${price.ask:.2f}")
        
        # Test candles
        print("\n📊 Candles (M15):")
        df = mt5_service.get_candles(timeframe='M15', count=5)
        if not df.empty:
            print(df.to_string())
        
        # Test calendar
        print("\n📰 Economic Calendar (High Impact USD):")
        news = mt5_service.get_high_impact_news()
        for n in news[:5]:
            print(f"   {n.time} | {n.currency} | {n.name}")
        
        # Shutdown
        mt5_service.shutdown()
    else:
        print("\n⚠️ MT5 not connected!")
        print("   1. Mở MetaTrader 5")
        print("   2. Đăng nhập tài khoản")
        print("   3. Chạy lại script này")
    
    print("\n✅ Test completed!")
