from __future__ import annotations

from PIL import Image, ImageDraw, ImageFont, ImageFilter
import io
from redbot.core.data_manager import bundled_data_path

from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from .battle import Battle
    from .trainer import Trainer

# bg-size: 753x500 
# positions of sprites are hard coded according to bg-size
# size of sprites, screens, hazards, text are also harcoded according to bg-size

status_abbr = {
    "poison": "PSN",
    "b-poison": "PSN",
    "burn": "BRN",
    "paralysis": "PAR",
    "freeze": "FRZ",
    "sleep": "SLP"
}

def get_sprite_image(path, name: str) -> Image.Image:
    try:
        normalized_name = name.lower().replace("_", "-").replace(" ", "-")
        sprite_path = path / "nsprites" / f"{normalized_name}.png"
        sprite_img = Image.open(sprite_path)
        return sprite_img
    except FileNotFoundError:
        # look for base form sprite
        prefix = normalized_name.split("-")[0]
        sprite_path = path / "nsprites" / f"{prefix}.png"
        try:
            sprite_img = Image.open(sprite_path)
            return sprite_img
        except FileNotFoundError:
            print(f"Sprite not found of {prefix}, using default")
            fallback_path = path / "nsprites" / "a.png"
            return Image.open(fallback_path)

def get_misc_image(path, name: str) -> Image.Image:
    try:
        image_path = path / "misc" / f"{name}.png"
        sprite_img = Image.open(image_path).convert("RGBA")
        return sprite_img
    except FileNotFoundError:
        print(f"Image not found at {image_path}")
        fallback_path = path / "nsprites" / "a.png"
        return Image.open(fallback_path).convert("RGBA")

def get_text_dimensions(text, font):
    text_bbox = font.getbbox(text)
    text_width = text_bbox[2] - text_bbox[0]  # right - left
    text_height = text_bbox[3] - text_bbox[1]  # bottom - top
    return text_width, text_height

def draw_screens(image: Image.Image, position: tuple, size: tuple, color: tuple, blur_radius: int = 0, corner_radius: int = 0, stroke_width = 0, stroke_color = None):
    overlay = Image.new("RGBA", image.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    top_left = position
    bottom_right = (position[0] + size[0], position[1] + size[1])
    # x1 >= x0  and y1 >= y0 
    draw.rounded_rectangle([top_left, bottom_right], fill=color, radius=corner_radius)

    if stroke_width > 0 and stroke_color:
        draw.rounded_rectangle(
            [top_left[0] - stroke_width, top_left[1] - stroke_width, 
                bottom_right[0] + stroke_width, bottom_right[1] + stroke_width],
            outline=stroke_color,  
            width=stroke_width,    
            radius=corner_radius
        )

    mask = Image.new("L", image.size, 0)
    mask_draw = ImageDraw.Draw(mask)
    mask_draw.rounded_rectangle([top_left, bottom_right], fill=255, radius=corner_radius)

    if blur_radius > 0:
        blurred_image = image.filter(ImageFilter.GaussianBlur(blur_radius))
        image.paste(blurred_image, (0, 0), mask=mask)  
        image.paste(overlay, (0, 0), mask=overlay)  
    else:
        image.alpha_composite(overlay)

def team_preview(path, base_image, trainerteams: tuple):
    sprite_width = 80
    sprite_height = 60
    width, height = base_image.size

    draw_screens(base_image, (10, 10), (width-20, height-20), (0,0,0,24), 4, 20)

    for i, trainer in enumerate(trainerteams):
        x_pos, y_pos = ((width - sprite_width - 30, 0 + 30) if i == 1 else (30, height - sprite_height - 30))
        for name, lvl in trainer:
            sprite_img = get_sprite_image(path, name).resize((80, 60), Image.Resampling.NEAREST)
            if i == 0:
                sprite_img = sprite_img.transpose(Image.Transpose.FLIP_LEFT_RIGHT)

            base_image.paste(sprite_img, (x_pos, y_pos), sprite_img)

            font = ImageFont.truetype(path / "misc" / "Poppins-Bold.ttf", 16)
            text = f"{name} | Lvl.{lvl} "
            text_width, text_height = get_text_dimensions(text=text, font=font)

            draw = ImageDraw.Draw(base_image)
            text_x = (x_pos - text_width) if i == 1 else (x_pos + sprite_width)
            draw.text((text_x, y_pos + (sprite_height - text_height) // 2), text, fill="black", font=font)

            if i == 1:
                y_pos += sprite_height
            else:
                y_pos -= sprite_height


def generate_field_image(battle: Battle):

    path = bundled_data_path(battle.ctx.cog)
    font = ImageFont.truetype(path / "misc" / "Poppins-Bold.ttf", 16)

    extratext = ""
    field = get_misc_image(path, battle.bg)
    draw = ImageDraw.Draw(field)

    if battle.terrain.item:
        timg = get_misc_image(path, battle.terrain.item)
        field = timg
        draw = ImageDraw.Draw(field)
        extratext += f"- {battle.terrain.item} terrain\n"
    if battle.weather._weather_type != "":
        wimg = get_misc_image(path, battle.weather._weather_type.split("-")[-1])
        field = wimg
        draw = ImageDraw.Draw(field)
        extratext += f"- {battle.weather._weather_type} weather\n"

    if battle.trick_room.active():
        extratext += f"- trick room\n"
    if battle.magic_room.active():
        extratext += f"- magic room\n"
    if battle.wonder_room.active():
        extratext += f"- wonder room\n"
    if battle.gravity.active():
        extratext += f"- gravity\n"

    if extratext != "":
        text_bbox = draw.textbbox((0, 0), extratext, font=font)
        text_width = text_bbox[2] - text_bbox[0]
        text_height = text_bbox[3] - text_bbox[1]
        
        draw_screens(field, (-20, -20), (text_width+40, text_height+40), (0,0,0,24), 4, 14)
        draw.text((10, 5), extratext, font=font, fill=(0, 0, 0))

    Side(path=path, field=field, trainer=battle.trainer1, position=(90, 250), size=250, spec="l", behind_the_sprite=True).draw_side()
    Side(path=path, field=field, trainer=battle.trainer2, position=(450, 100), size=200, spec="r", behind_the_sprite=False).draw_side()

    img_buffer = io.BytesIO()
    field.save(img_buffer, format="PNG")
    img_buffer.seek(0)

    return img_buffer


class Side:
    def __init__(self, path, field: Image.Image, trainer: Trainer, position: tuple, size: int, spec: str, behind_the_sprite: bool):
        self.path = path
        self.field = field
        self.trainer = trainer
        self.position = position # of pokemon
        self.size = size
        self.spec = spec
        self.behind_the_sprite = behind_the_sprite
        self.mon = trainer.current_pokemon
        self.draw = ImageDraw.Draw(self.field)

    def reflect_and_lightscreen(self):
        screen_position = (self.position[0] + (50 if self.spec == "l" else -50), self.position[1] + (0 if self.spec == "l" else 40))
        size = ((230, 140) if self.spec == "l" else (210, 120))
        if self.trainer.reflect.active():
            draw_screens(self.field, position=(screen_position[0], screen_position[1]), size=size, color=(255, 215, 0, 128))
        if self.trainer.light_screen.active():
            draw_screens(self.field, position=(screen_position[0]+20, screen_position[1]+20), size=size, color=(231, 84, 128, 128))

    def hazards(self):
        y_displace = [10, 20, 15]
        if self.trainer.sticky_web:
            webimg = get_misc_image(self.path, "web")
            self.field.paste(webimg, (self.position[0] + 50, self.position[1] + 110), webimg)
        if self.trainer.stealth_rock:
            rockimg = get_misc_image(self.path, "rock1")
            for i in range(3):
                self.field.paste(rockimg, (self.position[0] + 40 + (40*i), self.position[1] + 140 + (y_displace[i])), rockimg)
        if self.trainer.toxic_spikes > 0:
            toxic_img = get_misc_image(self.path, "poisoncaltrop")
            for i in range(self.trainer.toxic_spikes):
                self.field.paste(toxic_img, (self.position[0] + 60 + (20*i), self.position[1] + 140 + (y_displace[i])), toxic_img)
        if self.trainer.spikes > 0:
            spikes_img = get_misc_image(self.path, "caltrop")
            for i in range(min(self.trainer.spikes, 3)):
                self.field.paste(spikes_img, (self.position[0] + 70 + (20*i), self.position[1] + 160 + (y_displace[i])), spikes_img)

    def sprite(self):
        if self.mon.substitute == 0:
            sprite_img = get_sprite_image(self.path, self.mon._name) 
        else:
            sprite_img = get_misc_image(self.path, "substitute")
        width, height = sprite_img.size
        aspect_ratio = width / height
        new_width = self.size
        new_height = int(new_width / aspect_ratio)
        if self.spec == "l":
            sprite_img = sprite_img.transpose(Image.Transpose.FLIP_LEFT_RIGHT)
        sprite_img = sprite_img.resize(
            (new_width, new_height), Image.Resampling.NEAREST
        )
        self.field.paste(sprite_img, self.position, sprite_img)
    
    def hp_bar(self):
        bar_height = 24
        bar_padding = 3

        percentage = self.mon.hp / self.mon.starting_hp
        bar_length = int(percentage * self.size)

        base_y = self.position[1] - 30
        hp_bar_base = [self.position[0], base_y, self.position[0] + self.size, base_y + bar_height]
        self.draw.rectangle(hp_bar_base, fill=(255, 255, 255))

        hp_bar = [
            self.position[0] + bar_padding,
            base_y + bar_padding,
            self.position[0] + bar_length - bar_padding,
            base_y + bar_height - bar_padding,
        ]
        hp_color = (
            (230, 28, 28)
            if percentage < 0.3
            else (232, 199, 14) if percentage < 0.6 else (0, 255, 0)
        )
        self.draw.rectangle(hp_bar, fill=hp_color)
        hp_text = f"{self.mon.hp}/{self.mon.starting_hp}"

        font = ImageFont.truetype(self.path / "misc" / "Poppins-Bold.ttf", 18)
        text_bbox = self.draw.textbbox((0, 0), hp_text, font=font)
        text_width = text_bbox[2] - text_bbox[0]
        text_height = text_bbox[3] - text_bbox[1]

        text_position = (
            self.position[0] + (self.size - text_width) / 2, 
            (base_y + (bar_height - text_height) / 2) - 1,
        )
        self.draw.text(text_position, hp_text, font=font, fill=(0, 0, 0))
        
        #STAT CHANGES
        stat_stages = {
            "atk": self.mon.attack_stage,
            "def": self.mon.defense_stage,
            "spa": self.mon.spatk_stage,
            "spd": self.mon.spdef_stage,
            "spe": self.mon.speed_stage,
            "acc": self.mon.accuracy_stage,
            "eva": self.mon.evasion_stage
        }
        stage_multiplier = {-6: 2/8, -5: 2/7, -4: 2/6, -3: 2/5, -2: 2/4, -1: 2/3,
                            0: 1, 1: 3/2, 2: 2, 3: 5/2, 4: 3, 5: 7/2, 6: 4,}
        stat_base_x = hp_bar_base[0] - 10
        stat_base_y = base_y - text_height 
        for stat_stage_str, stat_stage in stat_stages.items():
            if stat_stage == 0:
                continue 
            stagemul = round(stage_multiplier[stat_stage], 1)
            text = f"{stat_stage_str} {stagemul}x"
            text_width, text_height = get_text_dimensions(text=text, font=font)
            if stat_base_x + text_width >= hp_bar_base[2] and stat_base_y <= (base_y - (2*text_height) - 8):
                stat_base_x = hp_bar_base[0] - 10
                stat_base_y = stat_base_y - text_height - 8
            elif stat_base_x + text_width >= hp_bar_base[2]:
                stat_base_x = hp_bar_base[0] - 10
                stat_base_y = stat_base_y - text_height - 8

            if stat_stage < 0:
                draw_screens(self.field, (stat_base_x, stat_base_y), (text_width, text_height), color=(255, 0, 0, 128), blur_radius=20, corner_radius=5, stroke_width=3, stroke_color=(128, 0, 0, 255))
            else:
                draw_screens(self.field, (stat_base_x, stat_base_y), (text_width, text_height), color=(144, 238, 144, 128), blur_radius=20, corner_radius=5, stroke_width=3, stroke_color=(0, 128, 0, 255))
            self.draw.text((stat_base_x, stat_base_y - 5), text, font=font, fill=(255, 255, 255))
            stat_base_x += text_width + 5

        #STATUS
        nv_str = self.mon.nv.current
        if nv_str:
            if nv_str == "poison" or nv_str == "b-poison":  
                base_color = (128, 0, 128, 128)  
                stroke_color = (64, 0, 64, 255)
            elif nv_str == "burn": 
                base_color = (255, 120, 0, 128)
                stroke_color = (255, 140, 0, 255)
            elif nv_str == "paralysis":  
                base_color = (255, 255, 0, 128)
                stroke_color = (128, 128, 0, 255)
            elif nv_str == "freeze":  
                base_color = (173, 216, 230, 128)
                stroke_color = (0, 0, 255, 255)
            elif nv_str == "sleep": 
                base_color = (186, 85, 211, 128)
                stroke_color = (138, 43, 226, 255) 
            font = ImageFont.truetype(self.path / "misc" / "Poppins-Bold.ttf", 20)
            text_width, text_height = get_text_dimensions(text=status_abbr[nv_str], font=font)

            status_base_x = hp_bar_base[0]
            status_base_y = base_y + bar_height
            draw_screens(self.field, (status_base_x, status_base_y), (text_width, text_height), 
                        color=base_color, blur_radius=20, corner_radius=5, 
                        stroke_width=4, stroke_color=stroke_color)
            self.draw.text((status_base_x, status_base_y - 7), status_abbr[nv_str], font=font, fill=(255, 255, 255))
            
    def team(self):
        pokes = [mon for mon in self.trainer.party if mon.hp > 0 and mon != self.mon]
        sprite_width = 80
        sprite_height = 60
        field_width, field_height = self.field.size
        x_pos, y_pos = ((field_width - sprite_width, 0) if self.spec == "r" else (0, field_height - sprite_height))
        if self.spec == "l":
            draw_screens(self.field, (-20, field_height - (len(pokes)*sprite_height)), (sprite_width+16, field_height), (0,0,0,64), 4, 20)
        else:
            draw_screens(self.field, (field_width-sprite_width, -20), (field_width, len(pokes)*sprite_height + 30), (0,0,0,64), 4, 20)

        for poke in pokes:
            sprite_img = get_sprite_image(self.path, poke._name).resize((80, 60), Image.Resampling.NEAREST)
            if self.spec == "l":
                sprite_img = sprite_img.transpose(Image.Transpose.FLIP_LEFT_RIGHT)
            self.field.paste(sprite_img, (x_pos, y_pos), sprite_img)
            #STATUS
            nv_str = poke.nv.current
            if nv_str:
                if nv_str == "poison" or nv_str == "b-poison":  
                    base_color = (128, 0, 128, 128)  
                    stroke_color = (64, 0, 64, 255)
                elif nv_str == "burn":  
                    base_color = (255, 120, 0, 128)  
                    stroke_color = (255, 140, 0, 255)  
                elif nv_str == "paralysis":  
                    base_color = (255, 255, 0, 128)
                    stroke_color = (128, 128, 0, 255)
                elif nv_str == "freeze":  
                    base_color = (173, 216, 230, 128)
                    stroke_color = (0, 0, 255, 255)
                elif nv_str == "sleep": 
                    base_color = (186, 85, 211, 128)
                    stroke_color = (138, 43, 226, 255) 
                font = ImageFont.truetype(self.path / "misc" / "Poppins-Bold.ttf", 16)
                text_width, text_height = get_text_dimensions(text=status_abbr[nv_str], font=font)

                status_base_x = x_pos if self.spec == "l" else x_pos + 40
                status_base_y = y_pos + 10
                draw_screens(self.field, (status_base_x, status_base_y), (text_width, text_height), 
                            color=base_color, blur_radius=20, corner_radius=4, 
                            stroke_width=4, stroke_color=stroke_color)
                self.draw.text((status_base_x, status_base_y - 7), status_abbr[nv_str], font=font, fill=(255, 255, 255))

            if self.spec == "r":
                y_pos += sprite_height
            else:
                y_pos -= sprite_height

    def draw_side(self):
        actions = []
        if self.behind_the_sprite:
            actions = [self.hazards, self.reflect_and_lightscreen, self.sprite, self.hp_bar, self.team]
        else:
            actions = [self.sprite, self.hazards, self.reflect_and_lightscreen, self.hp_bar, self.team]
        for action in actions:
            action()
