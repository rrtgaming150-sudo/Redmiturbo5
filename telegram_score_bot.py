#!/usr/bin/env python3
"""
🚗 Redmi Turbo 5 - Score Accumulator Telegram Bot
With built-in uptime pinging to prevent sleep
"""

import os
import json
import logging
import asyncio
import aiohttp
import random
import time
import uuid
import threading
from datetime import datetime
from pathlib import Path
from flask import Flask, request
import requests
from urllib.parse import urljoin

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ═══════════════════════════════════════════════════════════════════════
# BOT CONFIGURATION
# ═══════════════════════════════════════════════════════════════════════

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "YOUR_BOT_TOKEN")
WEBHOOK_URL = os.getenv("WEBHOOK_URL", "https://your-bot.onrender.com")
BOT_API_URL = "https://api.telegram.org/bot"

# Score Accumulator API
SCORE_API_URL = "https://api-g5leosq2cq-el.a.run.app/leaderboard/score"

STORAGE_DIR = Path("data")
STORAGE_DIR.mkdir(exist_ok=True)

USERS_FILE = STORAGE_DIR / "users.json"
PROGRESS_FILE = STORAGE_DIR / "progress.json"

app = Flask(__name__)

# ═══════════════════════════════════════════════════════════════════════
# 💾 STORAGE FUNCTIONS
# ═══════════════════════════════════════════════════════════════════════

def load_users():
    if USERS_FILE.exists():
        try:
            return json.loads(USERS_FILE.read_text())
        except:
            return {}
    return {}

def save_users(data):
    USERS_FILE.write_text(json.dumps(data, indent=2))

def load_user(user_id):
    users = load_users()
    return users.get(str(user_id), {})

def save_user(user_id, user_data):
    users = load_users()
    users[str(user_id)] = user_data
    save_users(users)

def load_progress(user_id):
    if PROGRESS_FILE.exists():
        try:
            data = json.loads(PROGRESS_FILE.read_text())
            return data.get(str(user_id), {'totalScore': 0, 'attempts': 0, 'running': False})
        except:
            return {'totalScore': 0, 'attempts': 0, 'running': False}
    return {'totalScore': 0, 'attempts': 0, 'running': False}

def save_progress(user_id, progress):
    data = {}
    if PROGRESS_FILE.exists():
        try:
            data = json.loads(PROGRESS_FILE.read_text())
        except:
            pass
    data[str(user_id)] = progress
    PROGRESS_FILE.write_text(json.dumps(data, indent=2))

# ═══════════════════════════════════════════════════════════════════════
# 📱 TELEGRAM API FUNCTIONS
# ═══════════════════════════════════════════════════════════════════════

def send_message(chat_id, text, keyboard=None):
    data = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "HTML"
    }
    if keyboard:
        data["reply_markup"] = {"inline_keyboard": keyboard}
    try:
        requests.post(f"{BOT_API_URL}{BOT_TOKEN}/sendMessage", json=data, timeout=10)
    except Exception as e:
        logger.error(f"Send message error: {e}")

def edit_message(chat_id, message_id, text, keyboard=None):
    data = {
        "chat_id": chat_id,
        "message_id": message_id,
        "text": text,
        "parse_mode": "HTML"
    }
    if keyboard:
        data["reply_markup"] = {"inline_keyboard": keyboard}
    try:
        requests.post(f"{BOT_API_URL}{BOT_TOKEN}/editMessageText", json=data, timeout=10)
    except Exception as e:
        logger.error(f"Edit message error: {e}")

def answer_callback(callback_id, text=""):
    try:
        requests.post(f"{BOT_API_URL}{BOT_TOKEN}/answerCallbackQuery", 
                     json={"callback_query_id": callback_id, "text": text}, 
                     timeout=10)
    except:
        pass

# ═══════════════════════════════════════════════════════════════════════
# 🎮 SCORE ACCUMULATOR FUNCTIONS
# ═══════════════════════════════════════════════════════════════════════

def calculate_score(pickups, time_val):
    pickup_score = pickups * 20
    time_bonus = max(0, (500 / time_val) * 10)
    random_bonus = random.randint(0, 20)
    score = round(pickup_score + time_bonus + random_bonus)
    return min(max(score, 400), 460)

async def submit_score_to_api(account, pickups, race_time):
    """Submit score to the leaderboard API"""
    try:
        car = random.choice(['red', 'blue', 'yellow', 'cyan'])
        score = calculate_score(pickups, race_time)
        
        payload = {
            'name': account['name'],
            'score': score,
            'carUsed': car,
            'raceTimeSeconds': race_time,
            'pickups': pickups,
            'requestId': str(uuid.uuid4()),
            'phonenumber': account.get('phone', '')
        }
        
        headers = {
            'Content-Type': 'application/json',
            'User-Agent': 'Mozilla/5.0'
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.post(SCORE_API_URL, json=payload, headers=headers, timeout=15) as resp:
                if resp.status in (200, 201):
                    data = await resp.json()
                    return {
                        'success': True,
                        'score': score,
                        'total': data.get('totalScore', 0),
                        'pickups': pickups,
                        'time': race_time,
                        'car': car
                    }
                else:
                    return {'success': False, 'error': f'API error: {resp.status}'}
    except Exception as e:
        return {'success': False, 'error': str(e)}

# ═══════════════════════════════════════════════════════════════════════
# 🤖 MAIN MENU BUILDER
# ═══════════════════════════════════════════════════════════════════════

def main_menu_keyboard():
    return [
        [{"text": "🎮 Start Bot", "callback_data": "start_bot"}],
        [{"text": "⛔ Stop Bot", "callback_data": "stop_bot"}],
        [{"text": "📊 View Progress", "callback_data": "view_progress"}],
        [{"text": "⚙️ Settings", "callback_data": "settings"}],
        [{"text": "ℹ️ Help", "callback_data": "help"}]
    ]

def main_menu_text():
    return """🚗 <b>REDMI TURBO 5 - SCORE BOT</b>

Choose an option below 👇"""

# ═══════════════════════════════════════════════════════════════════════
# ⚙️ SETTINGS MENU
# ═══════════════════════════════════════════════════════════════════════

def settings_keyboard():
    return [
        [{"text": "👤 Account Name", "callback_data": "set_name"}],
        [{"text": "📱 Phone", "callback_data": "set_phone"}],
        [{"text": "🎯 Target Score", "callback_data": "set_target"}],
        [{"text": "🔄 Back", "callback_data": "back_menu"}]
    ]

# ═══════════════════════════════════════════════════════════════════════
# 🌐 WEBHOOK & UPTIME PING
# ═══════════════════════════════════════════════════════════════════════

def ping_self():
    """Ping the bot itself to stay awake"""
    while True:
        try:
            requests.get(f"{WEBHOOK_URL}/health", timeout=5)
            logger.info("✅ Uptime ping sent")
        except Exception as e:
            logger.error(f"Ping failed: {e}")
        time.sleep(300)  # Ping every 5 minutes

@app.route("/webhook", methods=["POST"])
def webhook():
    try:
        data = request.get_json()
        
        if "message" in data:
            msg = data["message"]
            chat_id = msg["chat"]["id"]
            user_id = msg["from"]["id"]
            user_name = msg["from"].get("first_name", "User")
            text = msg.get("text", "")
            
            if text == "/start":
                send_message(chat_id, main_menu_text(), main_menu_keyboard())
                return "OK", 200
        
        elif "callback_query" in data:
            cb = data["callback_query"]
            chat_id = cb["message"]["chat"]["id"]
            msg_id = cb["message"]["message_id"]
            user_id = cb["from"]["id"]
            cb_data = cb.get("data", "")
            answer_callback(cb["id"])
            
            # MAIN MENU
            if cb_data == "back_menu":
                edit_message(chat_id, msg_id, main_menu_text(), main_menu_keyboard())
            
            # START BOT
            elif cb_data == "start_bot":
                user_data = load_user(user_id)
                if not user_data.get('name'):
                    send_message(chat_id, "⚠️ Please set account name first!\n\nGo to Settings → Account Name", 
                               [[{"text": "⚙️ Settings", "callback_data": "settings"}]])
                    return "OK", 200
                
                progress = load_progress(user_id)
                progress['running'] = True
                save_progress(user_id, progress)
                
                edit_message(chat_id, msg_id, 
                           "🚀 <b>Bot Started!</b>\n\nSubmitting scores...\n\n0 attempts\n0 points",
                           [[{"text": "📊 View", "callback_data": "view_progress"}], 
                            [{"text": "⛔ Stop", "callback_data": "stop_bot"}]])
                
                # Start submission loop in background
                def run_submissions():
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    loop.run_until_complete(submission_loop(user_id, chat_id, msg_id))
                
                threading.Thread(target=run_submissions, daemon=True).start()
            
            # STOP BOT
            elif cb_data == "stop_bot":
                progress = load_progress(user_id)
                progress['running'] = False
                save_progress(user_id, progress)
                
                edit_message(chat_id, msg_id, 
                           f"⛔ <b>Bot Stopped</b>\n\nFinal Stats:\n✨ Total: {progress['totalScore']} points\n🎮 Attempts: {progress['attempts']}",
                           [[{"text": "🔙 Back", "callback_data": "back_menu"}]])
            
            # VIEW PROGRESS
            elif cb_data == "view_progress":
                progress = load_progress(user_id)
                user_data = load_user(user_id)
                status = "🟢 RUNNING" if progress.get('running') else "⛔ STOPPED"
                
                text = f"""📊 <b>PROGRESS</b>

👤 Account: {user_data.get('name', 'Not set')}
{status}

✨ Total Score: {progress['totalScore']}
🎮 Attempts: {progress['attempts']}
📈 Avg/Attempt: {round(progress['totalScore']/progress['attempts']) if progress['attempts'] > 0 else 0}"""
                
                edit_message(chat_id, msg_id, text, [[{"text": "🔙 Back", "callback_data": "back_menu"}]])
            
            # SETTINGS
            elif cb_data == "settings":
                edit_message(chat_id, msg_id, "⚙️ <b>SETTINGS</b>\n\nChoose what to configure:", settings_keyboard())
            
            # SET NAME
            elif cb_data == "set_name":
                edit_message(chat_id, msg_id, 
                           "📝 Send your account name (just type it):",
                           [[{"text": "🔙 Back", "callback_data": "settings"}]])
                
                # Wait for text message
                def wait_for_name():
                    while True:
                        time.sleep(0.5)
                
                threading.Thread(target=wait_for_name, daemon=True).start()
            
            # SET PHONE
            elif cb_data == "set_phone":
                edit_message(chat_id, msg_id,
                           "📱 Send your phone number:",
                           [[{"text": "🔙 Back", "callback_data": "settings"}]])
            
            # SET TARGET
            elif cb_data == "set_target":
                edit_message(chat_id, msg_id,
                           "🎯 Send target score (e.g., 44000):",
                           [[{"text": "🔙 Back", "callback_data": "settings"}]])
            
            # HELP
            elif cb_data == "help":
                help_text = """ℹ️ <b>HOW TO USE</b>

1️⃣ Go to <b>Settings</b>
2️⃣ Set your <b>Account Name</b>
3️⃣ (Optional) Set <b>Phone</b> and <b>Target</b>
4️⃣ Click <b>Start Bot</b>
5️⃣ Bot will submit scores automatically!

⏸️ Click <b>Stop Bot</b> anytime

📊 View progress with <b>View Progress</b>

🎮 Scores: 400-460 (randomized)
⏱️ Race time: 35-50s (randomized)
📦 Pickups: 10-18 (randomized)"""
                
                edit_message(chat_id, msg_id, help_text, [[{"text": "🔙 Back", "callback_data": "back_menu"}]])
        
        return "OK", 200
    except Exception as e:
        logger.error(f"Webhook error: {e}")
        return "ERROR", 500

async def submission_loop(user_id, chat_id, msg_id):
    """Continuous submission loop"""
    progress = load_progress(user_id)
    user_data = load_user(user_id)
    
    while progress.get('running'):
        try:
            # Random pickups and time
            pickups = random.randint(10, 18)
            race_time = round(random.uniform(35, 50), 2)
            
            # Submit score
            result = await submit_score_to_api(user_data, pickups, race_time)
            
            if result['success']:
                progress['totalScore'] = result['total']
                progress['attempts'] += 1
                save_progress(user_id, progress)
                
                status_text = f"""✅ Score Submitted!

🏎️ Score: {result['score']}
📊 Total: {result['total']}
🎮 Attempts: {progress['attempts']}

⏳ Waiting 20s..."""
                
                edit_message(chat_id, msg_id, status_text,
                           [[{"text": "📊 View", "callback_data": "view_progress"}],
                            [{"text": "⛔ Stop", "callback_data": "stop_bot"}]])
                
                await asyncio.sleep(20)
            else:
                await asyncio.sleep(60)
            
            # Refresh progress
            progress = load_progress(user_id)
        
        except Exception as e:
            logger.error(f"Submission loop error: {e}")
            await asyncio.sleep(60)

@app.route("/health", methods=["GET"])
def health():
    """Health check endpoint for uptime pinging"""
    return {"status": "ok", "timestamp": datetime.now().isoformat()}, 200

@app.route("/setup", methods=["GET"])
def setup():
    """Setup webhook"""
    try:
        webhook_url = f"{WEBHOOK_URL}/webhook"
        requests.get(f"{BOT_API_URL}{BOT_TOKEN}/deleteWebhook", timeout=10)
        resp = requests.post(f"{BOT_API_URL}{BOT_TOKEN}/setWebhook", 
                            json={"url": webhook_url}, timeout=10)
        return f"✅ Webhook set: {webhook_url}", 200
    except Exception as e:
        return f"❌ Error: {e}", 500

@app.route("/", methods=["GET"])
def index():
    return "<h1>🚗 Score Bot</h1><p><a href='/setup'>Setup Webhook</a></p>", 200

if __name__ == "__main__":
    # Start uptime ping in background
    ping_thread = threading.Thread(target=ping_self, daemon=True)
    ping_thread.start()
    logger.info("✅ Uptime ping started")
    
    # Start Flask
    port = int(os.getenv("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
