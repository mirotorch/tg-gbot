import asyncio
import logging
import os

from aiogram import Bot, Dispatcher, F, types
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup
from dotenv import load_dotenv
from yt_dlp import YoutubeDL

load_dotenv()
API_TOKEN = os.getenv("GBOT_TOKEN")
ADMIN_ID = os.getenv("GBOT_ADMIN_ID")

logging.basicConfig(level=logging.INFO)

bot = Bot(token=API_TOKEN)
dp = Dispatcher()

ydl_opts = {
    "format": "best",
    "outtmpl": "downloads/%(title)s.%(ext)s",
    "noplaylist": True,
}

AUTHORIZED_FILE = "authorized_users.txt"
authorized_users: set = set()
waiting_for_confirmation: set = set()


def load_users():
    if not os.path.exists(AUTHORIZED_FILE):
        return
    with open(AUTHORIZED_FILE, "r") as f:
        for line in f:
            line = line.strip()
            if line.isdigit():
                authorized_users.add(int(line))
    logging.info(f"Loaded {len(authorized_users)} authorized users.")


def save_new_user(user_id: int):
    authorized_users.add(user_id)
    with open(AUTHORIZED_FILE, "a") as f:
        f.write(f"{user_id}\n")


def download_media(url: str) -> str:
    with YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)
        filename = ydl.prepare_filename(info)
        return filename


async def request_admin_confirmation(message: types.Message):
    user = message.from_user
    waiting_for_confirmation.add(user.id)

    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✅ Approve", callback_data=f"approve_{user.id}"
                ),
                InlineKeyboardButton(
                    text="❌ Reject", callback_data=f"reject_{user.id}"
                ),
            ]
        ]
    )

    admin_text = (
        f"🔔 <b>New access request</b>\n"
        f"User: {user.full_name}\n"
        f"Username: @{user.username}\n"
        f"ID: <code>{user.id}</code>"
    )

    try:
        await bot.send_message(
            chat_id=ADMIN_ID, text=admin_text, reply_markup=kb, parse_mode="HTML"
        )
    except Exception as e:
        logging.error(f"Failed to send request to admin: {e}")


@dp.callback_query(F.data.startswith(("approve_", "reject_")))
async def handle_admin_decision(callback: CallbackQuery):
    action, user_id_str = callback.data.split("_")
    user_id = int(user_id_str)

    if action == "approve":
        save_new_user(user_id)
        if user_id in waiting_for_confirmation:
            waiting_for_confirmation.remove(user_id)

        await callback.message.edit_text(f"✅ User {user_id} added to the whitelist.")
        try:
            await bot.send_message(
                user_id,
                "The administrator has confirmed your access. You can now send links.",
            )
        except:
            pass

    elif action == "reject":
        if user_id in waiting_for_confirmation:
            waiting_for_confirmation.remove(user_id)
        await callback.message.edit_text(f"❌ Request from {user_id} is rejected.")
        try:
            await bot.send_message(
                user_id, "⛔ Administrator has rejected your request."
            )
        except:
            pass


@dp.message(F.text)
async def handle_message(message: types.Message):
    user_id = message.from_user.id

    if user_id == ADMIN_ID:
        pass
    elif user_id not in authorized_users:
        if user_id not in waiting_for_confirmation:
            await message.reply(
                "🔒 You are not authorized. The request has been sent to the administrator, please wait."
            )
            await request_admin_confirmation(message)
        else:
            await message.reply(
                "⏳ Your request is still being reviewed by the administrator."
            )
        return

    url = message.text
    if not url.startswith(("http", "www")):
        await message.reply("This doesn't look like a link")
        return

    status_msg = await message.reply("⏳ Downloading...")

    try:
        loop = asyncio.get_event_loop()
        filename = await loop.run_in_executor(None, download_media, url)

        if filename and os.path.exists(filename):
            await message.reply_video(types.FSInputFile(filename))
            os.remove(filename)
            await status_msg.delete()
        else:
            await status_msg.edit_text("❌ Failed to download the video.")

    except Exception as e:
        await status_msg.edit_text(f"Error: {str(e)}")
        logging.error(e)


async def main():
    load_users()
    if not os.path.exists("downloads"):
        os.makedirs("downloads")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
