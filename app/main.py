import discord
import dotenv
import os

from server import server_thread

# 環境変数をロード
dotenv.load_dotenv()
TOKEN = os.environ.get("TOKEN")

# 必要な特権インテントを設定
intents = discord.Intents.default()
intents.message_content = True  # メッセージ内容の取得
intents.members = True          # サーバーメンバー情報の取得
intents.presences = True        # プレゼンス情報の取得（必要な場合）

# クライアントの初期化
client = discord.Client(intents=intents)

@client.event
async def on_ready():
    print(f'Logged in as {client.user}')

@client.event
async def on_message(message):
    if message.author == client.user:
        return
    if message.content.startswith('$hello'):
        await message.channel.send('Hello!')

# サーバー起動
server_thread()

# Botを実行
client.run(TOKEN)

