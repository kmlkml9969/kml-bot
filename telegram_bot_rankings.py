import logging
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from telegram import Update, ChatMember
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler,
    filters, ContextTypes, ChatMemberHandler
)
from datetime import datetime

# 配置日志
logging.basicConfig(level=logging.INFO)

# Telegram Token
TELEGRAM_TOKEN = "7541826709:AAF1A-1Efcb88oahgxOt5mTuzy6nP6Q7Jes"

# Google Sheets 设置
SHEET_NAME = "日报表"
SCOPE = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
import os
import json
import base64
from oauth2client.service_account import ServiceAccountCredentials

# 设置 Google Sheets API 权限范围
SCOPE = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']

# 从环境变量中获取 Base64 编码的 JSON
GOOGLE_CREDENTIALS_BASE64 = os.getenv("GOOGLE_CREDENTIALS")

if not GOOGLE_CREDENTIALS_BASE64:
    raise ValueError("环境变量 GOOGLE_CREDENTIALS 未设置，请在 Render 添加。")

# 解码 Base64 字符串为 JSON 对象
GOOGLE_CREDENTIALS_JSON = json.loads(base64.b64decode(GOOGLE_CREDENTIALS_BASE64))

# 用字典创建 Google 授权凭证
CREDS = ServiceAccountCredentials.from_json_keyfile_dict(GOOGLE_CREDENTIALS_JSON, SCOPE)

client = gspread.authorize(CREDS)
sheet = client.open(SHEET_NAME).sheet1

# 🟢 /start - 开始指令
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await help_command(update, context)

# 📋 /report - 提交日报
async def report(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("📋 Por favor, introduzca el informe diario de hoy en el siguiente formato：\n\nNúmero de BD enviados | fecha | Número de depositantes | Monto del depósito")

# 📆 /today - 查询是否提交
async def today(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user.full_name
    today_str = datetime.now().strftime("%Y-%m-%d")
    records = sheet.get_all_values()
    today_records = [r for r in records if len(r) >= 9 and r[0] == user and r[8] == today_str]

    if today_records:
        await update.message.reply_text(f"✅ Has enviado tu informe diario hoy：\n\n{' | '.join(today_records[0])}")
    else:
        await update.message.reply_text("📭 No has enviado tu informe diario hoy. Envía /report para empezar a rellenarlo.。")

# ❌ /undo - 撤销最后一条日报
async def undo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user.full_name
    records = sheet.get_all_values()

    for i in range(len(records) - 1, 0, -1):
        if len(records[i]) >= 1 and records[i][0] == user:
            sheet.delete_row(i + 1)
            await update.message.reply_text("❌ Su registro diario más reciente ha sido eliminado。")
            return
    await update.message.reply_text("🔍 No se encontró el registro que enviaste。")

# 🆘 /help - 帮助说明
async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    help_text = (
        "🤖 Bienvenido al Robot de Informes Diarios del Equipo JonyK！\n\n"
        "📌 Comandos disponibles：\n"
        "/report - Presentar informe diario\n"
        "/today - Comprueba si se ha enviado hoy\n"
        "/undo - Eliminar el registro diario más reciente\n"
        "/help - Ver información de ayuda"
    )
    await update.message.reply_text(help_text)

# 📩 普通文本：解析日报内容
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.chat.type != "private":
        return  # 群组内不处理普通文本
    user = update.message.from_user.full_name
    text = update.message.text
    parts = [p.strip() for p in text.split("|")]
    if len(parts) != 4:
        await update.message.reply_text("❌ El formato es incorrecto. Utilice | para separar y completar los 4 elementos.。")
        return
    parts.insert(0, user)
    parts.append(datetime.now().strftime("%Y-%m-%d"))
    sheet.append_row(parts)
    await update.message.reply_text("✅ ¡Informe diario grabado! Gracias por enviarlo.。")

# 🔔 新成员加入群组，自动提示
async def welcome_group(update: Update, context: ContextTypes.DEFAULT_TYPE):
    result = update.chat_member
    if result.new_chat_member.status == ChatMember.MEMBER:
        name = result.new_chat_member.user.full_name
        await context.bot.send_message(
            chat_id=update.chat_member.chat.id,
            text=f"👋 ¡Bienvenido {nombre} al grupo! Envíame un mensaje privado y envía /report para empezar a enviar informes diarios. 📝"
        )

# 主入口
if __name__ == '__main__':
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

    # 指令处理
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("report", report))
    app.add_handler(CommandHandler("today", today))
    app.add_handler(CommandHandler("undo", undo))
    app.add_handler(CommandHandler("help", help_command))

    # 文本信息处理（仅私聊）
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    # 群聊欢迎提示
    app.add_handler(ChatMemberHandler(welcome_group, ChatMemberHandler.CHAT_MEMBER))

    # 启动机器人
    app.run_polling()
