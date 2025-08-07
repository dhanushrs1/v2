from pyrogram import Client
from pyrogram.types import InlineKeyboardButton
from info import AUTH_CHANNEL, AUTH_REQ_CHANNEL

async def generate_invite_links(client: Client):
    """
    Always generate invite links for both AUTH_CHANNEL and AUTH_REQ_CHANNEL (if different).
    Returns a list of InlineKeyboardButton rows.
    """
    buttons = []
    try:
        # AUTH_CHANNEL invite link
        auth_invite = await client.create_chat_invite_link(
            int(AUTH_CHANNEL), creates_join_request=True
        )
        buttons.append([
            InlineKeyboardButton(
                "⛔️ ᴊᴏɪɴ ᴜᴘᴅᴀᴛᴇ ᴄʜᴀɴɴᴇʟ ⛔️",
                url=auth_invite.invite_link
            )
        ])
        # AUTH_REQ_CHANNEL invite link (if different)
        if str(AUTH_REQ_CHANNEL) != str(AUTH_CHANNEL):
            req_invite = await client.create_chat_invite_link(
                int(AUTH_REQ_CHANNEL), creates_join_request=True
            )
            buttons.append([
                InlineKeyboardButton(
                    "⛔️ ᴊᴏɪɴ ʀᴇǫᴜᴇꜱᴛ ᴄʜᴀɴɴᴇʟ ⛔️",
                    url=req_invite.invite_link
                )
            ])
    except Exception as e:
        print(f"Error generating invite links: {e}")
    return buttons
