import discord
from discord.ext.commands import Bot
from utils.database import get_database_connection

# Predefined domains and skills
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


async def handle_edit_stats_command(bot: Bot, interaction: discord.Interaction, member: discord.Member):
    try:
        # Start the selection process with Question Type
        embed = discord.Embed(
            title=f"Edit Stats for {member.display_name}",
            description="Select a question type to start editing.",
            color=discord.Color.blue()
        )
        embed.add_field(name="Step", value="**1. Select Question Type**", inline=False)

        await interaction.response.send_message(
            embed=embed,
            view=DetailedStatsTypeView(member),
            ephemeral=True
        )
    except Exception as e:
        await interaction.response.send_message(f"An error occurred: {e}", ephemeral=True)


class DetailedStatsTypeView(discord.ui.View):
    def __init__(self, member: discord.Member):
        super().__init__()
        self.member = member
        self.add_item(DetailedStatsTypeSelect(member))


class DetailedStatsTypeSelect(discord.ui.Select):
    def __init__(self, member: discord.Member):
        options = [
            discord.SelectOption(label="Math", value="Math"),
            discord.SelectOption(label="EBRW", value="EBRW")
        ]
        super().__init__(placeholder="Select a Question Type...", options=options)
        self.member = member

    async def callback(self, interaction: discord.Interaction):
        question_type = self.values[0]

        # Get domains based on the selected question type
        domains = MATH_DOMAINS if question_type == "Math" else EBRW_DOMAINS

        embed = discord.Embed(
            title=f"Edit Stats for {self.member.display_name}",
            description=f"**Question Type:** {question_type}\nSelect a domain to continue.",
            color=discord.Color.blue()
        )
        embed.add_field(name="Step", value="**2. Select Domain**", inline=False)

        await interaction.response.edit_message(embed=embed, view=DetailedStatsDomainView(self.member, question_type, domains))


class DetailedStatsDomainView(discord.ui.View):
    def __init__(self, member: discord.Member, question_type: str, domains: dict):
        super().__init__()
        self.add_item(DetailedStatsDomainSelect(member, question_type, domains))


class DetailedStatsDomainSelect(discord.ui.Select):
    def __init__(self, member: discord.Member, question_type: str, domains: dict):
        options = [
            discord.SelectOption(label=domain, value=domain) for domain in domains.keys()
        ]
        super().__init__(placeholder="Select a Domain...", options=options)
        self.member = member
        self.question_type = question_type
        self.domains = domains

    async def callback(self, interaction: discord.Interaction):
        domain = self.values[0]
        skills = self.domains[domain]

        embed = discord.Embed(
            title=f"Edit Stats for {self.member.display_name}",
            description=(
                f"**Question Type:** {self.question_type}\n"
                f"**Domain:** {domain}\nSelect a skill to continue."
            ),
            color=discord.Color.blue()
        )
        embed.add_field(name="Step", value="**3. Select Skill**", inline=False)

        await interaction.response.edit_message(embed=embed, view=DetailedStatsSkillView(self.member, self.question_type, domain, skills))


class DetailedStatsSkillView(discord.ui.View):
    def __init__(self, member: discord.Member, question_type: str, domain: str, skills: list):
        super().__init__()
        self.add_item(DetailedStatsSkillSelect(member, question_type, domain, skills))


class DetailedStatsSkillSelect(discord.ui.Select):
    def __init__(self, member: discord.Member, question_type: str, domain: str, skills: list):
        options = [
            discord.SelectOption(label=skill, value=skill) for skill in skills
        ]
        super().__init__(placeholder="Select a Skill...", options=options)
        self.member = member
        self.question_type = question_type
        self.domain = domain

    async def callback(self, interaction: discord.Interaction):
        skill = self.values[0]

        # Fetch stats for the selected type, domain, and skill
        conn = get_database_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT total_correct, total_attempts
            FROM user_skill_stats
            WHERE user_id = ? AND question_type = ? AND domain = ? AND skill = ?
        """, (self.member.id, self.question_type.lower(), self.domain, skill))  # Ensure question_type is lowercase
        result = cursor.fetchone()
        conn.close()

        # Set default values if no data exists
        total_correct = result[0] if result else 0
        total_attempts = result[1] if result else 0

        # Show a modal to edit stats for the selected skill
        modal = DetailedStatsEditModal(
            question_type=self.question_type,
            domain=self.domain,
            skill=skill,
            total_correct=total_correct,
            total_attempts=total_attempts,
            member=self.member
        )
        await interaction.response.send_modal(modal)


class DetailedStatsEditModal(discord.ui.Modal, title="Edit Stats for Skill"):
    def __init__(self, question_type: str, domain: str, skill: str, total_correct: int, total_attempts: int, member: discord.Member):
        super().__init__()
        self.question_type = question_type  # Will be converted to lowercase before database insertion
        self.domain = domain
        self.skill = skill
        self.total_correct = total_correct
        self.total_attempts = total_attempts
        self.member = member

        # Text inputs for editing stats
        self.add_item(discord.ui.TextInput(
            label="Correct Count",
            placeholder=f"Current: {self.total_correct}",  # Display current value in the placeholder
            required=True,
            style=discord.TextStyle.short
        ))

        self.add_item(discord.ui.TextInput(
            label="Total Attempts",
            placeholder=f"Current: {self.total_attempts}",  # Display current value in the placeholder
            required=True,
            style=discord.TextStyle.short
        ))

    async def on_submit(self, interaction: discord.Interaction):
        try:
            new_total_correct = int(self.children[0].value)  # First input field
            new_total_attempts = int(self.children[1].value)  # Second input field

            # Convert question_type to lowercase for database insertion
            lowercase_question_type = self.question_type.lower()

            conn = get_database_connection()
            cursor = conn.cursor()

            # Update or insert the data into the database
            cursor.execute("""
                INSERT INTO user_skill_stats (user_id, question_type, domain, skill, total_correct, total_attempts)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(user_id, question_type, domain, skill)
                DO UPDATE SET total_correct = excluded.total_correct, total_attempts = excluded.total_attempts
            """, (
                self.member.id, lowercase_question_type, self.domain, self.skill, new_total_correct, new_total_attempts
            ))

            # Update overall stats in user_stats table
            cursor.execute("""
                SELECT SUM(total_correct), SUM(total_attempts)
                FROM user_skill_stats
                WHERE user_id = ?
            """, (self.member.id,))
            correct_sum, attempts_sum = cursor.fetchone()
            cursor.execute("""
                INSERT INTO user_stats (user_id, total_correct, total_attempts)
                VALUES (?, ?, ?)
                ON CONFLICT(user_id)
                DO UPDATE SET total_correct = excluded.total_correct, total_attempts = excluded.total_attempts
            """, (self.member.id, correct_sum, attempts_sum))

            conn.commit()
            conn.close()

            # Create a success embed message
            embed = discord.Embed(
                title="Stats Updated Successfully!",
                description=(
                    f"**Updated {self.member.mention}'s Stats:**\n"
                    f"`{self.question_type}` → `{self.domain}` → `{self.skill}`\n\n"
                    f"🟢 **Skill Stats:**\n"
                    f"• **Correct:** {new_total_correct}\n"
                    f"• **Attempts:** {new_total_attempts}\n\n"
                    f"🔵 **Overall Stats:**\n"
                    f"• **Correct:** {correct_sum}\n"
                    f"• **Attempts:** {attempts_sum}"
                ),
                color=discord.Color.green()
            )

            await interaction.response.send_message(embed=embed, ephemeral=True)

        except Exception as e:
            await interaction.response.send_message(
                f"An error occurred while updating the stats: {e}",
                ephemeral=True
            )