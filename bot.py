# ============================================================
# 4B AI TRADER PRO
# FOREX 1M - MANUAL SIGNAL EDITION (WITH SUBSCRIPTION SYSTEM)
# ============================================================

import os
import logging
import requests
import pandas as pd
import numpy as np

from datetime import datetime, timezone

from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

# ============================================================
# CONFIG & SUBSCRIPTION LIST
# ============================================================

TELEGRAM_TOKEN = "8564085814:AAFr9XBwDA80jteJyxKKCBnAU9r5S55SMY4"
TWELVE_DATA_API_KEY = "625159396fa746229e049c853ee698bf"

API_URL = "https://api.twelvedata.com/time_series"

INTERVAL = "1min"
OUTPUT_SIZE = 150

# أقل درجة مطلوبة لإظهار الصفقة
MIN_SIGNAL_SCORE = 75

# قائمة المشتركين المسموح لهم (تم تضمين الآيدي الخاص بك 649387138)
ALLOWED_USERS = [649387138]

def check_subscription(user_id: int) -> bool:
    """التحقق مما إذا كان المستخدم مشتركاً ومصرحاً له بالاستخدام"""
    return user_id in ALLOWED_USERS

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)

logger = logging.getLogger(__name__)


# ============================================================
# GET FOREX DATA
# ============================================================

def get_market_data(symbol: str):

    params = {
        "symbol": symbol,
        "interval": INTERVAL,
        "outputsize": OUTPUT_SIZE,
        "apikey": TWELVE_DATA_API_KEY,
        "format": "JSON"
    }

    response = requests.get(
        API_URL,
        params=params,
        timeout=15
    )

    response.raise_for_status()

    data = response.json()

    if data.get("status") == "error":
        raise Exception(data.get("message", "API Error"))

    if "values" not in data:
        raise Exception("لم تصل بيانات السوق.")

    df = pd.DataFrame(data["values"])

    required = ["open", "high", "low", "close"]

    for column in required:
        df[column] = pd.to_numeric(
            df[column],
            errors="coerce"
        )

    df["datetime"] = pd.to_datetime(df["datetime"])

    df = df.sort_values("datetime")
    df = df.reset_index(drop=True)

    df = df.dropna(
        subset=["open", "high", "low", "close"]
    )

    return df


# ============================================================
# TECHNICAL INDICATORS
# ============================================================

def calculate_indicators(df):

    # -------------------------
    # EMA
    # -------------------------

    df["EMA9"] = df["close"].ewm(
        span=9,
        adjust=False
    ).mean()

    df["EMA21"] = df["close"].ewm(
        span=21,
        adjust=False
    ).mean()

    df["EMA50"] = df["close"].ewm(
        span=50,
        adjust=False
    ).mean()

    # -------------------------
    # RSI 14
    # -------------------------

    delta = df["close"].diff()

    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)

    avg_gain = gain.ewm(
        alpha=1 / 14,
        min_periods=14,
        adjust=False
    ).mean()

    avg_loss = loss.ewm(
        alpha=1 / 14,
        min_periods=14,
        adjust=False
    ).mean()

    rs = avg_gain / avg_loss.replace(0, np.nan)

    df["RSI"] = 100 - (
        100 / (1 + rs)
    )

    # -------------------------
    # MACD
    # -------------------------

    ema12 = df["close"].ewm(
        span=12,
        adjust=False
    ).mean()

    ema26 = df["close"].ewm(
        span=26,
        adjust=False
    ).mean()

    df["MACD"] = ema12 - ema26

    df["MACD_SIGNAL"] = df["MACD"].ewm(
        span=9,
        adjust=False
    ).mean()

    # -------------------------
    # ATR
    # -------------------------

    previous_close = df["close"].shift(1)

    tr1 = df["high"] - df["low"]
    tr2 = abs(df["high"] - previous_close)
    tr3 = abs(df["low"] - previous_close)

    true_range = pd.concat(
        [tr1, tr2, tr3],
        axis=1
    ).max(axis=1)

    df["ATR"] = true_range.rolling(14).mean()

    # -------------------------
    # Support / Resistance
    # -------------------------

    df["SUPPORT"] = (
        df["low"]
        .rolling(30)
        .min()
    )

    df["RESISTANCE"] = (
        df["high"]
        .rolling(30)
        .max()
    )

    return df


# ============================================================
# CANDLE ANALYSIS
# ============================================================

def candle_analysis(row):

    candle_range = row["high"] - row["low"]

    if candle_range <= 0:
        return "NEUTRAL"

    body = abs(
        row["close"] - row["open"]
    )

    body_ratio = body / candle_range

    # شمعة صاعدة قوية
    if (
        row["close"] > row["open"]
        and body_ratio >= 0.55
    ):
        return "BULLISH"

    # شمعة هابطة قوية
    if (
        row["close"] < row["open"]
        and body_ratio >= 0.55
    ):
        return "BEARISH"

    return "NEUTRAL"


# ============================================================
# MARKET ANALYSIS
# ============================================================

def analyze_market(df):

    latest = df.iloc[-1]
    previous = df.iloc[-2]

    score_buy = 0
    score_sell = 0

    reasons_buy = []
    reasons_sell = []

    # ========================================================
    # EMA TREND
    # ========================================================

    if (
        latest["EMA9"] > latest["EMA21"]
        and latest["EMA21"] > latest["EMA50"]
    ):
        score_buy += 25
        reasons_buy.append(
            "ترتيب المتوسطات EMA يدعم الصعود"
        )

    elif (
        latest["EMA9"] < latest["EMA21"]
        and latest["EMA21"] < latest["EMA50"]
    ):
        score_sell += 25
        reasons_sell.append(
            "ترتيب المتوسطات EMA يدعم الهبوط"
        )

    # ========================================================
    # RSI
    # ========================================================

    rsi = latest["RSI"]

    if 52 <= rsi <= 68:
        score_buy += 15
        reasons_buy.append(
            f"RSI داعم للشراء ({rsi:.1f})"
        )

    elif 32 <= rsi <= 48:
        score_sell += 15
        reasons_sell.append(
            f"RSI داعم للبيع ({rsi:.1f})"
        )

    # ========================================================
    # MACD
    # ========================================================

    if (
        latest["MACD"]
        > latest["MACD_SIGNAL"]
        and latest["MACD"] > previous["MACD"]
    ):
        score_buy += 20
        reasons_buy.append(
            "زخم MACD صاعد"
        )

    elif (
        latest["MACD"]
        < latest["MACD_SIGNAL"]
        and latest["MACD"] < previous["MACD"]
    ):
        score_sell += 20
        reasons_sell.append(
            "زخم MACD هابط"
        )

    # ========================================================
    # CANDLE
    # ========================================================

    candle = candle_analysis(latest)

    if candle == "BULLISH":
        score_buy += 15
        reasons_buy.append(
            "الشمعة الحالية صاعدة"
        )

    elif candle == "BEARISH":
        score_sell += 15
        reasons_sell.append(
            "الشمعة الحالية هابطة"
        )

    # ========================================================
    # PRICE POSITION
    # ========================================================

    if latest["close"] > latest["EMA21"]:
        score_buy += 10
        reasons_buy.append(
            "السعر أعلى EMA21"
        )

    elif latest["close"] < latest["EMA21"]:
        score_sell += 10
        reasons_sell.append(
            "السعر أسفل EMA21"
        )

    # ========================================================
    # SUPPORT / RESISTANCE
    # ========================================================

    support = latest["SUPPORT"]
    resistance = latest["RESISTANCE"]
    price = latest["close"]

    resistance_distance = (
        resistance - price
    )

    support_distance = (
        price - support
    )

    if (
        resistance_distance > 0
        and resistance_distance
        > latest["ATR"] * 0.35
    ):
        score_buy += 15
        reasons_buy.append(
            "يوجد مجال نسبي قبل المقاومة"
        )

    if (
        support_distance > 0
        and support_distance
        > latest["ATR"] * 0.35
    ):
        score_sell += 15
        reasons_sell.append(
            "ي

