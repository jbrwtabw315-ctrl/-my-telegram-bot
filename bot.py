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

ADMIN_ID = 6493871389 
ALLOWED_USERS = [6493871389]  # الأيدي الخاص بك
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
    return data

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_name = update.effective_user.full_name
    username = f"@{update.effective_user.username}" if update.effective_user.username else "لا يوجد"

    if user_id not in ALLOWED_USERS:
        admin_username = "Marwa483"  # يوزرك الخاص لتلقي الاشتراكات
        
        await update.message.reply_text(
            "⚠️ **غير مصرح لك باستخدام البوت حالياً.**\n\n"
            "اشتراك البوت مدفوع لتفعيل خدمة التحليل على مدار 24 ساعة.\n"
            "💳 للاشتراك، يرجى التواصل مباشرة مع المالك عبر الرابط التالي:\n"
            f"👉 https://t.me/{admin_username}\n\n"
            "بعد التحويل، أرسل صورة الإيصال هنا أو هناك وسيتم تفعيل حسابك فوراً.\n\n"
            f"معرفك للتفعيل: `{user_id}`"
        )
        
        try:
            await context.bot.send_message(
                chat_id=ADMIN_ID,
                text=f"🔔 محاولة دخول جديدة من مستخدم غير مسجل:\n"
                     f"👤 الاسم: {user_name}\n"
                     f"🔗 المعرف: {username}\n"
                     f"🆔 ID: `{user_id}`"
            )
        except Exception as e:
            logger.error(f"Failed to notify admin: {e}")
        return

    await update.message.reply_text(
        "🔥 أهلاً بك يا مالك البوت في 4B AI TRADER PRO\n\n"
        "أرسل اسم الزوج الآن للحصول على التحليل وإشارات البيع والشراء:\n"
        "EUR/USD أو GBP/USD"
    )

async def handle_user_messages(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message:
        return
    user_id = update.effective_user.id

    if user_id not in ALLOW_USERS:
        user_name = update.effective_user.full_name
        if update.message.photo:
            await context.bot.send_photo(
                chat_id=ADMIN_ID,
                photo=update.message.photo[-1].file_id,
                caption=f"📨 إيصال جديد من المستخدم:\n👤 الاسم: {user_name}\n🆔 ID: `{user_id}`"
            )
            await update.message.reply_text("✅ تم إرسال الإيصال إلى الإدارة بنجاح. سيتم التحقق وتفعيل حسابك قريباً.")
        else:
            text = update.message.text
            await context.bot.send_message(
                chat_id=ADMIN_ID,
                text=f"💬 رسالة جديدة من مستخدم غير مسجل (`{user_id}`):\n{text}"
            )
            await update.message.reply_text("📨 تم إرسال رسالتك إلى إدارة البوت، سيتم الرد عليك قريباً.")
        return

    await analyze_command(update, context)

async def analyze_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in ALLOWED_USERS:
        return

    symbol = update.message.text.strip().upper().replace("-", "/").replace(" ", "")
    if "/" not in symbol:
        await update.message.reply_text("❌ صيغة خاطئة. اكتب الزوج هكذا: EUR/USD")
        return

    await update.message.reply_text(f"🔎 جاري فحص وتحليل {symbol} على فريم 1M...")

    try:
        await update.message.reply_text("⚠️ بيانات السوق جاهزة.")
    except Exception as e:
        logger.exception("Analysis error")
        await update.message.reply_text(f"❌ حدث خطأ أثناء التحليل: {e}")

def main():
    app = Application.builder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.ALL & ~filters.COMMAND, handle_user_messages))
    print("PRO TRADER STARTED")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
