import logging
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from telegram import Update, ChatMember
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler,
    filters, ContextTypes, ChatMemberHandler
)
from datetime import datetime, timedelta
from collections import defaultdict
import os
import json
import base64

# 配置日志
logging.basicConfig(level=logging.INFO)

# Telegram Token
TELEGRAM_TOKEN = "7541826709:AAF1A-1Efcb88oahgxOt5mTuzy6nP6Q7Jes"

# Google Sheets 设置
SHEET_NAME = "日报表"
SCOPE = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]

# 解析 base64 编码的 Google 凭据
GOOGLE_CREDENTIALS_BASE64 = os.getenv("GOOGLE_CREDENTIALS")
if not GOOGLE_CREDENTIALS_BASE64:
    raise ValueError("环境变量 GOOGLE_CREDENTIALS 未设置，请在 Render 添加。")
GOOGLE_CREDENTIALS_JSON = json.loads(base64.b64decode(GOOGLE_CREDENTIALS_BASE64))
CREDS = ServiceAccountCredentials.from_json_keyfile_dict(GOOGLE_CREDENTIALS_JSON, SCOPE)
client = gspread.authorize(CREDS)
sheet = client.open(SHEET_NAME).sheet1

# 🟢 /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await help_command(update, context)

# 📋 /report
async def report(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📋 Por favor, introduzca el informe diario de hoy en el siguiente formato：\n\n"
        "Número de BD enviados | fecha | Número de depositantes | Monto del depósito"
    )

# 📆 /today
async def today(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user.full_name
    today_str = datetime.now().strftime("%Y-%m-%d")
    records = sheet.get_all_values()
    today_records = [r for r in records if len(r) >= 9 and r[0] == user and r[8] == today_str]

    if today_records:
        await update.message.reply_text(f"✅ Has enviado tu informe diario hoy：\n\n{' | '.join(today_records[0])}")
    else:
        await update.message.reply_text("📭 No has enviado tu informe diario hoy. Envía /report para empezar a rellenarlo.")

# ❌ /undo
async def undo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user.full_name
    records = sheet.get_all_values()

    for i in range(len(records) - 1, 0, -1):
        if len(records[i]) >= 1 and records[i][0] == user:
            sheet.delete_row(i + 1)
            await update.message.reply_text("❌ Su registro diario más reciente ha sido eliminado。")
            return
    await update.message.reply_text("🔍 No se encontró el registro que enviaste。")

# 🆘 /help
async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    help_text = (
        "🤖 Bienvenido al Robot de Informes Diarios del Equipo JonyK！\n\n"
        "📌 Comandos disponibles：\n"
        "/report - Presentar informe diario\n"
        "/today - Comprueba si se ha enviado hoy\n"
        "/undo - Eliminar el registro diario más reciente\n"
        "/rank - Clasificación semanal\n"
        "/help - Ver información de ayuda"
    )
    await update.message.reply_text(help_text)

# 📩 文本信息处理（仅限私聊）
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.chat.type != "private":
        return
    user = update.message.from_user.full_name
    text = update.message.text
    parts = [p.strip() for p in text.split("|")]
    if len(parts) != 4:
        await update.message.reply_text("❌ El formato es incorrecto. Utilice | para separar y completar los 4 elementos.")
        return
    parts.insert(0, user)
    parts.append(datetime.now().strftime("%Y-%m-%d"))
    sheet.append_row(parts)
    await update.message.reply_text("✅ ¡Informe diario grabado! Gracias por enviarlo。")

# 🔔 群聊欢迎提示
async def welcome_group(update: Update, context: ContextTypes.DEFAULT_TYPE):
    result = update.chat_member
    if result.new_chat_member.status == ChatMember.MEMBER:
        name = result.new_chat_member.user.full_name
        await context.bot.send_message(
            chat_id=update.chat_member.chat.id,
            text=f"👋 ¡Bienvenido {name} al grupo! Envíame un mensaje privado y envía /report para empezar a enviar informes diarios. 📝"
        )

# 📊 /rank 排行榜命令
def get_weekly_ranking(sheet):
    today = datetime.now().date()
    start_of_week = today - timedelta(days=today.weekday())
    data = sheet.get_all_records()
    rankings = defaultdict(int)

    for row in data:
        try:
            name = row.get("用户名") or row.get("NAME") or row.get("Nombre") or row.get("Usuario") or row.get("用户") or row.get("Name") or row.get("name") or row.get("Nombre completo") or row.get("Empleado")
            fecha_str = row.get("fecha") or row.get("Fecha") or row.get("date") or row.get("时间") or ""
            deposit_count = int(row.get("Número de depositantes", 0))
            fecha = datetime.strptime(fecha_str, "%Y-%m-%d").date()
            if fecha >= start_of_week:
                rankings[name] += deposit_count
        except Exception as e:
            print(f"[❌] Error processing row: {row} - {e}")

    return sorted(rankings.items(), key=lambda x: x[1], reverse=True)

async def rank(update: Update, context: ContextTypes.DEFAULT_TYPE):
    ranking = get_weekly_ranking(sheet)
    if not ranking:
        await update.message.reply_text("⚠️ No hay datos de esta semana aún.")
        return

    msg = "🏆 Clasificación semanal por número de depositantes:\n\n"
    for i, (name, total) in enumerate(ranking, 1):
        msg += f"{i}. {name} - {total} depositantes\n"

    await update.message.reply_text(msg)

# 主入口
if __name__ == '__main__':
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

    # 注册指令
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("report", report))
    app.add_handler(CommandHandler("today", today))
    app.add_handler(CommandHandler("undo", undo))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("rank", rank))

    # 文本消息（仅限私聊）
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    # 群组欢迎语
    app.add_handler(ChatMemberHandler(welcome_group, ChatMemberHandler.CHAT_MEMBER))

    # 启动 Bot
    app.run_polling()
