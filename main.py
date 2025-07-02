import asyncio
import logging
import os
import signal
import sys
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
from pyrogram import Client, filters
from pyrogram.types import Message
from pytgcalls import PyTgCalls
from pytgcalls.types.input_stream import InputStream
from pytgcalls.types.stream import Stream
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

# Suppress unnecessary logs
logging.getLogger("pyrogram").setLevel(logging.WARNING)
logging.getLogger("pytgcalls").setLevel(logging.WARNING)

# MongoDB setup
try:
    mongo_client = MongoClient(MONGO_URI)
    db = mongo_client.fm_bot
    fm_collection = db.fm_streams
    # Test connection
    mongo_client.admin.command('ping')
    logger.info("✅ MongoDB connected successfully")
except Exception as e:
    logger.error(f"❌ MongoDB connection failed: {e}")
    sys.exit(1)

# Pyrogram client for userbot
userbot = Client(
    "fm_userbot",
    api_id=API_ID,
    api_hash=API_HASH,
    session_string=SESSION_STRING
)

# PyTgCalls for voice chat
pytgcalls = PyTgCalls(userbot)

# Global variables
current_streams = {}  # chat_id: stream_info
bot_app = None

class FMPlayer:
    def __init__(self):
        self.active_calls = {}
    
    async def join_and_play(self, chat_id: int, stream_url: str, fm_name: str):
        """Join voice chat and play FM stream"""
        try:
            logger.info(f"🎵 Attempting to play {fm_name} in chat {chat_id}")
            logger.info(f"🔗 Stream URL: {stream_url}")
            
            # Check if already in call
            if chat_id in self.active_calls:
                logger.warning(f"Already in call for chat {chat_id}")
                return False
            
            # Create audio stream
            stream = AudioStream(
                stream_url,
                headers={
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
                }
            )
            
            # Join group call
            await pytgcalls.join_group_call(
                chat_id,
                stream,
                stream_type=Stream().pulse_stream
            )
            
            # Track active call
            self.active_calls[chat_id] = True
            current_streams[chat_id] = {
                'fm_name': fm_name,
                'stream_url': stream_url
            }
            
            logger.info(f"✅ Successfully started playing {fm_name} in chat {chat_id}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Error playing FM in chat {chat_id}: {e}")
            # Clean up on error
            if chat_id in self.active_calls:
                del self.active_calls[chat_id]
            if chat_id in current_streams:
                del current_streams[chat_id]
            return False
    
    async def stop_stream(self, chat_id: int):
        """Stop stream and leave voice chat"""
        try:
            logger.info(f"🛑 Stopping stream in chat {chat_id}")
            
            await pytgcalls.leave_group_call(chat_id)
            
            # Clean up tracking
            if chat_id in self.active_calls:
                del self.active_calls[chat_id]
            if chat_id in current_streams:
                del current_streams[chat_id]
            
            logger.info(f"✅ Successfully stopped stream in chat {chat_id}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Error stopping stream in chat {chat_id}: {e}")
            return False
    
    async def is_playing(self, chat_id: int):
        """Check if bot is currently playing in chat"""
        return chat_id in self.active_calls

fm_player = FMPlayer()

# PyTgCalls event handlers
@pytgcalls.on_stream_end()
async def on_stream_end(client, update):
    """Handle stream end"""
    chat_id = update.chat_id
    logger.info(f"🔚 Stream ended in chat {chat_id}")
    
    # Clean up tracking
    if chat_id in fm_player.active_calls:
        del fm_player.active_calls[chat_id]
    if chat_id in current_streams:
        del current_streams[chat_id]

@pytgcalls.on_closed_voice_chat()
async def on_closed_vc(client, chat_id: int):
    """Handle voice chat closure"""
    logger.info(f"🔇 Voice chat closed in chat {chat_id}")
    
    # Clean up tracking
    if chat_id in fm_player.active_calls:
        del fm_player.active_calls[chat_id]
    if chat_id in current_streams:
        del current_streams[chat_id]

# Bot command handlers
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start command handler"""
    await update.message.reply_text(
        "🎵 **FM Player Bot**\n\n"
        "**User Commands:**\n"
        "• `/playfm <fm_name>` - Play FM in voice chat\n"
        "• `/stopfm` - Stop current FM\n"
        "• `/listfm` - List available FMs\n"
        "• `/currentfm` - Show current playing FM\n\n"
        "**Owner Commands (private only):**\n"
        "• `/fm <name> <stream_url>` - Add FM stream\n"
        "• `/delfm <name>` - Delete FM stream\n\n"
        "**Note:** Bot must be added to voice chat to play music!",
        parse_mode='Markdown'
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
            "❌ **Usage:** `/fm <fm_name> <stream_url>`\n\n"
            "**Example:** `/fm RadioFM https://stream.radio.com/live.mp3`",
            parse_mode='Markdown'
        )
        return
    
    fm_name = context.args[0].lower()
    stream_url = ' '.join(context.args[1:])
    
    # Validate URL format
    url_pattern = re.compile(
        r'^https?://'  # http:// or https://
        r'(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+[A-Z]{2,6}\.?|'  # domain...
        r'localhost|'  # localhost...
        r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})'  # ...or ip
        r'(?::\d+)?'  # optional port
        r'(?:/?|[/?]\S+)$', re.IGNORECASE)
    
    if not url_pattern.match(stream_url):
        await update.message.reply_text("❌ Please provide a valid HTTP/HTTPS stream URL.")
        return
    
    try:
        # Save to database
        fm_collection.update_one(
            {"name": fm_name},
            {"$set": {
                "name": fm_name, 
                "stream_url": stream_url,
                "added_by": update.effective_user.id,
                "added_at": update.message.date
            }},
            upsert=True
        )
        
        await update.message.reply_text(
            f"✅ **FM Station Added!**\n\n"
            f"📻 **Name:** {fm_name}\n"
            f"🔗 **URL:** {stream_url[:50]}...\n\n"
            f"Users can now play it with: `/playfm {fm_name}`",
            parse_mode='Markdown'
        )
        logger.info(f"FM added: {fm_name} - {stream_url}")
        
    except Exception as e:
        await update.message.reply_text("❌ Error saving FM to database.")
        logger.error(f"Database error: {e}")

async def delete_fm_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Delete FM stream (owner only)"""
    if update.effective_user.id != OWNER_ID:
        await update.message.reply_text("❌ Only the owner can delete FM streams.")
        return
    
    if not context.args:
        await update.message.reply_text(
            "❌ **Usage:** `/delfm <fm_name>`\n\n"
            "**Example:** `/delfm RadioFM`",
            parse_mode='Markdown'
        )
        return
    
    fm_name = ' '.join(context.args).lower()
    
    try:
        result = fm_collection.delete_one({"name": fm_name})
        
        if result.deleted_count > 0:
            await update.message.reply_text(f"✅ FM station '{fm_name}' deleted successfully!")
        else:
            await update.message.reply_text(f"❌ FM station '{fm_name}' not found.")
            
    except Exception as e:
        await update.message.reply_text("❌ Error deleting FM from database.")
        logger.error(f"Database error: {e}")

async def play_fm_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Play FM in voice chat"""
    if not context.args:
        await update.message.reply_text(
            "❌ **Usage:** `/playfm <fm_name>`\n\n"
            "Use `/listfm` to see available FM stations.",
            parse_mode='Markdown'
        )
        return
    
    fm_name = ' '.join(context.args).lower()
    chat_id = update.effective_chat.id
    
    # Check if in group/supergroup
    if update.effective_chat.type == 'private':
        await update.message.reply_text(
            "❌ This command only works in **groups with voice chats**.\n\n"
            "Add me to a group and try again!",
            parse_mode='Markdown'
        )
        return
    
    # Check if bot is already playing in this chat
    if await fm_player.is_playing(chat_id):
        current_fm = current_streams[chat_id]['fm_name']
        await update.message.reply_text(
            f"🎵 **Already Playing:** {current_fm}\n\n"
            "Use `/stopfm` to stop current stream first.",
            parse_mode='Markdown'
        )
        return
    
    try:
        # Find FM in database
        fm_data = fm_collection.find_one({"name": fm_name})
        
        if not fm_data:
            # Suggest similar names
            all_fms = list(fm_collection.find({}, {"name": 1, "_id": 0}))
            suggestions = [f['name'] for f in all_fms if fm_name in f['name'] or f['name'] in fm_name]
            
            suggestion_text = ""
            if suggestions:
                suggestion_text = f"\n\n**Did you mean:** {', '.join(suggestions[:3])}"
            
            await update.message.reply_text(
                f"❌ **FM station '{fm_name}' not found.**\n\n"
                f"Use `/listfm` to see available stations.{suggestion_text}",
                parse_mode='Markdown'
            )
            return
        
        stream_url = fm_data['stream_url']
        
        # Send loading message
        loading_msg = await update.message.reply_text(
            f"🔄 **Connecting to {fm_name}...**\n\n"
            "⏳ Please wait while I join the voice chat...",
            parse_mode='Markdown'
        )
        
        # Play FM
        success = await fm_player.join_and_play(chat_id, stream_url, fm_name)
        
        if success:
            await loading_msg.edit_text(
                f"🎵 **Now Playing:** {fm_name}\n\n"
                f"📻 **Station:** {fm_name.title()}\n"
                f"💬 **Chat:** {update.effective_chat.title or 'Group'}\n"
                f"🌐 **Stream:** {stream_url[:40]}...\n\n"
                f"🛑 Use `/stopfm` to stop the stream.",
                parse_mode='Markdown'
            )
        else:
            await loading_msg.edit_text(
                f"❌ **Failed to play {fm_name}**\n\n"
                "**Possible issues:**\n"
                "• Stream URL might be down\n"
                "• Voice chat not active\n"
                "• Bot needs admin permissions\n\n"
                "Please check and try again.",
                parse_mode='Markdown'
            )
            
    except Exception as e:
        await update.message.reply_text(
            f"❌ **Error playing FM**\n\n"
            f"**Error:** {str(e)[:100]}...\n\n"
            "Please try again or contact the owner.",
            parse_mode='Markdown'
        )
        logger.error(f"Error in play_fm_command: {e}")

async def stop_fm_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Stop current FM stream"""
    chat_id = update.effective_chat.id
    
    if not await fm_player.is_playing(chat_id):
        await update.message.reply_text(
            "❌ **No FM is currently playing** in this chat.\n\n"
            "Use `/playfm <fm_name>` to start playing.",
            parse_mode='Markdown'
        )
        return
    
    current_fm = current_streams[chat_id]['fm_name']
    
    success = await fm_player.stop_stream(chat_id)
    
    if success:
        await update.message.reply_text(
            f"⏹️ **Stopped Playing:** {current_fm}\n\n"
            f"Thanks for listening! 🎵",
            parse_mode='Markdown'
        )
    else:
        await update.message.reply_text(
            "❌ **Error stopping the stream.**\n\n"
            "The stream might have already ended.",
            parse_mode='Markdown'
        )

async def list_fm_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """List all available FM streams"""
    try:
        fm_list = list(fm_collection.find({}, {"name": 1, "stream_url": 1, "_id": 0}))
        
        if not fm_list:
            await update.message.reply_text(
                "❌ **No FM stations available.**\n\n"
                f"Owner can add stations using `/fm <name> <url>`",
                parse_mode='Markdown'
            )
            return
        
        # Create formatted list
        fm_text = "📻 **Available FM Stations:**\n\n"
        for i, fm in enumerate(fm_list, 1):
            fm_text += f"**{i}.** {fm['name'].title()}\n"
            fm_text += f"   🔗 {fm['stream_url'][:50]}...\n\n"
        
        fm_text += f"**Total:** {len(fm_list)} stations\n\n"
        fm_text += "**Usage:** `/playfm <station_name>`"
        
        await update.message.reply_text(fm_text, parse_mode='Markdown')
        
    except Exception as e:
        await update.message.reply_text("❌ Error fetching FM list.")
        logger.error(f"Error in list_fm_command: {e}")

async def current_fm_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show currently playing FM"""
    chat_id = update.effective_chat.id
    
    if not await fm_player.is_playing(chat_id):
        await update.message.reply_text(
            "❌ **No FM is currently playing** in this chat.\n\n"
            "Use `/playfm <fm_name>` to start playing.",
            parse_mode='Markdown'
        )
        return
    
    stream_info = current_streams[chat_id]
    await update.message.reply_text(
        f"🎵 **Currently Playing:**\n\n"
        f"📻 **Station:** {stream_info['fm_name'].title()}\n"
        f"🌐 **Stream:** {stream_info['stream_url'][:50]}...\n"
        f"💬 **Chat:** {update.effective_chat.title or 'Group'}\n\n"
        f"🛑 Use `/stopfm` to stop",
        parse_mode='Markdown'
    )

# Error handler
async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle errors"""
    logger.error(f"Update {update} caused error {context.error}")

# Graceful shutdown
def signal_handler(signum, frame):
    """Handle shutdown signals"""
    logger.info("🛑 Shutdown signal received, cleaning up...")
    
    # Stop all active streams
    for chat_id in list(current_streams.keys()):
        try:
            asyncio.create_task(fm_player.stop_stream(chat_id))
        except:
            pass
    
    sys.exit(0)

async def main():
    """Main function to run both bots"""
    global bot_app
    
    # Setup signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    try:
        # Start keep_alive server
        keep_alive()
        
        # Initialize Telegram bot
        bot_app = Application.builder().token(BOT_TOKEN).build()
        
        # Add handlers
        bot_app.add_handler(CommandHandler("start", start_command))
        bot_app.add_handler(CommandHandler("fm", add_fm_command))
        bot_app.add_handler(CommandHandler("delfm", delete_fm_command))
        bot_app.add_handler(CommandHandler("playfm", play_fm_command))
        bot_app.add_handler(CommandHandler("stopfm", stop_fm_command))
        bot_app.add_handler(CommandHandler("listfm", list_fm_command))
        bot_app.add_handler(CommandHandler("currentfm", current_fm_command))
        bot_app.add_error_handler(error_handler)
        
        # Start userbot and pytgcalls
        logger.info("🤖 Starting userbot...")
        await userbot.start()
        
        logger.info("🎵 Starting PyTgCalls...")
        await pytgcalls.start()
        
        # Start bot
        logger.info("🚀 Starting bot...")
        await bot_app.initialize()
        await bot_app.start()
        await bot_app.updater.start_polling()
        
        logger.info("✅ Bot is running successfully!")
        logger.info("🌐 Web interface: http://localhost:8080")
        
        # Keep running
        try:
            await asyncio.Event().wait()
        except KeyboardInterrupt:
            logger.info("🛑 Keyboard interrupt received")
        
    except Exception as e:
        logger.error(f"❌ Fatal error: {e}")
        raise
    finally:
        # Cleanup
        logger.info("🧹 Cleaning up...")
        try:
            if bot_app:
                await bot_app.stop()
            await userbot.stop()
            await pytgcalls.stop()
        except Exception as e:
            logger.error(f"Error during cleanup: {e}")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("🛑 Bot stopped by user")
    except Exception as e:
        logger.error(f"❌ Bot crashed: {e}")
        sys.exit(1)
