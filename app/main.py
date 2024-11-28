import discord
import dotenv
import os
from discord.ext import commands
from discord import app_commands
from discord.ui import Button, View
from instagrapi import Client
import re

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

bot = commands.Bot(command_prefix='!', intents=intents)
instagram_clients = {}  # ユーザーIDごとのInstagramクライアント保存用

GUILD_ID = 1291316762339446835  # ギルドID
CATEGORY_ID = 1311757863512965161  # カテゴリーID

# ログインコマンド
@bot.tree.command(name='instagram_login', description='Instagramにログインします。')
@discord.app_commands.describe(username='Instagramのユーザー名', password='Instagramのパスワード')
async def instagram_login(interaction: discord.Interaction, username: str, password: str):
    await interaction.response.defer()  # 応答を遅延
    client = Client()
    try:
        # Instagramログイン
        client.login(username, password)
        instagram_clients[interaction.user.id] = client
        await interaction.followup.send("ログイン成功！", ephemeral=True)
    except Exception as e:
        await interaction.followup.send(f"ログインに失敗しました: {str(e)}", ephemeral=True)

# Embed作成コマンド（オプションで画像を指定）
@bot.event
async def on_interaction(interaction: discord.Interaction):
    try:
        # interactionのcustom_idを取得
        custom_id = interaction.data.get("custom_id")

        # "create_ticket" ボタンがクリックされた場合
        if custom_id == "create_ticket":
            # ギルドとカテゴリを取得
            guild = bot.get_guild(GUILD_ID)
            if not guild:
                return await interaction.response.send_message("サーバー情報を取得できませんでした。", ephemeral=True)

            # interaction.userでユーザー情報を取得（すでにmember情報が含まれている）
            member = interaction.user

            # カテゴリーを取得
            category = guild.get_channel(CATEGORY_ID)
            if category is None:
                return await interaction.response.send_message("指定されたカテゴリーが見つかりません。", ephemeral=True)

            # カテゴリー内にチャンネルを作成
            channel = await guild.create_text_channel(f"ticket-{member.name}", category=category)

            # アクセス制限を設定（@everyone に送信権限をなし、ユーザーに送信権限を付与）
            await channel.set_permissions(guild.default_role, send_messages=False)  # @everyone に送信権限をなし
            await channel.set_permissions(member, send_messages=True)

            # チャンネル作成者（ユーザー）にメッセージ送信権限を与え、メッセージを送信
            await channel.send(f"{member.mention} チケットが作成されました！\nInstagramのアカウントURLを送信してください。")

            # インタラクションに応答
            await interaction.response.send_message("チケットが作成されました# ticket-{member.name}", ephemeral=True)
    except Exception as e:
        # エラー処理
        await interaction.response.send_message(f"エラーが発生しました: {str(e)}", ephemeral=True)

# ボタンを作成するコマンド
@bot.tree.command(name="create_embed", description="Embedを作成して購入ボタンを追加します。")
@discord.app_commands.describe(image="画像を添付してください", description="Embedに表示する説明")
async def create_embed(interaction: discord.Interaction, image: discord.Attachment, description: str):
    await interaction.response.defer(ephemeral=False)  # 応答を遅延（ephemeralで送信）
    # 添付された画像URLを取得
    image_url = image.url

    # Embed作成
    embed = discord.Embed(title="購入情報", description=description, color=discord.Color.blue())
    embed.set_image(url=image_url)  # 画像URLをセット
    embed.set_footer(text="購入ボタンを押してください。")

    # Viewを作成
    view = discord.ui.View()

    # "create_ticket" カスタムIDを持つボタンを作成
    button = discord.ui.Button(label="購入", style=discord.ButtonStyle.green, custom_id="create_ticket")

    # ボタンをViewに追加
    view.add_item(button)

    # EmbedとViewを送信
    await interaction.followup.send(embed=embed, view=view, ephemeral=False)
    
# チケットでのURL受け取りと確認
def extract_username_from_url(url: str):
    match = re.match(r"https://www.instagram.com/([a-zA-Z0-9_.]+)", url)
    if match:
        return match.group(1)
    return None

@bot.event
async def on_message(message: discord.Message):
    # ボットからのメッセージは無視
    if message.author.bot:
        return

    # チケットチャンネル内での最初のメッセージを受け取る
    if message.channel.name.startswith("ticket-"):
        # チャンネルが作成されたときに送信される最初のメッセージを受け取る
        username_or_url = message.content.strip()  # ユーザー名またはURLを受け取る

        # InstagramのURL形式かユーザー名形式かをチェック
        username = extract_username_from_url(username_or_url)
        if not username:
            # URLでない場合はそのままユーザー名とみなす
            username = username_or_url

        # ユーザー名が英数字、アンダースコア、ピリオドで構成されているかを確認
        if not re.match(r'^[a-zA-Z0-9_.]+$', username):
            await message.channel.send("無効なユーザー名です。正しいユーザー名を入力してください。")
            return

        await message.channel.send("アカウント情報を取得中です...")

        # Instagram情報を取得
        user_id = message.author.id
        if user_id not in instagram_clients:
            await message.channel.send("Instagramにログインしていません。")
            return

        client = instagram_clients[user_id]
        try:
            # ユーザー名で情報を取得
            profile = client.user_id_from_username(username)
            user_info = client.user_info(profile)

            # 埋め込みメッセージの作成
            embed = discord.Embed(title=f"**{user_info.username}**のプロフィール情報", color=0x1DA1F2)
            embed.add_field(name="フルネーム", value=user_info.full_name, inline=False)
            embed.add_field(name="自己紹介", value=user_info.biography or "情報なし", inline=False)
            embed.add_field(name="フォロワー数", value=user_info.follower_count, inline=True)
            embed.add_field(name="フォロー中", value=user_info.following_count, inline=True)
            embed.set_thumbnail(url=user_info.profile_pic_url_hd)

            # 確認ボタンの作成
            class ConfirmButtons(View):
                @discord.ui.button(label="はい", style=discord.ButtonStyle.green)
                async def confirm_button(self, button: discord.ui.Button, interaction: discord.Interaction):
                    if user_info.follower_count >= 2000:
                        await interaction.response.send_message("このアカウントは1000人を超えているので対応しておりません。", ephemeral=True)
                    else:
                        await interaction.response.send_message("https://qr.paypay.ne.jp/p2p01_4iAho1YsmQ08Hwrb に3000円を送金お願いします。", ephemeral=True)

                @discord.ui.button(label="いいえ", style=discord.ButtonStyle.red)
                async def cancel_button(self, button: discord.ui.Button, interaction: discord.Interaction):
                    await interaction.response.send_message("やりなおしてください。", ephemeral=True)

            # 確認ボタン付きのビューを送信
            view = ConfirmButtons()
            await message.channel.send(embed=embed, view=view)
        except Exception as e:
            await message.channel.send(f"アカウント情報の取得に失敗しました: {str(e)}")

    # 他のコマンドを処理する
    await bot.process_commands(message)  # これが無いと、メッセージがコマンドとして処理されない

# サーバー起動
server_thread()

# Botを実行
client.run(TOKEN)

