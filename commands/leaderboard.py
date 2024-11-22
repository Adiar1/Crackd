from discord import Interaction, Embed
from utils.database import get_database_connection


async def handle_leaderboard_command(interaction: Interaction):
    conn = get_database_connection()
    c = conn.cursor()

    # Fetch top 10 users by accuracy
    c.execute('''
        SELECT 
            user_id, 
            total_correct, 
            total_attempts, 
            (total_correct * 100.0 / total_attempts) as accuracy 
        FROM user_stats 
        WHERE total_attempts > 0
        ORDER BY accuracy DESC 
        LIMIT 10
    ''')
    accuracy_leaderboard = c.fetchall()

    # Fetch top 10 users by total correct answers
    c.execute('''
        SELECT 
            user_id, 
            total_correct, 
            total_attempts 
        FROM user_stats 
        WHERE total_attempts > 0
        ORDER BY total_correct DESC 
        LIMIT 10
    ''')
    total_correct_leaderboard = c.fetchall()

    conn.close()

    # Create leaderboard embed for accuracy
    accuracy_embed = Embed(
        title="📊 SAT Practice Leaderboard - Accuracy",
        description="Top performers by accuracy in SAT practice questions",
        color=0x3498db
    )

    # Add accuracy leaderboard fields
    if not accuracy_leaderboard:
        accuracy_embed.description = "No stats available yet. Start playing to appear on the leaderboard!"
    else:
        for i, (user_id, correct, total, accuracy) in enumerate(accuracy_leaderboard, 1):
            try:
                # Attempt to get the member from the guild
                member = interaction.guild.get_member(int(user_id))
                if not member:
                    # If member is not cached, fetch them from the guild
                    member = await interaction.guild.fetch_member(int(user_id))

                # Use member.mention to ensure proper mention
                username = member.mention
            except Exception:
                try:
                    # If fetching the member fails, fetch the user instead
                    user = await interaction.client.fetch_user(int(user_id))
                    username = user.mention
                except Exception:
                    # Final fallback: Use raw user ID
                    username = f"<@{user_id}>"

            accuracy_embed.add_field(
                name=f"{i}",
                value=f"{username}\n"
                      f"✅ Correct: {correct}/{total} questions\n"
                      f"📊 Accuracy: {accuracy:.1f}%"
                      ,
                inline=False
            )

    # Create leaderboard embed for total correct answers
    total_correct_embed = Embed(
        title="📊 SAT Practice Leaderboard - Total Correct",
        description="Top performers by total correct answers in SAT practice questions",
        color=0x2ecc71
    )

    # Add total correct leaderboard fields
    if not total_correct_leaderboard:
        total_correct_embed.description = "No stats available yet. Start playing to appear on the leaderboard!"
    else:
        for i, (user_id, correct, total) in enumerate(total_correct_leaderboard, 1):
            try:
                # Attempt to get the member from the guild
                member = interaction.guild.get_member(int(user_id))
                if not member:
                    # If member is not cached, fetch them from the guild
                    member = await interaction.guild.fetch_member(int(user_id))

                # Use member.mention to ensure proper mention
                username = member.mention
            except Exception:
                try:
                    # If fetching the member fails, fetch the user instead
                    user = await interaction.client.fetch_user(int(user_id))
                    username = user.mention
                except Exception:
                    # Final fallback: Use raw user ID
                    username = f"<@{user_id}>"

            total_correct_embed.add_field(
                name=f"{i}",
                value=f"{username}\n"
                      f"✅ Total Correct: {correct} questions\n"
                      f"📚 Total Attempts: {total}",
                inline=False
            )

    # Add a footer to both embeds
    accuracy_embed.set_footer(text="Keep practicing to improve your accuracy!")
    total_correct_embed.set_footer(text="Keep practicing to increase your total correct answers!")

    # Send both embeds as a single message
    await interaction.response.send_message(embeds=[accuracy_embed, total_correct_embed])