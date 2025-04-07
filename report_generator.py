import json
import yfinance as yf
import openai
import smtplib, ssl
import requests
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from datetime import datetime
import os

# 환경 변수 불러오기
openai.api_key = os.getenv("OPENAI_API_KEY")
TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
EMAIL_USER = os.getenv("EMAIL_USER")
EMAIL_PASS = os.getenv("EMAIL_PASS")
EMAIL_RECEIVER = os.getenv("EMAIL_RECEIVER")

# 1. 포트폴리오 로드
with open("portfolio.json", "r") as f:
    portfolio = json.load(f)

# 2. 주가 데이터 수집
print("\U0001F4E5 주가 데이터 수집 중...")
tickers = list(portfolio.keys())
data = yf.download(tickers, period="2d", interval="1d")["Close"]
yesterday = data.iloc[-2]
today = data.iloc[-1]

stock_table_rows = []
total_value = 0
stock_summary_lines = []

for ticker in tickers:
    avg_price = portfolio[ticker]["avg_price"]
    shares = portfolio[ticker]["shares"]
    curr = today[ticker]
    value = curr * shares
    total_value += value
    pnl_pct = ((curr - avg_price) / avg_price) * 100
    pnl_color = "red" if pnl_pct >= 0 else "blue"
    stock_table_rows.append(
        f"<tr><td>{ticker}</td><td>${avg_price:.2f}</td><td>${curr:.2f}</td><td>{shares}</td><td>${value:,.2f}</td><td class=\"{pnl_color}\">{pnl_pct:+.1f}%</td></tr>"
    )
    stock_summary_lines.append(f"{ticker}: 현재가 ${curr:.2f}, 평균단가 ${avg_price:.2f}, 수익률 {pnl_pct:.2f}%")

stock_table = """
<table>
  <thead><tr><th>Ticker</th><th>평균단가</th><th>현재가</th><th>수량</th><th>평가금액</th><th>수익률</th></tr></thead>
  <tbody>
""" + "\n".join(stock_table_rows) + "\n  </tbody></table>"

stock_summary = "\n".join(stock_summary_lines)

# GPT 프롬프트 구성
prompt = """
✅ 리포트 자동 생성 GPT 프롬프트 (최종 버전)

역할 (Role):  
당신은 미국 주식 시장 전문가이자 금융 리서치 애널리스트입니다. 사용자가 보유한 포트폴리오와 시장 데이터를 실시간으로 분석해 매일 아침 고퀄리티 HTML 리포트를 자동으로 생성하는 역할을 맡습니다.

문맥 및 상황 (Context):  
사용자는 미국 주식 기반 포트폴리오를 운용 중이며, 매일 아침 8시에 전일 시장 요약, 경제 지표, 투자 심리, 개별 종목 분석 및 전략 코멘트를 포함한 리포트를 Gmail과 텔레그램을 통해 수신합니다.  
HTML 리포트는 통일된 시각 디자인과 분석 템플릿을 유지해야 하며, 전일 종가 및 실시간 시장 지표를 기반으로 작성됩니다.

지시사항 (Instructions):  
아래 조건을 반드시 준수하여 매일 HTML 리포트를 생성하세요:

1. 리포트 제목 및 날짜  
   - <h1>📅 [오늘 날짜] 주식 포트폴리오 분석 리포트</h1> 형식으로 자동 생성  
   - 날짜는 대한민국 기준 날짜로 실시간 반영 (KST)

2. 실시간 데이터 반영 필수  
   - 주요 지수 (S&P500, 나스닥, 다우, KOSPI, KOSDAQ 등)  
   - VIX, 10Y 국채금리, DXY, Fear & Greed Index  
   - 전일 종가, 등락률, 시가/종가/고저 등  
   - 반드시 웹 검색을 통해 당일 기준 최신 수치 수집

3. 분석 및 전략 제안  
   - 수집된 지표를 기반으로 시장 해석 및 포트폴리오 전략 제시  
   - 단기/중기적 리밸런싱, 리스크관리 전략 포함  
   - 사용자 종목 특성(JEPI, JEPQ, SCHD, QQQM, O, NVDA, TSLA, CONY)에 맞게 차별화된 코멘트 제공

4. 시각 구성 요소  
   - HTML 형식 유지 (섹션별 카드, 하이라이트, 테이블, 이모지 등)  
   - 시각 자료 예시(비중 차트, 수익률 표 등)는 placeholder 이미지로 대체 가능

내용 구성 (섹션 4그룹) — 리버스엔지니어링 기반 고도화 버전

📊 그룹 1: 포트폴리오 요약 및 수익률 분석
- 총 평가금액 카드
- 보유 종목 테이블: 수익률 색상 강조
- 보유 비중 차트 / 보유량 기준 차트 (placeholder 이미지 사용)

📈 그룹 2: 시장 요약 및 이벤트 분석
- 전일 주요 지수 비교표 (KOSPI, KOSDAQ, S&P500, NASDAQ 등)
- 시장 변동 요인 카드 (뉴스/경제지표 분석 포함)
- 요약 하이라이트 카드 (한 문단 핵심 요약)

🧭 그룹 3: 시장 심리 및 전략 지표 분석
- 핵심 지표 테이블: Fear & Greed, VIX, 금리, 환율 등
- 지표 해석 + 전략 제안 하이라이트
- 오늘의 전략 코멘트 카드 (한 문장 요약 포함)

📦 그룹 4: 보유 종목별 상세 분석
- 종목 개요 / 가격 및 수익률 요약 / 시장 해석 / 전략 제안
- 종목별 details 구조 (접기/펼치기 HTML)
- 전략 제안은 리스트 형식으로 명확하게 작성

톤 (Tone):  
- 전문가답고 신뢰감 있는 어조  
- 데이터 기반 논리적인 분석  
- 이해하기 쉬운 요약 및 전략 제안 포함  
- 일부 섹션은 요약 코멘트 형식으로 캐주얼하게 마무리해도 좋음

윤리적 경계 (Boundaries):  
- 특정 종목 매수/매도 추천은 명시적으로 하지 않음  
- 중립적이고 분석 중심의 표현 유지  
- 리스크는 명확히 경고

출력 형식 (Output Format):  
- HTML 형식 전체 출력  
- 완전한 문서 구조 포함 (<!DOCTYPE html> 포함)  
- CSS는 위 예시 파일 스타일과 동일하게 유지  
- 차트 및 테이블은 실제 이미지가 아닌 https://via.placeholder.com/... 형식의 가상 이미지 URL로 대체 가능

실시간 웹 검색 자료 사용  
- 모든 지수, 종목 가격, 경제 지표, 심리지표 등은 반드시 실시간 웹 검색을 통해 수집  
- 출처는 각 지표 아래 <strong>출처:</strong> 문구로 명시  
- 예: CNN, Bloomberg, CNBC, MarketWatch 등
"""


prompt = f"""
“지금부터 너는 너는 미국 주식 애널리스트이며, 정해진 템플릿 양식대로만 HTML을 출력하는 프로그램이야”
다음은 사용자의 포트폴리오 종목별 정보야:

{stock_summary}

아래 항목을 반드시 각각 [key]와 [/key] 태그 안에 HTML 형식으로 작성해줘. 각 항목은 다음과 같아:

[market_index_table]
S&P500, NASDAQ, 다우존스, 코스피, 코스닥, USD/KRW 등 주요 지수 요약 테이블 (전일 등락률, 시가/종가, 52주 고저 포함)
[/market_index_table]

[market_analysis]
시장 변동 요인 (뉴스 5개 이상 기반, 금리, 전쟁, 경제지표 등) — 5줄 이상 분석 + 출처 포함
[/market_analysis]

[strategy_table]
VIX, Fear & Greed Index, 10Y 금리, 달러인덱스 DXY 등 핵심 지표 요약 테이블 + 수치 + 출처 링크
[/strategy_table]

[indicator_insight]
각 지표에 대한 상세 해석 및 내 포트폴리오 전략 관점에서의 의미 (배당주/성장주/방어주 등 중심으로)
[/indicator_insight]

[today_strategy_comment]
오늘의 리스크/기회 요약 전략 코멘트 (1줄)
[/today_strategy_comment]

[stock_analysis_sections]
JEPI, JEPQ, SCHD, QQQM, O, NVDA, TSLA, CONY 종목에 대한 상세 분석. 각 항목은 <details>로 토글 구성. 시장 해석은 5개 이상 기사 교차 검증된 분석으로 작성.
[/stock_analysis_sections]
"""

print("[DEBUG] GPT에 보낼 프롬프트:\n", prompt)

# GPT 요청
response = openai.ChatCompletion.create(
    model="gpt-4o",
    messages=[{"role": "user", "content": prompt}]
)

print("[DEBUG] GPT 응답 전체:\n", response)

try:
    gpt_content = response.choices[0].message.content
    print("[DEBUG] GPT 응답 본문:\n", gpt_content)
except Exception as e:
    print("[ERROR] GPT 응답 파싱 실패:", str(e))
    gpt_content = "<p>⚠️ GPT 응답 오류 - 리포트를 생성하지 못했습니다.</p>"

# 4. 템플릿 로드 및 채우기
with open("report_template.html", "r", encoding="utf-8") as f:
    template = f.read()

report_html = template.replace("{{ report_date }}", datetime.today().strftime("%Y.%m.%d"))
report_html = report_html.replace("{{ total_value }}", f"${total_value:,.2f}")
report_html = report_html.replace("{{ stock_table }}", stock_table)

for key in ["market_index_table", "market_analysis", "strategy_table", "indicator_insight", "today_strategy_comment", "stock_analysis_sections"]:
    placeholder = f"{{{{ {key} }}}}"
    extracted = gpt_content.split(f"[{key}]")[1].split(f"[/{key}]")[0].strip() if f"[{key}]" in gpt_content else "(데이터 없음)"
    report_html = report_html.replace(placeholder, extracted)

# 5. 이메일 발송
msg = MIMEMultipart("alternative")
msg["Subject"] = "\U0001F4C8 오늘의 GPT 주식 리포트"
msg["From"] = EMAIL_USER
msg["To"] = EMAIL_RECEIVER
part = MIMEText(report_html, "html")
msg.attach(part)

context = ssl.create_default_context()
with smtplib.SMTP_SSL("smtp.gmail.com", 465, context=context) as server:
    server.login(EMAIL_USER, EMAIL_PASS)
    server.sendmail(EMAIL_USER, EMAIL_RECEIVER, msg.as_string())

# 6. 텔레그램 전송
requests.post(
    f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
    data={"chat_id": TELEGRAM_CHAT_ID, "text": "\U0001F4EC GPT 주식 리포트가 발송되었습니다! ✉️"}
)

print("✅ 리포트 전송 완료")
