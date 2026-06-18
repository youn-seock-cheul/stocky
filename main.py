import os
import sys
import json
import html
import glob
import copy
import re
import traceback
from datetime import datetime, timezone
from dotenv import load_dotenv
from market_data import MarketDataCollector
from ai_analysis import MarketAnalyzer
from telegram_bot import TelegramNotifier
from telegraph import Telegraph

def safe_html(text):
    """텔레그램 HTML 파싱 에러 방지 및 핵심 태그 복구"""
    if not text: return ""
    return html.escape(text.strip()).replace("&lt;pre&gt;", "<pre>").replace("&lt;/pre&gt;", "</pre>") \
                                    .replace("&lt;b&gt;", "<b>").replace("&lt;/b&gt;", "</b>")

def run_daily_report():
    # .env 파일이 없으면 샘플 파일 자동 생성
    if not os.path.exists(".env"):
        print("📄 '.env' 파일이 발견되지 않아 샘플 파일을 생성합니다...")
        with open(".env", "w", encoding="utf-8") as f:
            f.write("# Stocky 환경 변수 설정 샘플\n")
            f.write("GEMINI_API_KEY=your_gemini_api_key_here\n")
            f.write("TELEGRAM_TOKEN=your_telegram_bot_token_here\n")
            f.write("TELEGRAM_CHAT_ID=your_telegram_chat_id_here\n")
        print("✅ '.env' 파일이 생성되었습니다. 실제 API 키 값을 입력한 후 다시 실행해 주세요.")
        return

    # .env 파일이 있으면 환경 변수로 로드합니다.
    load_dotenv()

    # 1. 환경 변수 읽기 및 체크
    # GitHub Secrets 또는 로컬 .env 환경에서 설정된 값을 가져옵니다.
    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
    TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
    TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

    missing_vars = []
    if not GEMINI_API_KEY: missing_vars.append("GEMINI_API_KEY")
    if not TELEGRAM_TOKEN: missing_vars.append("TELEGRAM_TOKEN")
    if not TELEGRAM_CHAT_ID: missing_vars.append("TELEGRAM_CHAT_ID")

    if missing_vars:
        print(f"❌ 에러: 다음 환경 변수가 설정되지 않았습니다: {', '.join(missing_vars)}. GitHub Secrets 또는 로컬 .env 파일을 확인하세요.")
        return

    print("1. 데이터 수집 및 시각화 시작...")
    notifier = TelegramNotifier(TELEGRAM_TOKEN, TELEGRAM_CHAT_ID)

    try:
        collector = MarketDataCollector()
        analyzer = MarketAnalyzer(GEMINI_API_KEY)

        # [비전] 이미지 기반 포트폴리오 업데이트 (screenshots 폴더 내의 Screenshot_*.jpg/png 파일 처리)
        initial_portfolio = copy.deepcopy(collector.my_portfolio)
        screenshot_dir = "screenshots"

        if os.path.exists(screenshot_dir):
            # Screenshot_ 으로 시작하는 jpg, jpeg, png 파일 검색
            image_files_set = set()
            for ext in ["jpg", "jpeg", "png", "JPG", "JPEG", "PNG"]:
                image_files_set.update(glob.glob(os.path.join(screenshot_dir, f"Screenshot_*.{ext}")))
            
            if image_files_set:
                image_files = sorted(list(image_files_set))
                for img_path in image_files:
                    print(f"📸 잔고 스크린샷 분석 중: {img_path}...")
                    extracted_data = analyzer.extract_portfolio_from_image(img_path)
                    
                    # AI 응답에 'error' 키가 포함되어 있으면 실패로 간주
                    if '"error":' in extracted_data or not extracted_data.strip().startswith("["):
                        print(f"❌ 이미지 분석 스킵 (AI 오류): {extracted_data}")
                        continue

                    clean_json = extracted_data.strip().replace("```json", "").replace("```", "").strip()
                    print(f"Clean JSON for parsing: {clean_json}") # 파싱 전 정리된 JSON
                    try:
                        portfolio_list = json.loads(clean_json)
                        if isinstance(portfolio_list, list):
                            print(f"Parsed portfolio list size: {len(portfolio_list)}")
                            collector.update_portfolio_from_list(portfolio_list)
                            print(f"🎯 포트폴리오 업데이트 완료: {os.path.basename(img_path)}")
                        else:
                            print(f"⚠️ 경고: 추출된 데이터가 리스트 형식이 아닙니다: {portfolio_list}")
                    except json.JSONDecodeError as e:
                        print(f"❌ 포트폴리오 JSON 파싱 실패 ({img_path}): {e}")
                        print(f"  실패한 JSON 내용: {clean_json}")
                    except Exception as e:
                        print(f"❌ 포트폴리오 데이터 처리 중 예상치 못한 오류 발생 ({img_path}): {e}")

                # 변경 사항 확인 및 텔레그램 알림
                if initial_portfolio != collector.my_portfolio:
                    changes = []
                    for name, data in collector.my_portfolio.items():
                        if name not in initial_portfolio:
                            changes.append(f"🆕 <b>{name}</b> (신규 추가)")
                        elif initial_portfolio[name] != data:
                            changes.append(f"🔄 <b>{name}</b> (정보 갱신)")
                    
                    if changes:
                        update_msg = "♻️ <b>잔고 동기화 완료</b>\n\n" + "\n".join(changes)
                        update_msg += "\n\n💡 업데이트된 데이터를 기반으로 리포트를 생성합니다."
                        notifier.send_message(update_msg)

        # [데이터] 시장 지수 및 포트폴리오 최신 데이터 수집 (스크린샷 반영 후)
        market_data = collector.get_recent_data()

        # 보유 종목 예측 차트 생성
        chart_path = "chart.png"
        sentiment_path = "sentiment.png"
        collector.generate_portfolio_prediction_chart(chart_path)
        collector.generate_sentiment_gauge(market_data['market_sentiment'], sentiment_path)

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

        print("2. AI 분석 진행 중...")    
        analysis_result = analyzer.generate_analysis(market_data, report_type=report_type, trade_info=trade_info)

        print("3. 텔레그램 알림 전송...")
        now = datetime.now().strftime('%Y-%m-%d %H:%M')

        # 3-1. 지수 비교 차트 전송
        if os.path.exists(chart_path):
            notifier.send_photo(chart_path)
        if os.path.exists(sentiment_path):
            notifier.send_photo(sentiment_path)

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
                # 봇 클래스에서 자동 분할을 지원하므로 직접 호출만 수행
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
        elif response and response.status_code == 404:
            print("❌ 전송 실패: 404 - 텔레그램 토큰(TELEGRAM_TOKEN)이 올바르지 않거나 봇을 찾을 수 없습니다.")
            print("💡 GitHub Secrets 또는 .env 파일의 토큰 값을 다시 확인해 주세요.")
        else:
            status = response.status_code if response else "N/A"
            print(f"❌ 전송 실패: {status} - 통신 오류 발생")

    except Exception as e:
        error_trace = traceback.format_exc()
        print(f"❌ 시스템 런타임 에러 발생:\n{error_trace}")
        error_report = f"🚨 <b>Stocky 시스템 에러 발생</b>\n\n<pre>{html.escape(error_trace)}</pre>"
        notifier.send_message(error_report)

if __name__ == "__main__":
    run_daily_report()
