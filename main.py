import os
import sys
import json
import html
import glob
import re
from datetime import datetime, timezone
from market_data import MarketDataCollector
from ai_analysis import MarketAnalyzer
from telegram_bot import TelegramNotifier
from telegraph import Telegraph

def run_daily_report():
    # 1. 환경 변수 읽기 및 체크
    # GitHub Secrets 또는 로컬 .env 환경에서 설정된 값을 가져옵니다.
    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
    TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
    TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

    if not all([GEMINI_API_KEY, TELEGRAM_TOKEN, TELEGRAM_CHAT_ID]):
        print("❌ 에러: 환경 변수(API 키 등)가 설정되지 않았습니다. GitHub Secrets 또는 로컬 환경 변수를 확인하세요.")
        return

    print("1. 데이터 수집 및 시각화 시작...")
    collector = MarketDataCollector()
    
    # 보유 종목 예측 차트 생성
    chart_path = "chart.png"
    collector.generate_portfolio_prediction_chart(chart_path)
        
    # [비전] 이미지 기반 포트폴리오 업데이트 (screenshots 폴더 내의 Screenshot_*.jpg/png 파일 처리)
    analyzer = MarketAnalyzer(GEMINI_API_KEY)
    screenshot_dir = "screenshots"
    if os.path.exists(screenshot_dir):
        # Screenshot_ 으로 시작하는 jpg, jpeg, png 파일 검색
        image_files = []
        for ext in ["jpg", "jpeg", "png", "JPG", "JPEG", "PNG"]:
            image_files.extend(glob.glob(os.path.join(screenshot_dir, f"Screenshot_*.{ext}")))
        
        if image_files:
            image_files.sort()  # 파일명(날짜/시간) 순으로 정렬하여 순차 업데이트
            for img_path in image_files:
                print(f"📸 잔고 스크린샷 분석 중: {img_path}...")
                extracted_data = analyzer.extract_portfolio_from_image(img_path)
                print(f"Raw extracted data from Vision: {extracted_data}") # Vision 모델 원본 출력
                clean_json = extracted_data.strip().replace("```json", "").replace("```", "").strip()
                print(f"Clean JSON for parsing: {clean_json}") # 파싱 전 정리된 JSON
                try:
                    portfolio_list = json.loads(clean_json)
                    print(f"Parsed portfolio list: {portfolio_list}") # JSON 파싱 결과
                    collector.update_portfolio_from_list(portfolio_list)
                    print(f"🎯 포트폴리오 업데이트 완료: {os.path.basename(img_path)}")
                except json.JSONDecodeError as e:
                    print(f"❌ 포트폴리오 JSON 파싱 실패 ({img_path}): {e}")
                    print(f"  실패한 JSON 내용: {clean_json}")
                except Exception as e:
                    print(f"❌ 포트폴리오 데이터 처리 중 예상치 못한 오류 발생 ({img_path}): {e}")

    # [입력] GitHub Actions 수동 입력값(매매 진단용) 확인
    trade_ticker = os.getenv("TRADE_TICKER")
    trade_category = os.getenv("TRADE_CATEGORY")
    trade_action = os.getenv("TRADE_ACTION")
    trade_reason = os.getenv("TRADE_REASON")

    trade_info = None
    if trade_ticker and trade_category and trade_action:
        print(f"🎯 매매 분석 모드 작동: {trade_ticker}")
        ticker_data = collector.get_specific_ticker_data(trade_ticker)
        if ticker_data:
            trade_info = {
                "category": trade_category,
                "action": trade_action,
                "ticker": trade_ticker,
                "reason": trade_reason or "사유 미입력",
                "data": ticker_data
            }

    # [데이터] 시장 지수 및 포트폴리오 최신 데이터 수집
    market_data = collector.get_recent_data()

    # 2. 실행 모드 및 리포트 제목 결정
    if trade_info:
        report_type = "trade_eval"
        report_title = f"💡 매매 전략 진단 ({trade_ticker})"
    elif len(sys.argv) > 1:
        report_type = sys.argv[1] # 'opening' (장전) 또는 'closing' (장마감)
    else:
        # UTC 시간에 따라 자동으로 리포트 성격 결정 (21 UTC = 06시 KST)
        current_hour_utc = datetime.now(timezone.utc).hour
        report_type = "closing" if current_hour_utc == 21 else "opening"
        
    if report_type != "trade_eval":
        report_title = "🇺🇸 미국 증시 마감" if report_type == "closing" else "🇰🇷 국내 증시 개장 전"

    # 텔레그램 HTML 파싱 에러 방지를 위한 헬퍼 함수
    # AI가 생성한 텍스트 중 HTML 특수문자를 치환하되, 핵심 태그(b, pre)는 복구합니다.
    def safe_html(text):
        if not text: return ""
        return html.escape(text.strip()).replace("&lt;pre&gt;", "<pre>").replace("&lt;/pre&gt;", "</pre>").replace("&lt;b&gt;", "<b>").replace("&lt;/b&gt;", "</b>")

    print("2. AI 분석 진행 중...")    
    analysis_result = analyzer.generate_analysis(market_data, report_type=report_type, trade_info=trade_info)

    print("3. 텔레그램 알림 전송...")
    now = datetime.now().strftime('%Y-%m-%d %H:%M')
    notifier = TelegramNotifier(TELEGRAM_TOKEN, TELEGRAM_CHAT_ID)

    # 3-1. 지수 비교 차트 전송
    if os.path.exists(chart_path):
        notifier.send_photo(chart_path)

    # 3-3. 요약본과 상세본 분리 처리 (구분자 [SPLIT] 기준)
    if "[SPLIT]" in analysis_result:
        summary, details = analysis_result.split("[SPLIT]", 1)
        
        try:
            # Telegraph에 상세 분석 내용 업로드 (긴 텍스트 가독성 확보)
            telegraph = Telegraph()
            telegraph.create_account(short_name='Stocky')
            html_content = details.strip().replace('\n', '<br>')
            
            telegraph_response = telegraph.create_page(
                title=f"{report_title} 상세 분석 ({now})",
                html_content=f"<p>{html_content}</p>"
            )
            detail_url = telegraph_response['url']

            # 상세 보기 버튼 구성
            reply_markup = {
                "inline_keyboard": [[
                    {"text": "📖 상세 분석 리포트 더보기", "url": detail_url}
                ]]
            }

            # 요약 메시지 전송
            summary_text = f"📌 <b>{report_title} 핵심 요약 ({now})</b>\n\n{safe_html(summary)}"
            response = notifier.send_message(summary_text, reply_markup=reply_markup)
            
        except Exception as e:
            print(f"⚠️ Telegraph 업로드 실패: {e}")
            report_text = f"📊 <b>{report_title} 리포트 ({now})</b>\n\n{safe_html(analysis_result)}"
            response = notifier.send_message(report_text)
    else:
        # [SPLIT] 구분자가 없을 경우 전체 내용을 하나의 메시지로 전송
        report_text = f"📊 <b>{report_title} 리포트 ({now})</b>\n\n{safe_html(analysis_result)}"
        response = notifier.send_message(report_text)

    # 최종 결과 확인
    if response.status_code == 200:
        print("✅ 모든 리포트 및 차트 전송 완료!")
    else:
        print(f"❌ 전송 실패: {response.status_code} - {response.text}")

if __name__ == "__main__":
    run_daily_report()
