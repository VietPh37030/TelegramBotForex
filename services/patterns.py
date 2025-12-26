"""
Candlestick Patterns Module - Nhận diện mô hình nến
Pinbar, Engulfing, Inside Bar, FVG (Fair Value Gap)
"""
import pandas as pd
import numpy as np
from typing import List, Dict, Optional


def detect_patterns(df: pd.DataFrame) -> Dict:
    """
    Quét tất cả mô hình nến và trả về kết quả
    
    Args:
        df: DataFrame với columns [open, high, low, close]
        
    Returns:
        Dict chứa các mô hình phát hiện được
    """
    patterns = {
        'pinbar': detect_pinbar(df),
        'engulfing': detect_engulfing(df),
        'inside_bar': detect_inside_bar(df),
        'doji': detect_doji(df),
        'fvg': detect_fvg(df)
    }
    
    # Tổng hợp
    active_patterns = [k for k, v in patterns.items() if v and v.get('detected')]
    patterns['summary'] = active_patterns if active_patterns else ['No pattern']
    
    return patterns


def detect_pinbar(df: pd.DataFrame, tail_ratio: float = 2.5) -> Dict:
    """
    Phát hiện nến Pinbar (Hammer / Shooting Star)
    
    Đặc điểm:
    - Thân nến nhỏ
    - Râu nến (wick) dài gấp 2.5x thân nến
    
    Args:
        df: DataFrame với OHLC
        tail_ratio: Tỉ lệ râu/thân để xác định pinbar
        
    Returns:
        Dict với detected, type (BULLISH/BEARISH), strength
    """
    if len(df) < 1:
        return {'detected': False}
    
    last = df.iloc[-1]
    
    body = abs(last['close'] - last['open'])
    upper_wick = last['high'] - max(last['open'], last['close'])
    lower_wick = min(last['open'], last['close']) - last['low']
    
    # Tránh chia cho 0
    if body < 0.01:
        body = 0.01
    
    # Bullish Pinbar (Hammer): Râu dưới dài
    if lower_wick / body >= tail_ratio and upper_wick < body:
        return {
            'detected': True,
            'type': 'BULLISH_PINBAR',
            'strength': min(lower_wick / body / tail_ratio * 100, 100),
            'description': 'Nến búa (Hammer) - Tín hiệu đảo chiều tăng'
        }
    
    # Bearish Pinbar (Shooting Star): Râu trên dài
    elif upper_wick / body >= tail_ratio and lower_wick < body:
        return {
            'detected': True,
            'type': 'BEARISH_PINBAR',
            'strength': min(upper_wick / body / tail_ratio * 100, 100),
            'description': 'Nến sao băng (Shooting Star) - Tín hiệu đảo chiều giảm'
        }
    
    return {'detected': False}


def detect_engulfing(df: pd.DataFrame) -> Dict:
    """
    Phát hiện nến Engulfing (Nhấn chìm)
    
    Đặc điểm:
    - Nến sau bao trùm hoàn toàn thân nến trước
    - Nến sau có màu ngược với nến trước
    
    Returns:
        Dict với detected, type (BULLISH/BEARISH)
    """
    if len(df) < 2:
        return {'detected': False}
    
    prev = df.iloc[-2]
    curr = df.iloc[-1]
    
    prev_body_high = max(prev['open'], prev['close'])
    prev_body_low = min(prev['open'], prev['close'])
    curr_body_high = max(curr['open'], curr['close'])
    curr_body_low = min(curr['open'], curr['close'])
    
    prev_is_bearish = prev['close'] < prev['open']
    curr_is_bullish = curr['close'] > curr['open']
    
    # Bullish Engulfing: Nến trước đỏ, nến sau xanh bao trùm
    if prev_is_bearish and curr_is_bullish:
        if curr_body_high > prev_body_high and curr_body_low < prev_body_low:
            return {
                'detected': True,
                'type': 'BULLISH_ENGULFING',
                'strength': 85,
                'description': 'Nến nhấn chìm tăng - Tín hiệu đảo chiều mạnh'
            }
    
    # Bearish Engulfing: Nến trước xanh, nến sau đỏ bao trùm
    prev_is_bullish = prev['close'] > prev['open']
    curr_is_bearish = curr['close'] < curr['open']
    
    if prev_is_bullish and curr_is_bearish:
        if curr_body_high > prev_body_high and curr_body_low < prev_body_low:
            return {
                'detected': True,
                'type': 'BEARISH_ENGULFING',
                'strength': 85,
                'description': 'Nến nhấn chìm giảm - Tín hiệu đảo chiều mạnh'
            }
    
    return {'detected': False}


def detect_inside_bar(df: pd.DataFrame) -> Dict:
    """
    Phát hiện Inside Bar (Nến nằm trong)
    
    Đặc điểm:
    - High/Low của nến sau nằm trong range của nến trước
    - Thường báo hiệu sự tích lũy trước breakout
    
    Returns:
        Dict với detected và breakout_direction gợi ý
    """
    if len(df) < 2:
        return {'detected': False}
    
    prev = df.iloc[-2]
    curr = df.iloc[-1]
    
    # Inside Bar: Nến hiện tại nằm trong nến trước
    if curr['high'] < prev['high'] and curr['low'] > prev['low']:
        # Dự đoán hướng breakout dựa trên body
        if curr['close'] > curr['open']:
            bias = 'BULLISH_BIAS'
        elif curr['close'] < curr['open']:
            bias = 'BEARISH_BIAS'
        else:
            bias = 'NEUTRAL'
        
        return {
            'detected': True,
            'type': 'INSIDE_BAR',
            'bias': bias,
            'mother_high': prev['high'],
            'mother_low': prev['low'],
            'description': 'Inside Bar - Thị trường đang tích lũy, chờ breakout'
        }
    
    return {'detected': False}


def detect_doji(df: pd.DataFrame, threshold: float = 0.1) -> Dict:
    """
    Phát hiện nến Doji (Nến do dự)
    
    Đặc điểm:
    - Thân nến cực nhỏ (open ≈ close)
    - Cho thấy sự do dự của thị trường
    
    Args:
        threshold: Phần trăm max cho body/range để là doji
        
    Returns:
        Dict với detected và type
    """
    if len(df) < 1:
        return {'detected': False}
    
    last = df.iloc[-1]
    
    body = abs(last['close'] - last['open'])
    full_range = last['high'] - last['low']
    
    if full_range == 0:
        return {'detected': False}
    
    body_ratio = body / full_range
    
    if body_ratio <= threshold:
        upper_wick = last['high'] - max(last['open'], last['close'])
        lower_wick = min(last['open'], last['close']) - last['low']
        
        if upper_wick > lower_wick * 2:
            doji_type = 'GRAVESTONE_DOJI'  # Bearish
        elif lower_wick > upper_wick * 2:
            doji_type = 'DRAGONFLY_DOJI'  # Bullish
        else:
            doji_type = 'DOJI'
        
        return {
            'detected': True,
            'type': doji_type,
            'description': 'Nến Doji - Thị trường đang do dự'
        }
    
    return {'detected': False}


def detect_fvg(df: pd.DataFrame) -> Dict:
    """
    Phát hiện Fair Value Gap (FVG) - Khoảng trống giá trị hợp lý
    
    SMC Concept: Khoảng trống giữa High của nến i-2 và Low của nến i
    (hoặc ngược lại cho Bearish FVG)
    
    Returns:
        Dict với detected, type, zone coordinates
    """
    if len(df) < 3:
        return {'detected': False}
    
    # 3 nến gần nhất
    candle_1 = df.iloc[-3]  # Nến cũ nhất
    candle_2 = df.iloc[-2]  # Nến giữa
    candle_3 = df.iloc[-1]  # Nến mới nhất
    
    # Bullish FVG: Low của nến 3 > High của nến 1
    if candle_3['low'] > candle_1['high']:
        return {
            'detected': True,
            'type': 'BULLISH_FVG',
            'zone_top': candle_3['low'],
            'zone_bottom': candle_1['high'],
            'size': candle_3['low'] - candle_1['high'],
            'description': 'Bullish FVG - Vùng hỗ trợ tiềm năng'
        }
    
    # Bearish FVG: High của nến 3 < Low của nến 1
    elif candle_3['high'] < candle_1['low']:
        return {
            'detected': True,
            'type': 'BEARISH_FVG',
            'zone_top': candle_1['low'],
            'zone_bottom': candle_3['high'],
            'size': candle_1['low'] - candle_3['high'],
            'description': 'Bearish FVG - Vùng kháng cự tiềm năng'
        }
    
    return {'detected': False}


def get_pattern_summary(df: pd.DataFrame) -> str:
    """
    Tổng hợp tất cả patterns thành text cho AI
    
    Returns:
        Chuỗi mô tả các pattern phát hiện được
    """
    patterns = detect_patterns(df)
    
    lines = ["📌 MÔ HÌNH NẾN PHÁT HIỆN:"]
    
    for name, data in patterns.items():
        if name == 'summary':
            continue
        if data and data.get('detected'):
            pattern_type = data.get('type', name.upper())
            desc = data.get('description', '')
            strength = data.get('strength', 'N/A')
            lines.append(f"• {pattern_type}: {desc} (Strength: {strength})")
    
    if len(lines) == 1:
        lines.append("• Không phát hiện mô hình nến đặc biệt")
    
    return "\n".join(lines)


# Quick test
if __name__ == "__main__":
    # Create sample data with a potential pattern
    dates = pd.date_range(end='2024-01-01', periods=5, freq='15min')
    
    # Simulate Bullish Engulfing
    df = pd.DataFrame({
        'open': [2030, 2028, 2025, 2024, 2022],
        'high': [2032, 2030, 2027, 2030, 2028],
        'low': [2028, 2024, 2023, 2021, 2021],
        'close': [2029, 2025, 2024, 2028, 2027],
        'volume': [100, 150, 200, 300, 250]
    }, index=dates)
    
    patterns = detect_patterns(df)
    print("🔍 Pattern Detection Results:")
    for name, data in patterns.items():
        if data and (isinstance(data, list) or data.get('detected')):
            print(f"  {name}: {data}")
    
    print("\n" + get_pattern_summary(df))
