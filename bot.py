import os
import uuid
import requests
from telegram import Update, InlineQueryResultArticle, InputTextMessageContent
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    InlineQueryHandler,
    ContextTypes,
    filters,
)
from openai import OpenAI

# ================= CONFIG =================
TELEGRAM_TOKEN = os.environ["TELEGRAM_TOKEN"]
OWNER_ID = int(os.environ["OWNER_ID"])
OPENAI_API_KEY = os.environ["OPENAI_API_KEY"]
VOIP_API_KEY = os.environ["VOIP_API_KEY"]  # Abstract API per check numero

client = OpenAI(api_key=OPENAI_API_KEY)
FIRMA = "\n\n_Questo bot è stato programmato da blackdagger_"

# ================= FUNZIONI =================
def is_owner(update: Update):
    if update.message and update.message.from_user.id == OWNER_ID:
        return True
    if update.inline_query and update.inline_query.from_user.id == OWNER_ID:
        return True
    return False

# /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_owner(update):
        return
    await update.message.reply_text(
        "🤖 Bot attivo!\n"
        "Comandi disponibili:\n"
        "/chat testo → ChatGPT\n"
        "/image testo → genera immagine\n"
        "/sky testo → info programma Sky\n"
        "/skytoday → panoramica cosa danno oggi su Sky\n"
        "Messaggi privati triggerano automaticamente il check VOIP.\n"
        "In qualsiasi chat puoi usare @NomeBot per risposte inline."
    )

# ================= CHECK NUMERO AUTOMATICO =================
async def auto_check(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_owner(update):
        return

    user = update.message.from_user
    phone = getattr(user, "phone_number", None)

    if not phone:
        await update.message.reply_text("ℹ️ Numero non disponibile su Telegram." + FIRMA, parse_mode="Markdown")
        return

    try:
        r = requests.get(
            "https://phonevalidation.abstractapi.com/v1/",
            params={"api_key": VOIP_API_KEY, "phone": phone},
            timeout=10
        )
        data = r.json()
        country = data.get("country", {}).get("name", "Sconosciuto")
        carrier = data.get("carrier", "Sconosciuto")
        line_type = data.get("line_type", "sconosciuto")
        warning = " ⚠️" if line_type.lower() == "voip" else ""

        message = (
            f"🔍 Analisi contatto\n"
            f"📍 Paese: {country}\n"
            f"📞 Operatore: {carrier}\n"
            f"📡 Linea: {line_type.capitalize()}{warning}"
            f"{FIRMA}"
        )
        await update.message.reply_text(message, parse_mode="Markdown")

    except Exception as e:
        await update.message.reply_text("❌ Errore durante il controllo del numero." + FIRMA, parse_mode="Markdown")
        print("Errore VOIP:", e)

# ================= COMANDI =================
# /chat
async def chat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_owner(update):
        return
    user_text = " ".join(context.args)
    if not user_text:
        await update.message.reply_text("Scrivi qualcosa dopo /chat")
        return

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": "Sei un assistente personale che risponde in italiano."},
            {"role": "user", "content": user_text}
        ],
        temperature=0.7
    )
    await update.message.reply_text(response.choices[0].message.content + FIRMA, parse_mode="Markdown")

# /image
async def generate_image(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_owner(update):
        return
    prompt = " ".join(context.args)
    if not prompt:
        await update.message.reply_text("Scrivi qualcosa dopo /image")
        return
    result = client.images.generate(model="gpt-image-1", prompt=prompt, size="1024x1024")
    await update.message.reply_photo(result.data[0].url)

# /sky
async def sky_program(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_owner(update):
        return
    program = " ".join(context.args)
    if not program:
        await update.message.reply_text("Scrivi il nome del programma dopo /sky")
        return
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": "Sei un assistente esperto di programmi Sky. Spiega che programma è, che contenuto offre e su che tipo di canale va in onda."},
            {"role": "user", "content": program}
        ],
        temperature=0.4
    )
    await update.message.reply_text(response.choices[0].message.content + FIRMA, parse_mode="Markdown")

# /skytoday
async def sky_today(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_owner(update):
        return
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": "Sei una guida TV esperta di Sky Italia. Descrivi cosa viene solitamente trasmesso oggi su Sky, dividendo per categorie: Film, Serie TV, Sport, Intrattenimento. Non fornire orari precisi, ma una panoramica realistica."},
            {"role": "user", "content": "Cosa danno oggi su Sky?"}
        ],
        temperature=0.3
    )
    await update.message.reply_text(response.choices[0].message.content + FIRMA, parse_mode="Markdown")

# ================= INLINE =================
async def inline_query(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_owner(update):
        return
    query = update.inline_query.query
    if not query:
        return
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": "Sei un assistente personale che risponde in italiano."},
            {"role": "user", "content": query}
        ],
        temperature=0.7
    )
    result = InlineQueryResultArticle(
        id=str(uuid.uuid4()),
        title="Risposta del bot",
        input_message_content=InputTextMessageContent(response.choices[0].message.content)
    )
    await update.inline_query.answer([result], cache_time=0)

# ================= AVVIO =================
app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("chat", chat))
app.add_handler(CommandHandler("image", generate_image))
app.add_handler(CommandHandler("sky", sky_program))
app.add_handler(CommandHandler("skytoday", sky_today))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, auto_check))
app.add_handler(InlineQueryHandler(inline_query))

print("✅ Bot avviato correttamente")
app.run_polling()
