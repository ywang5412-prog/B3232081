import os
import logging

import requests
from flask import Flask, render_template, request


app = Flask(__name__)

TWSE_STOCK_DAY_URL = "https://www.twse.com.tw/rwd/zh/afterTrading/STOCK_DAY"
TWSE_HEADERS = {
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "zh-TW,zh;q=0.9,en;q=0.8",
    "Referer": "https://www.twse.com.tw/zh/trading/historical/stock-day.html",
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
}


def parse_price(value):
    try:
        return float(value.replace(",", ""))
    except (AttributeError, ValueError):
        return None


def fetch_stock_rows(stock_no):
    session = requests.Session()
    session.headers.update(TWSE_HEADERS)

    response = session.get(
        TWSE_STOCK_DAY_URL,
        params={"response": "json", "stockNo": stock_no},
        timeout=10,
    )
    response.raise_for_status()
    data = response.json()

    if data.get("stat") != "OK" or not data.get("data"):
        return None

    return data["data"]


def build_stock_answer(stock_no):
    rows = fetch_stock_rows(stock_no)
    if not rows:
        return None

    closing_prices = []
    for row in rows:
        close_price = parse_price(row[6])
        if close_price is not None:
            closing_prices.append(close_price)

    if not closing_prices:
        return None

    daily_prices = []
    for row in rows[-10:]:
        daily_prices.append(
            {
                "date": row[0],
                "open": row[3],
                "close": row[6],
            }
        )

    return {
        "stock_no": stock_no,
        "highest_close": max(closing_prices),
        "lowest_close": min(closing_prices),
        "daily_prices": daily_prices,
    }


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/stock", methods=["GET", "POST"])
def stock():
    answer = None
    warning = None
    stock_no = ""

    if request.method == "POST":
        stock_no = request.form.get("stock_no", "").strip()

        if not stock_no.isdigit():
            warning = "股票代號格式錯誤，請輸入數字，例如 2330。"
        else:
            try:
                answer = build_stock_answer(stock_no)
            except requests.RequestException:
                logging.exception("TWSE request failed for stock_no=%s", stock_no)
                warning = "查詢失敗，請稍後再試。"
            except ValueError:
                logging.exception("TWSE response was not valid JSON for stock_no=%s", stock_no)
                warning = "查詢失敗，請稍後再試。"

            if answer is None and warning is None:
                warning = "查無資料，請確認股票代號是否正確。"

    return render_template(
        "stock.html",
        answer=answer,
        warning=warning,
        stock_no=stock_no,
    )


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)
