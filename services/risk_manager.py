"""
Risk Manager Module - Quản lý rủi ro và tính toán lot size
Áp dụng quy tắc Kelly Criterion và Fixed Fractional
"""
from typing import Tuple, Optional
from dataclasses import dataclass


@dataclass
class TradeRisk:
    """Thông tin rủi ro cho một lệnh"""
    lot_size: float
    risk_amount: float
    risk_percent: float
    warning: Optional[str] = None


class RiskManager:
    """
    Quản lý rủi ro giao dịch
    - Tính toán lot size dựa trên % rủi ro
    - Kiểm tra drawdown
    - Lọc spread
    """
    
    # Contract size cho các cặp phổ biến
    CONTRACT_SIZES = {
        'XAUUSD': 100,   # 1 lot = 100 oz vàng
        'EURUSD': 100000,  # 1 lot = 100,000 EUR
        'GBPUSD': 100000,
        'USDJPY': 100000,
    }
    
    def __init__(self, 
                 capital: float,
                 risk_percent: float = 0.02,
                 min_lot: float = 0.01,
                 max_lot: float = 1.0,
                 max_daily_loss: float = 0.06):
        """
        Khởi tạo Risk Manager
        
        Args:
            capital: Số vốn (USD)
            risk_percent: % rủi ro mỗi lệnh (0.02 = 2%)
            min_lot: Lot tối thiểu
            max_lot: Lot tối đa cho phép
            max_daily_loss: % lỗ tối đa trong ngày
        """
        self.capital = capital
        self.risk_percent = risk_percent
        self.min_lot = min_lot
        self.max_lot = max_lot
        self.max_daily_loss = max_daily_loss
        
        self.daily_pnl = 0.0  # P/L trong ngày
        self.trades_today = 0
    
    def calculate_lot_size(self, 
                           entry: float, 
                           stoploss: float,
                           symbol: str = "XAUUSD") -> TradeRisk:
        """
        Tính khối lượng lệnh dựa trên rủi ro cố định
        
        Formula: Lot = Risk Amount / (SL Distance * Contract Size)
        
        Args:
            entry: Giá vào lệnh
            stoploss: Giá cắt lỗ
            symbol: Cặp tiền giao dịch
            
        Returns:
            TradeRisk object với lot_size và warnings
        """
        # Số tiền chấp nhận lỗ
        risk_amount = self.capital * self.risk_percent
        
        # Khoảng cách SL (giá)
        sl_distance = abs(entry - stoploss)
        
        if sl_distance == 0:
            return TradeRisk(
                lot_size=self.min_lot,
                risk_amount=0,
                risk_percent=0,
                warning="⚠️ SL distance = 0. Using minimum lot."
            )
        
        # Contract size
        contract_size = self.CONTRACT_SIZES.get(symbol, 100)
        
        # Tính lot size
        # Với Vàng: 1 lot, giá đi 1 USD = 100 USD P/L
        lot_size = risk_amount / (sl_distance * contract_size)
        
        warning = None
        
        # Kiểm tra lot tối thiểu
        if lot_size < self.min_lot:
            actual_risk = self.min_lot * sl_distance * contract_size
            actual_risk_percent = actual_risk / self.capital * 100
            
            warning = (f"⚠️ Lot tối thiểu = {self.min_lot}. "
                      f"Rủi ro thực tế: ${actual_risk:.2f} ({actual_risk_percent:.1f}%)")
            lot_size = self.min_lot
            risk_amount = actual_risk
        
        # Kiểm tra lot tối đa
        if lot_size > self.max_lot:
            warning = f"⚠️ Lot bị giới hạn từ {lot_size:.2f} xuống {self.max_lot}"
            lot_size = self.max_lot
            risk_amount = lot_size * sl_distance * contract_size
        
        return TradeRisk(
            lot_size=round(lot_size, 2),
            risk_amount=round(risk_amount, 2),
            risk_percent=round(risk_amount / self.capital * 100, 2),
            warning=warning
        )
    
    def check_daily_limit(self) -> Tuple[bool, str]:
        """
        Kiểm tra xem đã chạm giới hạn lỗ trong ngày chưa
        
        Returns:
            (can_trade, message)
        """
        daily_loss_percent = abs(self.daily_pnl) / self.capital if self.daily_pnl < 0 else 0
        
        if daily_loss_percent >= self.max_daily_loss:
            return False, (f"🛑 DỪNG GIAO DỊCH! Đã thua {daily_loss_percent*100:.1f}% "
                          f"(Max: {self.max_daily_loss*100:.0f}%)")
        
        remaining = (self.max_daily_loss - daily_loss_percent) * self.capital
        return True, f"✅ Còn ${remaining:.2f} trước khi chạm giới hạn ngày"
    
    def check_spread(self, spread: float, max_spread: float = 30) -> Tuple[bool, str]:
        """
        Kiểm tra spread có chấp nhận được không
        
        Args:
            spread: Spread hiện tại (points)
            max_spread: Spread tối đa cho phép
            
        Returns:
            (is_acceptable, message)
        """
        if spread > max_spread:
            return False, f"⚠️ Spread quá cao: {spread} points (Max: {max_spread})"
        return True, f"✅ Spread OK: {spread} points"
    
    def update_pnl(self, pnl: float):
        """Cập nhật P/L sau mỗi lệnh"""
        self.daily_pnl += pnl
        self.trades_today += 1
    
    def reset_daily(self):
        """Reset số liệu cuối ngày"""
        self.daily_pnl = 0.0
        self.trades_today = 0
    
    def update_capital(self, new_capital: float):
        """Cập nhật số vốn"""
        self.capital = new_capital
    
    def get_status(self) -> dict:
        """Lấy trạng thái hiện tại"""
        return {
            'capital': self.capital,
            'daily_pnl': self.daily_pnl,
            'trades_today': self.trades_today,
            'can_trade': self.check_daily_limit()[0],
            'risk_per_trade': f"{self.risk_percent*100:.1f}%"
        }


# Quick test
if __name__ == "__main__":
    # Test với vốn $100
    rm = RiskManager(capital=100, risk_percent=0.02)
    
    print("📊 Test Risk Manager với vốn $100\n")
    
    # Test case 1: Entry 2030, SL 2025 (5$ distance)
    entry = 2030
    sl = 2025
    result = rm.calculate_lot_size(entry, sl)
    
    print(f"📍 Entry: ${entry} | SL: ${sl}")
    print(f"   📦 Lot size: {result.lot_size}")
    print(f"   💰 Risk amount: ${result.risk_amount}")
    print(f"   📊 Risk %: {result.risk_percent}%")
    if result.warning:
        print(f"   {result.warning}")
    
    print("\n" + "="*50)
    
    # Test case 2: Entry 2030, SL 2028 (2$ distance)
    entry = 2030
    sl = 2028
    result = rm.calculate_lot_size(entry, sl)
    
    print(f"\n📍 Entry: ${entry} | SL: ${sl}")
    print(f"   📦 Lot size: {result.lot_size}")
    print(f"   💰 Risk amount: ${result.risk_amount}")
    print(f"   📊 Risk %: {result.risk_percent}%")
    if result.warning:
        print(f"   {result.warning}")
    
    # Test daily limit
    print("\n" + "="*50)
    rm.update_pnl(-5)  # Lỗ $5
    can_trade, msg = rm.check_daily_limit()
    print(f"\n🔍 Daily limit check: {msg}")
