import discord
import dotenv
import os  # osモジュールのインポート

from server import server_thread

# 環境変数をロード
dotenv.load_dotenv()

# 環境変数からトークンを取得
TOKEN = os.environ.get("TOKEN")
if not TOKEN:
    raise ValueError("TOKENが環境変数に設定されていません。")

# Discordの設定
intents = discord.Intents.default()
intents.message_content = True
intents.voice_states = True
client = discord.Client(intents=intents)

@client.event
async def on_message(message):
    if message.author == client.user:
        return

    if message.content.startswith('$hello'):
        await message.channel.send('Hello!')

# Koyeb用 サーバー立ち上げ
server_thread()

# Discordクライアントを起動
client.run(TOKEN)
