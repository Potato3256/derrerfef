import re
import discord
import dotenv
import os
from discord.ext import commands
from discord import app_commands
from discord.ui import Button, View
from instagrapi import Client
import re
import asyncio
from PIL import Image, ImageDraw
import io
import replicate

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
CATEGORY_ID = 1312128808979140658  # カテゴリーID


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

    # チャンネルIDの取得
    channel_id = interaction.channel_id
    print(f"コマンドが発行されたチャンネルID: {channel_id}")

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

            # 新しいチャンネルを作成
            channel = await guild.create_text_channel(f"ticket-{member.name}", category=category)

            # チャンネル作成後、そのIDを取得
            channel_id = channel.id
            print(f"作成されたチャンネルのID: {channel_id}")

            # 作成したチャンネルにアクセス権限を設定
            await channel.set_permissions(guild.default_role, send_messages=False)
            await channel.set_permissions(member, send_messages=True)
            await channel.send(f"{member.mention} \n **InstagramのアカウントURLを送信してください。**")

            # 作成されたチャンネルのリンクを送信
            await interaction.response.send_message(f"チケットが作成されました: {channel.mention}", ephemeral=True)

    except Exception as e:
        await interaction.response.send_message(f"エラーが発生しました: {str(e)}", ephemeral=True)


# Instagramアカウント情報の処理
def extract_username_from_url(url: str):
    match = re.match(r"https://www.instagram.com/([a-zA-Z0-9_.]+)", url)
    return match.group(1) if match else None

def create_base_image(width=300, height=30, bg_color=(255, 255, 255), border_color=(0, 0, 0)):
    img = Image.new('RGB', (width, height), bg_color)
    draw = ImageDraw.Draw(img)
    
    border_thickness = 2  # 外枠の太さ
    draw.rectangle([0, 0, width, height], outline=border_color, width=border_thickness)
    
    fill_color = (200, 200, 200)  # ゲージの空白部分（灰色）
    draw.rectangle([border_thickness, border_thickness, width - border_thickness, height - border_thickness], fill=fill_color)

    return img

class ConfirmButtons(discord.ui.View):
    def __init__(self, user_info ,ticket_channel):
        super().__init__(timeout=None)  # タイムアウトなし
        self.user_info = user_info
        self.ticket_channel = ticket_channel

    @discord.ui.button(label="はい", style=discord.ButtonStyle.green)
    async def confirm_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.user_info.follower_count >= 2000:
            await interaction.response.send_message("**フォロワー2000人以上のアカウントはこちらで受け付けていません;; **")
        else:
            # 送金ボタンと送金確認ボタンをビューに追加
            send_money_button = discord.ui.Button(label="送金", style=discord.ButtonStyle.green, url="https://qr.paypay.ne.jp/p2p01_4iAho1YsmQ08Hwrb")
            confirm_send_button = discord.ui.Button(label="送金確認", style=discord.ButtonStyle.blurple)
            
            # 送金確認ボタンのコールバック設定
            async def confirm_send(interaction: discord.Interaction):
                progress_message = None
                try:
                    # 送金確認後の進行状況更新
                    progress_message = await interaction.response.send_message("送金処理中... 進行状況をお待ちください。")
                    progress_bar = 0

                    while progress_bar <= 100:
                        img = create_base_image()
                        draw = ImageDraw.Draw(img)
                        
                        width, height = img.size
                        filled_width = int((progress_bar / 100) * width)
                        draw.rectangle([0, 0, filled_width, height], fill=(0, 0, 255))  # 進行状況の青い部分

                        with io.BytesIO() as image_binary:
                            img.save(image_binary, 'PNG')
                            image_binary.seek(0)
                            await progress_message.edit(
                                content=f"送金処理中... {progress_bar}% 完了", 
                                file=discord.File(image_binary, filename="progress.png")
                            )

                        progress_bar += 1
                        await asyncio.sleep(3)

                    # Stable Diffusionを使用して最終的な画像を生成
                    model = replicate.models.get("stability-ai/stable-diffusion")
                    version = model.versions.get("db21e1e6c51c0d3f3d8c2787e60f8b75")
                    output = version.predict(prompt="A beautiful digital artwork of a money transfer process")

                    # 生成した画像のURLを使って画像を取得し、メッセージを更新
                    final_image_url = output[0]
                    await progress_message.edit(content="送金処理が完了しました！", embed=None, file=discord.File(final_image_url))

                except Exception as e:
                    print(f"エラーが発生しました: {e}")
                    if progress_message:
                        await progress_message.edit(content="送金処理中にエラーが発生しました。再度お試しください。")

            confirm_send_button.callback = confirm_send

            # 新しいビューを作成し、ボタンを追加
            view = discord.ui.View()
            view.add_item(send_money_button)
            view.add_item(confirm_send_button)

            # 依頼料金メッセージを送信し、ビューを表示
            await interaction.response.send_message("**依頼料金3000円頂戴します!\n送金できましたら送金確認ボタンを押してください**", view=view)
            
    @discord.ui.button(label="違う", style=discord.ButtonStyle.red)
    async def cancel_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message("やりなおしてください。")

        delete_button = discord.ui.Button(label="チケットを削除", style=discord.ButtonStyle.danger)

        async def delete_ticket_button(interaction: discord.Interaction):
            await self.ticket_channel.delete()
            await interaction.response.send_message(f"{self.ticket_channel.name} チャンネルは削除されました。")

        delete_button.callback = delete_ticket_button
        view = discord.ui.View()
        view.add_item(delete_button)
        await interaction.followup.send("チケットを削除するには以下のボタンを押してください。", view=view)

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

        await message.channel.send("**アカウント情報を取得中です...**")

        user_id = message.author.id
        if user_id not in instagram_clients:
            await message.channel.send("**不具合がありました管理者をメンションしてください**")
            return

        client = instagram_clients[user_id]
        try:
            profile = client.user_id_from_username(username)
            user_info = client.user_info(profile)

            # エラー回避のために辞書のデフォルト値を指定
            username = getattr(user_info, "username", "不明")
            full_name = getattr(user_info, "full_name", "不明")
            biography = getattr(user_info, "biography", "情報なし")
            follower_count = getattr(user_info, "follower_count", "不明")
            following_count = getattr(user_info, "following_count", "不明")
            profile_pic_url_hd = getattr(user_info, "profile_pic_url_hd", None)

            embed = discord.Embed(title=f"**{username}**のプロフィール情報", color=0x1DA1F2)
            embed.add_field(name="フルネーム", value=full_name, inline=False)
            embed.add_field(name="自己紹介", value=biography, inline=False)
            embed.add_field(name="フォロワー数", value=follower_count, inline=True)
            embed.add_field(name="フォロー中", value=following_count, inline=True)
            if profile_pic_url_hd:
                embed.set_thumbnail(url=profile_pic_url_hd)

            await message.channel.send(embed=embed)  # プロフィール情報を表示

            # ボタンを別メッセージで送信
            view = ConfirmButtons(user_info, message.channel)
            await message.channel.send("**このアカウントでお間違いないですか？**", view=view)

        except Exception as e:
            await message.channel.send(f"アカウント情報の取得に失敗しました: {str(e)}")



# サーバー起動
server_thread()

# Botを実行
bot.run(TOKEN)

