import os
import subprocess
import telebot
from dotenv import load_dotenv
from pathlib import Path

# CONFIG - Universal Pathing
PROJECT_ROOT = Path(__file__).parent.parent
ENV_FILE = PROJECT_ROOT / '.hermes' / '.env'
ASSISTANT_SCRIPT = PROJECT_ROOT / 'scripts' / 'assistant.sh'

# Load Credentials
load_dotenv(ENV_FILE)
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
ALLOWED_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

if not TOKEN or not ALLOWED_CHAT_ID:
    print("❌ ERROR: Missing Telegram credentials in .hermes/.env")
    exit(1)

# Initialize Bot
bot = telebot.TeleBot(TOKEN)

print("🎧 Hermes Telegram Listener is LIVE and waiting for messages...")

@bot.message_handler(func=lambda message: True)
def handle_all_messages(message):
    # Security Check: Only listen to YOUR chat
    if str(message.chat.id) != ALLOWED_CHAT_ID:
        print(f"⚠️ Ignored message from unauthorized chat: {message.chat.id}")
        return

    user_query = message.text
    print(f"📩 Received query: '{user_query}'")

    # Send 'Thinking' Indicator
    thinking_msg = bot.reply_to(message, "🤖 *Hermes is analyzing the database...*", parse_mode='Markdown')

    try:
        # Run the Assistant Brain
        result = subprocess.run(
            [str(ASSISTANT_SCRIPT), user_query],
            capture_output=True,
            text=True,
            check=True
        )
        final_answer = result.stdout.strip()
        
        if not final_answer:
            final_answer = "⚠️ The Assistant Brain returned an empty response."

        # Update the 'Thinking' message with the final answer
        bot.edit_message_text(
            chat_id=message.chat.id,
            message_id=thinking_msg.message_id,
            text=final_answer
        )
        print("✅ Reply sent successfully.")

    except subprocess.CalledProcessError as e:
        error_msg = f"❌ **Assistant Crash:**\n`{e.stderr.strip()}`"
        bot.edit_message_text(chat_id=message.chat.id, message_id=thinking_msg.message_id, text=error_msg, parse_mode='Markdown')
        print(f"❌ Error during execution: {e}")

if __name__ == "__main__":
    bot.infinity_polling(timeout=10, long_polling_timeout=5)
