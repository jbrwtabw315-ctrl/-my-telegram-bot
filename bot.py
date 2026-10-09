import os
import logging
import requests
import pandas as pd
import numpy as np
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters

TELEGRAM_TOKEN = "8564085814:AAFr9XBwDA80jteJyxKKCBnAU9r5S55SMY4"
TWELVE_DATA_API_KEY = "625159396fa746229e049c853ee698bf"
API_URL = "https://api.twelvedata.com/time_series"
ALLOWED_USERS = [649387138]

logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in ALLOWED_USERS:
        await update.message.reply_text(f"⚠️ غير مصرح لك.\nمعرفك: `{user_id}`")
        return
    await update.message.reply_text("🔥 أهلاً بك في 4B AI TRADER PRO\nأرسل اسم الزوج مثل: EUR/USD")

async def analyze_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message:
        return
    user_id = update.effective_user.id
    if user_id not in ALLOWED_USERS:
        await update.message.reply_text(f"⚠️ غير مصرح لك.\nمعرفك: `{user_id}`")
        return
    
    symbol = update.message.text.strip().upper().replace("-", "/").replace(" ", "")
    if "/" not in symbol:
        await update.message.reply_text("❌ صيغة خاطئة. اكتب مثل: EUR/USD")
        return
    
    await update.message.reply_text(f"🔎 جاري تحليل {symbol}...")
    try:
        params = {"symbol": symbol, "interval": "1min", "outputsize": 150, "apikey": TWELVE_DATA_API_KEY, "format": "JSON"}
        res = requests.get(API_URL, params=params, timeout=15).json()
        if "values" not in res:
            raise Exception("لم تصل بيانات السوق.")
        
        df = pd.DataFrame(res["values"])
        for col in ["open", "high", "low", "close"]:
            df[col] = pd.to_numeric(df[col], errors="coerce")
        
        price = df.iloc[-1]["close"]
        await update.message.reply_text(f"✅ الزوج: {symbol}\n💰 السعر الحالي: {price:.5f}\n📊 الحالة: السوق مستقر.")
    except Exception as e:
        await update.message.reply_text(f"❌ حدث خطأ: {e}")

def main():
    app = Application.builder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, analyze_command))
    print("STARTED")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
