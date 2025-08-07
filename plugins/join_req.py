from pyrogram import Client, filters
from pyrogram.types import ChatJoinRequest
from database.users_chats_db import db
from info import ADMINS, AUTH_CHANNEL, AUTH_REQ_CHANNEL, AUTO_APPROVE_AUTH_REQ_CHANNEL



# Auto-approve join requests for AUTH_CHANNEL
@Client.on_chat_join_request(filters.chat(AUTH_CHANNEL))
async def approve_auth_channel(client, message: ChatJoinRequest):
    try:
        await client.approve_chat_join_request(message.chat.id, message.from_user.id)
    except Exception as e:
        print(f"Failed to auto-approve AUTH_CHANNEL join request: {e}")
    if not await db.find_join_req(message.from_user.id):
        await db.add_join_req(message.from_user.id)


# Conditionally auto-approve join requests for AUTH_REQ_CHANNEL
@Client.on_chat_join_request(filters.chat(AUTH_REQ_CHANNEL))
async def approve_auth_req_channel(client, message: ChatJoinRequest):
    if AUTO_APPROVE_AUTH_REQ_CHANNEL:
        try:
            await client.approve_chat_join_request(message.chat.id, message.from_user.id)
        except Exception as e:
            print(f"Failed to auto-approve AUTH_REQ_CHANNEL join request: {e}")
    # If AUTO_APPROVE_AUTH_REQ_CHANNEL is False, do not approve (manual approval required)


@Client.on_message(filters.command("delreq") & filters.private & filters.user(ADMINS))
async def del_requests(client, message):
    await db.del_join_req()
    await message.reply("<b>⚙ ꜱᴜᴄᴄᴇꜱꜱғᴜʟʟʏ ᴄʜᴀɴɴᴇʟ ʟᴇғᴛ ᴜꜱᴇʀꜱ ᴅᴇʟᴇᴛᴇᴅ</b>")
