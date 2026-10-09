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

TELEGRAM_TOKEN = "8564085814:AAFr9XBwDA80jteJyxKKCBnAU9r5S55SMY4"
TWELVE_DATA_API_KEY = "625159396fa746229e049c853ee698bf"
API_URL = "https://api.twelvedata.com/time_series"

ALLOWED_USERS = [6493871389]
MIN_SIGNAL_SCORE = 75

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

def get_market_data(symbol: str):
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

    if "values" not in data:
        raise Exception("لم تصل بيانات السوق.")

    df = pd.DataFrame(data["values"])
    for col in ["open", "high", "low", "close"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    df["datetime"] = pd.to_datetime(df["datetime"])
    df = df.sort_values("datetime").reset_index(drop=True)
    df = df.dropna(subset=["open", "high", "low", "close"])
    return df

def calculate_indicators(df):
    df["EMA9"] = df["close"].ewm(span=9, adjust=False).mean()
    df["EMA21"] = df["close"].ewm(span=21, adjust=False).mean()
    df["EMA50"] = df["close"].ewm(span=50, adjust=False).mean()

    delta = df["close"].diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(alpha=1/14, min_periods=14, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1/14, min_periods=14, adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    df["RSI"] = 100 - (100 / (1 + rs))

    ema12 = df["close"].ewm(span=12, adjust=False).mean()
    ema26 = df["close"].ewm(span=26, adjust=False).mean()
    df["MACD"] = ema12 - ema26
    df["MACD_SIGNAL"] = df["MACD"].ewm(span=9, adjust=False).mean()

    previous_close = df["close"].shift(1)
    tr1 = df["high"] - df["low"]
    tr2 = abs(df["high"] - previous_close)
    tr3 = abs(df["low"] - previous_close)
    df["ATR"] = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1).rolling(14).mean()

    df["SUPPORT"] = df["low"].rolling(30).min()
    df["RESISTANCE"] = df["high"].rolling(30).max()
    return df

def analyze_market(df):
    latest = df.iloc[-1]
    previous = df.iloc[-2]

    score_buy = 0
    score_sell = 0
    reasons_buy = []
    reasons_sell = []

    if latest["EMA9"] > latest["EMA21"] and latest["EMA21"] > latest["EMA50"]:
        score_buy += 25
        reasons_buy.append("ترتيب المتوسطات EMA صاعد")
    elif latest["EMA9"] < latest["EMA21"] and latest["EMA21"] < latest["EMA50"]:
        score_sell += 25
        reasons_sell.append("ترتيب المتوسطات EMA هابط")

    rsi = latest["RSI"]
    if 52 <= rsi <= 68:
        score_buy += 15
        reasons_buy.append(f"RSI داعم للصعود ({rsi:.1f})")
    elif 32 <= rsi <= 48:
        score_sell += 15
        reasons_sell.append(f"RSI داعم للهبوط ({rsi:.1f})")

    if latest["MACD"] > latest["MACD_SIGNAL"] and latest["MACD"] > previous["MACD"]:
        score_buy += 20
        reasons_buy.append("زخم MACD صاعد")
    elif latest["MACD"] < latest["MACD_SIGNAL"] and latest["MACD"] < previous["MACD"]:
        score_sell += 20
        reasons_sell.append("زخم MACD هابط")

    if latest["close"] > latest["EMA21"]:
        score_buy += 15
        reasons_buy.append("السعر فوق EMA21")
    elif latest["close"] < latest["EMA21"]:
        score_sell += 15
        reasons_sell.append("السعر تحت EMA21")

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
    user_id = update.effective_user.id
    if user_id not in ALLOWED_USERS:
        await update.message.reply_text(f"⚠️ غير مصرح لك.\nمعرفك: `{user_id}`")
        return
    await update.message.reply_text(
        "🔥 أهلاً بك في 4B AI TRADER PRO\n\n"
        "أرسل اسم الزوج الآن للحصول على التحليل وإشارات البيع والشراء:\n"
        "EUR/USD أو GBP/USD"
    )

async def analyze_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message:
        return
    user_id = update.effective_user.id
    if user_id not in ALLOWED_USERS:
        await update.message.reply_text(f"⚠️ غير مصرح لك.\nمعرفك: `{user_id}`")
        return

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
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, analyze_command))
    print("PRO TRADER STARTED")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
