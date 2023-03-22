import logging
import os
import time
from http import HTTPStatus
from json import JSONDecodeError

import requests
import telegram
from dotenv import load_dotenv

load_dotenv()

PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

RETRY_PERIOD = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f"OAuth {PRACTICUM_TOKEN}"}

HOMEWORK_VERDICTS = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}

logger = logging.getLogger(__name__)
logger.addHandler(logging.StreamHandler())


def check_tokens():
    """Checking tokens availability."""
    token_dict = {"PRACTICUM_TOKEN": PRACTICUM_TOKEN,
                  "TELEGRAM_TOKEN": TELEGRAM_TOKEN,
                  "TELEGRAM_CHAT_ID": TELEGRAM_CHAT_ID}
    for token_name, token_value in token_dict.items():
        if not token_value:
            logger.critical(f'Can not get {token_name}')
            exit()
        else:
            logger.info(f'Got token - {token_name}')
    return True


def send_message(bot, message):
    """Sending message to telegram, looking for correct telegram response."""
    try:
        bot.send_message(
            TELEGRAM_CHAT_ID,
            message
        )
        logger.debug(f'Message "{message}" sent')
    except telegram.error.TelegramError as error:
        logger.error(f'Can not send telegram message {error}')
        raise ValueError(f'Can not send telegram message {error}')


def get_api_answer(timestamp_now):
    """Sending request to Yandex Practicum API with current time."""
    current_time = timestamp_now or int(time.time())
    params_request = {
        'url': ENDPOINT,
        'headers': HEADERS,
        'params': {'from_date': current_time},
    }
    try:
        homework_status = requests.get(**params_request)
        logger.debug('Api request started')
    except requests.RequestException as error:
        logger.critical(f"API request error – {error}")
    except ConnectionError as error:
        logger.critical(f'{error} cen not connect to server')
    except JSONDecodeError as error:
        raise JSONDecodeError(f'Error in JSON - {error}')
    else:
        if homework_status.status_code != HTTPStatus.OK:
            error = f'{ENDPOINT} status code != 200'
            raise requests.HTTPError(error)
        return homework_status.json()


def check_response(response):
    """Checking correct response data."""
    logging.debug('Checking correct response data started')
    message = 'Incorrect type of response data'
    if not isinstance(response, dict):
        raise TypeError(message)
    elif 'homeworks' not in response:
        raise ValueError('No homework key in dict')
    homeworks = response.get('homeworks')
    if not isinstance(homeworks, list):
        raise TypeError(message)
    return homeworks


def parse_status(homework):
    """Getting homework status from json."""
    homework_name = homework.get("homework_name")
    status = homework.get("status")
    if 'homework_name' not in homework:
        message = 'No expected key in response'
        logger.error(message)
        raise KeyError(message)
    if status not in HOMEWORK_VERDICTS:
        message = 'Can not find this status in dict'
        logger.error(message)
        raise KeyError(message)
    verdict = HOMEWORK_VERDICTS[status]
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def main():
    """Runs bot tasks."""
    logger.debug('Checking tokens availability started')
    if not check_tokens():
        logger.critical("Can't get tokens")
        exit()
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    timestamp_now = int(time.time())
    last_hw = ''
    while True:
        try:
            response = get_api_answer(timestamp_now)
            homework_catalog = check_response(response)
            if not homework_catalog:
                message = 'No homework'
            else:
                message = parse_status(homework_catalog[0])
            if last_hw != message:
                send_message(
                    bot,
                    f'Attention! New HW status: {message}')
                last_hw = message
        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            logger.exception(message)
        finally:
            time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    logging.basicConfig(
        format='%(asctime)s'
               '%(name)s'
               '%(levelname)s'
               '%(message)s'
               '%(lineno)d',
        level=logging.INFO,
        filename='program.log',
        filemode='w'
    )
    main()
