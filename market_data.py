import os
import json
import re
import numpy as np
import yfinance as yf
import FinanceDataReader as fdr
import pandas as pd
import matplotlib.font_manager as fm
import matplotlib.pyplot as plt

class MarketDataCollector:
    def __init__(self):
        self.portfolio_file = "portfolio.json"
        self.indices = {"S&P500": "^GSPC", "Nasdaq": "^IXIC", "KOSPI": "^KS11", "KOSDAQ": "^KQ11", "USD_KRW": "USDKRW=X"}
        self.load_portfolio()
        self._setup_font()

    def _setup_font(self):
        """차트 한글 깨짐 방지를 위한 폰트 설정"""
        font_list = ['Malgun Gothic', 'AppleGothic', 'NanumGothic', 'Noto Sans CJK KR', 'Arial Unicode MS']
        for font in font_list:
            if font in [f.name for f in fm.fontManager.ttflist]:
                plt.rcParams['font.family'] = font
                break
        plt.rcParams['axes.unicode_minus'] = False

        # --- [추가해야 할 부분] ---
        # 현재 적용된 폰트 이름 가져오기
        current_font = plt.rcParams['font.family'][0]

        # 범례 객체 생성 시 폰트 정보 명시
        plt.legend(prop={'family': current_font}) 

    def load_portfolio(self):
        # 로드 실패 시 사용할 기본 데이터 정의
        default_portfolio = {
            "Samsung": {"ticker": "005930.KS", "avg_price": 299927, "deposit": 7384545},
            "RISE AI Infra": {"ticker": "0101N0.KS", "avg_price": 22931, "deposit": 43202755}
        }

        if os.path.exists(self.portfolio_file):
            try:
                with open(self.portfolio_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    if not isinstance(data, dict):
                        raise ValueError("JSON 데이터가 딕셔너리 형태가 아닙니다.")
                    
                    is_valid, msg = self._validate_portfolio(data) # Validate after loading
                    if not is_valid:
                        raise ValueError(f"로드된 포트폴리오 데이터 검증 실패: {msg}")                    
                    self.my_portfolio = data
            except (json.JSONDecodeError, ValueError, OSError) as e:
                print(f"⚠️ {self.portfolio_file} 로드 중 오류 발생: {e}")
                print("💡 기본 포트폴리오 데이터를 사용합니다.")
                self.my_portfolio = default_portfolio
        else:
            self.my_portfolio = default_portfolio

    def _calculate_rsi(self, series, period=14):
        delta = series.diff()
        up = delta.clip(lower=0)
        down = -1 * delta.clip(upper=0)
        ema_u = up.ewm(com=period-1, adjust=False).mean()
        ema_d = down.ewm(com=period-1, adjust=False).mean()
        rs = ema_u / ema_d
        return 100 - (100 / (1 + rs))

    def _calculate_macd(self, series):
        exp12 = series.ewm(span=12, adjust=False).mean()
        exp26 = series.ewm(span=26, adjust=False).mean()
        macd = exp12 - exp26
        signal = macd.ewm(span=9, adjust=False).mean()
        return macd, signal

    def _calculate_bollinger_bands(self, series, window=20, num_std=2):
        """볼린저 밴드(상단, 중단, 하단) 계산"""
        sma = series.rolling(window=window).mean()
        std = series.rolling(window=window).std()
        upper = sma + (std * num_std)
        lower = sma - (std * num_std)
        return upper, sma, lower

    def _get_bb_signal(self, price, upper, lower):
        """볼린저 밴드 기반 매매 신호 판단"""
        if price >= upper:
            return "상단 돌파 (과매수 주의)"
        elif price <= lower:
            return "하단 돌파 (과매도 반등 기대)"
        else:
            return "밴드 내 안정권"

    def _calculate_sentiment_score(self, series):
        """RSI와 이격도를 결합하여 0-100점 사이의 시장 심리 점수 계산"""
        if len(series) < 50: return 50.0
        
        # 1. RSI 기반 심리 (40%)
        rsi = self._calculate_rsi(series).iloc[-1]
        
        # 2. 50일 이동평균선 대비 이격도 기반 모멘텀 (60%)
        # 주가가 50일선 위에 있을수록 탐욕, 아래에 있을수록 공포
        ma50 = series.rolling(window=50).mean().iloc[-1]
        price_now = series.iloc[-1]
        # 이격도 0.95(공포) ~ 1.05(탐욕) 범위를 0~100점으로 정규화
        momentum_score = np.clip(((price_now / ma50) - 0.95) / 0.1 * 100, 0, 100)
        
        return round((rsi * 0.4) + (momentum_score * 0.6), 2)

    def get_recent_data(self, days=30):       
        sentiment_scores = []
        def fetch(target, is_p=False):
            res = {}
            for name, item in target.items():
                ticker = item["ticker"] if is_p else item
                
                # 국내 종목(.KS, .KQ)은 FinanceDataReader 사용, 그 외는 yfinance 사용
                try:
                    if ticker.endswith('.KS') or ticker.endswith('.KQ'):
                        symbol = ticker.split('.')[0]
                        # 1년 전부터 오늘까지 데이터 수집
                        start_date = (pd.Timestamp.now() - pd.DateOffset(years=1)).strftime('%Y-%m-%d')
                        data = fdr.DataReader(symbol, start=start_date)
                    else:
                        data = yf.Ticker(ticker).history(period="1y")
                except Exception as e:
                    print(f"❌ '{name}'({ticker}) 데이터 수집 중 오류: {e}")
                    data = pd.DataFrame()

                if not data.empty:
                    # 1차원 데이터 보장 및 인덱스 유지
                    close_col = 'Close' if 'Close' in data.columns else 'close' # fdr은 대소문자 섞일 수 있음
                    close = pd.Series(data[close_col].to_numpy().flatten(), index=data.index)
                    rsi = self._calculate_rsi(close)
                    macd, sig = self._calculate_macd(close)
                    upper_bb, mid_bb, lower_bb = self._calculate_bollinger_bands(close)
                    
                    entry = {"price": round(float(close.iloc[-1]), 2), "change_pct": round(((close.iloc[-1]/close.iloc[-2])-1)*100, 2),
                             "rsi": round(float(rsi.iloc[-1]), 2), "macd": round(float(macd.iloc[-1]), 2), "macd_signal": round(float(sig.iloc[-1]), 2),
                             "bb_upper": round(float(upper_bb.iloc[-1]), 2), "bb_lower": round(float(lower_bb.iloc[-1]), 2),
                             "bb_signal": self._get_bb_signal(close.iloc[-1], upper_bb.iloc[-1], lower_bb.iloc[-1]),
                             "history": {d.strftime('%m-%d'): round(float(p), 2) for d, p in close.tail(days).to_dict().items()}}
                    if is_p:
                        roi = (close.iloc[-1] - item['avg_price']) / item['avg_price'] * 100
                        val = (close.iloc[-1] / item['avg_price']) * item['deposit']
                        entry.update({"avg_price": item['avg_price'], "deposit": item['deposit'], "roi": round(roi, 2), "current_value": round(val, 0), "profit_loss": round(val - item['deposit'], 0)})
                    else:
                        # 지수 데이터인 경우 심리 점수 계산 (S&P500, KOSPI 등 주요 지수 합산용)
                        if name in ["S&P500", "KOSPI", "Nasdaq"]:
                            sentiment_scores.append(self._calculate_sentiment_score(close))

                    res[name] = entry
                else:
                    print(f"⚠️ 경고: '{name}'({ticker}) 데이터를 Yahoo Finance에서 찾을 수 없습니다.")
            return res

        indices_data = fetch(self.indices)
        portfolio_data = fetch(self.my_portfolio, True)
        
        # 평균 시장 심리 지수 계산
        avg_sentiment = sum(sentiment_scores) / len(sentiment_scores) if sentiment_scores else 50.0
        
        return {"indices": indices_data, "portfolio": portfolio_data, "market_sentiment": avg_sentiment}

    def generate_portfolio_prediction_chart(self, output_path="chart.png"):       
        plt.figure(figsize=(12, 6))
        for name, item in self.my_portfolio.items():
            ticker = item['ticker']
            try:
                if ticker.endswith('.KS') or ticker.endswith('.KQ'):
                    symbol = ticker.split('.')[0]
                    start_date = (pd.Timestamp.now() - pd.DateOffset(months=1)).strftime('%Y-%m-%d')
                    data = fdr.DataReader(symbol, start=start_date)
                else:
                    data = yf.download(ticker, period="1mo", interval="1h", progress=False)
            except:
                data = pd.DataFrame()

            if not data.empty:
                # 1차원 데이터 보장 (차원 오류 방지)
                close_col = 'Close' if 'Close' in data.columns else 'close'
                close_vals = data[close_col].to_numpy().flatten()
                norm = (close_vals / close_vals[0] - 1) * 100
                x = np.arange(len(norm)); slope, intercept = np.polyfit(x, norm, 1)
                
                # 볼린저 밴드 계산 (시각화용)
                upper_bb, _, lower_bb = self._calculate_bollinger_bands(pd.Series(norm))
                
                std = np.std(norm - (slope * x + intercept))
                f_x = np.arange(len(norm), len(norm) + 24); f_y = slope * f_x + intercept
                color = 'red' if slope > 0 else 'blue'
                p = plt.plot(x, norm, label=name, alpha=0.7)
                
                # 볼린저 밴드 영역 표시
                plt.fill_between(x, lower_bb, upper_bb, color=p[0].get_color(), alpha=0.1)
                
                plt.plot(f_x, f_y, linestyle='--', color=p[0].get_color())
                plt.fill_between(f_x, f_y - 2*std, f_y + 2*std, color=color, alpha=0.1)
        plt.title("Portfolio Prediction (Red: Up, Blue: Down)"); plt.legend(); plt.grid(True, alpha=0.3)
        plt.savefig(output_path); plt.close()

    def generate_sentiment_gauge(self, score, output_path="sentiment.png"):
        """시장 심리 지수를 게이지 형태로 시각화"""
        plt.figure(figsize=(6, 3))
        # 배경 영역 (공포 -> 탐욕 색상 바)
        colors = ['#ff4b4b', '#ffa500', '#f9d71c', '#90ee90', '#008000']
        for i, color in enumerate(colors):
            plt.barh(0, 20, left=i*20, color=color, alpha=0.3, height=0.5)
        
        # 지표 바늘
        plt.axvline(x=score, color='black', linewidth=3)
        plt.scatter(score, 0, color='black', s=100, zorder=5)
        
        # 텍스트 라벨
        plt.text(10, 0.4, "Extreme Fear", ha='center', fontsize=9, color='darkred')
        plt.text(50, 0.4, "Neutral", ha='center', fontsize=9, color='gray')
        plt.text(90, 0.4, "Extreme Greed", ha='center', fontsize=9, color='darkgreen')
        
        plt.text(score, -0.4, f"SCORE: {score}", ha='center', fontsize=12, fontweight='bold')
        
        plt.xlim(0, 100)
        plt.ylim(-0.8, 0.8)
        plt.axis('off')
        plt.title("Market Fear & Greed Index", pad=15, fontweight='bold')
        plt.tight_layout()
        plt.savefig(output_path); plt.close()

    def update_portfolio_from_list(self, portfolio_list):
        try:
            updates = {
                i['name']: {
                    "ticker": i['ticker'], 
                    "avg_price": float(i['avg_price']), 
                    "deposit": float(i['deposit'])
                } 
                for i in portfolio_list if all(k in i for k in ['name', 'ticker', 'avg_price', 'deposit'])
            }
            if updates: 
                self.my_portfolio.update(updates)
                self.save_portfolio()
        except (ValueError, TypeError, KeyError) as e:
            print(f"⚠️ 포트폴리오 업데이트 중 데이터 형식 오류 발생: {e}")

    def _validate_portfolio(self, data):
        """포트폴리오 데이터 무결성 검증"""
        if not isinstance(data, dict):
            return False, "포트폴리오 데이터가 딕셔너리 형식이 아닙니다."
        
        for name, info in data.items():
            if not isinstance(info, dict):
                return False, f"'{name}'의 정보가 올바른 형식이 아닙니다."
            for key in ['ticker', 'avg_price', 'deposit']:
                if key not in info:
                    return False, f"'{name}' 항목에 필수 키 '{key}'가 누락되었습니다."
            ticker = info['ticker']
            if not isinstance(ticker, str) or not ticker:
                 return False, f"'{name}'의 티커 정보가 유효하지 않습니다 (빈 문자열 또는 비문자열)."
            
            # 개선된 정규식: 
            # 1. 한국 종목: 6자리 영문/숫자 + .KS 또는 .KQ (예: 005930.KS, 0101N0.KS)
            # 2. 미국 종목: 1-5자리 영문 대문자 (예: AAPL, NVDA)
            # 3. 기타 특수 티커: 환율 등 (=X 접미사 허용)
            if not re.fullmatch(r'^([A-Z0-9]{6}\.(KS|KQ)|[A-Z]{1,5}|[A-Z0-9]+=X)$', ticker):
                return False, f"'{name}'의 티커 '{ticker}' 형식이 올바르지 않습니다. (올바른 예: 005930.KS, AAPL, USDKRW=X)"

            if not (isinstance(info['avg_price'], (int, float)) and info['avg_price'] >= 0):
                return False, f"'{name}'의 평단가가 유효하지 않습니다."
            if not (isinstance(info['deposit'], (int, float)) and info['deposit'] >= 0):
                return False, f"'{name}'의 매입금액이 유효하지 않습니다."
        return True, "OK"

    def save_portfolio(self):
        is_valid, msg = self._validate_portfolio(self.my_portfolio)
        if not is_valid:
            print(f"❌ 포트폴리오 저장 실패 (무결성 검증 오류): {msg}")
            return

        try:
            with open(self.portfolio_file, 'w', encoding='utf-8') as f: 
                json.dump(self.my_portfolio, f, ensure_ascii=False, indent=4)
        except OSError as e:
            print(f"❌ 포트폴리오 파일 저장 중 시스템 오류: {e}")
