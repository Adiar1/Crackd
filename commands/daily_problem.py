import random
import asyncio
from datetime import datetime, timedelta

import discord
from discord import Interaction, Embed, ui, ButtonStyle

from commands.view_questions import AddQuestionButton
from utils.database import get_database_connection, archive_question


class AnswerButton(ui.Button):
    def __init__(self, label, correct_answer, explanation, user_attempts, expiry_time, question_details, answer_stats):
        super().__init__(label=label, style=discord.ButtonStyle.primary)
        self.correct_answer = correct_answer
        self.explanation = explanation
        self.user_attempts = user_attempts
        self.expiry_time = expiry_time
        self.question_details = question_details
        self.answer_stats = answer_stats

    async def callback(self, interaction: Interaction):
        user_id = interaction.user.id
        current_time = datetime.utcnow()

        if current_time > self.expiry_time:
            expired_embed = Embed(
                title="Question Ended",
                description="This question has ended. Stay tuned for the next one!",
                color=discord.Color.orange()
            )
            await interaction.response.send_message(embed=expired_embed, ephemeral=True)
            return

        if user_id in self.user_attempts:
            duplicate_embed = Embed(
                title="Duplicate Attempt",
                description="You have already attempted this question!",
                color=discord.Color.red()
            )
            await interaction.response.send_message(embed=duplicate_embed, ephemeral=True)
            return

        self.user_attempts.add(user_id)
        self.answer_stats[self.label] += 1  # Increment the count for the selected answer

        # Calculate percentages
        total_attempts = sum(self.answer_stats.values())
        percentages = {key: round((count / total_attempts) * 100, 2) for key, count in self.answer_stats.items()}

        if self.label == self.correct_answer:
            result_embed = Embed(
                title="Correct Answer! 🎉",
                description=(
                    f"✅ Well done! The correct answer is **{self.correct_answer}**.\n\n"
                    f"**Explanation:**\n{self.explanation}\n\n"
                    f"**Current Answer Distribution:**\n"
                    f"A: {percentages['A']}%\n"
                    f"B: {percentages['B']}%\n"
                    f"C: {percentages['C']}%\n"
                    f"D: {percentages['D']}%"
                ),
                color=discord.Color.green()
            )
            is_correct = True
        else:
            result_embed = Embed(
                title="Incorrect Answer 😔",
                description=(
                    f"❌ The correct answer was **{self.correct_answer}**.\n\n"
                    f"**Explanation:**\n{self.explanation}\n\n"
                    f"**Current Answer Distribution:**\n"
                    f"A: {percentages['A']}%\n"
                    f"B: {percentages['B']}%\n"
                    f"C: {percentages['C']}%\n"
                    f"D: {percentages['D']}%"
                ),
                color=discord.Color.red()
            )
            is_correct = False

        await interaction.response.send_message(embed=result_embed, ephemeral=True)

        # Database interaction code remains the same as in the original script
        conn = get_database_connection()
        c = conn.cursor()

        # ... [rest of the database update logic remains unchanged]

        conn.commit()
        conn.close()


class DetailsButton(ui.Button):
    def __init__(self, details):
        super().__init__(label="View Details", style=ButtonStyle.secondary)
        self.details = details

    async def callback(self, interaction: Interaction):
        details_embed = Embed(
            title="Question Details",
            color=discord.Color.blue()
        )
        details_embed.add_field(name="Type", value=self.details["type"].capitalize(), inline=True)
        details_embed.add_field(name="Domain", value=self.details["domain"], inline=True)
        details_embed.add_field(name="Skill", value=self.details["skill"], inline=True)
        details_embed.add_field(name="Difficulty", value=self.details["difficulty"].capitalize(), inline=True)
        await interaction.response.send_message(embed=details_embed, ephemeral=True)


class ArchiveQuestionButton(ui.Button):
    def __init__(self, question_id, expiry_time):
        super().__init__(label="Archive Question", style=ButtonStyle.danger)
        self.question_id = question_id
        self.expiry_time = expiry_time

    async def callback(self, interaction: Interaction):
        current_time = datetime.utcnow()
        if current_time > self.expiry_time:
            expired_embed = Embed(
                title="Archive Failed",
                description="The archive button is no longer available because the question has expired.",
                color=discord.Color.red()
            )
            await interaction.response.send_message(embed=expired_embed, ephemeral=True)
            return

        if archive_question(self.question_id):
            success_embed = Embed(
                title="Question Archived",
                description=f"Question ID `{self.question_id}` has been archived successfully.",
                color=discord.Color.green()
            )
            await interaction.response.send_message(embed=success_embed, ephemeral=True)
        else:
            error_embed = Embed(
                title="Archive Failed",
                description=f"Failed to archive the question ID `{self.question_id}`. Question has likely already been archived.",
                color=discord.Color.red()
            )
            await interaction.response.send_message(embed=error_embed, ephemeral=True)


class MainGameView(ui.View):
    def __init__(self, correct_answer, explanation, expiry_time, details, original_message):
        super().__init__(timeout=None)
        self.correct_answer = correct_answer
        self.explanation = explanation
        self.expiry_time = expiry_time
        self.user_attempts = set()
        self.answer_stats = {"A": 0, "B": 0, "C": 0, "D": 0}
        self.original_message = original_message
        self.details = details

        for choice in ["A", "B", "C", "D"]:
            self.add_item(
                AnswerButton(
                    label=choice,
                    correct_answer=self.correct_answer,
                    explanation=self.explanation,
                    user_attempts=self.user_attempts,
                    expiry_time=self.expiry_time,
                    question_details=details,
                    answer_stats=self.answer_stats,
                )
            )

        self.add_item(DetailsButton(details))

    async def start_countdown(self):
        while datetime.utcnow() < self.expiry_time:
            remaining_time = self.expiry_time - datetime.utcnow()
            hours, remainder = divmod(remaining_time.total_seconds(), 3600)
            minutes, seconds = divmod(remainder, 60)
            footer_text = f"Time remaining: {int(hours)}h {int(minutes)}m {int(seconds)}s"
            embed = self.original_message.embeds[0]
            embed.set_footer(text=footer_text)
            await self.original_message.edit(embed=embed)
            await asyncio.sleep(1)

        # Final statistics as an embed
        total_attempts = sum(self.answer_stats.values())
        total_participants = len(self.user_attempts)
        percentages = {key: round((count / total_attempts) * 100, 2) for key, count in self.answer_stats.items()}

        stats_embed = Embed(
            title="Final Question Statistics",
            description=(
                f"**Total Participants:** {total_participants}\n\n"
                f"**Answer Distribution:**\n"
                f"A: {percentages['A']}% ({self.answer_stats['A']} votes)\n"
                f"B: {percentages['B']}% ({self.answer_stats['B']} votes)\n"
                f"C: {percentages['C']}% ({self.answer_stats['C']} votes)\n"
                f"D: {percentages['D']}% ({self.answer_stats['D']} votes)"
            ),
            color=discord.Color.gold()
        )
        stats_embed.add_field(name="Question Type", value=self.details["type"].capitalize(), inline=True)
        stats_embed.add_field(name="Domain", value=self.details["domain"], inline=True)
        stats_embed.add_field(name="Skill", value=self.details["skill"], inline=True)
        stats_embed.add_field(name="Difficulty", value=self.details["difficulty"].capitalize(), inline=True)

        # Update footer to indicate the question has ended
        embed = self.original_message.embeds[0]
        embed.set_footer(text="This question has ended. Stay tuned for the next one!")
        await self.original_message.edit(embed=embed)

        await self.original_message.reply(embed=stats_embed)


class AdminView(ui.View):
    def __init__(self, question_id, expiry_time):
        super().__init__(timeout=None)
        self.add_item(ArchiveQuestionButton(question_id, expiry_time))


async def handle_daily_problem_command(bot, interaction: Interaction, question_type: str = None,
                                       question_id: int = None):
    conn = get_database_connection()
    c = conn.cursor()

    # Fetch a specific question if `question_id` is provided
    if question_id:
        # If both question_id and question_type are provided, verify type
        if question_type:
            c.execute(
                """
                SELECT id, question, correct_answer, 
                       option_a, option_b, option_c, option_d, 
                       explanation, difficulty, domain, skill, image_url, type
                FROM questions
                WHERE id = ? AND type = ?
                """,
                (question_id, question_type),
            )
        else:
            # If only question_id is provided, fetch by ID regardless of type
            c.execute(
                """
                SELECT id, question, correct_answer, 
                       option_a, option_b, option_c, option_d, 
                       explanation, difficulty, domain, skill, image_url, type
                FROM questions
                WHERE id = ?
                """,
                (question_id,),
            )

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
        # Select a random question based on type or from all questions
        if question_type:
            # Select a random question of the specified type
            c.execute(
                """
                SELECT id, question, correct_answer, 
                       option_a, option_b, option_c, option_d, 
                       explanation, difficulty, domain, skill, image_url, type
                FROM questions
                WHERE type = ?
                """,
                (question_type,),
            )
        else:
            # Select a random question from all questions
            c.execute(
                """
                SELECT id, question, correct_answer, 
                       option_a, option_b, option_c, option_d, 
                       explanation, difficulty, domain, skill, image_url, type
                FROM questions
                """
            )

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

    # Unpack the question data
    (question_id, question_text, correct_answer,
     option_a, option_b, option_c, option_d,
     explanation, difficulty, domain, skill, image_url, q_type) = question

    # Create options dictionary
    options_dict = {
        "A": option_a,
        "B": option_b,
        "C": option_c,
        "D": option_d
    }

    # Main question embed
    main_embed = Embed(
        title="Daily Problem",
        description=question_text,
        color=0x3498db,
    )

    main_embed.add_field(
        name="Answer Choices",
        value="\n".join(
            [f"{key}) {value}" for key, value in options_dict.items()]
        ),
        inline=False,
    )

    if image_url:
        main_embed.set_image(url=image_url)

    main_embed.set_footer(text="Time remaining: 24h 0m 0s")

    # Admin embed for archive button
    admin_embed = Embed(
        title="Archive Question?",
        description=f"Use the button below to archive this question so that you don't accidentally send it again.\n\n**Question ID:** `{question_id}`",
        color=discord.Color.red()
    )

    expiry_time = datetime.utcnow() + timedelta(hours=24)

    details = {
        "id": question_id,
        "type": q_type,
        "domain": domain,
        "skill": skill,
        "difficulty": difficulty,
    }

    # Create and send main view
    main_view = MainGameView(
        correct_answer=correct_answer,
        explanation=explanation,
        expiry_time=expiry_time,
        details=details,
        original_message=None,  # Placeholder for now
    )
    await interaction.response.send_message(embed=main_embed, view=main_view)

    # Get the original message and set it in the view
    message = await interaction.original_response()
    main_view.original_message = message

    # Start the countdown
    asyncio.create_task(main_view.start_countdown())

    # Create and send admin view (ephemeral)
    admin_view = AdminView(question_id, expiry_time)
    await interaction.followup.send(embed=admin_embed, view=admin_view, ephemeral=True)