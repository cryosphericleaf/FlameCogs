import discord
from redbot.core.data_manager import bundled_data_path
import json
from .buttons import BattlePromptView, PreviewPromptView
from .FE import generate_field_image, get_misc_image, team_preview
import io


async def find(ctx, db, filter):
    """Fetch all matching rows from a data file."""
    path = str(bundled_data_path(ctx.cog) / db) + ".json"
    with open(path) as f:
        data = json.load(f)
    results = []
    for item in data:
        success = True
        for key, value in filter.items():
            if isinstance(value, dict):
                if "$nin" in value:
                    if item[key] in value["$nin"]:
                        success = False
                        break
            else:
                if item[key] != value:
                    success = False
                    break
        if success:
            results.append(item)
    return results

async def find_one(ctx, db, filter):
    """Fetch the first matching row from a data file."""
    results = await find(ctx, db, filter)
    if results:
        return results[0]
    return None


async def generate_team_preview(battle):
    """Generates a message for trainers to preview their team."""
    preview_view = PreviewPromptView(battle)
    battlefield = get_misc_image(bundled_data_path(battle.ctx.cog), battle.bg)
    p1_active_mons = tuple((mon._name, mon.level) for mon in battle.trainer1.party if mon.hp > 0)
    p2_active_mons = tuple((mon._name, mon.level) for mon in battle.trainer2.party if mon.hp > 0)
    trainerteams = (p1_active_mons, p2_active_mons)
    team_preview(bundled_data_path(battle.ctx.cog),battlefield, trainerteams)
    img_buffer = io.BytesIO()
    battlefield.save(img_buffer, format="PNG")
    img_buffer.seek(0)

    e = discord.Embed(title=f"Team Preview ({battle.trainer1.name} vs {battle.trainer2.name})", color=await battle.ctx.embed_color())
    file = discord.File(img_buffer, filename='field.png')
    e.set_image(url=f"attachment://{file.filename}")
    await battle.channel.send(embed=e, file=file,  view=preview_view)
    return preview_view

async def generate_main_battle_message(battle):
    """Generates a message representing the current state of the battle."""
    desc = ""
    
    if battle.weather._weather_type:
        desc += f"Weather: {battle.weather._weather_type.title()}\n" # TODO: pretty this output
    if battle.terrain.item:
        desc += f"Terrain: {battle.terrain.item.title()}\n" # TODO: pretty this output
    if battle.trick_room.active():
        desc += "Trick Room: Active\n"
    
    desc += "\n"
    desc += f"{battle.trainer1.name}'s {battle.trainer1.current_pokemon.name}\n"
    desc += f"  HP: {battle.trainer1.current_pokemon.hp}/{battle.trainer1.current_pokemon.starting_hp}\n"
    if battle.trainer1.current_pokemon.nv.current:
        desc += f"  Status: {battle.trainer1.current_pokemon.nv.current}\n"
    if battle.trainer1.current_pokemon.substitute:
        desc += "  Behind a substitute!\n"
    
    desc += "\n"
    desc += f"{battle.trainer2.name}'s {battle.trainer2.current_pokemon.name}\n"
    desc += f"  HP: {battle.trainer2.current_pokemon.hp}/{battle.trainer2.current_pokemon.starting_hp}\n"
    if battle.trainer2.current_pokemon.nv.current:
        desc += f"  Status: {battle.trainer2.current_pokemon.nv.current}\n"
    if battle.trainer2.current_pokemon.substitute:
        desc += "  Behind a substitute!\n"
    
    desc = f"```\n{desc.strip()}```"
    e = discord.Embed(
        title=f"Battle between {battle.trainer1.name} and {battle.trainer2.name}",
        color=await battle.ctx.embed_color(),
        description = desc,
    )
    e.set_footer(text="Who Wins!?")
    try: #aiohttp 3.7 introduced a bug in dpy which causes this to error when rate limited. This catch just lets the bot continue when that happens.
        img_data = generate_field_image(battle)
        battle_view = BattlePromptView(battle)
        if img_data:
            e = discord.Embed(title=f"Battle between {battle.trainer1.name} and {battle.trainer2.name}", color=await battle.ctx.embed_color(),)
            file = discord.File(img_data, filename='field.png')
            e.set_image(url=f"attachment://{file.filename}")
            await battle.channel.send(embed=e, file=file,  view=battle_view)
        else:
            await battle.channel.send(embed=e, view=battle_view)
    except RuntimeError:
        pass
    return battle_view

async def generate_text_battle_message(battle):
    """
    Send battle.msg in a boilerplate embed.
    
    Handles the message being too long.
    """
    page = ""
    pages = []
    base_embed = discord.Embed(color=await battle.ctx.embed_color())
    raw = battle.msg.strip().split("\n")
    for part in raw:
        if len(page + part) > 2000:
            embed = base_embed.copy()
            embed.description = page.strip()
            pages.append(embed)
            page = ""
        page += part + "\n"
    page = page.strip()
    if page:
        embed = base_embed.copy()
        embed.description = page
        pages.append(embed)
    for page in pages:
        await battle.channel.send(embed=page)
    battle.msg = ""
