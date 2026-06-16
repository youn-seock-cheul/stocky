import os
import json
import numpy as np
import yfinance as yf
import pandas as pd
import matplotlib.pyplot as plt

class MarketDataCollector:
    def __init__(self):
        self.portfolio_file = "portfolio.json"
        self.indices = {"S&P500": "^GSPC", "Nasdaq": "^IXIC", "KOSPI": "^KS11", "KOSDAQ": "^KQ11", "USD_KRW": "USDKRW=X"}
        self.load_portfolio()

    def load_portfolio(self):
        if os.path.exists(self.portfolio_file):
            with open(self.portfolio_file, 'r', encoding='utf-8') as f: self.my_portfolio = json.load(f)
        else:
            self.my_portfolio = [{"Samsung": {"ticker": "005930.KS", "avg_price": 6568901, "deposit": 7384545}}
                                 ,{"RISE AI전력인프라": {"ticker": "0101N0.KS", "avg_price": 43426200, "deposit": 43202755}}]

    def get_recent_data(self, days=30):
        def fetch(target, is_p=False):
            res = {}
            for name, item in target.items():
                ticker = item["ticker"] if is_p else item
                data = yf.Ticker(ticker).history(period="60d")
                if not data.empty:
                    close = data['Close']
                    # RSI (14)
                    delta = close.diff(); up = delta.clip(lower=0); down = -1*delta.clip(upper=0)
                    ema_u = up.ewm(com=13, adjust=False).mean(); ema_d = down.ewm(com=13, adjust=False).mean()
                    rsi = 100 - (100 / (1 + ema_u/ema_d))
                    # MACD
                    e12 = close.ewm(span=12, adjust=False).mean(); e26 = close.ewm(span=26, adjust=False).mean()
                    macd = e12 - e26; sig = macd.ewm(span=9, adjust=False).mean()
                    
                    entry = {"price": round(float(close.iloc[-1]), 2), "change_pct": round(((close.iloc[-1]/close.iloc[-2])-1)*100, 2),
                             "rsi": round(float(rsi.iloc[-1]), 2), "macd": round(float(macd.iloc[-1]), 2), "macd_signal": round(float(sig.iloc[-1]), 2),
                             "history": {d.strftime('%m-%d'): round(float(p), 2) for d, p in close.tail(days).to_dict().items()}}
                    if is_p:
                        roi = (close.iloc[-1] - item['avg_price']) / item['avg_price'] * 100
                        val = (close.iloc[-1] / item['avg_price']) * item['deposit']
                        entry.update({"avg_price": item['avg_price'], "deposit": item['deposit'], "roi": round(roi, 2), "current_value": round(val, 0), "profit_loss": round(val - item['deposit'], 0)})
                    res[name] = entry
            return res
        return {"indices": fetch(self.indices), "portfolio": fetch(self.my_portfolio, True)}

    def generate_portfolio_prediction_chart(self, output_path="chart.png"):
        plt.figure(figsize=(12, 6))
        for name, item in self.my_portfolio.items():
            data = yf.download(item['ticker'], period="1mo", interval="1h", progress=False)
            if not data.empty:
                norm = (data['Close'].values / data['Close'].values[0] - 1) * 100
                x = np.arange(len(norm)); slope, intercept = np.polyfit(x, norm, 1)
                std = np.std(norm - (slope * x + intercept))
                f_x = np.arange(len(norm), len(norm) + 24); f_y = slope * f_x + intercept
                color = 'red' if slope > 0 else 'blue'
                p = plt.plot(x, norm, label=name, alpha=0.7)
                plt.plot(f_x, f_y, linestyle='--', color=p[0].get_color())
                plt.fill_between(f_x, f_y - 2*std, f_y + 2*std, color=color, alpha=0.1)
        plt.title("Portfolio Prediction (Red: Up, Blue: Down)"); plt.legend(); plt.grid(True, alpha=0.3)
        plt.savefig(output_path); plt.close()

    def update_portfolio_from_list(self, portfolio_list):
        updates = {i['name']: {"ticker": i['ticker'], "avg_price": float(i['avg_price']), "deposit": float(i['deposit'])} for i in portfolio_list if 'name' in i}
        if updates: self.my_portfolio.update(updates); self.save_portfolio()

    def save_portfolio(self):
        with open(self.portfolio_file, 'w', encoding='utf-8') as f: json.dump(self.my_portfolio, f, ensure_ascii=False, indent=4)
