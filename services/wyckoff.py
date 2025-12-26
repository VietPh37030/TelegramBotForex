"""
Wyckoff Analysis Module - Phân tích theo phương pháp Wyckoff
Phát hiện Spring, Upthrust, SOS, SOW, LPS, Phases
"""
import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass


@dataclass
class WyckoffEvent:
    """Sự kiện Wyckoff được phát hiện"""
    event_type: str  # SPRING, UPTHRUST, SOS, SOW, SC, BC, AR, ST, LPS, LPSY
    confidence: float  # 0-100
    price_level: float
    volume_confirmation: bool
    description: str


class WyckoffAnalyzer:
    """
    Phân tích thị trường theo Phương pháp Wyckoff
    - Xác định Pha (Accumulation, Distribution, Markup, Markdown)
    - Phát hiện các Sự kiện (Spring, Upthrust, SOS, SOW...)
    - Volume Spread Analysis (VSA)
    """
    
    # Các pha Wyckoff
    PHASES = {
        'ACCUMULATION': 'Tích lũy - Composite Man đang mua',
        'DISTRIBUTION': 'Phân phối - Composite Man đang bán',
        'MARKUP': 'Đẩy giá lên - Xu hướng tăng',
        'MARKDOWN': 'Đẩy giá xuống - Xu hướng giảm',
        'UNKNOWN': 'Chưa xác định'
    }
    
    def __init__(self, lookback: int = 50):
        """
        Args:
            lookback: Số nến nhìn lại để phân tích
        """
        self.lookback = lookback
    
    def analyze(self, df: pd.DataFrame) -> Dict:
        """
        Phân tích toàn diện theo Wyckoff
        
        Returns:
            Dict với phase, events, signals
        """
        if len(df) < 20:
            return {'phase': 'UNKNOWN', 'events': [], 'signal': None}
        
        # Tính các chỉ số cần thiết
        df = self._prepare_data(df)
        
        # Xác định phase
        phase = self._detect_phase(df)
        
        # Phát hiện các sự kiện
        events = []
        
        spring = self._detect_spring(df)
        if spring:
            events.append(spring)
        
        upthrust = self._detect_upthrust(df)
        if upthrust:
            events.append(upthrust)
        
        sos = self._detect_sign_of_strength(df)
        if sos:
            events.append(sos)
        
        sow = self._detect_sign_of_weakness(df)
        if sow:
            events.append(sow)
        
        # VSA Analysis
        vsa = self._volume_spread_analysis(df)
        
        # Tổng hợp tín hiệu
        signal = self._generate_signal(phase, events, vsa)
        
        return {
            'phase': phase,
            'phase_description': self.PHASES.get(phase, ''),
            'events': events,
            'vsa': vsa,
            'signal': signal
        }
    
    def _prepare_data(self, df: pd.DataFrame) -> pd.DataFrame:
        """Chuẩn bị dữ liệu với các chỉ số cần thiết"""
        df = df.copy()
        
        # Volume moving average
        df['vol_sma'] = df['volume'].rolling(20).mean()
        df['rel_volume'] = df['volume'] / df['vol_sma']
        
        # Price spread
        df['spread'] = df['high'] - df['low']
        df['spread_sma'] = df['spread'].rolling(20).mean()
        
        # Body và Wicks
        df['body'] = abs(df['close'] - df['open'])
        df['upper_wick'] = df['high'] - df[['open', 'close']].max(axis=1)
        df['lower_wick'] = df[['open', 'close']].min(axis=1) - df['low']
        
        # Swing points
        df['swing_high'] = df['high'].rolling(5, center=True).max()
        df['swing_low'] = df['low'].rolling(5, center=True).min()
        
        return df
    
    def _detect_phase(self, df: pd.DataFrame) -> str:
        """Xác định pha Wyckoff hiện tại"""
        # Lấy dữ liệu gần nhất
        recent = df.tail(30)
        
        # Tính trend
        price_change = (recent['close'].iloc[-1] - recent['close'].iloc[0]) / recent['close'].iloc[0]
        
        # Range bound check
        high_range = recent['high'].max()
        low_range = recent['low'].min()
        range_size = (high_range - low_range) / recent['close'].mean()
        
        current_price = recent['close'].iloc[-1]
        mid_range = (high_range + low_range) / 2
        
        # Logic xác định phase
        if range_size < 0.03:  # Biên độ hẹp <3%
            # Đang trong Trading Range
            if current_price > mid_range:
                # Volume tăng ở đáy, giảm ở đỉnh -> Accumulation
                return 'ACCUMULATION'
            else:
                return 'DISTRIBUTION'
        else:
            if price_change > 0.02:
                return 'MARKUP'
            elif price_change < -0.02:
                return 'MARKDOWN'
        
        return 'UNKNOWN'
    
    def _detect_spring(self, df: pd.DataFrame) -> Optional[WyckoffEvent]:
        """
        Phát hiện Spring (Bẫy Gấu)
        - Giá phá vỡ support rồi quay lại
        - Volume cao tại điểm phá vỡ
        """
        if len(df) < 10:
            return None
        
        recent = df.tail(10)
        
        # Tìm support (đáy gần nhất trong 20 nến trước)
        support = df.tail(30).head(20)['low'].min()
        
        # Kiểm tra 5 nến gần nhất
        for i in range(-5, 0):
            candle = recent.iloc[i]
            
            # Điều kiện Spring:
            # 1. Low phá vỡ support
            if candle['low'] < support:
                # 2. Close quay lại trên support
                if candle['close'] > support:
                    # 3. Volume cao
                    vol_confirm = candle['volume'] > df['volume'].mean() * 1.2
                    
                    # 4. Lower wick dài (rejection)
                    wick_ratio = candle['lower_wick'] / candle['spread'] if candle['spread'] > 0 else 0
                    
                    if wick_ratio > 0.5:
                        confidence = 70 + (wick_ratio * 20) + (10 if vol_confirm else 0)
                        return WyckoffEvent(
                            event_type='SPRING',
                            confidence=min(confidence, 95),
                            price_level=support,
                            volume_confirmation=vol_confirm,
                            description=f'🟢 SPRING tại ${support:.2f} - Bẫy gấu, tín hiệu MUA mạnh!'
                        )
        
        return None
    
    def _detect_upthrust(self, df: pd.DataFrame) -> Optional[WyckoffEvent]:
        """
        Phát hiện Upthrust (Bẫy Bò)
        - Giá phá vỡ resistance rồi quay lại
        - Volume cao tại điểm phá vỡ
        """
        if len(df) < 10:
            return None
        
        recent = df.tail(10)
        
        # Tìm resistance
        resistance = df.tail(30).head(20)['high'].max()
        
        for i in range(-5, 0):
            candle = recent.iloc[i]
            
            # Điều kiện Upthrust
            if candle['high'] > resistance:
                if candle['close'] < resistance:
                    vol_confirm = candle['volume'] > df['volume'].mean() * 1.2
                    wick_ratio = candle['upper_wick'] / candle['spread'] if candle['spread'] > 0 else 0
                    
                    if wick_ratio > 0.5:
                        confidence = 70 + (wick_ratio * 20) + (10 if vol_confirm else 0)
                        return WyckoffEvent(
                            event_type='UPTHRUST',
                            confidence=min(confidence, 95),
                            price_level=resistance,
                            volume_confirmation=vol_confirm,
                            description=f'🔴 UPTHRUST tại ${resistance:.2f} - Bẫy bò, tín hiệu BÁN mạnh!'
                        )
        
        return None
    
    def _detect_sign_of_strength(self, df: pd.DataFrame) -> Optional[WyckoffEvent]:
        """
        Phát hiện Sign of Strength (SOS)
        - Nến tăng mạnh với volume cao
        - Phá vỡ resistance nhỏ
        """
        if len(df) < 5:
            return None
        
        last = df.iloc[-1]
        prev = df.iloc[-2]
        
        # Nến tăng mạnh
        is_bullish = last['close'] > last['open']
        big_spread = last['spread'] > df['spread_sma'].iloc[-1] * 1.5
        high_volume = last['volume'] > df['vol_sma'].iloc[-1] * 1.3
        
        # Phá vỡ high trước
        breaks_high = last['close'] > prev['high']
        
        if is_bullish and big_spread and high_volume and breaks_high:
            return WyckoffEvent(
                event_type='SOS',
                confidence=75,
                price_level=last['close'],
                volume_confirmation=True,
                description='📈 Sign of Strength - Phe mua đang kiểm soát!'
            )
        
        return None
    
    def _detect_sign_of_weakness(self, df: pd.DataFrame) -> Optional[WyckoffEvent]:
        """
        Phát hiện Sign of Weakness (SOW)
        """
        if len(df) < 5:
            return None
        
        last = df.iloc[-1]
        prev = df.iloc[-2]
        
        is_bearish = last['close'] < last['open']
        big_spread = last['spread'] > df['spread_sma'].iloc[-1] * 1.5
        high_volume = last['volume'] > df['vol_sma'].iloc[-1] * 1.3
        breaks_low = last['close'] < prev['low']
        
        if is_bearish and big_spread and high_volume and breaks_low:
            return WyckoffEvent(
                event_type='SOW',
                confidence=75,
                price_level=last['close'],
                volume_confirmation=True,
                description='📉 Sign of Weakness - Phe bán đang kiểm soát!'
            )
        
        return None
    
    def _volume_spread_analysis(self, df: pd.DataFrame) -> Dict:
        """
        Volume Spread Analysis (VSA)
        Định luật Nỗ lực vs Kết quả
        """
        if len(df) < 3:
            return {'signal': 'NEUTRAL', 'description': 'Không đủ dữ liệu'}
        
        last = df.iloc[-1]
        
        # Effort (Volume)
        rel_vol = last['volume'] / df['vol_sma'].iloc[-1] if df['vol_sma'].iloc[-1] > 0 else 1
        
        # Result (Spread)
        rel_spread = last['spread'] / df['spread_sma'].iloc[-1] if df['spread_sma'].iloc[-1] > 0 else 1
        
        # Efficiency Index
        if rel_spread > 0:
            efficiency = rel_vol / rel_spread
        else:
            efficiency = 1
        
        # Phân tích
        if efficiency > 2:
            # High volume, low spread -> Absorption (Hấp thụ)
            if last['close'] > last['open']:
                return {
                    'signal': 'ABSORPTION_SUPPORT',
                    'description': '🟢 Volume cao nhưng giá không tăng nhiều = Có lực mua hấp thụ áp lực bán',
                    'efficiency': efficiency
                }
            else:
                return {
                    'signal': 'ABSORPTION_RESISTANCE', 
                    'description': '🔴 Volume cao nhưng giá không giảm nhiều = Có lực bán hấp thụ áp lực mua',
                    'efficiency': efficiency
                }
        elif efficiency < 0.5:
            # Low volume, high spread -> Easy movement
            return {
                'signal': 'EASY_MOVEMENT',
                'description': '⚡ Giá di chuyển dễ dàng, ít kháng cự',
                'efficiency': efficiency
            }
        
        return {
            'signal': 'NEUTRAL',
            'description': 'Volume và Spread cân bằng',
            'efficiency': efficiency
        }
    
    def _generate_signal(self, phase: str, events: List[WyckoffEvent], vsa: Dict) -> Dict:
        """Tổng hợp tín hiệu giao dịch"""
        
        # Ưu tiên các sự kiện mạnh
        for event in events:
            if event.event_type == 'SPRING' and event.confidence > 70:
                return {
                    'action': 'BUY',
                    'reason': event.description,
                    'confidence': event.confidence,
                    'event': 'SPRING'
                }
            elif event.event_type == 'UPTHRUST' and event.confidence > 70:
                return {
                    'action': 'SELL',
                    'reason': event.description,
                    'confidence': event.confidence,
                    'event': 'UPTHRUST'
                }
            elif event.event_type == 'SOS':
                return {
                    'action': 'BUY',
                    'reason': event.description,
                    'confidence': event.confidence,
                    'event': 'SOS'
                }
            elif event.event_type == 'SOW':
                return {
                    'action': 'SELL',
                    'reason': event.description,
                    'confidence': event.confidence,
                    'event': 'SOW'
                }
        
        # Dựa trên phase
        if phase == 'ACCUMULATION':
            return {
                'action': 'WAIT',
                'reason': 'Đang trong pha Tích lũy - Chờ Spring/SOS để vào lệnh BUY',
                'confidence': 30,
                'event': None
            }
        elif phase == 'DISTRIBUTION':
            return {
                'action': 'WAIT',
                'reason': 'Đang trong pha Phân phối - Chờ Upthrust/SOW để vào lệnh SELL',
                'confidence': 30,
                'event': None
            }
        
        return {
            'action': 'WAIT',
            'reason': 'Không có tín hiệu Wyckoff rõ ràng',
            'confidence': 0,
            'event': None
        }
    
    def get_summary(self, df: pd.DataFrame) -> str:
        """Tạo tóm tắt phân tích Wyckoff dạng text"""
        result = self.analyze(df)
        
        lines = [
            "📊 WYCKOFF ANALYSIS",
            "=" * 30,
            f"🔮 Phase: {result['phase']}",
            f"   {result['phase_description']}",
        ]
        
        if result['events']:
            lines.append("\n🎯 Events Detected:")
            for event in result['events']:
                lines.append(f"   • {event.event_type}: {event.description}")
        
        if result['vsa']:
            lines.append(f"\n📈 VSA: {result['vsa']['signal']}")
            lines.append(f"   {result['vsa']['description']}")
        
        if result['signal']:
            lines.append(f"\n💡 Signal: {result['signal']['action']}")
            lines.append(f"   {result['signal']['reason']}")
        
        return "\n".join(lines)


# Quick test
if __name__ == "__main__":
    # Create sample data with potential Spring
    dates = pd.date_range(end='2024-01-01', periods=50, freq='15min')
    np.random.seed(42)
    
    base = 2620
    closes = base + np.cumsum(np.random.randn(50) * 2)
    
    # Simulate a Spring at index 45
    closes[45] = base - 10  # Drop below support
    closes[46] = base - 5   # Recover
    closes[47] = base + 2   # Continue up
    
    df = pd.DataFrame({
        'open': closes - np.random.rand(50),
        'high': closes + np.random.rand(50) * 3,
        'low': closes - np.random.rand(50) * 3,
        'close': closes,
        'volume': np.random.randint(100, 500, 50)
    }, index=dates)
    
    # Analyze
    analyzer = WyckoffAnalyzer()
    print(analyzer.get_summary(df))
