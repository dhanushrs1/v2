import os
import requests
import json
from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from typing import Dict, Any
import asyncio

# Configuration
MAX_UPLOAD_SIZE = 5 * 1024 * 1024  # 5 MB - Change this value to customize max upload size


class FileUploader:
    """Handles file uploads to multiple services"""
    
    def __init__(self):
        self.services = {
            "envs": {
                "name": "Envs.sh",
                "url": "https://envs.sh",
                "method": "POST",
                "file_param": "file",
                "max_size": 512 * 1024 * 1024,  # 512 MB
                "response_type": "text"
            },
            "telegraph": {
                "name": "Telegraph",
                "url": "https://telegra.ph/upload",
                "method": "POST",
                "file_param": "file",
                "max_size": 5 * 1024 * 1024,  # 5 MB
                "response_type": "json"
            },
            "catbox": {
                "name": "Catbox.moe",
                "url": "https://catbox.moe/user/api.php",
                "method": "POST",
                "file_param": "fileToUpload",
                "max_size": 200 * 1024 * 1024,  # 200 MB
                "response_type": "text",
                "extra_data": {"reqtype": "fileupload"}
            },
            "fileio": {
                "name": "File.io",
                "url": "https://file.io",
                "method": "POST",
                "file_param": "file",
                "max_size": 100 * 1024 * 1024,  # 100 MB
                "response_type": "json"
            },
            "uguu": {
                "name": "Uguu.se",
                "url": "https://uguu.se/upload.php",
                "method": "POST",
                "file_param": "files[]",
                "max_size": 128 * 1024 * 1024,  # 128 MB
                "response_type": "json"
            },
            "anonfiles": {
                "name": "AnonFiles",
                "url": "https://api.anonfiles.com/upload",
                "method": "POST",
                "file_param": "file",
                "max_size": 20 * 1024 * 1024 * 1024,  # 20 GB
                "response_type": "json"
            }
        }
    
    async def upload_file(self, file_path: str, service_key: str) -> Dict[str, Any]:
        """Upload file to specified service"""
        if service_key not in self.services:
            return {"success": False, "error": "Invalid service"}
        
        service = self.services[service_key]
        
        try:
            # Check file size against our maximum limit first
            file_size = os.path.getsize(file_path)
            if file_size > MAX_UPLOAD_SIZE:
                max_size_mb = MAX_UPLOAD_SIZE / (1024 * 1024)
                current_size_mb = file_size / (1024 * 1024)
                return {
                    "success": False, 
                    "error": f"File size ({current_size_mb:.2f} MB) exceeds maximum limit of {max_size_mb:.0f} MB"
                }
            
            # Also check service-specific limits
            if file_size > service["max_size"]:
                return {
                    "success": False, 
                    "error": f"File size ({file_size / (1024*1024):.2f} MB) exceeds service limit ({service['max_size'] / (1024*1024):.2f} MB)"
                }
            
            with open(file_path, "rb") as f:
                files = {service["file_param"]: f}
                data = service.get("extra_data", {})
                
                response = requests.post(
                    service["url"], 
                    files=files, 
                    data=data,
                    timeout=30
                )
                
                if response.status_code == 200:
                    return self._parse_response(response, service, service_key)
                else:
                    return {
                        "success": False, 
                        "error": f"HTTP {response.status_code}: {response.text[:100]}"
                    }
                    
        except requests.exceptions.RequestException as e:
            return {"success": False, "error": f"Network error: {str(e)}"}
        except Exception as e:
            return {"success": False, "error": f"Upload error: {str(e)}"}
    
    def _parse_response(self, response, service, service_key):
        """Parse response based on service type"""
        try:
            if service["response_type"] == "json":
                data = response.json()
                
                if service_key == "telegraph":
                    if data and len(data) > 0:
                        return {"success": True, "url": f"https://telegra.ph{data[0]['src']}"}
                
                elif service_key == "fileio":
                    if data.get("success"):
                        return {"success": True, "url": data["link"]}
                
                elif service_key == "uguu":
                    if "files" in data and len(data["files"]) > 0:
                        return {"success": True, "url": data["files"][0]["url"]}
                
                elif service_key == "anonfiles":
                    if data.get("status") and data["data"]:
                        return {"success": True, "url": data["data"]["file"]["url"]["full"]}
                
                return {"success": False, "error": "Invalid response format"}
                
            else:  # text response
                url = response.text.strip()
                if url.startswith("http"):
                    return {"success": True, "url": url}
                else:
                    return {"success": False, "error": "Invalid URL received"}
                    
        except Exception as e:
            return {"success": False, "error": f"Response parsing error: {str(e)}"}
    
    def get_service_info(self, service_key: str) -> str:
        """Get service information for display"""
        service = self.services.get(service_key)
        if not service:
            return "Unknown service"
        
        max_size_mb = service["max_size"] / (1024 * 1024)
        if max_size_mb >= 1024:
            size_str = f"{max_size_mb / 1024:.1f} GB"
        else:
            size_str = f"{max_size_mb:.0f} MB"
            
        return f"{service['name']} (Max: {size_str})"


# Initialize uploader
uploader = FileUploader()

# Store pending uploads
pending_uploads = {}


@Client.on_message(
    filters.command(["upload", "img", "cup", "telegraph"], prefixes="/") & filters.reply
)
async def upload_command(client, message: Message):
    """Handle upload command with service selection"""
    reply = message.reply_to_message

    if not reply.media:
        return await message.reply_text("❌ Please reply to a media file to upload it.")

    # Check file size against our maximum limit
    file_size = 0
    if reply.document:
        file_size = reply.document.file_size
    elif reply.photo:
        file_size = reply.photo.file_size
    elif reply.video:
        file_size = reply.video.file_size
    elif reply.audio:
        file_size = reply.audio.file_size
    elif reply.voice:
        file_size = reply.voice.file_size
    elif reply.video_note:
        file_size = reply.video_note.file_size
    elif reply.sticker:
        file_size = reply.sticker.file_size
    elif reply.animation:
        file_size = reply.animation.file_size
    
    if file_size > MAX_UPLOAD_SIZE:
        max_size_mb = MAX_UPLOAD_SIZE / (1024 * 1024)
        current_size_mb = file_size / (1024 * 1024)
        return await message.reply_text(
            f"❌ File size ({current_size_mb:.2f} MB) exceeds maximum limit of {max_size_mb:.0f} MB."
        )

    # Create service selection keyboard
    keyboard = []
    row = []
    
    for i, (key, service) in enumerate(uploader.services.items()):
        service_info = uploader.get_service_info(key)
        row.append(InlineKeyboardButton(service_info, callback_data=f"upload_{key}"))
        
        # 2 buttons per row
        if len(row) == 2:
            keyboard.append(row)
            row = []
    
    # Add remaining button if any
    if row:
        keyboard.append(row)
    
    # Add "Try All" and "Cancel" buttons
    keyboard.append([
        InlineKeyboardButton("🔄 Try All Services", callback_data="upload_all"),
        InlineKeyboardButton("❌ Cancel", callback_data="upload_cancel")
    ])

    # Store upload info for callback
    pending_uploads[message.from_user.id] = {
        "message_id": reply.id,
        "chat_id": message.chat.id,
        "original_msg": message
    }

    await message.reply_text(
        "📤 **Select Upload Service**\n\n"
        "Choose a service to upload your file or try all services automatically:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


@Client.on_callback_query(filters.regex(r"^upload_"))
async def handle_upload_callback(client, callback_query: CallbackQuery):
    """Handle service selection callback"""
    user_id = callback_query.from_user.id
    
    if user_id not in pending_uploads:
        return await callback_query.answer("❌ Upload session expired. Please try again.")
    
    action = callback_query.data.split("_", 1)[1]
    
    if action == "cancel":
        del pending_uploads[user_id]
        await callback_query.message.delete()
        return await callback_query.answer("Upload cancelled.")
    
    upload_info = pending_uploads[user_id]
    
    # Get the replied message
    try:
        replied_message = await client.get_messages(
            upload_info["chat_id"], 
            upload_info["message_id"]
        )
    except:
        del pending_uploads[user_id]
        await callback_query.message.delete()
        return await callback_query.answer("❌ Original message not found.")
    
    await callback_query.message.edit_text("⏳ **Processing...**\nDownloading file...")
    
    try:
        # Download the file
        downloaded_file = await replied_message.download()
        
        if not downloaded_file:
            await callback_query.message.edit_text("❌ Failed to download the file.")
            return
        
        if action == "all":
            # Try all services
            await try_all_services(callback_query.message, downloaded_file)
        else:
            # Upload to specific service
            await upload_to_service(callback_query.message, downloaded_file, action)
        
        # Clean up
        if os.path.exists(downloaded_file):
            os.remove(downloaded_file)
            
    except Exception as e:
        await callback_query.message.edit_text(f"❌ **Error:** {str(e)}")
    
    finally:
        if user_id in pending_uploads:
            del pending_uploads[user_id]


async def upload_to_service(message: Message, file_path: str, service_key: str):
    """Upload file to a specific service"""
    service_name = uploader.services[service_key]["name"]
    
    await message.edit_text(f"⏳ **Uploading to {service_name}...**")
    
    result = await uploader.upload_file(file_path, service_key)
    
    if result["success"]:
        await message.edit_text(
            f"✅ **Upload Successful!**\n\n"
            f"**Service:** {service_name}\n"
            f"**URL:** `{result['url']}`\n\n"
            f"**Direct Link:** {result['url']}"
        )
    else:
        await message.edit_text(
            f"❌ **Upload Failed**\n\n"
            f"**Service:** {service_name}\n"
            f"**Error:** {result['error']}\n\n"
            f"Try selecting a different service or use 'Try All Services'."
        )


async def try_all_services(message: Message, file_path: str):
    """Try uploading to all services until one succeeds"""
    await message.edit_text("🔄 **Trying all services...**\n\nThis may take a moment...")
    
    results = []
    success_found = False
    
    for service_key, service_info in uploader.services.items():
        if success_found:
            break
            
        service_name = service_info["name"]
        await message.edit_text(
            f"🔄 **Trying all services...**\n\n"
            f"Currently trying: **{service_name}**"
        )
        
        result = await uploader.upload_file(file_path, service_key)
        results.append({
            "service": service_name,
            "result": result
        })
        
        if result["success"]:
            success_found = True
            await message.edit_text(
                f"✅ **Upload Successful!**\n\n"
                f"**Service:** {service_name}\n"
                f"**URL:** `{result['url']}`\n\n"
                f"**Direct Link:** {result['url']}"
            )
            return
    
    # If no service worked, show all results
    if not success_found:
        error_text = "❌ **All services failed**\n\n"
        for res in results:
            error_text += f"**{res['service']}:** {res['result']['error'][:50]}...\n"
        
        error_text += "\n💡 Try again later or use a smaller file."
        await message.edit_text(error_text)


@Client.on_message(filters.command(["services", "uploadservices"], prefixes="/"))
async def show_services(client, message: Message):
    """Show available upload services"""
    max_size_mb = MAX_UPLOAD_SIZE / (1024 * 1024)
    text = f"📤 **Available Upload Services:**\n"
    text += f"**Maximum File Size:** {max_size_mb:.0f} MB\n\n"
    
    for key, service in uploader.services.items():
        info = uploader.get_service_info(key)
        text += f"• **{info}**\n"
    
    text += f"\n**Total Services:** {len(uploader.services)}\n"
    text += "\n**Usage:** Reply to any media with `/upload` to get started!"
    
    await message.reply_text(text)