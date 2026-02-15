import os
import re
import asyncio
import requests
from flask import Flask, request
from Crypto.Cipher import AES
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes

# --- Configuration ---
TOKEN = '8183534977:AAGYLeHEUExoQTY3YNJ9yRp-NuVCSDOgXug'
VIDEO_FILE_ID = "BAACAgUAAxkBAAICYWmSDu9PxdumNL2jt_HuEbhU9ej8AAJUIAACnY2RVB4XvSbfaDVBOgQ"

app = Flask(__name__)
# 🛠️ Set explicitly to catch all update types
ptb_instance = Application.builder().token(TOKEN).build()

MODELS = [
    "DeepSeek-V1", "DeepSeek-V2", "DeepSeek-V2.5", "DeepSeek-V3", "DeepSeek-V3-0324",
    "DeepSeek-V3.1", "DeepSeek-V3.2", "DeepSeek-R1", "DeepSeek-R1-0528", "DeepSeek-R1-Distill",
    "DeepSeek-Prover-V1", "DeepSeek-Prover-V1.5", "DeepSeek-Prover-V2", "DeepSeek-VL",
    "DeepSeek-Coder", "DeepSeek-Coder-V2", "DeepSeek-Coder-6.7B-base", "DeepSeek-Coder-6.7B-instruct"
]

class DeepSeekSession:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({'User-Agent': 'Mozilla/5.0'})
        self.model = "DeepSeek-R1"
        self.ready = False
        self.history = []

    def bypass(self):
        try:
            r = self.session.get('https://asmodeus.free.nf/', timeout=8)
            nums = re.findall(r'toNumbers\("([a-f0-9]+)"\)', r.text)
            if len(nums) >= 3:
                key, iv, data = [bytes.fromhex(n) for n in nums[:3]]
                cookie = AES.new(key, AES.MODE_CBC, iv).decrypt(data).hex()
                self.session.cookies.set('__test', cookie, domain='asmodeus.free.nf')
                self.session.get('https://asmodeus.free.nf/index.php?i=1')
                self.ready = True
        except: pass

    def ask(self, q):
        if not self.ready: self.bypass()
        prompt = "".join([f"U: {h['user']}\nA: {h['bot']}\n" for h in self.history[-3:]]) + f"U: {q}\nA: "
        try:
            r = self.session.post('https://asmodeus.free.nf/deepseek.php', 
                                 params={'i': '1'}, 
                                 data={'model': self.model, 'question': prompt}, 
                                 timeout=25)
            res = re.search(r'class="response-content">(.*?)</div>', r.text, re.DOTALL)
            if res:
                text = re.sub(r'<[^>]*>', '', res.group(1).replace('<br>', '\n')).strip()
                self.history.append({"user": q, "bot": text})
                return text
            return "⚠️ API is currently busy."
        except: return "❌ Timeout."

user_sessions = {}

async def start(u: Update, c: ContextTypes.DEFAULT_TYPE):
    uid = u.effective_user.id
    user_sessions[uid] = DeepSeekSession()
    kb = [[InlineKeyboardButton(MODELS[j], callback_data=f"set_{MODELS[j]}") for j in range(i, min(i+2, len(MODELS)))] for i in range(0, len(MODELS), 2)]
    await u.message.reply_video(video=VIDEO_FILE_ID, caption="🤖 **DeepSeek Bot OWNER:@ankneewayz**\nSelect model:", reply_markup=InlineKeyboardMarkup(kb), parse_mode='Markdown')

async def cb_handler(u: Update, c: ContextTypes.DEFAULT_TYPE):
    query = u.callback_query
    # ✅ CRITICAL: Tell Telegram the button was clicked immediately!
    await query.answer(text=f"Switching to {query.data.replace('set_', '')}...")
    
    uid = u.effective_user.id
    model = query.data.replace("set_", "")
    if uid not in user_sessions: user_sessions[uid] = DeepSeekSession()
    user_sessions[uid].model = model
    user_sessions[uid].bypass()
    await query.edit_message_caption(caption=f"✅ Model: **{model}**\nSend a message!", parse_mode='Markdown')

async def msg_handler(u: Update, c: ContextTypes.DEFAULT_TYPE):
    uid = u.effective_user.id
    if uid not in user_sessions: user_sessions[uid] = DeepSeekSession()
    wait_msg = await u.message.reply_text("(lmk if any inquiry @ankneewayz)typing...")
    ans = await asyncio.to_thread(user_sessions[uid].ask, u.message.text)
    await c.bot.edit_message_text(chat_id=uid, message_id=wait_msg.message_id, text=ans)

ptb_instance.add_handler(CommandHandler("start", start))
ptb_instance.add_handler(CallbackQueryHandler(cb_handler))
ptb_instance.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, msg_handler))

@app.route('/', methods=['POST', 'GET'])
def webhook():
    if request.method == "POST":
        update = Update.de_json(request.get_json(force=True), ptb_instance.bot)
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(ptb_instance.initialize())
        # Ensure it processes ALL update types properly
        loop.run_until_complete(ptb_instance.process_update(update))
        return "OK", 200
    return "Bot is Active!", 200

