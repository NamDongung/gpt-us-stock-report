# report_generator_refactor.py

import json
import yfinance as yf
import openai
import smtplib, ssl
import requests
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import os
from datetime import datetime

# ✅ 환경 변수 불러오기
openai.api_key = os.getenv("OPENAI_API_KEY")
TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
EMAIL_USER = os.getenv("EMAIL_USER")
EMAIL_PASS = os.getenv("EMAIL_PASS")
EMAIL_RECEIVER = os.getenv("EMAIL_RECEIVER")

# ✅ 날짜 설정
TODAY = datetime.today().strftime('%Y.%m.%d')

# ✅ 포트폴리오 불러오기
with open("portfolio.json", "r") as f:
    portfolio = json.load(f)

# ✅ 주가 데이터 수집
print("[INFO] 주가 데이터 수집 시작")
tickers = list(portfolio.keys())
data = yf.download(tickers, period="2d", interval="1d")["Close"]
yesterday, today = data.iloc[-2], data.iloc[-1]

report_table_rows = []
summary_lines = []
total_value = 0

for ticker in tickers:
    info = portfolio[ticker]
    shares = info["shares"]
    avg_price = info["avg_price"]
    name = info["name"]
    prev = yesterday[ticker]
    curr = today[ticker]
    rate = (curr - avg_price) / avg_price * 100
    diff = curr - prev
    value = curr * shares
    profit = (curr - avg_price) * shares
    total_value += value

    rate_style = "red" if rate >= 0 else "blue"
    summary_lines.append(f"{ticker}: {curr:.2f} USD ({diff:+.2f}), 수익률 {rate:.1f}%, 평가손익: ${profit:,.2f}")

    report_table_rows.append(f"<tr><td>{ticker}</td><td>{name}</td><td>${avg_price:.2f}</td><td>${curr:.2f}</td><td>{shares}</td><td>${value:,.2f}</td><td class=\"{rate_style}\">{rate:+.1f}%</td></tr>")

stock_table_html = "\n".join(report_table_rows)
stock_summary = "\n".join(summary_lines)

# ✅ GPT 그룹 2~4 요청
print("[INFO] GPT 분석 요청 시작")

prompt = f"""
너는 미국 주식 애널리스트야. 아래는 개인 포트폴리오와 주가 변화 요약이야:

{stock_summary}

다음 3개의 분석을 HTML 형식으로 각각 <section class=\"group2\">, <section class=\"group3\">, <section class=\"group4\"> 안에 작성해줘:
1. 그룹2: 전일 시장 요약 + 이슈 (미국 지수/금리/환율/정책 등)
2. 그룹3: 심리 및 전략 지표 분석 (Fear & Greed, VIX, 금리 등)
3. 그룹4: 각 종목별 상세 분석 (종목명, 수익률, 시장 동향, 전략 제안)

HTML 태그 구조와 계층도 함께 제공해줘. 한글로 작성해.
"""

response = openai.ChatCompletion.create(
    model="gpt-3.5-turbo",
    messages=[{"role": "user", "content": prompt}]
)

gpt_html = response.choices[0].message.content

# ✅ HTML 템플릿 합치기
html_report = f"""
<!DOCTYPE html>
<html><head><meta charset='utf-8'><title>{TODAY} 리포트</title></head>
<body>
<h1>📅 {TODAY} 주식 포트폴리오 리포트</h1>
<section class='group1'>
  <h2>📊 자산 요약 및 수익률</h2>
  <p><strong>총 평가금액:</strong> ${total_value:,.2f}</p>
  <table border='1' cellspacing='0' cellpadding='8'>
    <thead><tr><th>Ticker</th><th>종목명</th><th>평균단가</th><th>현재가</th><th>수량</th><th>평가금액</th><th>수익률</th></tr></thead>
    <tbody>{stock_table_html}</tbody>
  </table>
</section>

{gpt_html}

</body></html>
"""

# ✅ 이메일 전송
print("[INFO] 이메일 전송 시작")
msg = MIMEMultipart("alternative")
msg["Subject"] = f"{TODAY} 📈 GPT 미국 주식 분석 리포트"
msg["From"] = EMAIL_USER
msg["To"] = EMAIL_RECEIVER
part = MIMEText(html_report, "html")
msg.attach(part)

context = ssl.create_default_context()
with smtplib.SMTP_SSL("smtp.gmail.com", 465, context=context) as server:
    server.login(EMAIL_USER, EMAIL_PASS)
    server.sendmail(EMAIL_USER, EMAIL_RECEIVER, msg.as_string())

# ✅ 텔레그램 알림
print("[INFO] 텔레그램 알림 전송")
requests.post(
    f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
    data={"chat_id": TELEGRAM_CHAT_ID, "text": f"📬 {TODAY} GPT 리포트 전송 완료! 이메일을 확인하세요 ✉️"}
)

print("✅ 리포트 생성 및 전송 완료")
