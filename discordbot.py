import os
import asyncio
import discord
from discord.ext import commands
from datetime import timedelta
from better_profanity import profanity
from detection import find_word
from dotenv import load_dotenv
import logging
from discord import app_commands

from database import create_pool

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

load_dotenv(r"C:\Users\themb\Desktop\Discord Bot Project\discord.env")

intents = discord.Intents.default()
intents.members = True
intents.message_content = True
bot: commands.Bot = commands.Bot(command_prefix=".", intents=intents)

WELCOME_CHANNEL_ID = 1541510550411026485
TEST_GUILD_ID = 1539913747471011880


# helpers

async def ensure_guild(guild_id: int): #Sets Up Guild Settings
    """Make sure every server has a settings row."""
    async with bot.pool.acquire() as conn:
        await conn.execute(
            "INSERT INTO guild_settings (guild_id) VALUES ($1) ON CONFLICT (guild_id) DO NOTHING", #Displays the Guid Serring in The Database, If the Guild is Already in the Database, it Does Nothing.
            guild_id,
        )


#def find_word(text: str):
    #"""better_profanity only says yes/no, so compare the original with the censored text to find the word."""
    #censored = profanity.censor(text)
    #for original, hidden in zip(text.split(), censored.split()):
       # if original != hidden:
            #return original.lower()
    #return "unknown"




@bot.event
async def on_ready():
    for g in bot.guilds:      # create a settings row for servers the bot is already in
        await ensure_guild(g.id)

    guild = discord.Object(id=TEST_GUILD_ID)
    bot.tree.copy_global_to(guild=guild)      # makes /hello show up in your test server
    await bot.tree.sync(guild=guild)
    print("Slashed Commands Synced")
    print("Booting Robot")
    print(f"Robot Login Successfull Logged in as {bot.user.name}")
    print(f"Robot id: {bot.user.id}")


@bot.event
async def on_guild_join(guild):
    await ensure_guild(guild.id)


@bot.event
async def on_member_join(member):
    # Check the blocked_users table for this server + user
    async with bot.pool.acquire() as conn:
        blocked = await conn.fetchval(
            "SELECT 1 FROM blocked_users WHERE guild_id = $1 AND user_id = $2",
            member.guild.id, member.id, #This event handles the Members who are Joining the Server, Meaning that the Pool Checks from the database, Members who are Entering the Server and Then Kicks the Users, if Name Was Found in the blocked_users Table.
        )

    if blocked:
        try:
            await member.kick(reason="Blocked by Moderators") #If User is Blocked Inserts the User Who is Blocked into the Database \.
        except discord.Forbidden:
            print(f"Missing Permissions to Kick {member}")
        return                                

    channel = bot.get_channel(WELCOME_CHANNEL_ID)
    if channel is None:
        return
    await channel.send(f"{member} has Joined the Server, Welcome to the Server")

    await asyncio.sleep(2)
    await channel.send(f"Hello 👋 {member} Welcome to The {channel}")

    await asyncio.sleep(2)
    await channel.send("How May i Assist You Today 😊")


@bot.event
async def on_member_remove(member):
    channel = bot.get_channel(WELCOME_CHANNEL_ID)
    if channel is None:
        return
    await channel.send(f"{member} has left {channel}")

    count_member = member.guild.member_count
    await asyncio.sleep(5)
    await channel.send(f"{member} has Left {channel}, Avaible Members in {channel}: {count_member}")


# buttons and slash commands

class View(discord.ui.View):
    @discord.ui.button(label="I am Fine 😊", style=discord.ButtonStyle.success) #Displays a UI Button which shows the Text i am Fine 
    async def fine(self, interaction: discord.Interaction, button: discord.ui.Button):
        await asyncio.sleep(2)
        await interaction.response.send_message(f"I am Happy to Hear that {interaction.user.mention} 😊") #After Clicking the Button, it Responds to the User
        await asyncio.sleep(2)
        await interaction.followup.send(f"How May i Assist You Today {interaction.user.mention}")

    @discord.ui.button(label="I am Not Fine 😭", style=discord.ButtonStyle.danger) #Danger Displays a Red Button 
    async def not_fine(self, interaction: discord.Interaction, button: discord.ui.Button):
        await asyncio.sleep(2)
        await interaction.response.send_message(f"I am Sorry to Hear That {interaction.user.mention}")


@bot.tree.command(name="hello", description="Greets the User")
async def hello(interaction: discord.Interaction):
    await interaction.response.send_message(f"Hello {interaction.user.mention} ")
    await asyncio.sleep(2)
    await interaction.followup.send("How are You Today", view=View())

#Profanity Detection

async def check_profanity(message: discord.Message):
    word = find_word(message.content)
    if word is None:
        return

    # 1. Load this server's settings
    async with bot.pool.acquire() as conn:
        settings = await conn.fetchrow(
            "SELECT * FROM guild_settings WHERE guild_id = $1", message.guild.id
        )
    if settings is None or not settings["enabled"]:
        return

    # 2. Delete the offending message
    #If Message in Profanity, it Deletes the Message and Checks for The User that Sent the Message.
    try:
        await message.delete()
    except (discord.Forbidden, discord.NotFound):
        pass

    # 3. Count earlier strikes inside the strike window, then add this one
    async with bot.pool.acquire() as conn:
        previous = await conn.fetchval(
            """
            SELECT COUNT(*) FROM violations
            WHERE guild_id = $1 AND user_id = $2
              AND created_at > now() - make_interval(hours => $3)
            """,
            message.guild.id, message.author.id, settings["strike_window_hours"],
        )
    strikes = previous + 1
    limit = settings["strike_limit"]

    # 4. Decide and apply the action
    taken = "warn"
    if strikes >= limit and settings["action"] == "kick":
        await message.channel.send(f"{message.author.mention} has been kicked for offensive language.")
        await asyncio.sleep(5)
        try:
            await message.guild.kick(message.author, reason="Offensive language")
            taken = "kick"

            # NEW: remember this user so they are removed again if they rejoin, as Soon as the User is Kicked, He/ she is inserted into the Blocked Users Table, this Makes Sure that the User is Remembered even When He / She Wants to Rejoin the Server the Bot Automatically Kicks the User out.
            async with bot.pool.acquire() as conn:
                await conn.execute(
                    """
                    INSERT INTO blocked_users (guild_id, user_id, reason)
                    VALUES ($1, $2, $3)
                    ON CONFLICT (guild_id, user_id) DO NOTHING
                    """,
                    message.guild.id, message.author.id,
                    "Auto-blocked after reaching the strike limit",
                )
        except discord.Forbidden:
            taken = "none"
            await message.channel.send("Failed to kick user")

    elif strikes >= limit and settings["action"] == "timeout":
        try:
            await message.author.timeout(timedelta(minutes=10), reason="Offensive language")
            taken = "timeout"
            await message.channel.send(f"{message.author.mention} has been timed out for 10 minutes")
        except discord.Forbidden:
            taken = "none"
            await message.channel.send("Failed to time out user")

    else:
        await message.channel.send(
            f"{message.author.mention} has been warned for using offensive words. "
            f"Total warnings: {strikes}/{limit}"
        )


    # 5. Record what happened
    async with bot.pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO violations
                (guild_id, user_id, username_at_time, matched_word, message_id, action_taken) 
            VALUES ($1, $2, $3, $4, $5, $6)
            """,
            message.guild.id, message.author.id, str(message.author), #As Soon as the User is Warned / Hits Strike Limit, the User Id is inserted into the Violation Table in The Database.
            word, message.id, taken,
        )


@bot.tree.command(name="history", description="shows the history of the User") #Creates a slash Command which shows the History of The User /History
@app_commands.describe(user="Shows The History of the User") #When the User Uses the /History Command, it Shows the Description of what the Command Does
@app_commands.guild_only()
@app_commands.checks.has_permissions(moderate_members = True)
async def history(interaction: discord.Interaction, user: discord.User):

    rows = await bot.pool.fetch(
        """
        SELECT matched_word, action_taken, created_at
        FROM violations
        WHERE guild_id = $1 AND user_id = $2
        ORDER BY created_at DESC
        LIMIT 10
        """,
        interaction.guild.id, user.id,
    )


    if not rows:
        await interaction.response.send_message(f"{user.mention} has no violations.", ephemeral=True) #if it is Not in the Rows, means that the User is Not Guilty / Included in the violations Table.

        return

    lines = [] #Creates an Empty List which Will be used to Store the Violations Of the User.
    for r in rows:
        text = f"{r['created_at']:%Y-%m-%d %H:%M} | ** {r['matched_word']} ** | {r['action_taken']}" #This is The Text Format of how the Violations will Display
        lines.append(text) #add The Test to the List

    await interaction.response.send_message(f"Last {len(rows)} violations for {user.mention}: **\n" + "\n".join(lines),
        ephemeral=True, 
    )

    @history.error
    async def history_error(interaction: discord.interaction, error):
        if isinstance(error, app_commands.errors.MissiingPermissions):
            await interaction.response.send_message("You do not Have Permission to Use This", ephemeral=True)

        else:
            raise error


@bot.event
async def on_message(message):
    if not message.author.bot and message.guild is not None:
        try:
            await check_profanity(message)
        except Exception:
            logger.exception("Error Checking Profanity", message.id)
    await bot.process_commands(message)


#Start Discord In the Pool, Creates the Pool Which Resuses Existing Connection to the Database and Adds the Discord Bot to the Database.

async def main():
    bot.pool = await create_pool()
    try:
        async with bot:
            await bot.start(os.getenv("DISCORD_TOKEN"))
    finally:
        await bot.pool.close()


asyncio.run(main())