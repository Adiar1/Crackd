from discord import Interaction, Embed, Member
from utils.database import get_database_connection

async def handle_stats_command(interaction: Interaction, someone_else: Member = None):
    # Determine whose stats to fetch
    target_user = someone_else if someone_else else interaction.user
    user_id = target_user.id

    conn = get_database_connection()
    c = conn.cursor()

    # Fetch overall user stats
    c.execute('SELECT total_correct, total_attempts FROM user_stats WHERE user_id = ?', (user_id,))
    stats = c.fetchone()

    if stats is None or (stats[0] == 0 and stats[1] == 0):
        embed = Embed(
            title=f"Daily Problem Stats for {target_user.display_name}",
            color=0x2ecc71,
            description="No stats available yet."
        )
        await interaction.response.send_message(embed=embed)
        conn.close()
        return

    total_correct, total_attempts = stats
    overall_accuracy = (total_correct / total_attempts * 100) if total_attempts > 0 else 0

    # Fetch per-skill stats
    c.execute('''
        SELECT question_type, domain, skill, total_correct, total_attempts
        FROM user_skill_stats
        WHERE user_id = ? AND total_attempts > 0
    ''', (user_id,))
    skill_stats = c.fetchall()

    conn.close()

    # Create embed for stats
    embed = Embed(
        title=f"Daily Problem Stats for {target_user.display_name}",
        color=0x2ecc71
    )

    # Add overall stats
    embed.add_field(name="**Overall Stats**", value=f"**Correct Answers:** {total_correct}\n"
                                                    f"**Total Attempts:** {total_attempts}\n"
                                                    f"**Accuracy:** {overall_accuracy:.2f}%", inline=False)

    if not skill_stats:
        embed.add_field(name="**Detailed Stats**", value="No detailed stats available yet.", inline=False)
    else:
        # Organize stats by question type and domain
        detailed_stats = {}
        for question_type, domain, skill, total_correct, total_attempts in skill_stats:
            # Only include stats where there are attempts
            if total_attempts > 0:
                # Format question type to ensure "EBRW" and "Math" appear correctly
                formatted_question_type = "EBRW" if question_type.lower() == "ebrw" else question_type.capitalize()
                if formatted_question_type not in detailed_stats:
                    detailed_stats[formatted_question_type] = {}
                if domain not in detailed_stats[formatted_question_type]:
                    detailed_stats[formatted_question_type][domain] = []
                accuracy = (total_correct / total_attempts * 100)
                detailed_stats[formatted_question_type][domain].append((skill, total_correct, total_attempts, accuracy))

        # Add detailed stats to the embed
        for question_type, domains in detailed_stats.items():
            # Only add question types that have stats
            if domains:
                question_type_section = f"**{question_type} Questions**\n"
                for domain, skills in domains.items():
                    # Only add domains that have stats
                    if skills:
                        domain_section = f"- **{domain.capitalize()}**\n"
                        for skill, total_correct, total_attempts, accuracy in skills:
                            domain_section += (f"  - **{skill.capitalize()}**: {total_correct}/{total_attempts} "
                                           f"correct ({accuracy:.2f}%)\n")
                        question_type_section += domain_section
                if question_type_section != f"**{question_type} Questions**\n":
                    embed.add_field(name='', value=question_type_section, inline=False)

    await interaction.response.send_message(embed=embed)