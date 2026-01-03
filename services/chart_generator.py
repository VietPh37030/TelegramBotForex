import pandas as pd
import matplotlib
matplotlib.use('Agg')  # Set non-interactive backend before importing mplfinance
import mplfinance as mpf
import os
from datetime import datetime

class ChartGenerator:
    """Service to generate technical analysis charts"""
    
    def __init__(self, output_dir="charts"):
        self.output_dir = output_dir
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)
            
    def generate_chart(self, df: pd.DataFrame, title="XAU/USD Analysis", 
                      levels=None, filename=None) -> str:
        """
        Generate a candlestick chart and save to file
        
        Args:
            df: Pandas DataFrame with OHLCV data
            title: Chart title
            levels: Dict with 'entry', 'sl', 'tp' to draw horizontal lines
            filename: Output filename (optional)
            
        Returns:
            Path to the saved chart image
        """
        try:
            if df.empty:
                return None
                
            if filename is None:
                filename = f"chart_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
            
            filepath = os.path.join(self.output_dir, filename)
            
            # Prepare data (ensure column names are correct for mplfinance)
            plot_df = df.copy()
            # Ensure index is datetime
            if not isinstance(plot_df.index, pd.DatetimeIndex):
                plot_df.index = pd.to_datetime(plot_df.index)
            
            # Use only the last 30-50 bars for better visibility
            plot_df = plot_df.tail(40)
            
            # Style configuration
            mc = mpf.make_marketcolors(up='g', down='r', inherit=True)
            s  = mpf.make_mpf_style(marketcolors=mc, gridstyle='--', y_on_right=True)
            
            # Horizontal lines for levels
            hlines = []
            hcolors = []
            if levels:
                if levels.get('entry'):
                    hlines.append(levels['entry'])
                    hcolors.append('b')
                if levels.get('sl'):
                    hlines.append(levels['sl'])
                    hcolors.append('r')
                if levels.get('tp'):
                    hlines.append(levels['tp'])
                    hcolors.append('g')
            
            # Plot
            if hlines:
                mpf.plot(plot_df, type='candle', style=s, 
                         title=title, ylabel='Price ($)',
                         hlines=dict(hlines=hlines, colors=hcolors, linestyle='-.'),
                         savefig=filepath, volume=False)
            else:
                mpf.plot(plot_df, type='candle', style=s, 
                         title=title, ylabel='Price ($)',
                         savefig=filepath, volume=False)
                         
            return os.path.abspath(filepath)
            
        except Exception as e:
            print(f"❌ Chart generation error: {e}")
            return None
            
    def cleanup_old_charts(self, max_hours=24):
        """Cleanup charts older than X hours"""
        try:
            now = datetime.now()
            for f in os.listdir(self.output_dir):
                f_path = os.path.join(self.output_dir, f)
                if os.path.isfile(f_path):
                    f_time = datetime.fromtimestamp(os.path.getmtime(f_path))
                    if (now - f_time).total_seconds() > max_hours * 3600:
                        os.remove(f_path)
        except Exception as e:
            print(f"❌ Chart cleanup error: {e}")
