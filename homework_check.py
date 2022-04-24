import json
import logging
import os
import time
from http.client import OK

import requests
import telegram
from dotenv import load_dotenv

import exceptions

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    filename='main.log',
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
)

logger = logging.getLogger(__name__)
handler = logging.StreamHandler()
logger.addHandler(handler)


PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

RETRY_TIME = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}


HOMEWORK_STATUSES = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}


def send_message(bot, message):
    """отправка сообщения ботом."""
    bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=message)
    try:
        bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=message)
    except telegram.TelegramError as error:
        message = f'Чата с таким id={TELEGRAM_CHAT_ID} не существует'
        logger.error(message)
        raise error


def get_api_answer(current_timestamp):
    """получение ответа от api."""
    timestamp = current_timestamp
    params = {'from_date': timestamp}
    try:
        api_answer = requests.get(ENDPOINT, headers=HEADERS, params=params)
    except requests.exceptions.RequestException as error:
        message = 'API вернул ошибку'
        logger.error(message)
        raise error
    if api_answer.status_code == OK:
        try:
            return api_answer.json()
        except json.decoder.JSONDecodeError as error:
            message = 'Ошибка раскодирования json'
            logger.error(message)
            raise error
    else:
        message = 'Ошибка при получении данных от API'
        logger.error(message)
        raise exceptions.CustomException(message)


def check_response(response):
    """проверка ответа."""
    try:
        homeworks = response['homeworks']
    except KeyError as error:
        message = f'Ошибка доступа по ключу homeworks: {error}'
        logger.error(message)
        raise exceptions.CustomException(message)
    if homeworks is None:
        message = 'Ответ API не содержит словарь'
        logger.error(message)
        raise exceptions.CustomException(message)
    if not isinstance(homeworks, list):
        message = 'Ответ API не является списком'
        logger.error(message)
        raise exceptions.CustomException(message)
    return homeworks


def parse_status(homework):
    """парсим текущий статус домашней работы."""
    if homework == {}:
        message = 'API ответ вернул пустой словарь'
        logger.critical(message)
        raise exceptions.CustomException(message)
    try:
        homework_name = homework.get('homework_name')
        homework_status = homework.get('status')
    except KeyError as error:
        logger.error(f'Ошибка индекса {error}')
        return None
    if HOMEWORK_STATUSES[homework_status] is None:
        message = 'Данного статуса не существует'
        logger.error(message)
        raise exceptions.CustomException
    try:
        verdict = HOMEWORK_STATUSES[homework_status]
    except KeyError:
        raise
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def check_tokens():
    """проверка токенов."""
    if PRACTICUM_TOKEN is None:
        return False
    if TELEGRAM_TOKEN is None:
        return False
    if TELEGRAM_CHAT_ID is None:
        return False
    return True


def main():
    """Основная логика работы бота."""
    if not check_tokens():
        message = 'Отсутствуют токены'
        logger.critical(message)
        raise exceptions.TokenException(message)
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    current_timestamp = int(time.time())
    homeworks = None
    while True:
        try:
            response = get_api_answer(current_timestamp)
            if homeworks != check_response(response):
                homeworks = check_response(response)
                message = parse_status(homeworks[0])
                send_message(bot, message)
            time.sleep(RETRY_TIME)
        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            send_message(bot, message)
            time.sleep(RETRY_TIME)
        else:
            time.sleep(RETRY_TIME)


if __name__ == '__main__':
    main()
