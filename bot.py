import os
import logging
from dotenv import load_dotenv

import discord
from discord.ext import commands
from discord import Intents, app_commands

from commands.view_archives import handle_view_archives_command
from commands.view_questions import handle_view_questions_command
from utils.database import init_db
from commands.add_question import handle_add_question_command
from commands.daily_problem import handle_daily_problem_command
from commands.stats import handle_stats_command

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Bot setup
intents = Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='/', intents=intents)

# Event when the bot is ready
@bot.event
async def on_ready():
    print(f'{bot.user} is now running!')
    await bot.tree.sync()

def is_admin(interaction: discord.Interaction) -> bool:
    """
    Check if the user is an admin based on roles or user ID.
    """
    # Get admin role and user IDs from environment variables
    admin_role_ids = os.getenv("DISCORD_ADMIN_ROLE_IDS", "").split(",")
    admin_user_ids = os.getenv("DISCORD_ADMIN_USER_IDS", "").split(",")

    # Convert to sets for easier comparison
    admin_role_ids = {int(role_id) for role_id in admin_role_ids if role_id.strip().isdigit()}
    admin_user_ids = {int(user_id) for user_id in admin_user_ids if user_id.strip().isdigit()}

    # Check if the user is a privileged user
    if interaction.user.id in admin_user_ids:
        return True

    # Check if the user has one of the privileged roles
    user_roles = {role.id for role in interaction.user.roles}
    if admin_role_ids & user_roles:  # Intersection of sets
        return True

    return False

# Load commands
@bot.tree.command(name="addquestion", description="Add a new SAT question to the database")
async def add_question(interaction: discord.Interaction):
    if not is_admin(interaction):
        await interaction.response.send_message(
            "You do not have permission to use this command.", ephemeral=True
        )
        return

    await handle_add_question_command(interaction)


@bot.tree.command(name="dailyproblem", description="Send a daily problem")
@app_commands.describe(
    question_type="Optional: Choose the type of question",
    question_id="Optional: Specify a question ID to use"
)
@app_commands.choices(
    question_type=[
        app_commands.Choice(name="Math", value="math"),
        app_commands.Choice(name="EBRW", value="ebrw"),
    ]
)
async def daily_problem(
        interaction: discord.Interaction,
        question_type: app_commands.Choice[str] = None,
        question_id: int = None  # Optional argument for question ID
):
    if not is_admin(interaction):
        await interaction.response.send_message(
            "You do not have permission to use this command.", ephemeral=True
        )
        return

    # Only access `question_type.value` if `question_type` is not None
    type_value = question_type.value if question_type else None

    # Pass the type_value and question_id to the handler function
    await handle_daily_problem_command(bot, interaction, type_value, question_id)


@bot.tree.command(name="stats", description="View your SAT game stats or someone else's stats")
@app_commands.describe(someone_else="The member whose stats you want to view (optional)")
async def stats(interaction: discord.Interaction, someone_else: discord.Member = None):
    await handle_stats_command(interaction, someone_else)

from commands.edit_stats import handle_edit_stats_command

@bot.tree.command(name="editstats", description="Edit a member's SAT stats forcefully")
@app_commands.describe(member="The member whose stats you want to edit")
async def edit_stats(interaction: discord.Interaction, member: discord.Member):
    if not is_admin(interaction):
        await interaction.response.send_message(
            "You do not have permission to use this command.", ephemeral=True
        )
        return

    await handle_edit_stats_command(bot, interaction, member)


from commands.leaderboard import handle_leaderboard_command

# Add this under your other command decorators
@bot.tree.command(name="leaderboard", description="View SAT practice leaderboard")
async def leaderboard(interaction: discord.Interaction):
    if not is_admin(interaction):
        await interaction.response.send_message(
            "You do not have permission to use this command.", ephemeral=True
        )
        return

    await handle_leaderboard_command(interaction)

@bot.tree.command(name="viewquestions", description="View all SAT questions in the database")
async def view_questions(interaction: discord.Interaction):
    if not is_admin(interaction):
        await interaction.response.send_message(
            "You do not have permission to use this command.", ephemeral=True
        )
        return

    await handle_view_questions_command(interaction)

@bot.tree.command(name="viewarchives", description="View all archived SAT questions in the database")
async def view_archives(interaction: discord.Interaction):
    if not is_admin(interaction):
        await interaction.response.send_message(
            "You do not have permission to use this command.", ephemeral=True
        )
        return

    await handle_view_archives_command(interaction)


def main():
    load_dotenv()
    try:
        init_db()  # Initialize the database
        logger.info("Database initialized successfully.")
    except Exception as e:
        logger.error(f"Error initializing database: {e}")
    TOKEN = os.getenv('DISCORD_TOKEN')

    if TOKEN:
        bot.run(TOKEN)
    else:
        logger.error("DISCORD_TOKEN not found in environment variables.")

if __name__ == "__main__":
    main()