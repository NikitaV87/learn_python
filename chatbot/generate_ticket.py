import os
from io import BytesIO

import requests
from PIL import Image, ImageFont, ImageDraw

PATH_TEMPLATE = os.path.normpath('./files/template.png')
PATH_FONT = os.path.normpath('./files/font/Roboto-Bold.ttf')
FONT_SIZE = 20
NAME_OFFSET = (245, 269)
EMAIL_OFFSET = (245, 314)
BLACK = (0, 0, 0, 255)
AVATAR_SIZE = 160
AVATAR_OFFSET = (15, 240)


def generate_ticket(name: str, email: str):
    base = Image.open(PATH_TEMPLATE).convert('RGBA')
    font = ImageFont.truetype(PATH_FONT, FONT_SIZE)

    draw = ImageDraw.Draw(base)
    draw.text(NAME_OFFSET, name, font=font, fill=BLACK)
    draw.text(EMAIL_OFFSET, email, font=font, fill=BLACK)

    response = requests.get(url=f'https://api.adorable.io/avatars/{AVATAR_SIZE}/{email}')
    avatar_file = BytesIO(response.content)
    avatar_img = Image.open(avatar_file)
    base.paste(avatar_img, AVATAR_OFFSET)

    temp_files = BytesIO()
    base.save(temp_files, 'png')
    temp_files.seek(0)

    return temp_files
