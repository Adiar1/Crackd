import discord
from discord import Interaction, Embed, ui
from utils.database import get_database_connection, archive_question


class ViewQuestionsPaginator(ui.View):
    """
    Paginator for navigating multiple embeds. Hides buttons when navigation isn't possible.
    """

    def __init__(self, embeds):
        super().__init__()
        self.embeds = embeds
        self.current_page = 0
        self.update_buttons()

    def update_buttons(self):
        """
        Dynamically update which buttons are visible based on the current page.
        """
        self.clear_items()
        if len(self.embeds) > 1:
            if self.current_page > 0:
                self.add_item(self.previous_page_button)
            if self.current_page < len(self.embeds) - 1:
                self.add_item(self.next_page_button)

    async def update_embed(self, interaction: Interaction):
        """
        Update the embed message to show the current page.
        """
        self.update_buttons()
        await interaction.response.edit_message(
            embed=self.embeds[self.current_page],
            view=self
        )

    @ui.button(label="◀️", style=discord.ButtonStyle.secondary)
    async def previous_page_button(self, interaction: Interaction, button: ui.Button):
        self.current_page -= 1
        await self.update_embed(interaction)

    @ui.button(label="▶️", style=discord.ButtonStyle.secondary)
    async def next_page_button(self, interaction: Interaction, button: ui.Button):
        self.current_page += 1
        await self.update_embed(interaction)


class AddQuestionButton(ui.View):
    def __init__(self):
        super().__init__()

    @ui.button(label="Add Question", style=discord.ButtonStyle.primary)
    async def add_question(self, interaction: Interaction, button: ui.Button):
        from commands.add_question import handle_add_question_command
        await handle_add_question_command(interaction)
        self.stop()


class ArchiveQuestionSelector(ui.View):
    """
    A view containing the multi-select dropdown and archive button for archiving questions.
    """

    def __init__(self, question_ids):
        super().__init__()
        self.add_item(ArchiveDropdown(question_ids[:25]))  # Discord limit of 25 options
        self.add_item(ArchiveButton())


class ArchiveButton(ui.Button):
    """
    Button to confirm archiving of selected questions.
    """

    def __init__(self):
        super().__init__(
            label="Archive Selected",
            style=discord.ButtonStyle.danger,
            custom_id="archive_selected"
        )

    async def callback(self, interaction: Interaction):
        # Get the dropdown from the view
        dropdown = [x for x in self.view.children if isinstance(x, ArchiveDropdown)][0]

        if not dropdown.values:
            await interaction.response.send_message(
                embed=Embed(
                    title="Archiving Error",
                    description="❌ Please select at least one question to archive.",
                    color=discord.Color.red()
                ),
                ephemeral=True
            )
            return

        # Archive all selected questions
        success_ids = []
        fail_ids = []
        for question_id in dropdown.values:
            if archive_question(int(question_id)):
                success_ids.append(question_id)
            else:
                fail_ids.append(question_id)

        # Create embed response
        embed = Embed(
            title="Archive Results",
            color=discord.Color.green() if success_ids else discord.Color.red()
        )

        if success_ids:
            embed.add_field(
                name="Successful Archives",
                value=f"✅ Archived {len(success_ids)} question(s)\nIDs: {', '.join(success_ids)}",
                inline=False
            )
        if fail_ids:
            embed.add_field(
                name="Failed Archives",
                value=f"❌ Failed to archive {len(fail_ids)} question(s)\nIDs: {', '.join(fail_ids)}",
                inline=False
            )

        await interaction.response.send_message(
            embed=embed,
            ephemeral=True
        )


class ArchiveDropdown(ui.Select):
    """
    Multi-select dropdown component for selecting questions to archive.
    """

    def __init__(self, question_ids):
        options = [
            discord.SelectOption(label=f"Question ID: {qid}", value=str(qid))
            for qid in question_ids
        ]
        super().__init__(
            placeholder="Select questions to archive...",
            options=options,
            min_values=1,
            max_values=len(options)
        )

    async def callback(self, interaction: Interaction):
        # Acknowledge the selection without taking action
        await interaction.response.defer()


def format_question(question) -> tuple[str, int]:
    """
    Format a single question and return the formatted text and its character count.
    Updated to work with new database schema with individual option columns.
    """
    question_id, type_, question_title, correct_answer, option_a, option_b, option_c, option_d, difficulty, domain, skill = question

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
    question_text = (
        f"**Question ID:** {question_id}\n"
        f"**Question:** {question_title}\n"
        f"{formatted_choices}\n"
        f"{directory_tree}\n"
        f"**Difficulty:** {difficulty.capitalize()}\n\n"
    )

    return question_text, len(question_text)


def create_paginated_embeds(questions, title, max_chars=4000):
    """
    Create paginated embeds for a specific question type, ensuring no embed exceeds
    the character limit. Using 2000 as a conservative limit (about half of Discord's
    actual limit) to account for any potential formatting or hidden characters.
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
        question_text, text_length = format_question(question)

        # If this single question is longer than max_chars, split it into multiple embeds
        if text_length > max_chars:
            # If current embed has content, add it to embeds
            if current_embed and current_embed.description:
                embeds.append(current_embed)

            # Split the long question into chunks
            chunks = []
            remaining_text = question_text
            while remaining_text:
                # Find the last newline before max_chars
                split_point = remaining_text[:max_chars].rfind('\n')
                if split_point == -1:  # If no newline found, force split at max_chars
                    split_point = max_chars

                chunks.append(remaining_text[:split_point])
                remaining_text = remaining_text[split_point:].lstrip()

            # Update total pages count
            total_pages = max(total_pages, len(embeds) + len(chunks))

            # Create new embeds for each chunk
            for chunk in chunks:
                new_embed = create_new_embed(len(embeds) + 1)
                new_embed.description = chunk
                embeds.append(new_embed)

            # Start fresh embed for next question
            current_embed = create_new_embed(len(embeds) + 1)
            character_count = 0
            continue

        # If this is the first question or adding this question would exceed the limit
        if current_embed is None or character_count + text_length > max_chars:
            if current_embed:
                embeds.append(current_embed)
            total_pages = max(total_pages, len(embeds) + 1)
            current_embed = create_new_embed(len(embeds) + 1)
            character_count = 0

        current_embed.description += question_text
        character_count += text_length

    # Add the final embed if not empty
    if current_embed and current_embed.description:
        embeds.append(current_embed)

    # Update all footers with the correct total page count
    for i, embed in enumerate(embeds, 1):
        embed.title = f"{title} (Page {i}/{total_pages})"
        embed.set_footer(text=f"Page {i} of {total_pages}")

    return embeds


async def handle_view_questions_command(interaction: Interaction):
    """
    Command to view all questions split by type (e.g., Math, EBRW).
    Each type has its own paginated embed.
    """
    conn = get_database_connection()
    c = conn.cursor()

    c.execute(
        """
        SELECT id, type, question, correct_answer, option_a, option_b, option_c, option_d, 
               difficulty, domain, skill
        FROM questions
        """
    )
    questions = c.fetchall()
    conn.close()

    if not questions:
        embed = Embed(
            title="No Questions Available",
            description="There are no questions available right now. Would you like to add one?",
            color=discord.Color.orange()
        )
        view = AddQuestionButton()
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
        return

    # Separate questions by type
    math_questions = [q for q in questions if q[1] == "math"]
    ebrw_questions = [q for q in questions if q[1] == "ebrw"]

    # Create paginated embeds with conservative character limit
    math_embeds = create_paginated_embeds(math_questions, "Math Questions")
    ebrw_embeds = create_paginated_embeds(ebrw_questions, "EBRW Questions")

    # Extract question IDs for the selector
    question_ids = [q[0] for q in questions]

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
                title="Math Questions",
                description="No Math questions available.",
                color=discord.Color.yellow()
            ),
            ephemeral=True
        )

    # Send EBRW embeds as a followup
    if ebrw_embeds:
        await interaction.followup.send(
            embed=ebrw_embeds[0],
            view=ViewQuestionsPaginator(ebrw_embeds),
            ephemeral=True
        )
    else:
        await interaction.followup.send(
            embed=Embed(
                title="EBRW Questions",
                description="No EBRW questions available.",
                color=discord.Color.yellow()
            ),
            ephemeral=True
        )

    # Add the archive question selector
    archive_view = ArchiveQuestionSelector(question_ids)
    await interaction.followup.send(
        embed=Embed(
            title="Archive Questions",
            description="Select questions to archive using the dropdown below:",
            color=discord.Color.blue()
        ),
        view=archive_view,
        ephemeral=True
    )