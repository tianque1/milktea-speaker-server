import asyncio
from typing import Callable

from anybot import Event
from anybot.message import *

from . import NoneBot
from .command import handle_command, SwitchException
from .log import logger
from .natural_language import handle_natural_language

_message_preprocessors = set()


def message_preprocessor(func: Callable) -> Callable:
    _message_preprocessors.add(func)
    return func


async def handle_message(bot: NoneBot, event: Event) -> None:
    _log_message(event)

    assert isinstance(event.message, Message)
    if not event.message:
        event.message.append(MessageSegment.text(''))

    coros = []
    for preprocessor in _message_preprocessors:
        coros.append(preprocessor(bot, event))
    if coros:
        await asyncio.wait(coros)

    raw_to_me = event.get('to_me', False)
    _check_at_me(bot, event)
    _check_calling_me_nickname(bot, event)
    event['to_me'] = raw_to_me or event['to_me']

    while True:
        try:
            handled = await handle_command(bot, event)
            break
        except SwitchException as e:
            # we are sure that there is no session existing now
            event['message'] = e.new_message
            event['to_me'] = True
    if handled:
        logger.info(f'Message {event.message_id} is handled as a command')
        return

    handled = await handle_natural_language(bot, event)
    if handled:
        logger.info(f'Message {event.message_id} is handled '
                    f'as natural language')
        return


def _check_at_me(bot: NoneBot, event: Event) -> None:
    if event.detail_type == 'private':
        event['to_me'] = True
    else:
        # group or discuss
        event['to_me'] = False


def _check_calling_me_nickname(bot: NoneBot, event: Event) -> None:
    first_msg_seg = event.message[0]
    if first_msg_seg.type != 'text':
        return

    first_text = first_msg_seg.data['text']

    if bot.config.NICKNAME:
        # check if the user is calling me with my nickname
        if isinstance(bot.config.NICKNAME, str) or \
                not isinstance(bot.config.NICKNAME, Iterable):
            nicknames = (bot.config.NICKNAME, )
        else:
            nicknames = filter(lambda n: n, bot.config.NICKNAME)
        nickname_regex = '|'.join(nicknames)
        m = re.search(rf'^({nickname_regex})([\s,，]*|$)', first_text,
                      re.IGNORECASE)
        if m:
            nickname = m.group(1)
            logger.debug(f'User is calling me {nickname}')
            event['to_me'] = True
            first_msg_seg.data['text'] = first_text[m.end():]


def _log_message(event: Event) -> None:
    logger.info(f'Self: {event.self_id}, message {event.message_id}: '
                f'{repr(str(event.message))}')
