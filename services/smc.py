"""
Smart Money Concepts (SMC) Module
Phân tích FVG, Order Blocks, Liquidity, BOS, CHoCH
"""
import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass


@dataclass
class SMCZone:
    """Vùng SMC (Order Block, FVG, Liquidity)"""
    zone_type: str  # FVG, ORDER_BLOCK, LIQUIDITY_HIGH, LIQUIDITY_LOW
    direction: str  # BULLISH, BEARISH
    top: float
    bottom: float
    strength: float  # 0-100
    is_mitigated: bool  # Đã bị test chưa


class SMCAnalyzer:
    """
    Smart Money Concepts Analysis
    - Fair Value Gap (FVG)
    - Order Blocks (OB)
    - Liquidity Sweep
    - Break of Structure (BOS)
    - Change of Character (CHoCH)
    """
    
    def __init__(self):
        self.zones: List[SMCZone] = []
    
    def analyze(self, df: pd.DataFrame) -> Dict:
        """Phân tích toàn diện SMC"""
        if len(df) < 10:
            return {'fvgs': [], 'order_blocks': [], 'structure': 'UNKNOWN'}
        
        df = df.copy()
        
        # Detect zones
        fvgs = self._detect_fvg(df)
        order_blocks = self._detect_order_blocks(df)
        liquidity = self._detect_liquidity_pools(df)
        
        # Market structure
        structure = self._analyze_structure(df)
        
        # Check for sweeps
        sweep = self._detect_liquidity_sweep(df, liquidity)
        
        return {
            'fvgs': fvgs,
            'order_blocks': order_blocks,
            'liquidity_pools': liquidity,
            'structure': structure,
            'sweep': sweep,
            'signal': self._generate_signal(fvgs, order_blocks, sweep, structure, df)
        }
    
    def _detect_fvg(self, df: pd.DataFrame) -> List[SMCZone]:
        """
        Phát hiện Fair Value Gap (Khoảng trống giá trị hợp lý)
        FVG xảy ra khi nến giữa không lấp đầy khoảng cách giữa nến 1 và nến 3
        """
        fvgs = []
        
        for i in range(2, len(df)):
            candle_1 = df.iloc[i-2]
            candle_2 = df.iloc[i-1]  # Nến tạo gap
            candle_3 = df.iloc[i]
            
            # Bullish FVG: Low của nến 3 > High của nến 1
            if candle_3['low'] > candle_1['high']:
                gap_size = candle_3['low'] - candle_1['high']
                avg_spread = df['high'].mean() - df['low'].mean()
                
                if gap_size > avg_spread * 0.3:  # Gap có ý nghĩa
                    fvgs.append(SMCZone(
                        zone_type='FVG',
                        direction='BULLISH',
                        top=candle_3['low'],
                        bottom=candle_1['high'],
                        strength=min(gap_size / avg_spread * 50, 100),
                        is_mitigated=self._is_zone_mitigated(df, candle_1['high'], candle_3['low'], i)
                    ))
            
            # Bearish FVG: High của nến 3 < Low của nến 1
            elif candle_3['high'] < candle_1['low']:
                gap_size = candle_1['low'] - candle_3['high']
                avg_spread = df['high'].mean() - df['low'].mean()
                
                if gap_size > avg_spread * 0.3:
                    fvgs.append(SMCZone(
                        zone_type='FVG',
                        direction='BEARISH',
                        top=candle_1['low'],
                        bottom=candle_3['high'],
                        strength=min(gap_size / avg_spread * 50, 100),
                        is_mitigated=self._is_zone_mitigated(df, candle_3['high'], candle_1['low'], i)
                    ))
        
        # Chỉ giữ FVG chưa bị mitigated và gần nhất
        active_fvgs = [f for f in fvgs if not f.is_mitigated]
        return active_fvgs[-5:] if active_fvgs else []  # 5 FVG gần nhất
    
    def _detect_order_blocks(self, df: pd.DataFrame) -> List[SMCZone]:
        """
        Phát hiện Order Blocks (Vùng lệnh tổ chức)
        OB là nến cuối cùng trước một đợt di chuyển mạnh
        """
        order_blocks = []
        
        for i in range(3, len(df) - 1):
            current = df.iloc[i]
            next_candle = df.iloc[i + 1]
            
            # Xác định direction của move
            move = next_candle['close'] - current['close']
            avg_move = df['close'].diff().abs().mean()
            
            # Strong move (>2x average)
            if abs(move) > avg_move * 2:
                if move > 0:  # Bullish move -> Bullish OB là nến giảm cuối cùng
                    if current['close'] < current['open']:  # Nến giảm
                        order_blocks.append(SMCZone(
                            zone_type='ORDER_BLOCK',
                            direction='BULLISH',
                            top=current['high'],
                            bottom=current['low'],
                            strength=min(abs(move) / avg_move * 30, 100),
                            is_mitigated=self._is_zone_mitigated(df, current['low'], current['high'], i)
                        ))
                else:  # Bearish move -> Bearish OB là nến tăng cuối cùng
                    if current['close'] > current['open']:
                        order_blocks.append(SMCZone(
                            zone_type='ORDER_BLOCK',
                            direction='BEARISH',
                            top=current['high'],
                            bottom=current['low'],
                            strength=min(abs(move) / avg_move * 30, 100),
                            is_mitigated=self._is_zone_mitigated(df, current['low'], current['high'], i)
                        ))
        
        active_obs = [ob for ob in order_blocks if not ob.is_mitigated]
        return active_obs[-3:]  # 3 OB gần nhất
    
    def _detect_liquidity_pools(self, df: pd.DataFrame) -> Dict:
        """
        Phát hiện vùng thanh khoản (Equal Highs/Lows, Swing Points)
        """
        # Swing highs và lows
        swing_highs = []
        swing_lows = []
        
        for i in range(2, len(df) - 2):
            # Swing High: high[i] > high của 2 nến trước và sau
            if (df['high'].iloc[i] > df['high'].iloc[i-1] and 
                df['high'].iloc[i] > df['high'].iloc[i-2] and
                df['high'].iloc[i] > df['high'].iloc[i+1] and
                df['high'].iloc[i] > df['high'].iloc[i+2]):
                swing_highs.append(df['high'].iloc[i])
            
            # Swing Low
            if (df['low'].iloc[i] < df['low'].iloc[i-1] and 
                df['low'].iloc[i] < df['low'].iloc[i-2] and
                df['low'].iloc[i] < df['low'].iloc[i+1] and
                df['low'].iloc[i] < df['low'].iloc[i+2]):
                swing_lows.append(df['low'].iloc[i])
        
        # Equal highs/lows (liquidity traps)
        equal_highs = self._find_equal_levels(swing_highs)
        equal_lows = self._find_equal_levels(swing_lows)
        
        return {
            'swing_highs': swing_highs[-5:] if swing_highs else [],
            'swing_lows': swing_lows[-5:] if swing_lows else [],
            'equal_highs': equal_highs,
            'equal_lows': equal_lows,
            'buy_stops': max(swing_highs) if swing_highs else None,
            'sell_stops': min(swing_lows) if swing_lows else None
        }
    
    def _find_equal_levels(self, levels: List[float], tolerance: float = 0.002) -> List[float]:
        """Tìm các mức giá bằng nhau (đỉnh/đáy đôi)"""
        if len(levels) < 2:
            return []
        
        equal_levels = []
        for i in range(len(levels)):
            for j in range(i + 1, len(levels)):
                if abs(levels[i] - levels[j]) / levels[i] < tolerance:
                    equal_levels.append((levels[i] + levels[j]) / 2)
        
        return equal_levels
    
    def _detect_liquidity_sweep(self, df: pd.DataFrame, liquidity: Dict) -> Optional[Dict]:
        """
        Phát hiện cú quét thanh khoản (Stop Hunt)
        """
        if not liquidity.get('buy_stops') or not liquidity.get('sell_stops'):
            return None
        
        last = df.iloc[-1]
        prev = df.iloc[-2] if len(df) > 1 else last
        
        buy_stops = liquidity['buy_stops']
        sell_stops = liquidity['sell_stops']
        
        # Sweep buy stops (phá đỉnh rồi quay lại)
        if last['high'] > buy_stops and last['close'] < buy_stops:
            return {
                'type': 'BUY_STOP_SWEEP',
                'level': buy_stops,
                'direction': 'BEARISH',
                'description': f'🔴 Quét thanh khoản phía trên ${buy_stops:.2f} - Tín hiệu BÁN!'
            }
        
        # Sweep sell stops
        if last['low'] < sell_stops and last['close'] > sell_stops:
            return {
                'type': 'SELL_STOP_SWEEP',
                'level': sell_stops,
                'direction': 'BULLISH',
                'description': f'🟢 Quét thanh khoản phía dưới ${sell_stops:.2f} - Tín hiệu MUA!'
            }
        
        return None
    
    def _analyze_structure(self, df: pd.DataFrame) -> Dict:
        """Phân tích cấu trúc thị trường (BOS, CHoCH)"""
        if len(df) < 10:
            return {'trend': 'UNKNOWN', 'bos': None, 'choch': None}
        
        # Find recent swing points
        swing_highs = []
        swing_lows = []
        
        for i in range(2, len(df) - 2):
            if df['high'].iloc[i] == df['high'].iloc[i-2:i+3].max():
                swing_highs.append((i, df['high'].iloc[i]))
            if df['low'].iloc[i] == df['low'].iloc[i-2:i+3].min():
                swing_lows.append((i, df['low'].iloc[i]))
        
        if len(swing_highs) < 2 or len(swing_lows) < 2:
            return {'trend': 'UNKNOWN', 'bos': None, 'choch': None}
        
        # Trend analysis
        last_high = swing_highs[-1][1]
        prev_high = swing_highs[-2][1]
        last_low = swing_lows[-1][1]
        prev_low = swing_lows[-2][1]
        
        higher_highs = last_high > prev_high
        higher_lows = last_low > prev_low
        lower_highs = last_high < prev_high
        lower_lows = last_low < prev_low
        
        if higher_highs and higher_lows:
            trend = 'BULLISH'
        elif lower_highs and lower_lows:
            trend = 'BEARISH'
        else:
            trend = 'RANGING'
        
        return {
            'trend': trend,
            'last_high': last_high,
            'last_low': last_low,
            'higher_highs': higher_highs,
            'higher_lows': higher_lows
        }
    
    def _is_zone_mitigated(self, df: pd.DataFrame, bottom: float, top: float, start_idx: int) -> bool:
        """Kiểm tra zone đã bị test (mitigated) chưa"""
        for i in range(start_idx + 1, len(df)):
            candle = df.iloc[i]
            # Giá đã đi qua zone
            if candle['low'] <= top and candle['high'] >= bottom:
                return True
        return False
    
    def _generate_signal(self, fvgs: List[SMCZone], order_blocks: List[SMCZone], 
                         sweep: Optional[Dict], structure: Dict, df: pd.DataFrame) -> Dict:
        """Tổng hợp tín hiệu SMC"""
        
        current_price = df['close'].iloc[-1]
        
        # Ưu tiên Liquidity Sweep
        if sweep:
            action = 'BUY' if sweep['direction'] == 'BULLISH' else 'SELL'
            return {
                'action': action,
                'reason': sweep['description'],
                'confidence': 80,
                'trigger': 'LIQUIDITY_SWEEP'
            }
        
        # Giá tiến vào FVG
        for fvg in fvgs:
            if fvg.bottom <= current_price <= fvg.top:
                action = 'BUY' if fvg.direction == 'BULLISH' else 'SELL'
                return {
                    'action': action,
                    'reason': f"Giá đang trong vùng FVG {fvg.direction}",
                    'confidence': 65,
                    'trigger': 'FVG'
                }
        
        # Giá tiến vào Order Block
        for ob in order_blocks:
            if ob.bottom <= current_price <= ob.top:
                action = 'BUY' if ob.direction == 'BULLISH' else 'SELL'
                return {
                    'action': action,
                    'reason': f"Giá đang trong Order Block {ob.direction}",
                    'confidence': 70,
                    'trigger': 'ORDER_BLOCK'
                }
        
        return {
            'action': 'WAIT',
            'reason': 'Không có setup SMC rõ ràng',
            'confidence': 0,
            'trigger': None
        }
    
    def get_summary(self, df: pd.DataFrame) -> str:
        """Tạo tóm tắt SMC dạng text"""
        result = self.analyze(df)
        
        lines = [
            "🎯 SMART MONEY CONCEPTS",
            "=" * 30,
            f"📊 Market Structure: {result['structure'].get('trend', 'UNKNOWN')}",
        ]
        
        if result['fvgs']:
            lines.append(f"\n📍 Fair Value Gaps: {len(result['fvgs'])}")
            for fvg in result['fvgs'][:2]:
                lines.append(f"   • {fvg.direction} FVG: ${fvg.bottom:.2f} - ${fvg.top:.2f}")
        
        if result['order_blocks']:
            lines.append(f"\n📦 Order Blocks: {len(result['order_blocks'])}")
            for ob in result['order_blocks'][:2]:
                lines.append(f"   • {ob.direction} OB: ${ob.bottom:.2f} - ${ob.top:.2f}")
        
        if result['sweep']:
            lines.append(f"\n⚡ Sweep: {result['sweep']['description']}")
        
        if result['signal']:
            lines.append(f"\n💡 Signal: {result['signal']['action']}")
            lines.append(f"   {result['signal']['reason']}")
        
        return "\n".join(lines)


# Quick test
if __name__ == "__main__":
    print("Testing SMC Analyzer...")
    
    dates = pd.date_range(end='2024-01-01', periods=50, freq='15min')
    np.random.seed(42)
    
    base = 2620
    closes = base + np.cumsum(np.random.randn(50) * 2)
    
    df = pd.DataFrame({
        'open': closes - np.random.rand(50),
        'high': closes + np.random.rand(50) * 3,
        'low': closes - np.random.rand(50) * 3,
        'close': closes,
        'volume': np.random.randint(100, 500, 50)
    }, index=dates)
    
    analyzer = SMCAnalyzer()
    print(analyzer.get_summary(df))
