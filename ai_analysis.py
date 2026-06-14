from google import genai
import PIL.Image

class MarketAnalyzer:
    def __init__(self, api_key):
        # 최신 Gemini SDK 클라이언트 설정
        self.client = genai.Client(api_key=api_key)

    def list_available_models(self):
        """현재 API 키로 접근 가능한 모델 리스트 출력 (디버깅용)"""
        try:
            print("🔍 사용 가능한 모델 리스트 확인 중...")
            for model in self.client.models.list():
                print(f"  - {model.name}")
        except Exception as e:
            print(f"⚠️ 모델 목록을 가져오지 못했습니다: {e}")

    def generate_analysis(self, market_data, report_type="opening", trade_info=None):
        """수집된 데이터를 기반으로 AI 분석 리포트 생성"""
        
        # 1. 지수 데이터 및 포트폴리오 데이터를 각각 텍스트로 변환
        indices_data = market_data.get('indices', {})
        portfolio_data = market_data.get('portfolio', {})
        
        indices_summary = ""
        for name, info in indices_data.items():
            indices_summary += f"- {name}: 현재가 {info['price']}, 등락률 {info['change_pct']}%\n"
            
        portfolio_summary = ""
        total_deposit = sum(info.get('deposit', 0) for info in portfolio_data.values())
        total_value = sum(info.get('current_value', 0) for info in portfolio_data.values())

        for name, info in portfolio_data.items():
            current_val = info.get('current_value', 0)
            weight = (current_val / total_value * 100) if total_value > 0 else 0
            history_str = ", ".join([f"{d}: {p}" for d, p in info.get('history', {}).items()])
            portfolio_summary += f"- {name}: 현재가 {info['price']} (평단 {info['avg_price']}), 수익률 {info['roi']}%, 비중 {round(weight, 1)}%, 평가손익 {info['profit_loss']}원\n"
            portfolio_summary += f"  [기술적 지표]: RSI({info.get('rsi')}), MACD({info.get('macd')}), Signal({info.get('macd_signal')})\n"
            portfolio_summary += f"  [최근 1개월 가격 데이터]: {history_str}\n"

        if total_deposit > 0:
            total_roi = (total_value - total_deposit) / total_deposit * 100
            portfolio_summary += f"\n💰 총 투자금: {int(total_deposit)}원\n"
            portfolio_summary += f"📈 총 평가금액: {int(total_value)}원\n"
            portfolio_summary += f"📊 전체 수익률: {round(total_roi, 2)}%\n"

        # 2. 매매 판단 요청인 경우 (trade_info 존재 시)
        if trade_info:
            ticker_data = trade_info['data']
            prompt = f"""
            당신은 개인 투자자의 매매 결정을 돕는 수석 투자 컨설턴트입니다.
            
            [사용자 요청]
            - 투자 유형: {trade_info['category']}
            - 수행 작업: {trade_info['action']}
            - 대상 종목: {trade_info['ticker']} (현재가: {ticker_data['price']}, 등락률: {ticker_data['change_pct']}%)
            - 매매 사유: {trade_info['reason']}
            
            [최근 시장 맥락]
            {indices_summary}

            [요청 사항]
            1. **매매 진단**: 해당 매매가 현재 시장 흐름상 적절한지 '적정/주의/위험' 단계로 구분하여 결론을 내주세요.
            2. **오늘의 대응**: 오늘 당장 실행해야 할 매매 가격 및 비중 조절 가이드를 제시하세요.
            3. **주간/장기 전망**: 기술적 지표(RSI, MACD, 이동평균선 등) 분석을 근거로 활용하여 이번 주 예상 흐름과 목표가/손절가를 명확한 수치로 제안하세요.
            4. **유형별 특이사항**: {trade_info['category']} 특성에 따른 주의점(환율, 배당, 지수 연동 등)을 언급하세요.
            """
            report_type = "trade_eval"

        # 2. 리포트 유형에 따른 차별화된 프롬프트 구성
        elif report_type == "closing":
            prompt = f"""
            당신은 글로벌 매크로 분석 전문가입니다. 미국 증시 마감 상황을 요약하여 한국 투자자들에게 전달하세요.

            [최신 시장 데이터]
            {indices_summary}
            
            [나의 보유 종목]
            {portfolio_summary}

            [요청 사항]
            1. **미국 증시 마감 요약**: 간밤 뉴욕 증시의 핵심 변동 원인과 흐름을 설명해줘.
            2. **주요 종목 동향**: 테크주(빅테크, 반도체 등)의 눈에 띄는 움직임 분석.
            3. **보유 종목 진단 (오늘/이번주/전망)**:
               - **오늘의 여파**: 미국장 결과가 내 종목들에 미칠 즉각적인 영향.
               - **이번 주 흐름**: 기술적 지표(RSI, MACD 등) 분석을 바탕으로 본 이번 주 예상 변동성.
               - **향후 전망**: 보유 및 매도 여부에 대한 중장기적 관점.
            4. **매크로 지표**: 환율, 금리 등의 변화가 주는 시사점.
            """
        else:
            prompt = f"""
            당신은 실전 투자 전략가입니다. 한국 증시 개장 직전, 투자자가 즉각 참고할 전략 리포트를 작성하세요.

            [최신 시장 데이터]
            {indices_summary}
            
            [나의 보유 종목]
            {portfolio_summary}

            [요청 사항]
            1. **오늘의 장전 관전 포인트**: 개장 직후 가장 주목해야 할 핵심 변수.
            2. **한국 증시 예상 흐름**: 미국장 결과를 반영한 코스피/코스닥 시초가 분위기 예측.
            3. **보유 종목 실전 전략 (필수)**:
               - **한 달간의 흐름 분석**: 제공된 1개월 가격 데이터를 기반으로 폭등/폭락 지점을 찾아내고, 당시의 시장 상황이나 이벤트를 추론하여 설명하세요.
               - **상승/하락 확률 예측**: 기술적 지표(RSI, MACD, 볼린저 밴드 등) 분석 결과를 바탕으로 향후 상승 또는 하락 가능성을 확률(%)로 제시하세요.
               - **예상 매매 타이밍**: 기술적 지표상의 과매수/과매도 구간을 근거로 활용하여, 언제 매도하거나 추가 매수하는 것이 최선일지 구체적인 가격 수치와 함께 전략을 세우세요.
               - **향후 전망**: 중장기적 관점에서의 투자 방향.
            4. **오늘의 주도 섹터**: 수급이 몰릴 것으로 예상되는 섹터 2개와 구체적 이유.
            """

        # 요약과 상세 내용을 나누기 위한 지시사항 추가
        prompt += """
        
        **중요 지시사항**:
        1. 보고서 시작 부분에 **'오늘의 핵심 요약'**을 3줄 이내로 작성하세요. (가장 중요)
        2. 요약 바로 아래에 **[보유 종목 매매 예측 요약 표]**를 작성하세요. 
           텔레그램 가독성을 위해 반드시 <pre> 태그로 표 전체를 감싸고, 내부 컬럼 간격을 공백으로 맞춰 정렬하세요.
           표 구성: | 종목명 | 비중 | 수익률 | 매매예측(매수/매도/관망) | 목표가 |
        3. 표가 끝난 후 반드시 `[SPLIT]` 이라는 단어만 포함된 줄을 삽입하세요.
        4. 상세 분석 내용은 반드시 다음의 소제목을 사용하고, 섹터별로 나누어 가독성을 극대화하세요:
           - ▣ 오늘의 시장 동향 및 대응
           - ▣ 보유 종목 수익률 분석 및 주간 전망
           - ▣ 향후 투자 관점 및 목표
        5. 전문적이면서도 투자자가 행동에 옮길 수 있도록 구체적인 한국어로 작성해주세요.
        """

        # 시도할 모델 순서 (최신 모델 -> 안정화 모델)
        models_to_try = ['gemini-2.0-flash', 'gemini-2.5-flash', 'gemini-3.0-flash', 'gemini-3.5-flash']
        
        for model_name in models_to_try:
            try:
                response = self.client.models.generate_content(model=model_name, contents=prompt)
                return response.text
            except Exception as e:
                error_msg = str(e)
                if "429" in error_msg:
                    print(f"⚠️ {model_name} 할당량 초과. 다음 모델로 즉시 전환합니다.")
                else:
                    print(f"❌ {model_name} 호출 중 오류 발생: {error_msg}")
                continue

        return f"AI 분석 중 오류가 발생했습니다 ({report_type}): 모든 가용 모델의 할당량이 초과되었습니다."

    def extract_portfolio_from_image(self, image_path):
        """증권사 잔고 스크린샷에서 종목명, 평단가, 보유금액 추출"""
        try:
            img = PIL.Image.open(image_path)
            prompt = """
            당신은 한국 증권사(MTS) 잔고 스크린샷 분석 전문가입니다. 이미지에서 주식 및 ETF 잔고 정보를 추출하여 JSON 배열로 응답하세요.

            [레이아웃 분석 팁]
            - 한국 MTS(CYBOS, 영웅문 등)는 보통 한 종목의 정보를 2줄(상/하)로 배치합니다.
            - 상단 행: 종목명, 평가손익, 잔고수량, 매입단가(평단)
            - 하단 행: 구분(현금/신용 등), 수익률, 평가금액, 현재가
            - 이 상/하 두 줄을 하나의 '데이터 블록'으로 묶어서 분석하세요.

            [추출 세부 지침]
            1. **name (종목명)**: 상단 행 첫 번째 칸의 이름을 추출하세요. (예: 삼성전자, TIGER 미국우주테크)
            2. **ticker (티커)**: 종목명을 기반으로 검색하거나 이미지 내 숫자를 참고하여 정확한 티커를 매핑하세요.
               - 한국 종목은 6자리 숫자 뒤에 `.KS`(코스피) 또는 `.KQ`(코스닥)를 반드시 붙이세요. 
               - ETF는 주로 코스피(.KS)에 상장되어 있습니다.
            3. **avg_price (평균단가)**: 상단 행 가장 우측의 '매입가' 또는 '평균단가' 수치를 가져오세요.
            4. **deposit (매입금액)**: 이미지에 '매입금액'이 명시되어 있지 않다면, (매입단가 * 잔고수량)을 계산하여 산출하세요.
            
            [데이터 정제 규칙]
            - 숫자에 포함된 모든 기호(쉼표 ',', 통화 '원', '₩', 백분율 '%')를 제거하고 순수 숫자(정수 또는 실수)만 반환하세요.
            - '현금', '예수금', '합계'와 같은 비주식 항목은 제외하세요.
            - 텍스트가 흐릿할 경우 주변 수치(수익률과 손익의 관계)를 고려하여 합리적으로 추론하세요.
            
            [출력 형식]
            반드시 아래 구조의 JSON 배열만 응답하세요. 다른 설명은 생략합니다.
            [
                {"name": "종목명", "ticker": "티커.KS", "avg_price": 0, "deposit": 0}
            ]
            """
            response = self.client.models.generate_content(model='gemini-2.0-flash', contents=[prompt, img])
            return response.text
        except Exception as e:
            return f"이미지 분석 실패: {e}"