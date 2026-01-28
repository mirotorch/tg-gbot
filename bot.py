import asyncio
import logging
import os

from aiogram import Bot, Dispatcher, F, types
from yt_dlp import YoutubeDL

API_TOKEN = os.getenv("GBOT_TOKEN")

logging.basicConfig(level=logging.INFO)

bot = Bot(token=API_TOKEN)
dp = Dispatcher()

ydl_opts = {
    "format": "best",
    "outtmpl": "downloads/%(title)s.%(ext)s",
    "noplaylist": True,
}


def download_media(url: str) -> str:
    with YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)
        filename = ydl.prepare_filename(info)
        return filename


@dp.message(F.text)
async def download_video(message: types.Message):
    url = message.text
    if not url.startswith(("http", "www")):
        await message.reply("The message is not an URL")
        return

    status_msg = await message.reply("Loading...")

    try:
        loop = asyncio.get_event_loop()
        filename = await loop.run_in_executor(None, download_media, url)

        if filename:
            await message.reply_video(types.FSInputFile(filename))
            os.remove(filename)
            await status_msg.delete()
        else:
            await status_msg.edit_text("Failed to download the video")

    except Exception as e:
        await status_msg.edit_text(f"Error: {e}")


async def main():
    await dp.start_polling(bot)


if __name__ == "__main__":
    if not os.path.exists("downloads"):
        os.makedirs("downloads")
    asyncio.run(main())
