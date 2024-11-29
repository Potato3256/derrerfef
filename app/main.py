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
intents.message_content = True
intents.members = True

# Botの初期化
bot = commands.Bot(command_prefix='!', intents=intents)
instagram_clients = {}  # ユーザーIDごとのInstagramクライアント保存用

GUILD_ID = 1291316762339446835  # ギルドID
CATEGORY_ID = 1311757863512965161  # カテゴリーID


@bot.event
async def on_ready():
    print(f'Logged in as {bot.user}')
    try:
        synced = await bot.tree.sync()  # コマンドを同期
        print(f"Synced {len(synced)} commands.")
    except Exception as e:
        print(f"コマンド同期中にエラーが発生しました: {e}")


# ログインコマンド
@bot.tree.command(name='instagram_login', description='Instagramにログインします。')
@app_commands.describe(username='Instagramのユーザー名', password='Instagramのパスワード')
async def instagram_login(interaction: discord.Interaction, username: str, password: str):
    await interaction.response.defer(ephemeral=True)
    client = Client()
    try:
        client.login(username, password)
        instagram_clients[interaction.user.id] = client
        await interaction.followup.send("ログイン成功！", ephemeral=True)
    except Exception as e:
        await interaction.followup.send(f"ログインに失敗しました: {str(e)}", ephemeral=True)


# Embed作成コマンド
@bot.tree.command(name="create_embed", description="Embedを作成して購入ボタンを追加します。")
@app_commands.describe(image="画像を添付してください", description="Embedに表示する説明")
async def create_embed(interaction: discord.Interaction, image: discord.Attachment, description: str):
    await interaction.response.defer(ephemeral=False)
    image_url = image.url
    embed = discord.Embed(title="購入情報", description=description, color=discord.Color.blue())
    embed.set_image(url=image_url)
    embed.set_footer(text="購入ボタンを押してください。")

    view = discord.ui.View()
    button = discord.ui.Button(label="購入", style=discord.ButtonStyle.green, custom_id="create_ticket")
    view.add_item(button)
    await interaction.followup.send(embed=embed, view=view, ephemeral=False)


# チケット作成ボタンの処理
@bot.event
async def on_interaction(interaction: discord.Interaction):
    try:
        custom_id = interaction.data.get("custom_id")
        if custom_id == "create_ticket":
            guild = bot.get_guild(GUILD_ID)
            if not guild:
                return await interaction.response.send_message("サーバー情報を取得できませんでした。", ephemeral=True)

            member = interaction.user
            category = guild.get_channel(CATEGORY_ID)
            if category is None:
                return await interaction.response.send_message("指定されたカテゴリーが見つかりません。", ephemeral=True)

            channel = await guild.create_text_channel(f"ticket-{member.name}", category=category)
            await channel.set_permissions(guild.default_role, send_messages=False)
            await channel.set_permissions(member, send_messages=True)
            await channel.send(f"{member.mention} チケットが作成されました！\nInstagramのアカウントURLを送信してください。")
            await interaction.response.send_message(f"チケットが作成されました: {channel.mention}", ephemeral=True)
    except Exception as e:
        await interaction.response.send_message(f"エラーが発生しました: {str(e)}", ephemeral=True)


# Instagramアカウント情報の処理
def extract_username_from_url(url: str):
    match = re.match(r"https://www.instagram.com/([a-zA-Z0-9_.]+)", url)
    return match.group(1) if match else None


@bot.event
async def on_message(message: discord.Message):
    if message.author.bot:
        return

    if message.channel.name.startswith("ticket-"):
        username_or_url = message.content.strip()
        username = extract_username_from_url(username_or_url) or username_or_url

        if not re.match(r'^[a-zA-Z0-9_.]+$', username):
            await message.channel.send("無効なユーザー名です。正しいユーザー名を入力してください。")
            return

        await message.channel.send("アカウント情報を取得中です...")
        user_id = message.author.id
        if user_id not in instagram_clients:
            await message.channel.send("Instagramにログインしていません。")
            return

        client = instagram_clients[user_id]
        try:
            profile = client.user_id_from_username(username)
            user_info = client.user_info(profile)
            embed = discord.Embed(title=f"**{user_info.username}**のプロフィール情報", color=0x1DA1F2)
            embed.add_field(name="フルネーム", value=user_info.full_name, inline=False)
            embed.add_field(name="自己紹介", value=user_info.biography or "情報なし", inline=False)
            embed.add_field(name="フォロワー数", value=user_info.follower_count, inline=True)
            embed.add_field(name="フォロー中", value=user_info.following_count, inline=True)
            embed.set_thumbnail(url=user_info.profile_pic_url_hd)

            class ConfirmButtons(View):
                @discord.ui.button(label="はい", style=discord.ButtonStyle.green)
                async def confirm_button(self, button: discord.ui.Button, interaction: discord.Interaction):
                    if user_info.follower_count >= 2000:
                        await interaction.response.send_message("このアカウントはフォロワー数が多すぎます。", ephemeral=True)
                    else:
                        await interaction.response.send_message("https://qr.paypay.ne.jp/p2p01_4iAho1YsmQ08Hwrb に3000円を送金してください。", ephemeral=True)

                @discord.ui.button(label="いいえ", style=discord.ButtonStyle.red)
                async def cancel_button(self, button: discord.ui.Button, interaction: discord.Interaction):
                    await interaction.response.send_message("やりなおしてください。", ephemeral=True)

            view = ConfirmButtons()
            await message.channel.send(embed=embed, view=view)
        except Exception as e:
            await message.channel.send(f"アカウント情報の取得に失敗しました: {str(e)}")

    await bot.process_commands(message)


# サーバー起動
server_thread()

# Botを実行
bot.run(TOKEN)

