# 📈 Stocky - AI 기반 주식 리포트 자동화 시스템

Stocky는 **Google Gemini AI**와 **yfinance**를 결합하여 한국 및 미국 증시 시황을 분석하고, 사용자의 포트폴리오 수익률과 향후 주가 예측 그래프를 텔레그램으로 전송해주는 자동화 시스템입니다.

## 🚀 주요 기능
- **일일 시황 리포트**: 한국 개장 전(07:50 KST) 및 미국 마감 후(06:00 KST) 자동 발송.
- **개인 포트폴리오 관리**: 매수 평단가 기반 수익률 계산 및 일간/월간 수익률 추이 그래프 생성.
- **AI 매매 진단**: 특정 종목에 대한 매수/매도 적절성 및 목표가 분석 (GitHub Actions 수동 실행 연동).
- **주가 예측**: 최근 1개월 데이터를 기반으로 향후 24시간의 시간별 주가 흐름 예측 그래프 생성.
- **시각화 리포트**: 지수 변동, 포트폴리오 성과, 종목 트렌드 차트를 이미지로 전송.
- **잔고 자동 업데이트**: 증권사 잔고 스크린샷(`balance.png`)을 분석하여 포트폴리오 및 평단가를 자동 갱신.
- **Telegraph 연동**: 긴 상세 분석 내용은 Telegraph 페이지 링크로 깔끔하게 제공.

## 🛠 설치 및 설정 방법 (다른 PC에서 시작하기)

### 1. 필수 요구사항
- **Python 3.10** 이상
- **Git**

### 2. 저장소 복제 및 라이브러리 설치
```bash
git clone <본인의-저장소-URL>
cd stocky

# 가상환경 설정 (권장)
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 필요 라이브러리 설치
pip install -U yfinance pandas google-genai requests telegraph matplotlib numpy pillow
```

### 3. 환경 변수 설정
로컬 테스트를 위해 프로젝트 루트 폴더에 `.env` 파일을 생성하거나 터미널 환경 변수에 아래 값을 설정해야 합니다.

| 변수명 | 설명 | 비고 |
| :--- | :--- | :--- |
| `GEMINI_API_KEY` | Google AI Studio에서 발급받은 API 키 | 발급받기 |
| `TELEGRAM_TOKEN` | 텔레그램 BotFather를 통해 만든 봇 토큰 | |
| `TELEGRAM_CHAT_ID` | 알림을 받을 본인의 텔레그램 숫자 ID | |

### 4. GitHub Secrets 설정
GitHub Actions를 통한 자동화를 위해 GitHub 저장소의 `Settings > Secrets and variables > Actions`에 위 3가지 환경 변수를 등록해야 합니다.

## 💻 실행 방법

### 로컬 테스트
```bash
# 한국 증시 개장 전 리포트 테스트
python main.py opening

# 미국 증시 마감 후 리포트 테스트
python main.py closing

# 특정 종목 매매 진단 시뮬레이션 (환경 변수 설정 필요)
python main.py
```

### GitHub Actions 수동 실행
GitHub 저장소의 `Actions` 탭에서 `Daily Stock Report`를 선택한 후 `Run workflow`를 클릭하여 종목 코드와 매매 사유를 입력하고 실행할 수 있습니다. (모바일 단축어 연동 가능)

## 📸 잔고 스크린샷 업데이트 방법
1. 증권사 앱에서 잔고 화면을 캡처합니다.
2. 파일명을 `Screenshot_YYYYMMDD_HHMMSS.jpg` 형식으로 저장하여 `screenshots` 폴더에 넣습니다.
3. `main.py`를 실행하면 AI가 폴더 내의 스크린샷들을 분석하여 `portfolio.json`을 자동으로 갱신합니다.
4. 한 번 업데이트된 데이터는 파일로 보관되므로, 이후에는 사진이 없어도 기존 잔고를 기준으로 분석이 진행됩니다.

## 📁 파일 구조
- `main.py`: 프로그램 전체 로직 제어 및 실행 엔트리 포인트.
- `market_data.py`: yfinance를 통한 데이터 수집 및 matplotlib 기반 각종 차트 생성.
- `ai_analysis.py`: Gemini API를 활용한 시황 분석 및 이미지 분석(Vision).
- `telegram_bot.py`: 텔레그램 메시지 및 사진 전송 모듈.
- `.github/workflows/daily_report.yml`: GitHub Actions 자동화 스케줄 및 입력 설정.
- `.gitignore`: 불필요한 캐시 및 개인 설정 파일 제외.

## ⚠️ 주의사항
- **종목 코드**: 한국 종목은 `.KS`(코스피) 또는 `.KQ`(코스닥) 접미사가 필요합니다. (예: `005930.KS`)
- **데이터 지연**: `yfinance` 데이터는 실제 거래소보다 약 15~20분 지연될 수 있습니다.
- **API 할당량**: Gemini 무료 티어 사용 시 분당 요청 수 제한(429 Error)이 발생할 수 있으며, 이 경우 자동으로 다음 모델로 전환을 시도합니다.

## 📝 라이선스
이 프로젝트는 개인 학습 및 투자 참고용으로 제작되었습니다. 투자에 대한 모든 책임은 사용자 본인에게 있습니다.