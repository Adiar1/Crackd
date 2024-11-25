import re
import aiohttp
import discord
from discord import Interaction, Embed, ui, SelectOption
from utils.database import get_database_connection

# Constants remain the same
MATH_DOMAINS = {
    "Algebra": [
        "Linear equations in one variable",
        "Linear functions",
        "Linear equations in two variables",
        "Systems of two linear equations in two variables",
        "Linear inequalities in one or two variables"
    ],
    "Advanced Math": [
        "Nonlinear functions",
        "Nonlinear equations in one variable and systems of equations in two variables",
        "Equivalent expressions"
    ],
    "Problem-Solving and Data Analysis": [
        "Ratios, rates, proportional relationships, and units",
        "Percentages",
        "One-variable data: Distributions and measures of center and spread",
        "Two-variable data: Models and scatterplots",
        "Probability and conditional probability",
        "Inference from sample statistics and margin of error",
        "Evaluating statistical claims: Observational studies and experiments"
    ],
    "Geometry and Trigonometry": [
        "Area and volume",
        "Lines, angles, and triangles",
        "Right triangles and trigonometry",
        "Circles"
    ]
}

EBRW_DOMAINS = {
    "Information and Ideas": [
        "Central Ideas and Details",
        "Inferences",
        "Command of Evidence"
    ],
    "Craft and Structure": [
        "Words in Context",
        "Text Structure and Purpose",
        "Cross-Text Connections"
    ],
    "Expression of Ideas": [
        "Rhetorical Synthesis",
        "Transitions"
    ],
    "Standard English Conventions": [
        "Boundaries",
        "Form, Structure, and Sense"
    ]
}


class SmartEmbed:
    """Intelligent embed manager that handles Discord's size limits"""

    def __init__(self, title, color=discord.Color.blue()):
        self.pages = []
        self.current_embed = None
        self.title = title[:256]
        self.color = color
        self.create_new_embed()

    def create_new_embed(self):
        """Create a new embed page"""
        self.current_embed = Embed(title=self.title, color=self.color)
        self.char_count = len(self.title)
        self.field_count = 0

    def should_paginate(self, content_length):
        """Check if content would exceed Discord's limits"""
        return (self.field_count >= 25 or
                self.char_count + content_length > 6000)

    def add_field(self, name, value, inline=False):
        """Add a field, paginating if necessary"""
        name = name[:256]
        value = value[:1024]

        if self.should_paginate(len(name) + len(value)):
            self.pages.append(self.current_embed)
            self.create_new_embed()

        self.current_embed.add_field(name=name, value=value, inline=inline)
        self.field_count += 1
        self.char_count += len(name) + len(value)

    def set_description(self, description):
        """Set description with proper length limit"""
        description = description[:4096]
        self.current_embed.description = description
        self.char_count += len(description)

    def get_embeds(self):
        """Get all embeds including the current one"""
        if self.current_embed and (self.current_embed not in self.pages):
            self.pages.append(self.current_embed)
        return self.pages


class PaginationView(ui.View):
    def __init__(self, embeds):
        super().__init__(timeout=180)
        self.embeds = embeds
        self.current_page = 0
        self.update_buttons()

    def update_buttons(self):
        """Update button states based on current page"""
        self.previous_button.disabled = self.current_page == 0
        self.next_button.disabled = self.current_page == len(self.embeds) - 1

    @ui.button(label="◀️", style=discord.ButtonStyle.secondary)
    async def previous_button(self, interaction: Interaction, button: ui.Button):
        self.current_page = max(0, self.current_page - 1)
        self.update_buttons()
        await interaction.response.edit_message(
            embed=self.embeds[self.current_page],
            view=self
        )

    @ui.button(label="▶️", style=discord.ButtonStyle.secondary)
    async def next_button(self, interaction: Interaction, button: ui.Button):
        self.current_page = min(len(self.embeds) - 1, self.current_page + 1)
        self.update_buttons()
        await interaction.response.edit_message(
            embed=self.embeds[self.current_page],
            view=self
        )


class AddQuestionModal(ui.Modal, title="Add a New SAT Question"):
    def __init__(self, question_type):
        super().__init__()
        self.question_type = question_type

    question = ui.TextInput(
        label="Enter the question",
        style=discord.TextStyle.paragraph,
        placeholder="Type the SAT question here...",
        max_length=2000
    )
    choice_a = ui.TextInput(
        label="Enter answer choice A",
        placeholder="Type the text for choice A...",
        max_length=250
    )
    choice_b = ui.TextInput(
        label="Enter answer choice B",
        placeholder="Type the text for choice B...",
        max_length=250
    )
    choice_c = ui.TextInput(
        label="Enter answer choice C",
        placeholder="Type the text for choice C...",
        max_length=250
    )
    choice_d = ui.TextInput(
        label="Enter answer choice D",
        placeholder="Type the text for choice D...",
        max_length=250
    )

    async def on_submit(self, interaction: Interaction):
        question_data = {
            "type": self.question_type,
            "question": self.question.value,
            "choices": {
                "A": self.choice_a.value,
                "B": self.choice_b.value,
                "C": self.choice_c.value,
                "D": self.choice_d.value,
            }
        }

        interaction.client.question_data = question_data
        domains = MATH_DOMAINS if self.question_type == "math" else EBRW_DOMAINS
        domain_options = [SelectOption(label=domain, value=domain) for domain in domains.keys()]
        view = DomainSelectionView(domain_options)

        smart_embed = SmartEmbed("Select Domain")
        smart_embed.set_description(
            f"Please select the domain for this question:\n\n"
            f"**Question:** {question_data['question']}\n\n"
            f"**Answer Choices:**\n"
            f"A) {question_data['choices']['A']}\n"
            f"B) {question_data['choices']['B']}\n"
            f"C) {question_data['choices']['C']}\n"
            f"D) {question_data['choices']['D']}"
        )

        embeds = smart_embed.get_embeds()
        if len(embeds) > 1:
            view = PaginationView(embeds)

        await interaction.response.send_message(
            embed=embeds[0],
            view=view,
            ephemeral=True
        )


class ExplanationModal(ui.Modal, title="Add Explanation"):
    explanation = ui.TextInput(
        label="Enter explanation",
        style=discord.TextStyle.paragraph,
        placeholder="Explain the solution to this question...",
        max_length=2000
    )

    image_url = ui.TextInput(
        label="Optional Image URL",
        placeholder="Enter a link to an image (if applicable)...",
        required=False,
        max_length=500
    )

    async def validate_url(self, url):
        if not url:
            return True

        # Accept almost any URL that might be an image
        url_pattern = re.compile(
            r'^https?:\/\/'  # http:// or https://
            r'[^\s<>\"]*'  # Anything that's not whitespace or angle brackets
            r'(?:'  # Non-capturing group for optional image extensions
            r'\.(jpg|jpeg|png|gif|webp|svg|bmp|ico)|'  # Common image extensions
            r'\/[\w\-]+\.(jpg|jpeg|png|gif|webp|svg|bmp|ico)|'  # Path ending with extension
            r'.*\?.*=.*|'  # URLs with query parameters
            r'.*\.(com|net|org|edu)\/.*|'  # General domain URLs
            r'.*\/(id|image|img|photo|picture)\/.*|'  # Common image path keywords
            r'.*\/(static|media|images|photos|pictures)\/.*'  # Common media paths
            r')'
        )

        return bool(url_pattern.match(url))

        return bool(url_pattern.match(url))

    async def on_submit(self, interaction: Interaction):
        await interaction.response.defer(ephemeral=True)

        image_url = self.image_url.value.strip() if self.image_url.value else None

        # Store the explanation and image URL regardless of validation
        interaction.client.question_data["explanation"] = self.explanation.value
        interaction.client.question_data["image_url"] = image_url
        question_data = interaction.client.question_data

        # If there's an image URL but it's invalid, show a warning but continue the flow
        if image_url and not await self.validate_url(image_url):
            await interaction.followup.send(
                "⚠️ Warning: The image URL provided might not work correctly. "
                "The question will still be saved, but please verify the image URL.",
                ephemeral=True
            )

        smart_embed = SmartEmbed("Select the Correct Answer")
        smart_embed.set_description(
            f"Choose the correct answer for this question:\n\n"
            f"**Question:** {question_data['question']}\n\n"
            f"**Answer Choices:**\n"
            f"A) {question_data['choices']['A']}\n"
            f"B) {question_data['choices']['B']}\n"
            f"C) {question_data['choices']['C']}\n"
            f"D) {question_data['choices']['D']}"
        )

        embeds = smart_embed.get_embeds()
        view = CorrectAnswerView(question_data['choices'])

        if len(embeds) > 1:
            view = PaginationView(embeds)
            view.add_item(CorrectAnswerSelect([
                SelectOption(label=f"{letter}) {question_data['choices'][letter]}"[:100], value=letter)
                for letter in ["A", "B", "C", "D"]
            ]))

        await interaction.followup.send(embed=embeds[0], view=view, ephemeral=True)


class DomainSelectionView(ui.View):
    def __init__(self, options):
        super().__init__()
        self.add_item(DomainSelect(options))


class DomainSelect(ui.Select):
    def __init__(self, options):
        super().__init__(placeholder="Select domain...", options=options)

    async def callback(self, interaction: Interaction):
        interaction.client.question_data["domain"] = self.values[0]
        modal = ExplanationModal()
        await interaction.response.send_modal(modal)


class CorrectAnswerView(ui.View):
    def __init__(self, choices):
        super().__init__()
        options = [
            SelectOption(label=f"{letter}) {choices[letter]}"[:100], value=letter)
            for letter in ["A", "B", "C", "D"]
        ]
        self.add_item(CorrectAnswerSelect(options))


class CorrectAnswerSelect(ui.Select):
    def __init__(self, options):
        super().__init__(placeholder="Select correct answer...", options=options)

    async def callback(self, interaction: Interaction):
        interaction.client.question_data["correct_answer"] = self.values[0]
        question_data = interaction.client.question_data
        question_type = question_data["type"]
        domain = question_data["domain"]

        domains = MATH_DOMAINS if question_type == "math" else EBRW_DOMAINS
        skill_options = [SelectOption(label=skill, value=skill) for skill in domains[domain]]

        view = SkillSelectionView(skill_options)
        smart_embed = SmartEmbed("Select Skill")
        smart_embed.set_description(f"Please select the specific skill under domain **{domain}**")

        embeds = smart_embed.get_embeds()
        await interaction.response.edit_message(embed=embeds[0], view=view)


class SkillSelectionView(ui.View):
    def __init__(self, options):
        super().__init__()
        self.add_item(SkillSelect(options))


class SkillSelect(ui.Select):
    def __init__(self, options):
        super().__init__(placeholder="Select skill...", options=options)

    async def callback(self, interaction: Interaction):
        interaction.client.question_data["skill"] = self.values[0]

        difficulty_options = [
            SelectOption(label="Easy", value="easy"),
            SelectOption(label="Medium", value="medium"),
            SelectOption(label="Hard", value="hard")
        ]

        view = DifficultySelectionView(difficulty_options)
        smart_embed = SmartEmbed("Select Difficulty")
        smart_embed.set_description("Please select the difficulty level for this question.")

        embeds = smart_embed.get_embeds()
        await interaction.response.edit_message(embed=embeds[0], view=view)


class DifficultySelectionView(ui.View):
    def __init__(self, options):
        super().__init__()
        self.add_item(FinalizeEverything(options))


class FinalizeEverything(ui.Select):
    def __init__(self, options):
        super().__init__(placeholder="Select difficulty...", options=options)

    async def callback(self, interaction: Interaction):
        try:
            question_data = interaction.client.question_data
            question_data["difficulty"] = self.values[0]

            conn = get_database_connection()
            c = conn.cursor()

            c.execute(
                '''
                INSERT INTO questions (
                    type, question, correct_answer, 
                    option_a, option_b, option_c, option_d, 
                    explanation, difficulty, domain, skill, image_url
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''',
                (
                    question_data["type"],
                    question_data["question"],
                    question_data["correct_answer"],
                    question_data['choices']['A'],
                    question_data['choices']['B'],
                    question_data['choices']['C'],
                    question_data['choices']['D'],
                    question_data["explanation"],
                    question_data["difficulty"],
                    question_data["domain"],
                    question_data["skill"],
                    question_data["image_url"]
                )
            )

            # Get the ID of the last inserted row
            question_id = c.lastrowid

            conn.commit()
            conn.close()

            # Update the embed creation part to reflect the new structure
            smart_embed = SmartEmbed(f"Question ID {str(question_id)} Added Successfully", color=discord.Color.green())

            # First embed: Basic information and question
            smart_embed.add_field("Type", "Math" if question_data["type"] == "math" else "EBRW", True)
            smart_embed.add_field("Domain", question_data["domain"], True)
            smart_embed.add_field("Skill", question_data["skill"], True)
            smart_embed.add_field("Difficulty", question_data["difficulty"].capitalize(), True)

            # Make sure question gets its own embed if it's long
            if len(question_data["question"]) > 1000:
                smart_embed.pages.append(smart_embed.current_embed)
                smart_embed.create_new_embed()
            smart_embed.add_field("Question", question_data["question"], False)

            # Second embed: Answer choices and correct answer
            if smart_embed.should_paginate(1000):  # Approximate length of answer choices
                smart_embed.pages.append(smart_embed.current_embed)
                smart_embed.create_new_embed()

            answer_choices = (
                f"A) {question_data['choices']['A']}\n"
                f"B) {question_data['choices']['B']}\n"
                f"C) {question_data['choices']['C']}\n"
                f"D) {question_data['choices']['D']}"
            )
            smart_embed.add_field("Answer Choices", answer_choices, False)
            smart_embed.add_field(
                "Correct Answer",
                f"{question_data['correct_answer']}) {question_data['choices'][question_data['correct_answer']]}",
                False
            )

            # Third embed: Explanation (if needed)
            if len(question_data["explanation"]) > 1000:
                smart_embed.pages.append(smart_embed.current_embed)
                smart_embed.create_new_embed()
            smart_embed.add_field("Explanation", question_data["explanation"], False)

            # Add image to the last embed
            if question_data["image_url"]:
                if smart_embed.should_paginate(100):  # Small buffer for image
                    smart_embed.pages.append(smart_embed.current_embed)
                    smart_embed.create_new_embed()
                smart_embed.current_embed.set_image(url=question_data["image_url"])

            embeds = smart_embed.get_embeds()

            # Always use PaginationView if there are multiple embeds
            if len(embeds) > 1:
                view = PaginationView(embeds)
                await interaction.response.edit_message(embed=embeds[0], view=view)
            else:
                await interaction.response.edit_message(embed=embeds[0], view=None)

        except Exception as e:
            error_embed = SmartEmbed("Error Adding Question", color=discord.Color.red())
            error_embed.set_description(f"An error occurred: {str(e)[:4096]}")
            await interaction.response.edit_message(embed=error_embed.get_embeds()[0], view=None)


class AddQuestionView(ui.View):
    def __init__(self):
        super().__init__()

    @discord.ui.button(label="EBRW", style=discord.ButtonStyle.primary)
    async def ebrw_button(self, interaction: Interaction, button: discord.ui.Button):
        modal = AddQuestionModal(question_type="ebrw")
        await interaction.response.send_modal(modal)

    @discord.ui.button(label="Math", style=discord.ButtonStyle.primary)
    async def math_button(self, interaction: Interaction, button: discord.ui.Button):
        modal = AddQuestionModal(question_type="math")
        await interaction.response.send_modal(modal)

async def handle_add_question_command(interaction: Interaction):
    smart_embed = SmartEmbed("Add a New SAT Question")
    smart_embed.set_description("Select the type of question you'd like to add.")
    smart_embed.add_field("EBRW", "Evidence-Based Reading and Writing", False)
    smart_embed.add_field("Math", "Math questions for SAT preparation", False)

    view = AddQuestionView()
    await interaction.response.send_message(
        embed=smart_embed.get_embeds()[0],
        view=view,
        ephemeral=True
    )