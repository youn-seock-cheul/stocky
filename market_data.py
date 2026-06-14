import yfinance as yf
import pandas as pd
try:
    import matplotlib.pyplot as plt
    HAS_MATPLOTLIB = True
except ImportError:
    plt = None
    HAS_MATPLOTLIB = False

class MarketDataCollector:
    def __init__(self):
        # 1. 시장 흐름 파악을 위한 주요 지수
        self.indices = {
            "S&P500": "^GSPC",      # 미국 S&P 500
            "Nasdaq": "^IXIC",      # 미국 나스닥
            "KOSPI": "^KS11",       # 한국 코스피
            "KOSDAQ": "^KQ11",      # 한국 코스닥
            "USD_KRW": "USDKRW=X"   # 원/달러 환율
        }
        # 2. 실제 보유 중인 개인 포트폴리오 (원하시는 종목으로 변경하세요)
        self.my_portfolio = {
            "Samsung": "005930.KS",
            "TIGER 미국우주테크": "479880.KS",
            "ACE AI반도체TOP3+": "469150.KS"
        }

    def get_recent_data(self, days=5):
        """최근 n일간의 종가 데이터를 가져와 요약본 반환"""
        def fetch_data(target_dict):
            report = {}
            for name, ticker in target_dict.items():
                try:
                    t = yf.Ticker(ticker)
                    data = t.history(period=f"{days}d")
                    
                    if not data.empty and len(data) >= 2:
                        current_price = float(data['Close'].iloc[-1])
                        prev_price = float(data['Close'].iloc[-2])
                        change_pct = (current_price - prev_price) / prev_price * 100
                        
                        report[name] = {
                            "price": round(float(current_price), 2),
                            "change_pct": round(float(change_pct), 2)
                        }
                    else:
                        print(f"⚠️ {name} 데이터를 충분히 가져오지 못했습니다.")
                except Exception as e:
                    print(f"❌ {name} 수집 중 오류 발생: {e}")
            return report
        
        return {
            "indices": fetch_data(self.indices),
            "portfolio": fetch_data(self.my_portfolio)
        }

    def generate_chart(self, output_path="chart.png"):
        """주요 지수의 5일 흐름을 차트로 생성"""
        if not HAS_MATPLOTLIB:
            print("⚠️ Matplotlib 라이브러리 로드 실패로 차트 생성을 건너뜁니다.")
            return

        plt.figure(figsize=(10, 6))
        for name, ticker in self.indices.items():
            if name == "USD_KRW": continue # 환율은 단위가 달라 제외
            data = yf.Ticker(ticker).history(period="5d")
            if not data.empty:
                # 첫날 기준 변동률로 정규화
                normalized = (data['Close'] / data['Close'].iloc[0] - 1) * 100
                plt.plot(normalized.index.strftime('%m-%d'), normalized, label=name, marker='o')
        
        plt.title("Recent Market Trends (Normalized %)")
        plt.xlabel("Date")
        plt.ylabel("Change (%)")
        plt.legend()
        plt.grid(True)
        plt.savefig(output_path)
        plt.close()

    def get_specific_ticker_data(self, ticker):
        """특정 종목 한 개의 최신 데이터 수집"""
        try:
            t = yf.Ticker(ticker)
            data = t.history(period="10d") # 기술적 분석을 위해 10일치 수집
            if not data.empty:
                current_price = float(data['Close'].iloc[-1])
                prev_price = float(data['Close'].iloc[-2])
                change_pct = (current_price - prev_price) / prev_price * 100
                return {
                    "name": ticker,
                    "price": round(current_price, 2),
                    "change_pct": round(change_pct, 2),
                    "history": data['Close'].tail(5).to_dict() # 최근 5일 종가 흐름
                }
        except Exception as e:
            print(f"❌ {ticker} 데이터 수집 실패: {e}")
        return None
