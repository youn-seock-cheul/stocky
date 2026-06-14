import os
import json
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
        self.portfolio_file = "portfolio.json"
        # 1. 시장 흐름 파악을 위한 주요 지수
        self.indices = {
            "S&P500": "^GSPC",      # 미국 S&P 500
            "Nasdaq": "^IXIC",      # 미국 나스닥
            "KOSPI": "^KS11",       # 한국 코스피
            "KOSDAQ": "^KQ11",      # 한국 코스닥
            "USD_KRW": "USDKRW=X"   # 원/달러 환율
        }
        # 2. 실제 보유 중인 개인 포트폴리오 (원하시는 종목으로 변경하세요)
        self.load_portfolio()

    def load_portfolio(self):
        """파일에서 포트폴리오 로드 또는 기본값 설정"""
        if os.path.exists(self.portfolio_file):
            try:
                with open(self.portfolio_file, 'r', encoding='utf-8') as f:
                    self.my_portfolio = json.load(f)
                print(f"✅ 포트폴리오 데이터를 {self.portfolio_file}에서 불러왔습니다.")
            except Exception as e:
                print(f"⚠️ 포트폴리오 로드 실패: {e}")
                self._set_default_portfolio()
        else:
            self._set_default_portfolio()
            self.save_portfolio()

    def _set_default_portfolio(self):
        self.my_portfolio = {
            "Samsung": {"ticker": "005930.KS", "avg_price": 75000, "deposit": 1500000}
        }

    def save_portfolio(self):
        """현재 포트폴리오를 파일에 저장"""
        with open(self.portfolio_file, 'w', encoding='utf-8') as f:
            json.dump(self.my_portfolio, f, ensure_ascii=False, indent=4)

    def get_recent_data(self, days=30):
        """최근 n일간의 종가 데이터를 가져와 요약본 반환"""
        def fetch_data(target_dict, is_portfolio=False):
            report = {}
            for name, item in target_dict.items():
                ticker = item["ticker"] if is_portfolio else item
                try:
                    t = yf.Ticker(ticker)
                    # RSI, MACD 등 지표 계산을 위해 충분한 데이터(60일) 수집
                    data = t.history(period="60d")
                    
                    if not data.empty and len(data) >= 2:
                        current_price = float(data['Close'].iloc[-1])
                        prev_price = float(data['Close'].iloc[-2])
                        change_pct = (current_price - prev_price) / prev_price * 100
                        
                        # RSI 계산 (14일 기준)
                        delta = data['Close'].diff()
                        up = delta.clip(lower=0)
                        down = -1 * delta.clip(upper=0)
                        ema_up = up.ewm(com=13, adjust=False).mean()
                        ema_down = down.ewm(com=13, adjust=False).mean()
                        rs = ema_up / ema_down
                        rsi = 100 - (100 / (1 + rs))

                        # MACD 계산 (12, 26, 9)
                        exp12 = data['Close'].ewm(span=12, adjust=False).mean()
                        exp26 = data['Close'].ewm(span=26, adjust=False).mean()
                        macd = exp12 - exp26
                        macd_signal = macd.ewm(span=9, adjust=False).mean()

                        entry = {
                            "price": round(float(current_price), 2),
                            "change_pct": round(float(change_pct), 2),
                            "rsi": round(float(rsi.iloc[-1]), 2),
                            "macd": round(float(macd.iloc[-1]), 2),
                            "macd_signal": round(float(macd_signal.iloc[-1]), 2),
                            "history": {d.strftime('%Y-%m-%d'): round(float(p), 2) for d, p in data['Close'].tail(days).to_dict().items()}
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

    def generate_portfolio_prediction_chart(self, output_path="chart.png"):
        """보유 종목의 한 달 흐름 및 향후 24시간 예측 차트 생성"""
        if not HAS_MATPLOTLIB:
            print("⚠️ Matplotlib 라이브러리 로드 실패로 차트 생성을 건너뜁니다.")
            return

        plt.figure(figsize=(12, 6))
        for name, item in self.my_portfolio.items():
            ticker = item["ticker"]
            # 최근 1개월 시간별 데이터 수집 (예측 정확도 향상)
            data = yf.download(ticker, period="1mo", interval="1h", progress=False)
            if not data.empty:
                prices = data['Close'].values
                # 첫 가격 기준 변동률(%) 정규화 (여러 종목 비교용)
                norm_prices = (prices / prices[0] - 1) * 100
                
                # 추세 분석 (선형 회귀)
                x = np.arange(len(norm_prices))
                slope, intercept = np.polyfit(x, norm_prices, 1)

                # 변동성 범위를 위한 표준편차 계산 (잔차 기준)
                trend_line = slope * x + intercept
                std_dev = np.std(norm_prices - trend_line)
                
                # 향후 24시간(데이터 포인트 24개) 예측
                future_x = np.arange(len(norm_prices), len(norm_prices) + 24)
                forecast = slope * future_x + intercept
                
                # 추세에 따른 신뢰 구간 색상 결정 (상승: 빨강, 하락: 파랑)
                shadow_color = 'red' if slope > 0 else 'blue'

                # 과거 데이터 및 예측 데이터(점선) 플롯
                p = plt.plot(range(len(norm_prices)), norm_prices, label=f"{name}", alpha=0.7)
                plt.plot(future_x, forecast, linestyle='--', color=p[0].get_color(), alpha=0.8)
                
                # 신뢰 구간 (Shadow) 추가 - 추세별 색상 적용
                plt.fill_between(future_x, forecast - 2*std_dev, forecast + 2*std_dev, color=shadow_color, alpha=0.15)
        
        plt.title("Portfolio Trend & 24h Prediction (Normalized %)")
        plt.xlabel("Time (Hourly Intervals)")
        plt.ylabel("Normalized Change (%)")
        plt.legend()
        plt.grid(True, alpha=0.3)
        plt.savefig(output_path)
        plt.close()

    def update_portfolio_from_list(self, portfolio_list):
        """AI가 추출한 리스트로 포트폴리오 업데이트"""
        updated_items_from_screenshot = {}
        for item in portfolio_list:
            name = item.get("name")
            ticker = item.get("ticker")
            avg_price = item.get("avg_price")
            deposit = item.get("deposit")
            if name and ticker and avg_price is not None and deposit is not None:
                updated_items_from_screenshot[name] = {
                    "ticker": ticker,
                    "avg_price": float(avg_price),
                    "deposit": float(deposit)
                }
            else:
                print(f"⚠️ 이미지 분석에서 필수 정보 누락 또는 형식 오류: {item}")
        if updated_items_from_screenshot:
            # 기존 포트폴리오에 스크린샷에서 추출된 항목들을 병합 (업데이트 또는 추가)
            self.my_portfolio.update(updated_items_from_screenshot)
            self.save_portfolio()
            print("✅ 포트폴리오 파일이 업데이트되었습니다.")
        else:
            print("⚠️ 이미지 분석에서 유효한 포트폴리오 항목을 추출하지 못했습니다.")

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
