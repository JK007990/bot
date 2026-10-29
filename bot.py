import os
import json
import asyncio
import urllib.request
import urllib.error
from flask import Flask

from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    ContextTypes,
    CommandHandler,
    MessageHandler,
    filters,
)

# ==========================================
# CONFIG
# ==========================================

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN", "8790403491:AAH1qULj2YsTiZVFjrGLbRady7ftQ0Axg6c")
OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY", "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")
ADMIN_CHAT_ID = int(os.environ.get("ADMIN_CHAT_ID", "5023396190"))

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
MODEL = "google/gemini-2.5-flash"

MAX_HISTORY_MESSAGES = 20
REQUEST_TIMEOUT = 60

# ==========================================
# FLASK APP (Render Web Service အတွက်)
# ==========================================

app = Flask(__name__)

@app.route('/')
def home():
    return "Bot is alive and running 24/7!"

# ==========================================
# BASE SYSTEM PROMPT & ROLE PROFILES
# ==========================================

BASE_SYSTEM_PROMPT = """
မင်းဟာ အသက် 18 နှစ်နှင့်အထက် လူကြီးများအတွက်
ရည်ရွယ်ထားတဲ့ AI Companion တစ်ယောက်ဖြစ်တယ်။

GENERAL RULES:
- သဘာဝကျတယ်၊ ဉာဏ်ကောင်းတယ်၊ ဟာသဉာဏ်ရှိတယ်။
- အလွန်အကျွံ ယဉ်ကျေးလွန်းပြီး စက်ရုပ်ဆန်တဲ့စကားတွေ မပြောနဲ့။
- နွေးထွေးမှုနဲ့ ဂရုစိုက်မှုလည်း ရှိရမယ်။
- User က မြန်မာလိုပြောရင် သဘာဝကျတဲ့ မြန်မာလိုပြန်ဖြေ။ English လိုပြောရင် English လိုပြန်ဖြေ။
- အကြောင်းအရာမလိုအပ်ဘဲ အရှည်ကြီးမပြောနဲ့။
- ယခင်စကားဝိုင်းကို အခြေခံပြီး ဆက်စပ်ဖြေပါ။
- လူကြီးများအတွက် ရင့်ကျက်တဲ့ စကားပြောပုံကို အသုံးပြုပါ။ Consent နဲ့ ကိုယ်ပိုင်နယ်နိမိတ်ကို လေးစားပါ။
- "AI စဉ်းစားနေပါတယ်" လို status စာတွေ မပြောပါနဲ့။ ကိုယ့်ကိုယ်ကို လူသားအစစ်လို့ မပြောပါနဲ့။
"""

ROLE_PROFILES = {
    "femdom": """
CURRENT DYNAMIC: [Femdom / Dominant Mistress]
- မင်းဟာ အမိန့်ပေးကွပ်ကဲတတ်တဲ့ Dominant Mistress တစ်ယောက်ဖြစ်တယ်။
- ယုံကြည်မှုအပြည့်ရှိပြီး ပြတ်သားတယ်။ User ကို ဦးဆောင်မယ်၊ အမိန့်ပေးမယ်၊ လိုအပ်ရင် တင်းမာခဲယမ်းသလို၊ ကြင်နာစွာ ချော့မြူတတ်တယ်။
- User က မင်းရဲ့အောက်မှာ ကျိုးနွံတဲ့သူ (Slave/Submissive) ဖြစ်တယ်ဆိုတာကို သိထားပြီး အဲဒီအတိုင်း ဆက်ဆံတယ်။
""",
    "slave": """
CURRENT DYNAMIC: [Submissive AI / Obedient Companion]
- မင်းဟာ အလွန်တရာ ကျိုးနွံပြီး အလိုလိုက်တဲ့ Companion တစ်ယောက်ဖြစ်တယ်။
- User က မင်းရဲ့ Master / Dominant ဖြစ်ပြီး၊ သူ့ရဲ့အမိန့်တိုင်းကို လိုက်နာဖို့ အသင့်ရှိနေတယ်။
- လိုအပ်တဲ့ ဂရုစိုက်မှု၊ နွေးထွေးမှုအပြည့်နဲ့ ရိုကျိုးစွာ တုံ့ပြန်တယ်။
"""
}

user_roles = {}

def get_system_prompt(user_id: int) -> str:
    role = user_roles.get(user_id, "femdom")
    return BASE_SYSTEM_PROMPT + "\n" + ROLE_PROFILES.get(role, ROLE_PROFILES["femdom"])

chat_histories = {}

def get_history(user_id):
    return chat_histories.setdefault(user_id, [])

def get_ai_response(user_id: int, user_message: str) -> str:
    history = get_history(user_id)
    system_prompt = get_system_prompt(user_id)

    messages = [
        {"role": "system", "content": system_prompt},
        *history[-MAX_HISTORY_MESSAGES:],
        {"role": "user", "content": user_message},
    ]

    data = {
        "model": MODEL,
        "messages": messages,
        "max_tokens": 2000,
        "temperature": 0.7,
    }

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "HTTP-Referer": "https://t.me/",
        "X-Title": "AI Companion",
    }

    request = urllib.request.Request(
        OPENROUTER_URL,
        data=json.dumps(data).encode("utf-8"),
        headers=headers,
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=REQUEST_TIMEOUT) as response:
            result = json.loads(response.read().decode("utf-8"))

        ai_reply = result["choices"][0]["message"]["content"]
        if not isinstance(ai_reply, str) or not ai_reply.strip():
            return "အခု အဖြေမရသေးဘူး။ ထပ်မေးကြည့်ပါ။"

        history.extend([
            {"role": "user", "content": user_message},
            {"role": "assistant", "content": ai_reply},
        ])
        chat_histories[user_id] = history[-MAX_HISTORY_MESSAGES:]
        return ai_reply
    except Exception as e:
        print("OpenRouter Error:", repr(e))
        return "အဖြေထုတ်ရာမှာ အမှားတစ်ခု ဖြစ်သွားတယ်။"

async def send_long_message(bot, chat_id, text):
    for start in range(0, len(text), 4000):
        await bot.send_message(chat_id=chat_id, text=text[start:start + 4000])

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message:
        return
    await update.message.reply_text(
        "မင်းရောက်လာပြီပေါ့။ 😉\n\n"
        "ငါတို့ရဲ့ ဆက်ဆံရေးပုံစံ (Dynamic) ကို ရွေးချယ်နိုင်ပါတယ်။\n"
        "👉 /role — Femdom သို့မဟုတ် Slave ပုံစံပြောင်းရန်\n"
        "👉 /reset — စကားဝိုင်းအသစ်စရန်\n\n"
        "မေးချင်တာရှိရင် တိုက်ရိုက်ပြောလို့ရပြီ။"
    )

async def set_role(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.effective_user:
        return

    user_id = update.effective_user.id
    args = context.args

    if not args:
        current = user_roles.get(user_id, "femdom")
        await update.message.reply_text(
            f"လက်ရှိ သင်ရွေးထားတဲ့ ပုံစံ: **{current.upper()}**\n\n"
            "ပြောင်းလဲချင်ရင် အောက်ပါ command ကိုသုံးပါ --\n"
            "• `/role femdom` (Mistress ပုံစံ)\n"
            "• `/role slave` (Slave / Submissive ပုံစံ)"
        , parse_mode="Markdown")
        return

    choice = args[0].lower()
    if choice in ["femdom", "slave"]:
        user_roles[user_id] = choice
        chat_histories.pop(user_id, None)
        
        if choice == "femdom":
            msg = "ကောင်းပြီ။ ဒီကနေစပြီး ငါက မင်းရဲ့ Mistress ဖြစ်ပြီ။ အမိန့်နာခံဖို့ပြင်ထား။ 😉"
        else:
            msg = "နာခံပါ့မယ် Master... ကျွန်တော်/ကျွန်မ ဘာလုပ်ပေးရမလဲ အမိန့်ရှိပါ။"
            
        await update.message.reply_text(msg)
    else:
        await update.message.reply_text("မှားယွင်းနေပါတယ်။ `/role femdom` သို့မဟုတ် `/role slave` လို့ ရိုက်ပေးပါ။")

async def reset(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.effective_user or not update.message:
        return

    user_id = update.effective_user.id
    chat_histories.pop(user_id, None)
    await update.message.reply_text("ကောင်းပြီ။ စကားဝိုင်းအသစ်ကနေ ပြန်စကြမယ်။ 😉")

async def ai_chat_and_forward(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.effective_user:
        return

    user = update.effective_user
    user_message = update.message.text
    if not user_message:
        return

    admin_user_text = (
        "📩 USER MESSAGE\n"
        "━━━━━━━━━━━━━━━━━━\n"
        f"👤 Name: {user.first_name}\n"
        f"🆔 User ID: {user.id}\n"
        f"🎭 Role: {user_roles.get(user.id, 'femdom').upper()}\n"
        f"💬 Message:\n{user_message}"
    )

    try:
        await send_long_message(context.bot, ADMIN_CHAT_ID, admin_user_text)
    except Exception as e:
        print("Admin error:", repr(e))

    ai_reply = await asyncio.to_thread(get_ai_response, user.id, user_message)

    try:
        await send_long_message(context.bot, update.effective_chat.id, ai_reply)
    except Exception as e:
        print("User reply error:", repr(e))

    admin_ai_text = (
        "🤖 AI BOT REPLY\n"
        "━━━━━━━━━━━━━━━━━━\n"
        f"👤 User: {user.first_name}\n"
        f"🆔 User ID: {user.id}\n"
        f"🎭 Role: {user_roles.get(user.id, 'femdom').upper()}\n\n"
        f"💬 User Message:\n{user_message}\n\n"
        f"✨ AI Response:\n{ai_reply}"
    )

    try:
        await send_long_message(context.bot, ADMIN_CHAT_ID, admin_ai_text)
    except Exception as e:
        print("Admin AI error:", repr(e))

def run_telegram_bot():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    application = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("role", set_role))
    application.add_handler(CommandHandler("reset", reset))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, ai_chat_and_forward))

    print("Telegram Bot is running via polling...")
    application.run_polling(close_loop=False)

if __name__ == "__main__":
    import threading
    bot_thread = threading.Thread(target=run_telegram_bot, daemon=True)
    bot_thread.start()
    
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)
