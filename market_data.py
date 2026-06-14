import os
import numpy as np
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
            "Samsung": {
                "ticker": "005930.KS", "avg_price": 75000, "deposit": 1500000,
                "transactions": [
                    {"date": "2024-01-10", "price": 72000, "type": "buy"},
                    {"date": "2024-03-05", "price": 81000, "type": "sell"}
                ]
            },
            "NVIDIA": {
                "ticker": "NVDA", "avg_price": 110.0, "deposit": 1000000,
                "transactions": [
                    {"date": "2024-02-15", "price": 75.0, "type": "buy"}
                ]
            }
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
        monthly_data = df_returns.resample('ME').last()
        plt.figure(figsize=(10, 5))
        plt.bar(monthly_data.index.strftime('%Y-%m'), monthly_data.values, color='lightgreen')
        plt.axhline(0, color='red', linestyle='-')
        plt.title("Portfolio Monthly Return (%) - Last 6 Months")
        plt.ylabel("Return (%)")
        plt.savefig(monthly_path)
        plt.close()
        generated_files.append(monthly_path)

        return generated_files

    def generate_expert_dashboard(self, output_path="expert_dashboard.png"):
        """주요 지수들을 하나의 화면에 모은 전문가용 대시보드 생성"""
        if not HAS_MATPLOTLIB: return
        
        fig, axes = plt.subplots(2, 2, figsize=(15, 10))
        fig.suptitle(f"Global Market Expert Dashboard ({pd.Timestamp.now().strftime('%Y-%m-%d')})", fontsize=16)
        
        indices_to_plot = [("^GSPC", "S&P 500"), ("^IXIC", "Nasdaq"), ("^KS11", "KOSPI"), ("USDKRW=X", "USD/KRW")]
        
        for i, (ticker, title) in enumerate(indices_to_plot):
            ax = axes[i//2, i%2]
            data = yf.Ticker(ticker).history(period="1mo")
            if not data.empty:
                color = 'tab:red' if data['Close'].iloc[-1] > data['Close'].iloc[0] else 'tab:blue'
                ax.plot(data.index, data['Close'], color=color)
                ax.set_title(title, fontweight='bold')
                ax.grid(True, alpha=0.3)
                # 상하단 여백 조정
                y_min, y_max = data['Close'].min(), data['Close'].max()
                ax.set_ylim(y_min * 0.98, y_max * 1.02)

        plt.tight_layout(rect=[0, 0.03, 1, 0.95])
        plt.savefig(output_path, dpi=150)
        plt.close()
        return output_path

    def generate_stock_trend_charts(self, output_dir="charts"):
        """각 종목별 트렌드와 매매 시점을 비교하는 차트 생성"""
        if not HAS_MATPLOTLIB: return []
        if not os.path.exists(output_dir): os.makedirs(output_dir)
        
        generated_files = []
        for name, item in self.my_portfolio.items():
            ticker = item["ticker"]
            hist = yf.Ticker(ticker).history(period="1y") # 1년치 트렌드
            if hist.empty: continue

            plt.figure(figsize=(12, 6))
            plt.plot(hist.index, hist['Close'], label=f"{name} Price", color='gray', alpha=0.5)
            
            # 매매 시점 표시
            transactions = item.get("transactions", [])
            for tx in transactions:
                tx_date = pd.to_datetime(tx["date"]).tz_localize(hist.index.tz)
                # 가장 가까운 영업일 데이터 찾기
                idx = hist.index.get_indexer([tx_date], method='nearest')[0]
                actual_date = hist.index[idx]
                price = tx["price"]
                
                color = 'red' if tx["type"] == 'buy' else 'blue'
                marker = '^' if tx["type"] == 'buy' else 'v'
                plt.scatter(actual_date, price, color=color, marker=marker, s=100, 
                            label=f"{tx['type'].upper()} @ {price}", zorder=5)

            plt.title(f"{name} ({ticker}) Trend vs My Transactions")
            plt.legend()
            plt.grid(True, alpha=0.3)
            path = os.path.join(output_dir, f"trend_{name}.png")
            plt.savefig(path)
            plt.close()
            generated_files.append(path)
        return generated_files

    def generate_30m_forecast_charts(self, output_dir="forecasts"):
        """30분 단위 데이터를 기반으로 과거 추세와 향후 24시간 예측 그래프 생성"""
        if not HAS_MATPLOTLIB: return []
        if not os.path.exists(output_dir): os.makedirs(output_dir)
        
        generated_files = []
        for name, item in self.my_portfolio.items():
            ticker = item["ticker"]
            # 30분 단위 데이터 수집 (최근 1개월 내 가능)
            data = yf.download(ticker, period="1mo", interval="30m", progress=False)
            if data.empty: continue

            # 추세 분석 (선형 회귀)
            prices = data['Close'].values
            x = np.arange(len(prices))
            slope, intercept = np.polyfit(x, prices, 1)
            
            # 향후 24시간 예측 (30분 단위이므로 48개 포인트)
            future_x = np.arange(len(prices), len(prices) + 48)
            forecast_values = slope * future_x + intercept
            
            # 미래 시간 인덱스 생성 (30분 단위)
            last_time = data.index[-1]
            future_dates = [last_time + pd.Timedelta(minutes=30*(i+1)) for i in range(48)]

            plt.figure(figsize=(12, 6))
            # 과거 데이터 (최근 2일치만 강조해서 보여줌)
            recent_data = data.tail(96) # 30분 * 96 = 2일
            plt.plot(recent_data.index, recent_data['Close'], label="Historical (30m)", color='black', linewidth=1)
            
            # 예측 데이터
            plt.plot(future_dates, forecast_values, label="30m Forecast (Next 24h)", 
                     color='orange', linestyle='--', linewidth=2)
            
            plt.title(f"{name} ({ticker}) 30-Min Interval Strategy Chart")
            plt.xlabel("Time")
            plt.ylabel("Price")
            plt.legend()
            plt.grid(True, alpha=0.3)
            path = os.path.join(output_dir, f"forecast_{name}.png")
            plt.savefig(path)
            plt.close()
            generated_files.append(path)
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
