import yfinance as yf
import pandas as pd
from datetime import datetime, timedelta

class MarketDataCollector:
    def __init__(self):
        # 수집하고자 하는 주요 지표 정의
        self.tickers = {
            "S&P500": "^GSPC",      # 미국 S&P 500
            "Nasdaq": "^IXIC",      # 미국 나스닥
            "KOSPI": "^KS11",       # 한국 코스피
            "KOSDAQ": "^KQ11",      # 한국 코스닥
            "USD_KRW": "USDKRW=X",  # 원/달러 환율
            "Samsung": "005930.KS", # 개별 종목 예시 (삼성전자)
            "Apple": "AAPL"         # 개별 종목 예시 (애플)
        }

    def get_recent_data(self, days=5):
        """최근 n일간의 종가 데이터를 가져옴"""
        market_report = {}
        
        for name, ticker in self.tickers.items():
            try:
                # 데이터 다운로드 (최근 5일치)
                data = yf.download(ticker, period=f"{days}d", interval="1d", progress=False)
                
                if not data.empty:
                    # 전일 종가와 현재가 추출
                    current_price = data['Close'].iloc[-1]
                    prev_price = data['Close'].iloc[-2]
                    change_pct = ((current_price - prev_price) / prev_price) * 100
                    
                    market_report[name] = {
                        "price": round(float(current_price), 2),
                        "change_pct": round(float(change_pct), 2),
                        "last_updated": data.index[-1].strftime('%Y-%m-%d')
                    }
                else:
                    print(f"⚠️ {name} 데이터를 찾을 수 없습니다.")
            except Exception as e:
                print(f"❌ {name} 수집 중 오류 발생: {e}")
                
        return market_report

# 실행 테스트
if __name__ == "__main__":
    collector = MarketDataCollector()
    data = collector.get_recent_data()
    
    print(f"--- 수집된 시장 데이터 ({datetime.now().strftime('%Y-%m-%d %H:%M')}) ---")
    for name, info in data.items():
        print(f"[{name}] 가격: {info['price']} | 등락률: {info['change_pct']}%")
