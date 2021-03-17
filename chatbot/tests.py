import os
from copy import deepcopy
from unittest import TestCase
from unittest.mock import patch, Mock

from pony.orm import db_session, rollback
from vk_api.bot_longpoll import VkBotMessageEvent
from chatbot import settings
from chatbot.bot import Bot
from chatbot.generate_ticket import generate_ticket


def isolate_db(func_test):
    def wrapper(*args, **kwargs):
        with db_session:
            func_test(*args, **kwargs)
            rollback()

    return wrapper


class Test1(TestCase):
    RAW_EVENT = {'type': 'message_new', 'object': {
        'message': {'date': 1600705878, 'from_id': 28840832, 'id': 105, 'out': 0, 'peer_id': 28840839, 'text': 'k',
                    'conversation_message_id': 104, 'fwd_messages': [], 'important': False, 'random_id': 0,
                    'attachments': [], 'is_hidden': False},
        'client_info': {'button_actions': ['text', 'vkpay', 'open_app', 'location', 'open_link'], 'keyboard': True,
                        'inline_keyboard': True, 'carousel': False, 'lang_id': 0}}, 'group_id': 198667864,
                 'event_id': 'da89e48d82b7d2f748089ba78e72b7fea69c253c'}
    IPUTUTS = ['Привет', 'А когда?', 'Где будет конференция?', 'Зарегистрируй меня', 'Вениамин',
               'мой адрес email@email', 'email@email.ru']
    EXEPTED_OUTPUTS = [settings.DEFAULT_ANSWER, settings.INTENTS[0]['answer'], settings.INTENTS[1]['answer'],
                       settings.SCENARIOS['registration']['steps']['step1']['text'],
                       settings.SCENARIOS['registration']['steps']['step2']['text'],
                       settings.SCENARIOS['registration']['steps']['step2']['failure_text'],
                       settings.SCENARIOS['registration']['steps']['step3']['text'].format(name='Вениамин',
                                                                                           email='email@email.ru')]

    def test_run(self):
        count = 5
        obj = {}
        events = [obj] * count
        long_poller_mock = Mock(return_value=events)
        long_poller_listen_mock = Mock()
        long_poller_listen_mock.listen = long_poller_mock
        with patch('chatbot.bot.vk_api.VkApi'):
            with patch('chatbot.bot.VkBotLongPoll', return_value=long_poller_listen_mock):
                bot = Bot('', '')
                bot.on_event = Mock()
                bot.send_image = Mock()
                bot.run()

                bot.on_event.assert_called()
                bot.on_event.assert_any_call(obj)
                assert bot.on_event.call_count == count

    @isolate_db
    def test_run_ok(self):
        send_mock = Mock()
        api_mock = Mock()
        api_mock.messages.send = send_mock

        events = []
        for input_text in self.IPUTUTS:
            event = deepcopy(self.RAW_EVENT)
            event['object']['message']['text'] = input_text
            events.append(VkBotMessageEvent(event))

        long_poller_mock = Mock()
        long_poller_mock.listen = Mock(return_value=events)

        with patch('chatbot.bot.VkBotLongPoll', return_value=long_poller_mock):
            bot = Bot('', '')
            bot.api = api_mock
            bot.send_image = Mock()
            bot.run()

        assert send_mock.call_count == len(self.IPUTUTS)

        real_outputs = []
        for call in send_mock.call_args_list:
            args, kwargs = call
            real_outputs.append(kwargs['message'])
        assert real_outputs == self.EXEPTED_OUTPUTS

    def test_image_generation(self):
        avatar_mock = Mock()
        with open(os.path.normpath('./files/test/avatar.png'), 'rb') as file_avatar:
            avatar_mock.content = file_avatar.read()
        with patch('chatbot.generate_ticket.requests.get', return_value=avatar_mock):
           ticket_file = generate_ticket('test', 'test@email.ru')
        with open(os.path.normpath('./files/test/teplete_complete.png'), 'rb') as ex_file:
            ex_bytes = ex_file.read()
        assert ticket_file.read() == ex_bytes
