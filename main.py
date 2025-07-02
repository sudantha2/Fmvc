import asyncio
import logging
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
from pyrogram import Client, filters
from pyrogram.types import Message
from pytgcalls import PyTgCalls, StreamType
from pytgcalls.types.input_stream import AudioPiped
from pymongo import MongoClient
import re
from keep_alive import keep_alive

# Configuration - Add your credentials here
API_ID = "24140233"
API_HASH = "d81fccd3356451ff20e577a5192e5782"
BOT_TOKEN = "7695188163:AAFLPNDuxRIJkEkUMpG_Qijfi7-OoILOMzM"
OWNER_ID = 5132917762  # Your Telegram user ID
MONGO_URI = "mongodb+srv://VcPlayer:Sudantha123@cluster1.cqjy4g5.mongodb.net/?retryWrites=true&w=majority&appName=Cluster1"
SESSION_STRING = "BQFwWckAkVTWSuGuyozXMYQfOxuCxo2fthsVol4raSEdPzz9k56C9MjykE83fvnvXWLJN0P8qTGcNkdYITRDcKZBK2Avf-XoYljtg2G2wq-NZsZtp6bxG7Vq0GtDrDcHubD7_knc0VAtka8SuaDZSfmVkkydrsp5gmfIqlcVDhj66ylHQdP7FlAr5QD7-BCnPCmKwufQ8xlYlXK5BdiECJIgsQvkgq4WjuCB9J29hhlqSl9QMGC4aiwbFbF5CAi6uBCOieQksCHimxAfl2u_hWm9xw5yM4hgP8rE1ocRUhLwz7wO2a1FcmLpvG8rE0-mA58yvN-hZS1Ht2wiWAmO5Y-jMZgsQgAAAAHWkUM3AA"

# Logging setup
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# MongoDB setup
mongo_client = MongoClient(MONGO_URI)
db = mongo_client.fm_bot
fm_collection = db.fm_streams

# Pyrogram client for userbot
userbot = Client(
    "fm_userbot",
    api_id=API_ID,
    api_hash=API_HASH,
    session_string=SESSION_STRING
)

# PyTgCalls for voice chat
pytgcalls = PyTgCalls(userbot, cache_duration=120)

# Global variables
current_streams = {}  # chat_id: stream_info
bot_app = None

class FMPlayer:
    def __init__(self):
        self.active_calls = {}
    
    async def join_and_play(self, chat_id: int, stream_url: str, fm_name: str):
        try:
            # Join voice chat and play stream
            await pytgcalls.join_group_call(
                chat_id,
                AudioPiped(stream_url),
                stream_type=StreamType().pulse_stream
            )
            
            current_streams[chat_id] = {
                'fm_name': fm_name,
                'stream_url': stream_url
            }
            
            logger.info(f"Started playing {fm_name} in chat {chat_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error playing FM: {e}")
            return False
    
    async def stop_stream(self, chat_id: int):
        try:
            await pytgcalls.leave_group_call(chat_id)
            if chat_id in current_streams:
                del current_streams[chat_id]
            return True
        except Exception as e:
            logger.error(f"Error stopping stream: {e}")
            return False

fm_player = FMPlayer()

# Bot command handlers
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start command handler"""
    await update.message.reply_text(
        "🎵 FM Player Bot\n\n"
        "Commands:\n"
        "• /playfm <fm_name> - Play FM in voice chat\n"
        "• /stopfm - Stop current FM\n"
        "• /listfm - List available FMs\n"
        "• /currentfm - Show current playing FM\n\n"
        "Owner commands (private chat only):\n"
        "• /fm <name> <stream_url> - Add FM stream"
    )

async def add_fm_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Add FM stream (owner only, private chat only)"""
    if update.effective_user.id != OWNER_ID:
        await update.message.reply_text("❌ Only the owner can add FM streams.")
        return
    
    if update.effective_chat.type != 'private':
        await update.message.reply_text("❌ This command only works in private chat.")
        return
    
    if len(context.args) < 2:
        await update.message.reply_text(
            "❌ Usage: /fm <fm_name> <stream_url>\n"
            "Example: /fm RadioFM https://stream.radio.com/live"
        )
        return
    
    fm_name = context.args[0].lower()
    stream_url = ' '.join(context.args[1:])
    
    # Validate URL
    url_pattern = re.compile(
        r'^https?://'  # http:// or https://
        r'(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+[A-Z]{2,6}\.?|'  # domain...
        r'localhost|'  # localhost...
        r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})'  # ...or ip
        r'(?::\d+)?'  # optional port
        r'(?:/?|[/?]\S+)$', re.IGNORECASE)
    
    if not url_pattern.match(stream_url):
        await update.message.reply_text("❌ Please provide a valid stream URL.")
        return
    
    try:
        # Save to database
        fm_collection.update_one(
            {"name": fm_name},
            {"$set": {"name": fm_name, "stream_url": stream_url}},
            upsert=True
        )
        
        await update.message.reply_text(f"✅ FM '{fm_name}' added successfully!")
        logger.info(f"FM added: {fm_name} - {stream_url}")
        
    except Exception as e:
        await update.message.reply_text("❌ Error saving FM to database.")
        logger.error(f"Database error: {e}")

async def play_fm_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Play FM in voice chat"""
    if not context.args:
        await update.message.reply_text(
            "❌ Usage: /playfm <fm_name>\n"
            "Use /listfm to see available FMs."
        )
        return
    
    fm_name = ' '.join(context.args).lower()
    chat_id = update.effective_chat.id
    
    # Check if bot is already playing in this chat
    if chat_id in current_streams:
        current_fm = current_streams[chat_id]['fm_name']
        await update.message.reply_text(
            f"🎵 Already playing: {current_fm}\n"
            "Use /stopfm to stop current stream first."
        )
        return
    
    try:
        # Find FM in database
        fm_data = fm_collection.find_one({"name": fm_name})
        
        if not fm_data:
            await update.message.reply_text(
                f"❌ FM '{fm_name}' not found.\n"
                "Use /listfm to see available FMs."
            )
            return
        
        stream_url = fm_data['stream_url']
        
        # Send loading message
        loading_msg = await update.message.reply_text(
            f"🔄 Connecting to {fm_name}...\n"
            "Please wait while I join the voice chat."
        )
        
        # Play FM
        success = await fm_player.join_and_play(chat_id, stream_url, fm_name)
        
        if success:
            await loading_msg.edit_text(
                f"🎵 Now playing: **{fm_name}**\n"
                f"🔗 Stream: {stream_url[:50]}...\n"
                f"💬 Chat: {update.effective_chat.title or 'Private'}\n\n"
                "Use /stopfm to stop the stream."
            )
        else:
            await loading_msg.edit_text(
                f"❌ Failed to play {fm_name}\n"
                "Please check if the stream URL is working."
            )
            
    except Exception as e:
        await update.message.reply_text(f"❌ Error playing FM: {str(e)}")
        logger.error(f"Error in play_fm_command: {e}")

async def stop_fm_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Stop current FM stream"""
    chat_id = update.effective_chat.id
    
    if chat_id not in current_streams:
        await update.message.reply_text("❌ No FM is currently playing in this chat.")
        return
    
    current_fm = current_streams[chat_id]['fm_name']
    
    success = await fm_player.stop_stream(chat_id)
    
    if success:
        await update.message.reply_text(f"⏹️ Stopped playing: {current_fm}")
    else:
        await update.message.reply_text("❌ Error stopping the stream.")

async def list_fm_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """List all available FM streams"""
    try:
        fm_list = list(fm_collection.find({}, {"name": 1, "_id": 0}))
        
        if not fm_list:
            await update.message.reply_text("❌ No FM streams available.")
            return
        
        fm_names = [fm['name'] for fm in fm_list]
        fm_text = "📻 Available FM Streams:\n\n" + "\n".join([f"• {name}" for name in fm_names])
        
        await update.message.reply_text(fm_text)
        
    except Exception as e:
        await update.message.reply_text("❌ Error fetching FM list.")
        logger.error(f"Error in list_fm_command: {e}")

async def current_fm_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show currently playing FM"""
    chat_id = update.effective_chat.id
    
    if chat_id not in current_streams:
        await update.message.reply_text("❌ No FM is currently playing in this chat.")
        return
    
    stream_info = current_streams[chat_id]
    await update.message.reply_text(
        f"🎵 Currently playing:\n"
        f"📻 FM: {stream_info['fm_name']}\n"
        f"🔗 Stream: {stream_info['stream_url'][:50]}..."
    )

# Pyrogram handlers for userbot
@userbot.on_message(filters.private & filters.text & filters.regex("^/status$"))
async def userbot_status(client: Client, message: Message):
    """Check userbot status"""
    if message.from_user.id == OWNER_ID:
        active_calls = len(current_streams)
        await message.reply_text(
            f"🤖 Userbot Status: Online\n"
            f"📞 Active calls: {active_calls}\n"
            f"🎵 Streams: {list(current_streams.keys())}"
        )

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle errors"""
    logger.error(f"Update {update} caused error {context.error}")

async def main():
    """Main function to run both bots"""
    global bot_app
    
    # Start keep_alive server
    keep_alive()
    
    # Initialize Telegram bot
    bot_app = Application.builder().token(BOT_TOKEN).build()
    
    # Add handlers
    bot_app.add_handler(CommandHandler("start", start_command))
    bot_app.add_handler(CommandHandler("fm", add_fm_command))
    bot_app.add_handler(CommandHandler("playfm", play_fm_command))
    bot_app.add_handler(CommandHandler("stopfm", stop_fm_command))
    bot_app.add_handler(CommandHandler("listfm", list_fm_command))
    bot_app.add_handler(CommandHandler("currentfm", current_fm_command))
    bot_app.add_error_handler(error_handler)
    
    # Start userbot and pytgcalls
    logger.info("Starting userbot...")
    await userbot.start()
    await pytgcalls.start()
    
    # Start bot
    logger.info("Starting bot...")
    await bot_app.initialize()
    await bot_app.start()
    
    logger.info("Bot is running...")
    
    # Keep running
    await bot_app.updater.start_polling()
    
    # Wait indefinitely
    try:
        await asyncio.Event().wait()
    except KeyboardInterrupt:
        logger.info("Shutting down...")
        await bot_app.stop()
        await userbot.stop()
        await pytgcalls.stop()

if __name__ == "__main__":
    asyncio.run(main()
