"""
Handler - функция, которая принимает на вход text(текст входящего сообщения) и context (dict), а возращает bool:
True если шаг пройден, False если данные введены непрвильно.
"""
import re

from chatbot.generate_ticket import generate_ticket

re_name = re.compile(r'^[\w\-\s]{3,40}$')
re_email = re.compile(r'\b[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+\b')


def handle_name(text: str, context: dict):
    match = re.match(re_name, text)
    if match:
        context['name'] = text
        return True
    else:
        return False


def handle_email(text: str, context: dict):
    matches = re.findall(re_email, text)
    if matches:
        context['email'] = matches[0]
        return True
    else:
        return False


def generate_ticket_handler(text: str, context: dict):
    return generate_ticket(name=context['name'], email=context['email'])
