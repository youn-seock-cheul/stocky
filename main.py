import os
import sys
from datetime import datetime, timezone
from market_data import MarketDataCollector
from ai_analysis import MarketAnalyzer
from telegram_bot import TelegramNotifier
from telegraph import Telegraph

def run_daily_report():
    # API 키 및 설정 (환경 변수에서 읽어오도록 수정)
    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
    TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
    TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

    # 환경 변수 체크
    if not all([GEMINI_API_KEY, TELEGRAM_TOKEN, TELEGRAM_CHAT_ID]):
        print("❌ 에러: 환경 변수(API 키 등)가 설정되지 않았습니다. GitHub Secrets 또는 로컬 환경 변수를 확인하세요.")
        return

    print("1. 데이터 수집 시작...")
    collector = MarketDataCollector()
    market_data = collector.get_recent_data()

    # 2. 실행 시간에 따른 리포트 성격 결정 (UTC 기준)
    # 21시 UTC = 06:00 KST (미국 마감), 22시 UTC = 07:50 KST (한국 개장 전)
    # 테스트를 위해 명령행 인자가 있으면 해당 인자를 사용 (예: python main.py closing)
    if len(sys.argv) > 1:
        report_type = sys.argv[1]
    else:
        # datetime.utcnow()는 향후 폐기될 예정이므로 최신 방식을 권장하지만, 
        # 현재 코드의 일관성을 위해 유지하거나 아래와 같이 처리합니다.
        current_hour_utc = datetime.now(timezone.utc).hour
        report_type = "closing" if current_hour_utc == 21 else "opening"
        
    report_title = "🇺🇸 미국 증시 마감" if report_type == "closing" else "🇰🇷 국내 증시 개장 전"

    print("2. AI 분석 진행 중...")
    analyzer = MarketAnalyzer(GEMINI_API_KEY)
    analysis_result = analyzer.generate_analysis(market_data, report_type=report_type)

    print("3. 텔레그램 알림 전송...")
    now = datetime.now().strftime('%Y-%m-%d %H:%M')
    notifier = TelegramNotifier(TELEGRAM_TOKEN, TELEGRAM_CHAT_ID)

    if "[SPLIT]" in analysis_result:
        summary, details = analysis_result.split("[SPLIT]", 1)
        
        try:
            # 1. Telegraph에 상세 내용 업로드
            telegraph = Telegraph()
            telegraph.create_account(short_name='Stocky')
            # 줄바꿈을 HTML 태그로 변환하여 업로드
            html_content = details.strip().replace('\n', '<br>')
            telegraph_response = telegraph.create_page(
                title=f"{report_title} 상세 분석 ({now})",
                html_content=f"<p>{html_content}</p>"
            )
            detail_url = telegraph_response['url']

            # 2. 버튼 구성 (인라인 키보드)
            reply_markup = {
                "inline_keyboard": [[
                    {"text": "📖 상세 분석 리포트 더보기", "url": detail_url}
                ]]
            }

            # 3. 요약본과 버튼 전송
            summary_text = f"📌 <b>{report_title} 핵심 요약 ({now})</b>\n\n{summary.strip()}"
            response = notifier.send_message(summary_text, reply_markup=reply_markup)
        except Exception as e:
            print(f"⚠️ Telegraph 업로드 실패: {e}")
            # 실패 시 기존처럼 텍스트로 전체 전송
            report_text = f"📊 <b>{report_title} 리포트 ({now})</b>\n\n{analysis_result}"
            response = notifier.send_message(report_text)
    else:
        # 구분자가 없을 경우 전체 전송 (예외 처리)
        report_text = f"📊 <b>{report_title} 리포트 ({now})</b>\n\n{analysis_result}"
        response = notifier.send_message(report_text)

    if response.status_code == 200:
        print("✅ 리포트 전송 완료!")
    else:
        print(f"❌ 전송 실패: {response.status_code} - {response.text}")

if __name__ == "__main__":
    run_daily_report()