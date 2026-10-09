import os
import logging
import requests
import pandas as pd
import numpy as np
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

TELEGRAM_TOKEN = "625159396fa746229e049c853ee698bf"
TWELVE_DATA_API_KEY = "625159396fa746229e049c853ee698bf"
API_URL = "https://api.twelvedata.com/time_series"

ADMIN_ID = 6493871389 
ALLOWED_USERS = [6493871389]
MIN_SIGNAL_SCORE = 75

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

def get_market_data(symbol: str) -> pd.DataFrame:
    params = {
        "symbol": symbol,
        "interval": "1min",
        "outputsize": 150,
        "apikey": TWELVE_DATA_API_KEY,
        "format": "JSON"
    }
    response = requests.get(API_URL, params=params, timeout=15)
    response.raise_for_status()
    data = response.json()

    if data.get("status") == "error":
        raise Exception(data.get("message", "API Error"))
        
    values = data.get("values", [])
    if not values:
        raise Exception("لم يتم استرجاع بيانات من السوق.")
        
    df = pd.DataFrame(values)
    df = df.iloc[::-1].reset_index(drop=True)
    
    for col in ["open", "high", "low", "close"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")
        
    return df

def calculate_indicators(df: pd.DataFrame) -> pd.DataFrame:
    df["EMA9"] = df["close"].ewm(span=9, adjust=False).mean()
    df["EMA21"] = df["close"].ewm(span=21, adjust=False).mean()
    df["EMA50"] = df["close"].ewm(span=50, adjust=False).mean()

    delta = df["close"].diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    
    avg_gain = gain.ewm(alpha=1/14, min_periods=14).mean()
    avg_loss = loss.ewm(alpha=1/14, min_periods=14).mean()
    
    rs = avg_gain / avg_loss
    df["RSI"] = 100 - (100 / (1 + rs))
    return df

def analyze_market(df: pd.DataFrame) -> dict:
    latest = df.iloc[-1]
    prev = df.iloc[-2]
    
    rsi = latest["RSI"]
    score_buy = 50
    score_sell = 50
    reasons_buy = []
    reasons_sell = []

    if latest["EMA9"] > latest["EMA21"]:
        score_buy += 15
        reasons_buy.append("متوسط EMA9 أعلى من EMA21 (إيجابي)")
    else:
        score_sell += 15
        reasons_sell.append("متوسط EMA9 أقل من EMA21 (سلبي)")
        
    if rsi < 35:
        score_buy += 25
        reasons_buy.append(f"مؤشر القوة النسبية RSI منخفض ({rsi:.2f}) - تشبع بيعي")
    elif rsi > 65:
        score_sell += 25
        reasons_sell.append(f"مؤشر القوة النسبية RSI مرتفع ({rsi:.2f}) - تشبع شرائي")

    if latest["close"] > prev["close"]:
        score_buy += 10
        reasons_buy.append("السعر الحالي مرتفع عن الشمعة السابقة")
    else:
        score_sell += 10
        reasons_sell.append("السعر الحالي منخفض عن الشمعة السابقة")

    if score_buy >= MIN_SIGNAL_SCORE and score_buy > score_sell:
        return {
            "signal": "BUY",
            "score": score_buy,
            "price": latest["close"],
            "rsi": rsi,
            "reasons": reasons_buy
        }

    if score_sell >= MIN_SIGNAL_SCORE and score_sell > score_buy:
        return {
            "signal": "SELL",
            "score": score_sell,
            "price": latest["close"],
            "rsi": rsi,
            "reasons": reasons_sell
        }

    return {
        "signal": "NO_TRADE",
        "score": max(score_buy, score_sell),
        "price": latest["close"],
        "rsi": rsi
    }

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🔥 أهلاً بك يا مالك البوت في 4B AI TRADER PRO\n\n"
        "أرسل اسم الزوج الآن للحصول على التحليل وإشارات البيع والشراء:\n"
        "EUR/USD أو GBP/USD"
    )

async def handle_user_messages(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message:
        return
    await analyze_command(update, context)

async def analyze_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    symbol = update.message.text.strip().upper().replace("-", "/").replace(" ", "")
    if "/" not in symbol:
        await update.message.reply_text("❌ صيغة خاطئة. اكتب الزوج هكذا: EUR/USD")
        return

    await update.message.reply_text(f"🔎 جاري فحص وتحليل {symbol} على فريم 1M...")

    try:
        df = get_market_data(symbol)
        if len(df) < 60:
            raise Exception("البيانات غير كافية للتحليل.")
        
        df = calculate_indicators(df)
        result = analyze_market(df)

        if result["signal"] == "NO_TRADE":
            msg = (
                "⚪ 4B AI TRADER PRO\n"
                "━━━━━━━━━━━━━━━━━━\n"
                f"💱 الزوج: {symbol}\n"
                f"💰 السعر: {result['price']:.5f}\n"
                f"📈 RSI: {result['rsi']:.2f}\n\n"
                "🚫 لا توجد صفقة حالياً\n"
                "الشروط غير كافية، انتظر فرصة أوضح."
            )
        else:
            direction = "🟢 شراء (CALL)" if result["signal"] == "BUY" else "🔴 بيع (PUT)"
            reasons_txt = "\n".join(f"• {r}" for r in result["reasons"])
            msg = (
                "🔥 4B AI TRADER PRO\n"
                "━━━━━━━━━━━━━━━━━━\n"
                f"💱 الزوج: {symbol}\n"
                f"📌 الإشارة: {direction}\n"
                f"⏳ مدة الصفقة: 1 دقيقة\n\n"
                f"📊 قوة الإشارة: {result['score']}%\n"
                f"💰 السعر: {result['price']:.5f}\n"
                f"📈 RSI: {result['rsi']:.2f}\n\n"
                "🧠 الأسباب:\n"
                f"{reasons_txt}\n"
                "━━━━━━━━━━━━━━━━━━"
            )
        await update.message.reply_text(msg)
    except Exception as e:
        logger.exception("Analysis error")
        await update.message.reply_text(f"❌ حدث خطأ أثناء التحليل: {e}")

def main():
    app = Application.builder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_user_messages))
    print("PRO TRADER STARTED")
    app.run_polling()

if __name__ == "__main__":
    main()
