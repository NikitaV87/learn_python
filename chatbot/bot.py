# -*- coding: utf-8 -*-
# !usr/bin/env python3.8.5

import random
import logging
from io import BytesIO

import requests
import vk_api
from pony.orm import db_session
from vk_api.bot_longpoll import VkBotLongPoll, VkBotEventType

from chatbot import handlers

from chatbot.models import UserState, Registration

try:
    import chatbot.settings as cfg
except ImportError:
    exit('DO cp settings.py.default settings.py and set token!')

log = logging.getLogger('bot')


def configure_logging():
    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(logging.Formatter("%(levelname)s %(message)s"))
    stream_handler.setLevel(logging.INFO)

    file_handeler = logging.FileHandler(filename='bot.log', encoding='utf8')
    file_handeler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s", '%d.%m.%Y %H:%m'))
    file_handeler.setLevel(logging.DEBUG)

    log.addHandler(stream_handler)
    log.addHandler(file_handeler)

    log.setLevel(logging.DEBUG)


class Bot:
    """
    Сценарий регистрации на конференцию "SkillBox" через vk.com.
    Use Python3.8.5

    Поддерживает ответы на вопросы про дату, место проведения и сценарий регистрации:
    -Спрашиваем имя
    -спрашиваем e-mail
    -говорим об успешной регистрации
    Если шаг не пройден, задаем уточняющий вопрос пока шаг не будет пройден.
    """

    def __init__(self, group_id, token):
        """
        :param group_id: group id из группы в вк
        :param token: секретный токен
        """
        self.group_id = group_id
        self.token = token
        self.vk = vk_api.VkApi(token=token)
        self.long_poller = VkBotLongPoll(vk=self.vk, group_id=self.group_id)
        self.api = self.vk.get_api()

    def run(self):
        """
        Запуск бота
        """
        for event in self.long_poller.listen():
            try:
                self.on_event(event)
            except Exception:
                log.exception("Ошибка в обработке события")

    @db_session
    def on_event(self, event):
        """
        Отправляет сообщение назад
        :param event VkBotMessageEvent Object
        :return: None
        """
        if event.type != VkBotEventType.MESSAGE_NEW:
            log.info("Мы пока не умеем обрабатывать событие такого типа %s: ", event.type)
            return

        user_id = event.object.message['peer_id']
        text = event.message.text
        state = UserState.get(user_id=str(user_id))

        if state is not None:
            self.continue_scenario(text=text, state=state, user_id=user_id)
        else:
            # search intent
            for intent in cfg.INTENTS:
                if any(token in text.lower() for token in intent['tokens']):
                    # run intent
                    log.debug(f"User get: {intent}")
                    if intent['answer']:
                        self.send_text(text_to_send=intent['answer'], user_id=user_id)
                    else:
                        self.start_scenario(scenario_name=intent['scenario'], user_id=user_id, text=text)
                    break
            else:
                self.send_text(text_to_send=cfg.DEFAULT_ANSWER, user_id=user_id)

    def send_text(self, text_to_send: str, user_id: int):
        self.api.messages.send(message=text_to_send,
                               random_id=random.randint(0, 2 ** 20),
                               peer_id=user_id, )

    def send_image(self, image: BytesIO, user_id: int):
        upload_url = self.api.photos.getMessagesUploadServer()['upload_url']
        upload_data = requests.post(url=upload_url, files={'photo': ('image.png', image, 'image/png')}).json()
        image_data = self.api.photos.saveMessagesPhoto(**upload_data)
        owner_id = image_data[0]['owner_id']
        media_id = image_data[0]['id']
        attachment = f'photo{owner_id}_{media_id}'

        self.api.messages.send(attachment=attachment,
                               random_id=random.randint(0, 2 ** 20),
                               peer_id=user_id, )

    def send_step(self, step: dict, user_id: int, text: str, context: dict):
        if 'text' in step:
            self.send_text(step['text'].format(**context), user_id=user_id)
        if 'image' in step:
            handler = getattr(handlers, step['image'])
            image = handler(text, context)
            self.send_image(image=image, user_id=user_id)

    def start_scenario(self, scenario_name: str, user_id: int, text: str):
        scenario = cfg.SCENARIOS[scenario_name]
        first_step = scenario['first_step']
        step = scenario['steps'][first_step]
        self.send_step(step=step, user_id=user_id, text=text, context={})
        UserState(scenario_name=scenario_name, step_name=first_step, context={}, user_id=str(user_id))

    def continue_scenario(self, text: str, state: UserState, user_id: int):
        steps = cfg.SCENARIOS[state.scenario_name]['steps']
        step = steps[state.step_name]
        handler = getattr(handlers, step['handler'])
        if handler(text, context=state.context):
            # next step
            next_step = steps[step['next_step']]
            self.send_step(step=next_step, user_id=user_id, text=text, context=state.context)

            if next_step['next_step']:
                # switch to next step
                state.step_name = step['next_step']
            else:
                # finish scenario
                log.info('Зарегистрирован {name} {email}'.format(**state.context))
                Registration(name=state.context['name'], email=state.context['email'])
                state.delete()

        else:
            # retry current step
            text_to_send = step['failure_text'].format(**state.context)
            self.send_text(text_to_send=text_to_send, user_id=user_id)


if __name__ == '__main__':
    configure_logging()
    bot = Bot(group_id=cfg.GROUP_ID, token=cfg.KEY_TOKEN)
    bot.run()
