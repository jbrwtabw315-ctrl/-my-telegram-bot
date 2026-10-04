# ============================================================
# 4B AI TRADER PRO
# Advanced Market Analysis Engine + Telegram Bot
# ============================================================

import os
import math
import logging
import requests
import pandas as pd
import numpy as np

from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes
)

# ============================================================
# CONFIG
# ============================================================

TOKEN="8564085814:AAHQF6mBUz5Ju6AGbpyC-5eF5AGe_lBP3QY"
# مصدر البيانات
DATA_URL = "https://api.binance.com/api/v3/klines"

DEFAULT_INTERVAL = "5m"
CANDLE_LIMIT = 250

# ============================================================
# LOGGING
# ============================================================

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)

logger = logging.getLogger("4B_AI_TRADER")


# ============================================================
# GET MARKET DATA
# ============================================================

def get_market_data(pair, interval=DEFAULT_INTERVAL, limit=CANDLE_LIMIT):

    pair = pair.upper()

    params = {
        "symbol": pair,
        "interval": interval,
        "limit": limit
    }

    response = requests.get(
        DATA_URL,
        params=params,
        timeout=10
    )

    response.raise_for_status()

    data = response.json()

    if not isinstance(data, list) or len(data) < 50:
        raise ValueError("بيانات السوق غير كافية.")

    df = pd.DataFrame(data, columns=[
        "time",
        "open",
        "high",
        "low",
        "close",
        "volume",
        "close_time",
        "quote_volume",
        "trades",
        "buy_volume",
        "buy_quote_volume",
        "ignore"
    ])

    numeric_columns = [
        "open",
        "high",
        "low",
        "close",
        "volume"
    ]

    for column in numeric_columns:
        df[column] = pd.to_numeric(
            df[column],
            errors="coerce"
        )

    df.dropna(inplace=True)

    return df


# ============================================================
# EMA
# ============================================================

def calculate_ema(df, period):

    return df["close"].ewm(
        span=period,
        adjust=False
    ).mean()


# ============================================================
# RSI
# ============================================================

def calculate_rsi(df, period=14):

    delta = df["close"].diff()

    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)

    avg_gain = gain.ewm(
        alpha=1 / period,
        adjust=False
    ).mean()

    avg_loss = loss.ewm(
        alpha=1 / period,
        adjust=False
    ).mean()

    rs = avg_gain / avg_loss.replace(0, np.nan)

    rsi = 100 - (100 / (1 + rs))

    return rsi.fillna(50)


# ============================================================
# MACD
# ============================================================

def calculate_macd(df):

    ema12 = df["close"].ewm(
        span=12,
        adjust=False
    ).mean()

    ema26 = df["close"].ewm(
        span=26,
        adjust=False
    ).mean()

    macd = ema12 - ema26

    signal = macd.ewm(
        span=9,
        adjust=False
    ).mean()

    histogram = macd - signal

    return macd, signal, histogram


# ============================================================
# SUPPORT / RESISTANCE
# ============================================================

def calculate_support_resistance(df, lookback=50):

    recent = df.tail(lookback)

    support = recent["low"].min()

    resistance = recent["high"].max()

    return support, resistance


# ============================================================
# MARKET STRUCTURE
# ============================================================

def calculate_market_structure(df):

    recent = df.tail(20)

    highs = recent["high"].values
    lows = recent["low"].values

    higher_highs = highs[-1] > highs[-5]
    higher_lows = lows[-1] > lows[-5]

    lower_highs = highs[-1] < highs[-5]
    lower_lows = lows[-1] < lows[-5]

    if higher_highs and higher_lows:
        return "صاعد"

    if lower_highs and lower_lows:
        return "هابط"

    return "عرضي"


# ============================================================
# ANALYSIS ENGINE
# ============================================================

def market_analysis(pair, interval=DEFAULT_INTERVAL):

    df = get_market_data(
        pair,
        interval,
        CANDLE_LIMIT
    )

    # --------------------------------------------------------
    # Indicators
    # --------------------------------------------------------

    df["EMA9"] = calculate_ema(df, 9)
    df["EMA21"] = calculate_ema(df, 21)
    df["EMA50"] = calculate_ema(df, 50)
    df["EMA200"] = calculate_ema(df, 200)

    df["RSI"] = calculate_rsi(df)

    (
        df["MACD"],
        df["MACD_SIGNAL"],
        df["MACD_HIST"]
    ) = calculate_macd(df)

    # --------------------------------------------------------
    # Current values
    # --------------------------------------------------------

    last = df.iloc[-1]

    price = float(last["close"])

    ema9 = float(last["EMA9"])
    ema21 = float(last["EMA21"])
    ema50 = float(last["EMA50"])
    ema200 = float(last["EMA200"])

    rsi = float(last["RSI"])

    macd = float(last["MACD"])
    macd_signal = float(last["MACD_SIGNAL"])
    macd_hist = float(last["MACD_HIST"])

    # --------------------------------------------------------
    # Support / Resistance
    # --------------------------------------------------------

    support, resistance = calculate_support_resistance(df)

    # --------------------------------------------------------
    # Market structure
    # --------------------------------------------------------

    structure = calculate_market_structure(df)

    # ========================================================
    # SCORE SYSTEM
    # ========================================================

    bullish_score = 0
    bearish_score = 0

    reasons_bullish = []
    reasons_bearish = []

    # --------------------------------------------------------
    # EMA 9 / 21
    # --------------------------------------------------------

    if ema9 > ema21:

        bullish_score += 1

        reasons_bullish.append(
            "EMA 9 أعلى من EMA 21"
        )

    elif ema9 < ema21:

        bearish_score += 1

        reasons_bearish.append(
            "EMA 9 أسفل EMA 21"
        )

    # --------------------------------------------------------
    # EMA 50 / 200
    # --------------------------------------------------------

    if ema50 > ema200:

        bullish_score += 2

        reasons_bullish.append(
            "EMA 50 أعلى من EMA 200"
        )

    elif ema50 < ema200:

        bearish_score += 2

        reasons_bearish.append(
            "EMA 50 أسفل EMA 200"
        )

    # --------------------------------------------------------
    # Price vs EMA 200
    # --------------------------------------------------------

    if price > ema200:

        bullish_score += 2

        reasons_bullish.append(
            "السعر فوق EMA 200"
        )

    elif price < ema200:

        bearish_score += 2

        reasons_bearish.append(
            "السعر تحت EMA 200"
        )

    # --------------------------------------------------------
    # RSI
    # --------------------------------------------------------

    if 50 < rsi < 70:

        bullish_score += 1

        reasons_bullish.append(
            f"RSI إيجابي ({rsi:.1f})"
        )

    elif 30 < rsi < 50:

        bearish_score += 1

        reasons_bearish.append(
            f"RSI سلبي ({rsi:.1f})"
        )

    elif rsi >= 70:

        reasons_bullish.append(
            f"RSI في تشبع شرائي ({rsi:.1f})"
        )

    elif rsi <= 30:

        reasons_bearish.append(
            f"RSI في تشبع بيعي ({rsi:.1f})"
        )

    # --------------------------------------------------------
    # MACD
    # --------------------------------------------------------

    if macd > macd_signal and macd_hist > 0:

        bullish_score += 2

        reasons_bullish.append(
            "MACD يعطي زخمًا صاعدًا"
        )

    elif macd < macd_signal and macd_hist < 0:

        bearish_score += 2

        reasons_bearish.append(
            "MACD يعطي زخمًا هابطًا"
        )

    # --------------------------------------------------------
    # Market Structure
    # --------------------------------------------------------

    if structure == "صاعد":

        bullish_score += 2

        reasons_bullish.append(
            "هيكل السوق صاعد"
        )

    elif structure == "هابط":

        bearish_score += 2

        reasons_bearish.append(
            "هيكل السوق هابط"
        )

    # ========================================================
    # FINAL DECISION
    # ========================================================

    difference = bullish_score - bearish_score

    if difference >= 5:

        direction = "📈 صاعد قوي"
        signal = "🟢 CALL محتمل"
        confidence = min(
            95,
            60 + difference * 5
        )

    elif difference >= 2:

        direction = "📈 صاعد"
        signal = "🟢 CALL بحذر"
        confidence = min(
            85,
            55 + difference * 5
        )

    elif difference <= -5:

        direction = "📉 هابط قوي"
        signal = "🔴 PUT محتمل"
        confidence = min(
            95,
            60 + abs(difference) * 5
        )

    elif difference <= -2:

        direction = "📉 هابط"
        signal = "🔴 PUT بحذر"
        confidence = min(
            85,
            55 + abs(difference) * 5
        )

    else:

        direction = "⚪ عرضي / غير واضح"
        signal = "⏳ NO TRADE"
        confidence = 50

    # ========================================================
    # SUPPORT / RESISTANCE DISTANCE
    # ========================================================

    support_distance = (
        ((price - support) / price) * 100
        if price != 0
        else 0
    )

    resistance_distance = (
        ((resistance - price) / price) * 100
        if price != 0
        else 0
    )

    # ========================================================
    # BUILD REPORT
    # ========================================================

    bullish_text = "\n".join(
        f"• {x}"
        for x in reasons_bullish
    )

    bearish_text = "\n".join(
        f"• {x}"
        for x in reasons_bearish
    )

    report = f"""
🤖 4B AI TRADER PRO
━━━━━━━━━━━━━━━━━━

📊 الزوج: {pair}
⏱ الفريم: {interval}

💰 السعر الحالي:
{price:.8f}

━━━━━━━━━━━━━━━━━━
📈 الاتجاه العام
{direction}

🏗 هيكل السوق:
{structure}

━━━━━━━━━━━━━━━━━━
📐 المتوسطات

EMA 9   : {ema9:.8f}
EMA 21  : {ema21:.8f}
EMA 50  : {ema50:.8f}
EMA 200 : {ema200:.8f}

━━━━━━━━━━━━━━━━━━
📊 RSI

RSI 14 : {rsi:.2f}

━━━━━━━━━━━━━━━━━━
📉 MACD

MACD        : {macd:.8f}
Signal      : {macd_signal:.8f}
Histogram   : {macd_hist:.8f}

━━━━━━━━━━━━━━━━━━
🧱 الدعم والمقاومة

الدعم:
{support:.8f}

المقاومة:
{resistance:.8f}

📍 بُعد السعر عن الدعم:
{support_distance:.2f}%

📍 بُعد السعر عن المقاومة:
{resistance_distance:.2f}%

━━━━━━━━━━━━━━━━━━
🧠 نقاط الصعود

{bullish_text if bullish_text else "• لا توجد عوامل صعود قوية"}

━━━━━━━━━━━━━━━━━━
⚠️ نقاط الهبوط

{bearish_text if bearish_text else "• لا توجد عوامل هبوط قوية"}

━━━━━━━━━━━━━━━━━━
🎯 النتيجة

🟢 قوة الصعود:
{bullish_score}

🔴 قوة الهبوط:
{bearish_score}

📊 الثقة التحليلية:
{confidence:.0f}%

🚦 الإشارة:
{signal}

━━━━━━━━━━━━━━━━━━
⚠️ تنبيه

هذا تحليل آلي مبني على المؤشرات
ولا يمثل ضمانًا للربح.

استخدم إدارة رأس المال
ولا تدخل صفقة اعتمادًا على
إشارة واحدة فقط.

🔥 4B AI TRADER PRO
"""

    return report


# ============================================================
# TELEGRAM / START
# ============================================================

async def start(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    await update.message.reply_text(
        """
🤖 4B AI TRADER PRO

🧠 محرك تحليل السوق جاهز.

الأوامر:

/analyze BTCUSDT
/analyze ETHUSDT

مثال:

/analyze BTCUSDT

سيقوم المحرك بتحليل:

📈 EMA 9 / 21 / 50 / 200
📊 RSI
📉 MACD
🧱 الدعم والمقاومة
🏗 هيكل السوق
🎯 قوة الاتجاه
🚦 السيناريو المحتمل
"""
    )


# ============================================================
# ANALYZE COMMAND
# ============================================================

async def analyze(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    if not context.args:

        await update.message.reply_text(
            """
❌ لم تحدد الزوج.

مثال:

/analyze BTCUSDT
"""
        )

        return

    pair = context.args[0].upper()

    # منع إدخال رموز غريبة
    if not pair.isalnum():

        await update.message.reply_text(
            "❌ رمز الزوج غير صالح."
        )

        return

    await update.message.reply_text(
        f"🧠 جاري تحليل {pair}..."
    )

    try:

        result = market_analysis(pair)

        await update.message.reply_text(
            result
        )

    except requests.exceptions.RequestException:

        await update.message.reply_text(
            """
❌ تعذر الاتصال بمصدر بيانات السوق.

حاول مرة أخرى لاحقًا.
"""
        )

    except Exception as e:

        logger.exception(
            "Analysis error"
        )

        await update.message.reply_text(
            f"""
❌ حدث خطأ أثناء التحليل.

الزوج:
{pair}

الخطأ:
{str(e)}
"""
        )


# ============================================================
# MAIN
# ============================================================

def main():

    if TOKEN == "PUT_YOUR_TELEGRAM_TOKEN_HERE":

        raise ValueError(
            "ضع Telegram Bot Token في متغير TELEGRAM_BOT_TOKEN"
        )

    app = (
        Application
        .builder()
        .token(TOKEN)
        .build()
    )

    app.add_handler(
        CommandHandler(
            "start",
            start
        )
    )

    app.add_handler(
        CommandHandler(
            "analyze",
            analyze
        )
    )

    print(
        "🤖 4B AI TRADER PRO Running..."
    )

    app.run_polling()


# ============================================================
# RUN
# ============================================================
print("🔥 بدأ تشغيل 4B AI TRADER PRO")

if __name__ == "__main__":
    main()
