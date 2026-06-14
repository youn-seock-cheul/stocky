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
            "Samsung": {"ticker": "005930.KS", "avg_price": 75000, "deposit": 1500000},
            "TIGER 미국우주테크": {"ticker": "479880.KS", "avg_price": 10500, "deposit": 500000},
            "ACE AI반도체TOP3+": {"ticker": "469150.KS", "avg_price": 11000, "deposit": 500000}
        }

    def get_recent_data(self, days=5):
        """최근 n일간의 종가 데이터를 가져와 요약본 반환"""
        def fetch_data(target_dict, is_portfolio=False):
            report = {}
            for name, item in target_dict.items():
                ticker = item["ticker"] if is_portfolio else item
                try:
                    t = yf.Ticker(ticker)
                    data = t.history(period=f"{days}d")
                    
                    if not data.empty and len(data) >= 2:
                        current_price = float(data['Close'].iloc[-1])
                        prev_price = float(data['Close'].iloc[-2])
                        change_pct = (current_price - prev_price) / prev_price * 100
                        
                        entry = {
                            "price": round(float(current_price), 2),
                            "change_pct": round(float(change_pct), 2)
                        }

                        if is_portfolio:
                            avg_price = item["avg_price"]
                            deposit = item["deposit"]
                            # 수익률 계산: (현재가 - 평단가) / 평단가 * 100
                            roi = (current_price - avg_price) / avg_price * 100
                            # 평가금액: (현재가 / 평단가) * 입금액
                            current_value = (current_price / avg_price) * deposit
                            profit_loss = current_value - deposit
                            
                            entry.update({
                                "avg_price": avg_price,
                                "deposit": deposit,
                                "roi": round(roi, 2),
                                "current_value": round(current_value, 0),
                                "profit_loss": round(profit_loss, 0)
                            })
                        
                        report[name] = entry
                    else:
                        print(f"⚠️ {name} 데이터를 충분히 가져오지 못했습니다.")
                except Exception as e:
                    print(f"❌ {name} 수집 중 오류 발생: {e}")
            return report
        
        return {
            "indices": fetch_data(self.indices, is_portfolio=False),
            "portfolio": fetch_data(self.my_portfolio, is_portfolio=True)
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

    def generate_portfolio_charts(self, output_prefix="portfolio"):
        """보유 종목의 일간/월간 수익률 그래프 생성"""
        if not HAS_MATPLOTLIB:
            print("⚠️ Matplotlib 라이브러리 로드 실패로 수익률 차트 생성을 건너뜁니다.")
            return []

        total_deposit = sum(item["deposit"] for item in self.my_portfolio.values())
        if total_deposit == 0:
            return []

        # 역사적 데이터 수집 (최근 6개월)
        all_hist = {}
        for name, item in self.my_portfolio.items():
            ticker = item["ticker"]
            shares = item["deposit"] / item["avg_price"] # 보유 주식 수 계산
            hist = yf.Ticker(ticker).history(period="6mo")
            if not hist.empty:
                all_hist[name] = hist['Close'] * shares

        if not all_hist:
            return []

        # 전체 포트폴리오 가치 및 수익률 계산
        df_values = pd.DataFrame(all_hist).ffill()
        df_total = df_values.sum(axis=1)
        df_returns = (df_total - total_deposit) / total_deposit * 100

        generated_files = []
        
        # 1. 일별 수익률 그래프 (최근 30일)
        daily_path = f"{output_prefix}_daily.png"
        daily_data = df_returns.tail(30)
        plt.figure(figsize=(10, 5))
        plt.plot(daily_data.index, daily_data.values, marker='o', linestyle='-', color='royalblue', markersize=4)
        plt.axhline(0, color='red', linestyle='--')
        plt.title("Portfolio Daily Return (%) - Last 30 Days")
        plt.grid(True, alpha=0.3)
        plt.savefig(daily_path)
        plt.close()
        generated_files.append(daily_path)

        # 2. 월별 수익률 그래프 (최근 6개월)
        monthly_path = f"{output_prefix}_monthly.png"
        monthly_data = df_returns.resample('M').last()
        plt.figure(figsize=(10, 5))
        plt.bar(monthly_data.index.strftime('%Y-%m'), monthly_data.values, color='lightgreen')
        plt.axhline(0, color='red', linestyle='-')
        plt.title("Portfolio Monthly Return (%) - Last 6 Months")
        plt.ylabel("Return (%)")
        plt.savefig(monthly_path)
        plt.close()
        generated_files.append(monthly_path)

        return generated_files

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
