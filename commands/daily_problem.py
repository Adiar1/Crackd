import random
import asyncio
from datetime import datetime, timedelta

import discord
from discord import Interaction, Embed, ui, ButtonStyle

from commands.view_questions import AddQuestionButton
from utils.database import get_database_connection, archive_question


class AnswerButton(ui.Button):
    def __init__(self, label, question_id):
        super().__init__(label=label, style=discord.ButtonStyle.primary)
        self.question_id = question_id

    async def callback(self, interaction: Interaction):
        conn = get_database_connection()
        c = conn.cursor()

        # Get question details
        c.execute("""
            SELECT correct_answer, explanation, type, domain, skill, difficulty
            FROM questions 
            WHERE id = ?
        """, (self.question_id,))
        question_data = c.fetchone()

        if not question_data:
            await interaction.response.send_message(
                embed=Embed(
                    title="Error",
                    description="This question is no longer available.",
                    color=discord.Color.red()
                ),
                ephemeral=True
            )
            return

        correct_answer, explanation, q_type, domain, skill, difficulty = question_data

        # Check if user has already attempted
        c.execute("""
            SELECT is_correct FROM daily_problem
            WHERE question_id = ? AND user_id = ?
        """, (self.question_id, interaction.user.id))
        existing_attempt = c.fetchone()

        if existing_attempt:
            await interaction.response.send_message(
                embed=Embed(
                    title="Already Attempted",
                    description="You have already answered this question!",
                    color=discord.Color.red()
                ),
                ephemeral=True
            )
            return

        # Record the attempt
        is_correct = (self.label == correct_answer)
        c.execute("""
            INSERT INTO daily_problem (user_id, question_id, correct_answer, selected_answer, is_correct, response_time)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (interaction.user.id, self.question_id, correct_answer, self.label, is_correct, datetime.utcnow()))

        # Update user stats
        c.execute("""
            INSERT INTO user_stats (user_id, total_correct, total_attempts)
            VALUES (?, ?, 1)
            ON CONFLICT(user_id) DO UPDATE SET
            total_correct = total_correct + ?,
            total_attempts = total_attempts + 1
        """, (interaction.user.id, 1 if is_correct else 0, 1 if is_correct else 0))

        # Update skill stats
        c.execute("""
            INSERT INTO user_skill_stats (user_id, question_type, domain, skill, total_correct, total_attempts)
            VALUES (?, ?, ?, ?, ?, 1)
            ON CONFLICT(user_id, question_type, domain, skill) DO UPDATE SET
            total_correct = total_correct + ?,
            total_attempts = total_attempts + 1
        """, (interaction.user.id, q_type, domain, skill, 1 if is_correct else 0, 1 if is_correct else 0))

        # Get current answer distribution
        c.execute("""
            SELECT selected_answer, COUNT(*) as count
            FROM daily_problem
            WHERE question_id = ?
            GROUP BY selected_answer
        """, (self.question_id,))
        answer_stats = dict(c.fetchall())

        total_attempts = sum(answer_stats.values())
        percentages = {
            "A": round((answer_stats.get("A", 0) / total_attempts) * 100, 2),
            "B": round((answer_stats.get("B", 0) / total_attempts) * 100, 2),
            "C": round((answer_stats.get("C", 0) / total_attempts) * 100, 2),
            "D": round((answer_stats.get("D", 0) / total_attempts) * 100, 2)
        }

        if is_correct:
            result_embed = Embed(
                title="Correct Answer! 🎉",
                description=(
                    f"✅ Well done! The correct answer is **{correct_answer}**.\n\n"
                    f"**Explanation:**\n{explanation}\n\n"
                    f"**Current Answer Distribution:**\n"
                    f"A: {percentages['A']}%\n"
                    f"B: {percentages['B']}%\n"
                    f"C: {percentages['C']}%\n"
                    f"D: {percentages['D']}%"
                ),
                color=discord.Color.green()
            )
        else:
            result_embed = Embed(
                title="Incorrect Answer 😔",
                description=(
                    f"❌ The correct answer was **{correct_answer}**.\n\n"
                    f"**Explanation:**\n{explanation}\n\n"
                    f"**Current Answer Distribution:**\n"
                    f"A: {percentages['A']}%\n"
                    f"B: {percentages['B']}%\n"
                    f"C: {percentages['C']}%\n"
                    f"D: {percentages['D']}%"
                ),
                color=discord.Color.red()
            )

        conn.commit()
        conn.close()

        await interaction.response.send_message(embed=result_embed, ephemeral=True)


class DetailsButton(ui.Button):
    def __init__(self, question_id):
        super().__init__(label="View Details", style=ButtonStyle.secondary)
        self.question_id = question_id

    async def callback(self, interaction: Interaction):
        conn = get_database_connection()
        c = conn.cursor()

        c.execute("""
            SELECT type, domain, skill, difficulty
            FROM questions
            WHERE id = ?
        """, (self.question_id,))

        details = c.fetchone()
        conn.close()

        if not details:
            await interaction.response.send_message(
                embed=Embed(
                    title="Error",
                    description="Question details are no longer available.",
                    color=discord.Color.red()
                ),
                ephemeral=True
            )
            return

        q_type, domain, skill, difficulty = details

        details_embed = Embed(
            title="Question Details",
            color=discord.Color.blue()
        )
        details_embed.add_field(name="Type", value=q_type.capitalize(), inline=True)
        details_embed.add_field(name="Domain", value=domain, inline=True)
        details_embed.add_field(name="Skill", value=skill, inline=True)
        details_embed.add_field(name="Difficulty", value=difficulty.capitalize(), inline=True)

        await interaction.response.send_message(embed=details_embed, ephemeral=True)


class MainGameView(ui.View):
    def __init__(self, question_id):
        super().__init__(timeout=None)

        for choice in ["A", "B", "C", "D"]:
            self.add_item(AnswerButton(label=choice, question_id=question_id))

        self.add_item(DetailsButton(question_id))


async def update_timer(message, end_time):
    try:
        while datetime.utcnow() < end_time:
            remaining_time = end_time - datetime.utcnow()
            hours, remainder = divmod(remaining_time.total_seconds(), 3600)
            minutes, seconds = divmod(remainder, 60)

            if hours < 0:
                break

            footer_text = f"Time remaining: {int(hours)}h {int(minutes)}m {int(seconds)}s"
            embed = message.embeds[0]
            embed.set_footer(text=footer_text)

            try:
                await message.edit(embed=embed)
            except discord.NotFound:
                # Message was deleted
                return
            except discord.HTTPException:
                # Handle other Discord API errors
                continue

            await asyncio.sleep(1)  # Update every minute instead of every second

        # Time's up - post final statistics
        await post_final_stats(message)
    except Exception as e:
        print(f"Error in update_timer: {e}")


async def post_final_stats(message):
    try:
        conn = get_database_connection()
        c = conn.cursor()

        # Extract question_id from the message
        question_id = int(message.embeds[0].footer.text.split()[-1])

        # Get question details
        c.execute("""
            SELECT type, domain, skill, difficulty
            FROM questions
            WHERE id = ?
        """, (question_id,))
        q_type, domain, skill, difficulty = c.fetchone()

        # Get answer statistics
        c.execute("""
            SELECT selected_answer, COUNT(*) as count,
                   SUM(CASE WHEN is_correct = 1 THEN 1 ELSE 0 END) as correct_count
            FROM daily_problem
            WHERE question_id = ?
            GROUP BY selected_answer
        """, (question_id,))

        stats = dict(c.fetchall())
        total_attempts = sum(stats.values())
        total_participants = c.execute(
            "SELECT COUNT(DISTINCT user_id) FROM daily_problem WHERE question_id = ?",
            (question_id,)
        ).fetchone()[0]

        percentages = {
            key: round((count / total_attempts) * 100, 2)
            for key, count in stats.items()
        }

        stats_embed = Embed(
            title="Final Question Statistics",
            description=(
                f"**Total Participants:** {total_participants}\n\n"
                f"**Answer Distribution:**\n"
                f"A: {percentages.get('A', 0)}% ({stats.get('A', 0)} votes)\n"
                f"B: {percentages.get('B', 0)}% ({stats.get('B', 0)} votes)\n"
                f"C: {percentages.get('C', 0)}% ({stats.get('C', 0)} votes)\n"
                f"D: {percentages.get('D', 0)}% ({stats.get('D', 0)} votes)"
            ),
            color=discord.Color.gold()
        )

        stats_embed.add_field(name="Question Type", value=q_type.capitalize(), inline=True)
        stats_embed.add_field(name="Domain", value=domain, inline=True)
        stats_embed.add_field(name="Skill", value=skill, inline=True)
        stats_embed.add_field(name="Difficulty", value=difficulty.capitalize(), inline=True)

        # Update original message footer
        embed = message.embeds[0]
        embed.set_footer(text=f"This question has ended. Question ID: {question_id}")
        await message.edit(embed=embed)

        # Send stats as a reply
        await message.reply(embed=stats_embed)

        conn.close()
    except Exception as e:
        print(f"Error in post_final_stats: {e}")


async def handle_daily_problem_command(bot, interaction: Interaction, question_type: str = None,
                                       question_id: int = None):
    conn = get_database_connection()
    c = conn.cursor()

    # Fetch question logic (same as before)
    if question_id:
        if question_type:
            c.execute("""
                SELECT id, question, correct_answer, 
                       option_a, option_b, option_c, option_d, 
                       explanation, difficulty, domain, skill, image_url, type
                FROM questions
                WHERE id = ? AND type = ?
            """, (question_id, question_type))
        else:
            c.execute("""
                SELECT id, question, correct_answer, 
                       option_a, option_b, option_c, option_d, 
                       explanation, difficulty, domain, skill, image_url, type
                FROM questions
                WHERE id = ?
            """, (question_id,))

        question = c.fetchone()

        if not question:
            no_question_embed = Embed(
                title="Question Not Found",
                description=f"No question found with ID `{question_id}` {'and type `' + question_type + '`' if question_type else ''}. Please check and try again.",
                color=discord.Color.red()
            )
            await interaction.response.send_message(embed=no_question_embed, ephemeral=True)
            conn.close()
            return
    else:
        if question_type:
            c.execute("""
                SELECT id, question, correct_answer, 
                       option_a, option_b, option_c, option_d, 
                       explanation, difficulty, domain, skill, image_url, type
                FROM questions
                WHERE type = ?
            """, (question_type,))
        else:
            c.execute("""
                SELECT id, question, correct_answer, 
                       option_a, option_b, option_c, option_d, 
                       explanation, difficulty, domain, skill, image_url, type
                FROM questions
            """)

        questions = c.fetchall()

        if not questions:
            no_questions_embed = Embed(
                title="No Questions Available",
                description=f"There are no questions available {'for `' + question_type + '`' if question_type else ''} right now. Would you like to add one?",
                color=discord.Color.orange()
            )
            view = AddQuestionButton()
            await interaction.response.send_message(embed=no_questions_embed, view=view, ephemeral=True)
            conn.close()
            return

        question = random.choice(questions)

    # Unpack question data
    (question_id, question_text, correct_answer,
     option_a, option_b, option_c, option_d,
     explanation, difficulty, domain, skill, image_url, q_type) = question

    options_dict = {
        "A": option_a,
        "B": option_b,
        "C": option_c,
        "D": option_d
    }

    # Create main embed
    main_embed = Embed(
        title="Daily Problem",
        description=question_text,
        color=0x3498db,
    )

    main_embed.add_field(
        name="Answer Choices",
        value="\n".join([f"{key}) {value}" for key, value in options_dict.items()]),
        inline=False,
    )

    if image_url:
        main_embed.set_image(url=image_url)

    main_embed.set_footer(text=f"Time remaining: 24h 0m 0s | Question ID: {question_id}")

    # Create and send main view
    main_view = MainGameView(question_id)
    await interaction.response.send_message(embed=main_embed, view=main_view)

    # Get the original message
    message = await interaction.original_response()

    # Start the countdown timer
    end_time = datetime.utcnow() + timedelta(hours=24)
    asyncio.create_task(update_timer(message, end_time))

    # Create and send admin embed (ephemeral)
    admin_embed = Embed(
        title="Archive Question?",
        description=f"Use the button below to archive this question so that you don't accidentally send it again.\n\n**Question ID:** `{question_id}`",
        color=discord.Color.red()
    )

    admin_view = ui.View(timeout=None)
    admin_view.add_item(ui.Button(
        label="Archive Question",
        style=ButtonStyle.danger,
        custom_id=f"archive_{question_id}"
    ))

    await interaction.followup.send(embed=admin_embed, view=admin_view, ephemeral=True)

    conn.close()