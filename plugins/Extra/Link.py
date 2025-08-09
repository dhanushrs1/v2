import re
import aiohttp
import asyncio
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ForceReply
from info import ADMINS, REDIRECT_CHANNEL
from database.ia_filterdb import get_search_results
from utils_extra import get_size, formate_file_name

# --- State management for multi-admin usage ---
user_post_data = {}

# --- Lists to identify languages and qualities from filenames ---
LANGUAGES = [
    "english", "hindi", "malayalam", "tamil", "telugu", 
    "kannada", "marathi", "bengali", "gujarati", "punjabi"
]
QUALITIES = [
    "1080p", "720p", "480p", "576p", "WEB-DL", "WEBRip", "HDTV", 
    "BluRay", "HDRip", "DVDRip", "CAMRip", "HDCAM"
]

# --- Helper Functions ---

async def get_movie_details_from_api(query):
    """Fetches movie details from your Vercel API."""
    api_url = f"https://imdbapi-beige.vercel.app/search?query={query}"
    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(api_url) as response:
                if response.status == 200:
                    return await response.json()
        except Exception as e:
            print(f"API Error: {e}")
            return None
    return None

def format_movie_text(data):
    """Formats movie text simply."""
    title = data.get('title', 'Unknown Movie')
    year = data.get('year', 'N/A')
    rating = data.get('rating', 'N/A')
    audio = data.get('audio', 'N/A')
    quality = data.get('quality', 'N/A')
    
    text = f"🎬 <b>MOVIE INFO</b>\n\n"
    text += f"📽️ <b>Title:</b> {title}\n"
    text += f"📅 <b>Year:</b> {year}\n"
    text += f"⭐ <b>Rating:</b> {rating}/10\n"
    text += f"🔊 <b>Audio:</b> {audio}\n"
    text += f"💿 <b>Quality:</b> {quality}\n\n"
    
    return text

async def build_post_text(data, bot_username, chat_id):
    """Builds the text for the movie post."""
    # Movie info
    info_text = format_movie_text(data)
    
    # Files section
    file_list_text = "📁 <b>AVAILABLE FILES</b>\n\n"
    
    # Filter out removed files
    active_files = [file for i, file in enumerate(data['original_files']) if i not in data.get('removed_files', set())]

    for i, file in enumerate(active_files, 1):
        # Handle different file types
        if hasattr(file, 'file_name'):
            file_name = file.file_name
        else:
            file_name = getattr(file, 'file_name', 'Unknown File')
        
        file_name_formatted = formate_file_name(file_name)
        
        # Handle file size
        if hasattr(file, 'file_size'):
            file_size = get_size(file.file_size)
        else:
            file_size = "Unknown Size"
        
        # Create file link
        file_id = getattr(file, 'file_id', 'unknown')
        file_link = f"https://t.me/{bot_username}?start=file_{chat_id}_{file_id}"
        
        file_list_text += f"{i}. {file_name_formatted}\n"
        file_list_text += f"   📦 Size: {file_size} | <a href='{file_link}'>Download</a>\n\n"

    # Footer with stats
    file_count = len(active_files)
    file_list_text += f"📊 <b>Total Files:</b> {file_count}\n\n"

    return info_text, file_list_text

async def show_preview(client, chat_id, user_id, message_id=None):
    """Displays or updates the preview message."""
    if user_id not in user_post_data:
        return
        
    data = user_post_data[user_id]
    bot_username = (await client.get_me()).username
    
    info_text, file_list_text = await build_post_text(data, bot_username, chat_id)
    
    # Add poster preview if available
    poster_preview = ""
    if data.get('poster_url') and data['poster_url'].strip():
        poster_preview = f"<a href='{data['poster_url']}'>🖼️</a>"
    
    final_text = f"{poster_preview}{info_text}{file_list_text}"
    
    # Add available commands
    commands_text = f"<b>📋 AVAILABLE COMMANDS:</b>\n"
    commands_text += f"• <code>/publish</code> - Publish the post\n"
    commands_text += f"• <code>/poster [URL]</code> - Update poster\n"
    commands_text += f"• <code>/info [details]</code> - Update movie info\n"
    commands_text += f"• <code>/button [text|url]</code> - Update button\n"
    commands_text += f"• <code>/addfile</code> - Add files (reply to file)\n"
    commands_text += f"• <code>/dropfile [number]</code> - Remove file\n"
    commands_text += f"• <code>/listfiles</code> - Show all files\n"
    commands_text += f"• <code>/cancel</code> - Cancel operation\n\n"
    
    final_text += commands_text

    try:
        if message_id:
            await client.edit_message_text(
                chat_id=chat_id,
                message_id=message_id,
                text=final_text,
                disable_web_page_preview=False
            )
        else:
            preview_msg = await client.send_message(
                chat_id=chat_id,
                text=final_text,
                disable_web_page_preview=False
            )
            user_post_data[user_id]["preview_message_id"] = preview_msg.id
    except Exception as e:
        print(f"Error showing preview: {e}")

def is_in_preview_mode(user_id):
    """Check if user is in preview mode."""
    return user_id in user_post_data

# --- Main Command ---

@Client.on_message(filters.command("link") & filters.user(ADMINS))
async def generate_link_command(client, message):
    user_id = message.from_user.id
    
    if len(message.command) == 1:
        help_text = "🎬 <b>MOVIE LINK GENERATOR</b>\n\n"
        help_text += "📝 <b>Usage:</b> <code>/link movie_name</code>\n\n"
        help_text += "💡 <b>Example:</b> <code>/link Inception</code>\n\n"
        help_text += "🔧 <b>Features:</b>\n"
        help_text += "• Auto fetch movie details\n"
        help_text += "• Command-based editing\n"
        help_text += "• File management\n"
        help_text += "• Custom poster & button"
        return await message.reply_text(help_text)

    movie_name = message.text.split(" ", 1)[1]
    
    processing_msg = await message.reply_text("🔍 <b>Searching for files...</b>")
    
    all_files, _, _ = await get_search_results(movie_name, max_results=50)
    if not all_files:
        return await processing_msg.edit_text(f"❌ <b>No files found for '{movie_name}'</b>\n\n💡 Try a different search term.")

    await processing_msg.edit_text("🎭 <b>Fetching movie details...</b>")
    api_data = await get_movie_details_from_api(movie_name)

    found_langs = {lang.title() for file in all_files for lang in LANGUAGES if lang in file.file_name.lower()}
    found_quals = {qual for file in all_files for qual in QUALITIES if qual.lower() in file.file_name.lower()}

    user_post_data[user_id] = {
        "title": api_data.get("title") if api_data else movie_name,
        "year": api_data.get("year") if api_data else "N/A",
        "rating": api_data.get("rating") if api_data else "N/A",
        "poster_url": api_data.get("poster") if api_data else "",
        "audio": ', '.join(sorted(list(found_langs))) if found_langs else 'N/A',
        "quality": ', '.join(sorted(list(found_quals))) if found_quals else 'N/A',
        "original_files": all_files,
        "removed_files": set(),
        "request_button_text": "🔔 Request More Files",
        "request_button_url": "https://t.me/+o_VcAI8GRQ8zYzA9",
        "original_chat_id": message.chat.id
    }

    await processing_msg.delete()
    await show_preview(client, message.chat.id, user_id)

# --- Update Commands ---

@Client.on_message(filters.command("publish") & filters.user(ADMINS))
async def publish_post_command(client, message):
    user_id = message.from_user.id
    
    if not is_in_preview_mode(user_id):
        return await message.reply_text("❌ No active post session. Use <code>/link movie_name</code> first.")
    
    try:
        data = user_post_data[user_id]
        bot_username = (await client.get_me()).username
        info_text, file_list_text = await build_post_text(data, bot_username, data["original_chat_id"])
        
        poster_preview = ""
        if data.get('poster_url') and data['poster_url'].strip():
            poster_preview = f"<a href='{data['poster_url']}'>🖼️</a>"
        
        final_text = f"{poster_preview}{info_text}{file_list_text}"
        buttons = [[InlineKeyboardButton(data["request_button_text"], url=data["request_button_url"])]]
        
        published_message = await client.send_message(
            chat_id=REDIRECT_CHANNEL,
            text=final_text,
            reply_markup=InlineKeyboardMarkup(buttons),
            disable_web_page_preview=False
        )
        
        # Get post link
        try:
            channel_info = await client.get_chat(REDIRECT_CHANNEL)
            if hasattr(channel_info, 'username') and channel_info.username:
                post_link = f"https://t.me/{channel_info.username}/{published_message.id}"
            else:
                post_link = f"Post published (Message ID: {published_message.id})"
        except:
            post_link = f"Post published successfully"
        
        file_count = len([f for i, f in enumerate(data['original_files']) if i not in data.get('removed_files', set())])
        
        success_text = f"✅ <b>SUCCESS!</b>\n\n"
        success_text += f"🎉 Post published successfully!\n\n"
        success_text += f"🔗 <b>Post Link:</b> {post_link}\n\n"
        success_text += f"📊 <b>Files Published:</b> {file_count}"
        
        await message.reply_text(success_text, disable_web_page_preview=True)
        
        # Clean up
        del user_post_data[user_id]
        
    except Exception as e:
        print(f"Publishing error: {e}")
        await message.reply_text(f"❌ Failed to publish: {str(e)}")

@Client.on_message(filters.command("poster") & filters.user(ADMINS))
async def update_poster_command(client, message):
    user_id = message.from_user.id
    
    if not is_in_preview_mode(user_id):
        return await message.reply_text("❌ No active post session. Use <code>/link movie_name</code> first.")
    
    if len(message.command) == 1:
        return await message.reply_text("📝 <b>Usage:</b> <code>/poster https://example.com/poster.jpg</code>")
    
    poster_url = message.text.split(" ", 1)[1].strip()
    
    if not poster_url.startswith(('http://', 'https://')):
        return await message.reply_text("❌ Invalid URL! Please use a valid HTTP/HTTPS URL.")
    
    user_post_data[user_id]["poster_url"] = poster_url
    await message.reply_text("✅ Poster updated successfully!")
    
    # Update preview
    preview_msg_id = user_post_data[user_id].get("preview_message_id")
    if preview_msg_id:
        await show_preview(client, message.chat.id, user_id, preview_msg_id)

@Client.on_message(filters.command("info") & filters.user(ADMINS))
async def update_info_command(client, message):
    user_id = message.from_user.id
    
    if not is_in_preview_mode(user_id):
        return await message.reply_text("❌ No active post session. Use <code>/link movie_name</code> first.")
    
    if len(message.command) == 1:
        current_info = user_post_data[user_id]
        info_text = f"<b>📝 Current Info:</b>\n"
        info_text += f"• Title: {current_info.get('title', 'N/A')}\n"
        info_text += f"• Year: {current_info.get('year', 'N/A')}\n"
        info_text += f"• Rating: {current_info.get('rating', 'N/A')}\n"
        info_text += f"• Audio: {current_info.get('audio', 'N/A')}\n"
        info_text += f"• Quality: {current_info.get('quality', 'N/A')}\n\n"
        info_text += f"<b>Usage:</b> <code>/info title=New Title; year=2023; rating=8.5</code>"
        return await message.reply_text(info_text)
    
    info_text = message.text.split(" ", 1)[1]
    info_parts = info_text.split(';')
    updated_fields = []
    
    for part in info_parts:
        if '=' in part:
            key, value = part.split('=', 1)
            key = key.strip().lower()
            value = value.strip()
            
            if key in ["title", "year", "rating", "audio", "quality"] and value:
                user_post_data[user_id][key] = value
                updated_fields.append(key.title())
    
    if updated_fields:
        await message.reply_text(f"✅ Updated: {', '.join(updated_fields)}")
        
        # Update preview
        preview_msg_id = user_post_data[user_id].get("preview_message_id")
        if preview_msg_id:
            await show_preview(client, message.chat.id, user_id, preview_msg_id)
    else:
        await message.reply_text("❌ No valid fields found! Use format: <code>title=...; year=...</code>")

@Client.on_message(filters.command("button") & filters.user(ADMINS))
async def update_button_command(client, message):
    user_id = message.from_user.id
    
    if not is_in_preview_mode(user_id):
        return await message.reply_text("❌ No active post session. Use <code>/link movie_name</code> first.")
    
    if len(message.command) == 1:
        current_button = user_post_data[user_id]
        button_text = f"<b>🔘 Current Button:</b>\n"
        button_text += f"• Text: {current_button.get('request_button_text', 'N/A')}\n"
        button_text += f"• URL: {current_button.get('request_button_url', 'N/A')}\n\n"
        button_text += f"<b>Usage:</b> <code>/button Button Text | https://t.me/channel</code>"
        return await message.reply_text(button_text)
    
    button_data = message.text.split(" ", 1)[1]
    
    if '|' not in button_data:
        return await message.reply_text("❌ Invalid format! Use: <code>/button Text | URL</code>")
    
    text, url = button_data.split('|', 1)
    text = text.strip()
    url = url.strip()
    
    if not text or not url:
        return await message.reply_text("❌ Both text and URL are required!")
    
    user_post_data[user_id]["request_button_text"] = text
    user_post_data[user_id]["request_button_url"] = url
    
    await message.reply_text("✅ Button updated successfully!")
    
    # Update preview
    preview_msg_id = user_post_data[user_id].get("preview_message_id")
    if preview_msg_id:
        await show_preview(client, message.chat.id, user_id, preview_msg_id)

@Client.on_message(filters.command("addfile") & filters.user(ADMINS) & filters.reply)
async def add_file_command(client, message):
    user_id = message.from_user.id
    
    if not is_in_preview_mode(user_id):
        return await message.reply_text("❌ No active post session. Use <code>/link movie_name</code> first.")
    
    replied_msg = message.reply_to_message
    file_obj = None
    file_name = None
    
    # Check for different file types
    if replied_msg.document:
        file_obj = replied_msg.document
        file_name = replied_msg.document.file_name
    elif replied_msg.video:
        file_obj = replied_msg.video
        file_name = getattr(replied_msg.video, 'file_name', 'Video File')
    elif replied_msg.audio:
        file_obj = replied_msg.audio
        file_name = getattr(replied_msg.audio, 'file_name', 'Audio File')
    
    if not file_obj:
        return await message.reply_text("❌ Please reply to a valid file (document, video, or audio).")
    
    # Check if file already exists
    existing_files = user_post_data[user_id]["original_files"]
    file_exists = any(
        hasattr(f, 'file_id') and f.file_id == file_obj.file_id 
        for f in existing_files
    )
    
    if file_exists:
        return await message.reply_text("❌ This file is already in the list.")
    
    # Add the file
    user_post_data[user_id]["original_files"].append(file_obj)
    await message.reply_text(f"✅ Added: {file_name}")
    
    # Update preview
    preview_msg_id = user_post_data[user_id].get("preview_message_id")
    if preview_msg_id:
        await show_preview(client, message.chat.id, user_id, preview_msg_id)

@Client.on_message(filters.command("dropfile") & filters.user(ADMINS))
async def drop_file_command(client, message):
    user_id = message.from_user.id
    
    if not is_in_preview_mode(user_id):
        return await message.reply_text("❌ No active post session. Use <code>/link movie_name</code> first.")
    
    if len(message.command) == 1:
        return await message.reply_text("📝 <b>Usage:</b> <code>/dropfile 3</code> (to remove file number 3)\n\nUse <code>/listfiles</code> to see file numbers.")
    
    try:
        file_number = int(message.command[1])
        files = user_post_data[user_id]["original_files"]
        
        if file_number < 1 or file_number > len(files):
            return await message.reply_text(f"❌ Invalid file number! Use 1-{len(files)}")
        
        # Add to removed files (convert to 0-based index)
        file_index = file_number - 1
        removed_files = user_post_data[user_id].get("removed_files", set())
        removed_files.add(file_index)
        user_post_data[user_id]["removed_files"] = removed_files
        
        file_name = getattr(files[file_index], 'file_name', 'Unknown File')
        await message.reply_text(f"✅ Removed: {file_name}")
        
        # Update preview
        preview_msg_id = user_post_data[user_id].get("preview_message_id")
        if preview_msg_id:
            await show_preview(client, message.chat.id, user_id, preview_msg_id)
            
    except ValueError:
        await message.reply_text("❌ Please provide a valid file number!")

@Client.on_message(filters.command("listfiles") & filters.user(ADMINS))
async def list_files_command(client, message):
    user_id = message.from_user.id
    
    if not is_in_preview_mode(user_id):
        return await message.reply_text("❌ No active post session. Use <code>/link movie_name</code> first.")
    
    data = user_post_data[user_id]
    files = data["original_files"]
    removed_files = data.get("removed_files", set())
    
    if not files:
        return await message.reply_text("❌ No files found!")
    
    file_text = f"📁 <b>ALL FILES ({len(files)} total)</b>\n\n"
    
    for i, file in enumerate(files):
        status = "❌" if i in removed_files else "✅"
        file_name = getattr(file, 'file_name', 'Unknown File')
        file_size = get_size(getattr(file, 'file_size', 0))
        
        file_text += f"{i+1}. {status} {file_name}\n"
        file_text += f"    📦 {file_size}\n\n"
    
    active_count = len(files) - len(removed_files)
    file_text += f"📊 <b>Active:</b> {active_count} | <b>Removed:</b> {len(removed_files)}"
    
    await message.reply_text(file_text)

@Client.on_message(filters.command("cancel") & filters.user(ADMINS))
async def cancel_post_command(client, message):
    user_id = message.from_user.id
    
    if not is_in_preview_mode(user_id):
        return await message.reply_text("❌ No active post session found.")
    
    del user_post_data[user_id]
    await message.reply_text("❌ <b>OPERATION CANCELLED</b>\n\nUse <code>/link movie_name</code> to start again.")
