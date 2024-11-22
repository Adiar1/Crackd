import discord
from discord import Interaction, Embed, ui, SelectOption
from commands.view_questions import ViewQuestionsPaginator
from utils.database import get_database_connection
from datetime import datetime


def format_archived_question(question) -> tuple[str, int]:
    """
    Format an archived question and return the formatted text and its character count.
    """
    question_id, type_, question_title, correct_answer, option_a, option_b, option_c, option_d, difficulty, domain, skill, archived_at = question

    # Format the answer choices with the correct answer bolded
    choices = [
        f"A) {option_a}",
        f"B) {option_b}",
        f"C) {option_c}",
        f"D) {option_d}"
    ]
    formatted_choices = "\n".join(
        f"**{choice}**" if choice.startswith(f"{correct_answer.upper()})") else choice
        for choice in choices
    )

    # Format the domain and skill as a directory tree
    directory_tree = f"**Domain/Skill:** `{domain}` ➔ `{skill}`"

    # Parse and format the archived date
    archived_date = datetime.strptime(archived_at, '%Y-%m-%d %H:%M:%S')
    formatted_date = archived_date.strftime('%B %d, %Y at %I:%M %p')

    question_text = (
        f"**Question ID:** {question_id}\n"
        f"**Question:** {question_title}\n"
        f"{formatted_choices}\n"
        f"{directory_tree}\n"
        f"**Difficulty:** {difficulty.capitalize()}\n"
        f"**Archived:** {formatted_date} UTC\n\n"
    )

    return question_text, len(question_text)


def create_paginated_embeds(questions, title, max_chars=4000):
    """
    Create paginated embeds for archived questions, ensuring no embed exceeds the character limit.
    """
    embeds = []
    current_embed = None
    character_count = 0
    total_pages = 1  # Will be updated as we create embeds

    def create_new_embed(page_num):
        new_embed = Embed(
            title=f"{title} (Page {page_num})",
            color=discord.Color.blue()
        )
        new_embed.set_footer(text=f"Page {page_num}/{total_pages}")
        new_embed.description = ""
        return new_embed

    for question in questions:
        question_text, text_length = format_archived_question(question)

        # If this single question is longer than max_chars, split it into multiple embeds
        if text_length > max_chars:
            if current_embed and current_embed.description:
                embeds.append(current_embed)

            # Split the long question into chunks
            remaining_text = question_text
            while remaining_text:
                split_point = remaining_text[:max_chars].rfind('\n')
                if split_point == -1:  # If no newline found, force split at max_chars
                    split_point = max_chars

                chunk = remaining_text[:split_point]
                remaining_text = remaining_text[split_point:].lstrip()

                new_embed = create_new_embed(len(embeds) + 1)
                total_pages = max(total_pages, len(embeds) + 1)
                new_embed.description = chunk
                embeds.append(new_embed)

            current_embed = None
            character_count = 0
            continue

        if current_embed is None or character_count + text_length > max_chars:
            if current_embed:
                embeds.append(current_embed)
            total_pages = max(total_pages, len(embeds) + 1)
            current_embed = create_new_embed(len(embeds) + 1)
            character_count = 0

        current_embed.description += question_text
        character_count += text_length

    if current_embed and current_embed.description:
        embeds.append(current_embed)

    # Update all footers with the correct total page count
    for i, embed in enumerate(embeds, 1):
        embed.title = f"{title} (Page {i}/{total_pages})"
        embed.set_footer(text=f"Page {i} of {total_pages}")

    return embeds


class ArchiveActionSelector(ui.View):
    """
    A view containing the multi-select dropdown and action buttons for archived questions.
    """

    def __init__(self, question_ids):
        super().__init__()
        self.add_item(ArchiveActionDropdown(question_ids[:25]))  # Discord limit of 25 options
        self.add_item(RecoverButton())
        self.add_item(DeleteButton())


class ArchiveActionDropdown(ui.Select):
    """
    Multi-select dropdown component for selecting archived questions.
    """

    def __init__(self, question_ids):
        options = [
            SelectOption(label=f"Question ID: {qid}", value=str(qid))
            for qid in question_ids
        ]
        super().__init__(
            placeholder="Select questions to recover or delete...",
            options=options,
            min_values=1,
            max_values=len(options)
        )

    async def callback(self, interaction: Interaction):
        # Acknowledge the selection without taking action
        await interaction.response.defer()


class DeleteButton(ui.Button):
    """
    Button to confirm and delete selected archived questions.
    """

    def __init__(self):
        super().__init__(
            label="Delete Questions",
            style=discord.ButtonStyle.danger,
            custom_id="delete_archived"
        )

    async def callback(self, interaction: Interaction):
        # Get the dropdown from the view
        dropdown = [x for x in self.view.children if isinstance(x, ArchiveActionDropdown)][0]

        if not dropdown.values:
            await interaction.response.send_message(
                embed=Embed(
                    title="Deletion Error",
                    description="❌ Please select at least one question to delete.",
                    color=discord.Color.red()
                ),
                ephemeral=True
            )
            return

        # Create a confirmation embed
        confirm_embed = Embed(
            title="Confirm Deletion",
            description=(
                f"Are you sure you want to permanently delete {len(dropdown.values)} archived question(s)? "
                "This action cannot be undone."
            ),
            color=discord.Color.red()
        )

        # Create a confirmation view
        class ConfirmationView(ui.View):
            @ui.button(label="Yes, Delete", style=discord.ButtonStyle.danger)
            async def confirm_delete(self, confirm_interaction: Interaction, button: ui.Button):
                conn = get_database_connection()
                c = conn.cursor()

                try:
                    c.execute("BEGIN TRANSACTION")
                    deleted_ids = []
                    for qid in dropdown.values:
                        c.execute("DELETE FROM question_archives WHERE id = ?", (int(qid),))
                        deleted_ids.append(qid)
                    c.execute("COMMIT")

                    # Create result embed
                    result_embed = Embed(
                        title="Deletion Complete",
                        description=f"✅ Successfully deleted {len(deleted_ids)} archived question(s).",
                        color=discord.Color.green()
                    )
                    result_embed.add_field(
                        name="Deleted Question IDs",
                        value=", ".join(deleted_ids),
                        inline=False
                    )
                    await confirm_interaction.response.edit_message(embed=result_embed, view=None)
                except Exception as e:
                    c.execute("ROLLBACK")
                    error_embed = Embed(
                        title="Deletion Failed",
                        description=f"❌ An error occurred: {str(e)}",
                        color=discord.Color.red()
                    )
                    await confirm_interaction.response.edit_message(embed=error_embed, view=None)
                finally:
                    conn.close()

            @ui.button(label="Cancel", style=discord.ButtonStyle.secondary)
            async def cancel(self, cancel_interaction: Interaction, button: ui.Button):
                cancel_embed = Embed(
                    title="Deletion Cancelled",
                    description="The deletion process was cancelled.",
                    color=discord.Color.blue()
                )
                await cancel_interaction.response.edit_message(embed=cancel_embed, view=None)

        await interaction.response.send_message(
            embed=confirm_embed,
            view=ConfirmationView(),
            ephemeral=True
        )


class RecoverButton(ui.Button):
    """
    Button to recover selected archived questions.
    """

    def __init__(self):
        super().__init__(
            label="Recover Questions",
            style=discord.ButtonStyle.success,
            custom_id="recover_archived"
        )

    async def callback(self, interaction: Interaction):
        # Get the dropdown from the view
        dropdown = [x for x in self.view.children if isinstance(x, ArchiveActionDropdown)][0]

        if not dropdown.values:
            await interaction.response.send_message(
                embed=Embed(
                    title="Recovery Error",
                    description="❌ Please select at least one question to recover.",
                    color=discord.Color.red()
                ),
                ephemeral=True
            )
            return

        conn = get_database_connection()
        c = conn.cursor()

        try:
            c.execute("BEGIN TRANSACTION")
            recovered_ids = []
            for qid in dropdown.values:
                # Retrieve the archived question
                c.execute("""
                        SELECT id, type, question, correct_answer, option_a, option_b, option_c, option_d, 
                               explanation, difficulty, domain, skill, image_url
                        FROM question_archives WHERE id = ?
                    """, (int(qid),))
                question_data = c.fetchone()

                if question_data:
                    # Unpack the data, skipping the ID
                    orig_id, *data = question_data

                    # Insert back into main questions table with the original ID
                    c.execute("""
                            INSERT OR REPLACE INTO questions (
                                id, type, question, correct_answer, option_a, option_b, option_c, option_d, 
                                explanation, difficulty, domain, skill, image_url
                            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """, (orig_id, *data))

                    # Remove from archives
                    c.execute("DELETE FROM question_archives WHERE id = ?", (int(qid),))
                    recovered_ids.append(str(orig_id))

            c.execute("COMMIT")

            # Create result embed
            result_embed = Embed(
                title="Recovery Complete",
                description=f"✅ Successfully recovered {len(recovered_ids)} question(s).",
                color=discord.Color.green()
            )
            result_embed.add_field(
                name="Recovered Question IDs",
                value=", ".join(recovered_ids),
                inline=False
            )
            await interaction.response.send_message(embed=result_embed, ephemeral=True)
        except Exception as e:
            c.execute("ROLLBACK")
            error_embed = Embed(
                title="Recovery Failed",
                description=f"❌ An error occurred: {str(e)}",
                color=discord.Color.red()
            )
            await interaction.response.send_message(embed=error_embed, ephemeral=True)
        finally:
            conn.close()


async def handle_view_archives_command(interaction: Interaction):
    """
    Command to view all archived questions with options to recover or delete.
    """
    conn = get_database_connection()
    c = conn.cursor()

    c.execute("""
        SELECT id, type, question, correct_answer, option_a, option_b, option_c, option_d, 
               difficulty, domain, skill, archived_at
        FROM question_archives
        ORDER BY archived_at DESC
    """)
    questions = c.fetchall()
    conn.close()

    if not questions:
        embed = Embed(
            title="No Archived Questions",
            description="There are no archived questions available.",
            color=discord.Color.orange()
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return

    # Separate questions by type
    math_questions = [q for q in questions if q[1] == "math"]
    ebrw_questions = [q for q in questions if q[1] == "ebrw"]

    # Create paginated embeds for Math and EBRW questions
    math_embeds = create_paginated_embeds(math_questions, "Archived Math Questions")
    ebrw_embeds = create_paginated_embeds(ebrw_questions, "Archived EBRW Questions")

    # Send embeds for Math if any
    if math_embeds:
        await interaction.response.send_message(
            embed=math_embeds[0],
            view=ViewQuestionsPaginator(math_embeds),
            ephemeral=True
        )
    else:
        await interaction.response.send_message(
            embed=Embed(
                title="Archived Math Questions",
                description="No archived Math questions available.",
                color=discord.Color.yellow()
            ),
            ephemeral=True
        )

    # Send EBRW embeds as a follow-up
    if ebrw_embeds:
        await interaction.followup.send(
            embed=ebrw_embeds[0],
            view=ViewQuestionsPaginator(ebrw_embeds),
            ephemeral=True
        )
    else:
        await interaction.followup.send(
            embed=Embed(
                title="Archived EBRW Questions",
                description="No archived EBRW questions available.",
                color=discord.Color.yellow()
            ),
            ephemeral=True
        )

    # Extract question IDs for the selector
    question_ids = [q[0] for q in questions]

    # Add multi-select dropdown for recovering or deleting questions
    archive_view = ArchiveActionSelector(question_ids)
    await interaction.followup.send(
        embed=Embed(
            title="Manage Archived Questions",
            description=(
                "Use the dropdown to select questions, then choose to either:\n"
                "• Recover questions back to the main question bank\n"
                "• Permanently delete archived questions"
            ),
            color=discord.Color.blue()
        ),
        view=archive_view,
        ephemeral=True
    )