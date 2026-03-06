import asyncio
import logging
import json
import os
import re
import random
from datetime import datetime, timedelta
from collections import Counter
from telethon import TelegramClient
from telethon.errors import FloodWaitError, ChatWriteForbiddenError, InviteHashExpiredError, InviteHashInvalidError
from telethon.tl.functions.messages import CheckChatInviteRequest, ImportChatInviteRequest, GetDiscussionMessageRequest
from telethon.tl.types import Message
import requests
from bs4 import BeautifulSoup
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes, MessageHandler, filters, ConversationHandler
import nest_asyncio
nest_asyncio.apply()

# ========== НАСТРОЙКИ ==========
# Данные для пользовательского аккаунта (комментатора)
USER_API_ID = 38611409
USER_API_HASH = 'f32e667381a1ac988b8530658ffbef0b'
USER_PHONE = '+17087366241'

# Данные для управляющего БОТА
BOT_TOKEN = "8687777365:AAFeI8nIQcYUgyYp0Ol3Fwrx_pdSYRFLxKA"

# СПИСОК АДМИНИСТРАТОРОВ (можно добавить несколько ID)
ADMIN_IDS = [
    8558085032,  # Твой ID
    # Добавьте сюда другие ID через запятую
    # 123456789,  # Пример другого админа
    # 987654321,  # Пример третьего админа
]

# Каналы для мониторинга
CHANNELS = []  # Публичные каналы
PRIVATE_CHANNELS = {}  # Приватные каналы {channel_id: invite_link}

# Настройки комментариев по умолчанию
COMMENT_TEXTS = [
    "я первый",
    "первый!",
    "кто первый?",
    "я здесь!",
    "топ 1"
]
COMMENT_TEXT = random.choice(COMMENT_TEXTS)

# ========== НАСТРОЙКИ УМНЫХ КОММЕНТАРИЕВ ==========
SMART_COMMENT_ENABLED = True  # Включен ли умный анализ

# Контекстные правила для разных типов заданий
CONTEXT_RULES = [
    # Формат: (паттерн для поиска, номер группы с нужным словом, описание)
    (r'(?:напиши|написать|отправь|отправить|скажи|сказать)\s+(?:слово\s+)?["]?([а-яa-z0-9]+)["]?', 1, "напиши слово"),
    (r'(?:слово|слово\s+дня|ключевое\s+слово)[:\s]+["]?([а-яa-z0-9]+)["]?', 1, "ключевое слово"),
    (r'(?:введи|введите|набери|набрать)\s+["]?([а-яa-z0-9]+)["]?', 1, "введи"),
    (r'кто\s+(?:первый|быстрее|раньше)\s+(?:напишет|напишет|скажет|отправит)\s+["]?([а-яa-z0-9]+)["]?', 1, "конкурс"),
    (r'(?:приз|подарок|бонус).*?(?:получить|выиграть).*?(?:написав|написать|сказав|сказать)\s+["]?([а-яa-z0-9]+)["]?', 1, "приз"),
]

# Ключевые слова для быстрого поиска
QUICK_KEYWORDS = {
    "розыгрыш": "участвую",
    "конкурс": "участвую",
    "giveaway": "I participate",
    "приз": "хочу приз",
    "подарок": "хочу подарок",
}

# ========== НАСТРОЙКИ АВТОМАТИЧЕСКОГО ОБУЧЕНИЯ ==========
AUTO_LEARN_ENABLED = True  # Включено ли автоматическое обучение
AUTO_LEARN_SETTINGS = {
    'min_word_length': 3,  # Минимальная длина слова для обучения
    'max_word_length': 20,  # Максимальная длина слова
    'min_occurrences': 2,  # Минимальное количество повторений для добавления
    'save_only_nouns': True,  # Сохранять только существительные (упрощенно)
    'ignore_common_words': True,  # Игнорировать общие слова
    'auto_add_threshold': 3,  # Порог для автоматического добавления (сколько раз слово встретилось)
    'max_keywords_to_learn': 100,  # Максимальное количество изучаемых ключевых слов
}

# Общие слова, которые игнорируем
COMMON_WORDS = {
    'и', 'в', 'во', 'не', 'что', 'он', 'на', 'я', 'с', 'со', 'как', 'а', 'то', 'все', 'она', 'так', 'его',
    'но', 'да', 'ты', 'к', 'у', 'же', 'вы', 'за', 'бы', 'по', 'только', 'ее', 'мне', 'было', 'вот', 'от',
    'меня', 'еще', 'нет', 'о', 'из', 'ему', 'теперь', 'когда', 'даже', 'ну', 'вдруг', 'ли', 'если', 'уже',
    'или', 'ни', 'быть', 'был', 'него', 'до', 'вас', 'нибудь', 'опять', 'уж', 'вам', 'ведь', 'там', 'потом',
    'себя', 'ничего', 'ей', 'может', 'они', 'тут', 'где', 'есть', 'надо', 'ней', 'для', 'мы', 'тебя', 'их',
    'чем', 'была', 'сам', 'чтоб', 'без', 'будто', 'чего', 'раз', 'тоже', 'себе', 'под', 'будет', 'ж', 'тогда',
    'кто', 'этот', 'того', 'потому', 'этого', 'какой', 'совсем', 'ним', 'здесь', 'этом', 'один', 'почти', 'мой',
    'тем', 'чтобы', 'нее', 'сейчас', 'были', 'куда', 'зачем', 'всех', 'никогда', 'можно', 'при', 'наконец', 'два',
    'об', 'другой', 'хоть', 'после', 'над', 'больше', 'тот', 'через', 'эти', 'нас', 'про', 'всего', 'них', 'какая',
    'много', 'разве', 'сказал', 'просто', 'свою', 'этой', 'перед', 'иногда', 'лучше', 'чуть', 'том', 'нельзя',
    'такой', 'им', 'более', 'всегда', 'конечно', 'всю', 'между'
}

# Статистика обучения
learning_stats = {
    'words_analyzed': 0,
    'potential_keywords': 0,
    'auto_added': 0,
    'ignored_common': 0,
    'ignored_short': 0,
    'ignored_long': 0
}

# Временное хранилище для обнаруженных слов
detected_words = Counter()
auto_learned_keywords = {}  # Слова, которые бот выучил автоматически

# Статистика умных комментариев
smart_stats = {
    'total_analyzed': 0,
    'matched_context': 0,
    'matched_keywords': 0,
    'manual_comments': 0
}

CHECK_INTERVAL = 30
MAX_CHANNELS = 50

# ========== ГЛОБАЛЬНЫЕ ПЕРЕМЕННЫЕ ==========
is_bot_running = False
last_posts = {}
DATA_FILE = "last_posts.json"
user_client = None
joined_private_channels = set()
comment_stats = {'total': 0, 'success': 0, 'failed': 0, 'last_comment_time': None}

# Режимы ожидания
waiting_for_private = False
waiting_for_public = False
waiting_for_text = False
waiting_for_interval = False
waiting_for_remove = False
waiting_for_add_admin = False
waiting_for_remove_admin = False
waiting_for_add_keyword = False
waiting_for_remove_keyword = False
waiting_for_add_pattern = False
waiting_for_remove_pattern = False
waiting_for_learn_settings = False

# ========== НАСТРОЙКА ЛОГОВ ==========
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Функция проверки прав администратора
def is_admin(user_id):
    """Проверяет, является ли пользователь администратором"""
    return user_id in ADMIN_IDS

# ========== ФУНКЦИИ РАБОТЫ С ДАННЫМИ ==========
def load_data():
    global last_posts, CHANNELS, PRIVATE_CHANNELS, COMMENT_TEXT, CHECK_INTERVAL, comment_stats, joined_private_channels, ADMIN_IDS
    global SMART_COMMENT_ENABLED, QUICK_KEYWORDS, CONTEXT_RULES, smart_stats
    global AUTO_LEARN_ENABLED, AUTO_LEARN_SETTINGS, learning_stats, detected_words, auto_learned_keywords
    
    try:
        if os.path.exists(DATA_FILE):
            with open(DATA_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                last_posts = data.get('last_posts', {})
                CHANNELS = data.get('channels', [])
                PRIVATE_CHANNELS = data.get('private_channels', {})
                joined_private_channels = set(data.get('joined_channels', []))
                COMMENT_TEXT = data.get('comment_text', COMMENT_TEXT)
                CHECK_INTERVAL = data.get('check_interval', CHECK_INTERVAL)
                comment_stats = data.get('stats', comment_stats)
                
                # Загружаем настройки умных комментариев
                SMART_COMMENT_ENABLED = data.get('smart_comment_enabled', SMART_COMMENT_ENABLED)
                QUICK_KEYWORDS.update(data.get('quick_keywords', {}))
                
                # Загружаем контекстные правила
                loaded_rules = data.get('context_rules', [])
                if loaded_rules:
                    CONTEXT_RULES.clear()
                    for rule in loaded_rules:
                        if len(rule) == 3:
                            CONTEXT_RULES.append((rule[0], rule[1], rule[2]))
                
                smart_stats.update(data.get('smart_stats', smart_stats))
                
                # Загружаем настройки автоматического обучения
                AUTO_LEARN_ENABLED = data.get('auto_learn_enabled', AUTO_LEARN_ENABLED)
                saved_settings = data.get('auto_learn_settings', {})
                if saved_settings:
                    AUTO_LEARN_SETTINGS.update(saved_settings)
                
                learning_stats.update(data.get('learning_stats', learning_stats))
                auto_learned_keywords.update(data.get('auto_learned_keywords', {}))
                
                # Загружаем обнаруженные слова (конвертируем обратно в Counter)
                detected_words_data = data.get('detected_words', {})
                detected_words.clear()
                detected_words.update(detected_words_data)
                
                # Загружаем список администраторов, если он есть в файле
                saved_admins = data.get('admin_ids', [])
                if saved_admins:
                    # Объединяем с текущим списком, но сохраняем уникальность
                    ADMIN_IDS = list(set(ADMIN_IDS + saved_admins))
                    
            logger.info(f"📂 Загружено: {len(CHANNELS)} публичных, {len(PRIVATE_CHANNELS)} приватных")
            logger.info(f"👥 Администраторов: {len(ADMIN_IDS)}")
            logger.info(f"🤖 Умные комментарии: {'включены' if SMART_COMMENT_ENABLED else 'выключены'}")
            logger.info(f"📚 Автообучение: {'включено' if AUTO_LEARN_ENABLED else 'выключено'}")
            logger.info(f"📊 Накоплено слов для анализа: {len(detected_words)}")
    except Exception as e:
        logger.error(f"Ошибка загрузки: {e}")

def save_data():
    try:
        # Конвертируем правила для JSON сериализации
        serializable_rules = []
        for pattern, group, desc in CONTEXT_RULES:
            serializable_rules.append([pattern, group, desc])
        
        data = {
            'last_posts': last_posts,
            'channels': CHANNELS,
            'private_channels': PRIVATE_CHANNELS,
            'joined_channels': list(joined_private_channels),
            'comment_text': COMMENT_TEXT,
            'check_interval': CHECK_INTERVAL,
            'stats': comment_stats,
            'admin_ids': ADMIN_IDS,
            'smart_comment_enabled': SMART_COMMENT_ENABLED,
            'quick_keywords': QUICK_KEYWORDS,
            'context_rules': serializable_rules,
            'smart_stats': smart_stats,
            'auto_learn_enabled': AUTO_LEARN_ENABLED,
            'auto_learn_settings': AUTO_LEARN_SETTINGS,
            'learning_stats': learning_stats,
            'detected_words': dict(detected_words),
            'auto_learned_keywords': auto_learned_keywords,
            'saved_at': datetime.now().isoformat()
        }
        with open(DATA_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        logger.info(f"💾 Данные сохранены")
    except Exception as e:
        logger.error(f"Ошибка сохранения: {e}")

def extract_channel_username(text):
    """Извлекает username из ссылки или текста"""
    text = text.strip()
    
    # Убираем @ в начале
    if text.startswith('@'):
        text = text[1:]
    
    # Извлекаем из URL
    patterns = [
        r'(?:https?://)?(?:www\.)?t\.me/([a-zA-Z0-9_]+)',
        r'(?:https?://)?(?:www\.)?telegram\.me/([a-zA-Z0-9_]+)',
        r'^([a-zA-Z0-9_]+)$'
    ]
    
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            username = match.group(1)
            if username and re.match(r'^[a-zA-Z0-9_]+$', username):
                return username.lower()
    
    return None

def is_private_invite_link(text):
    text = text.strip()
    return bool(re.search(r'(?:https?://)?(?:www\.)?t\.me/\+([a-zA-Z0-9_-]+)', text)) or \
           bool(re.search(r'(?:https?://)?(?:www\.)?t\.me/joinchat/([a-zA-Z0-9_-]+)', text))

# ========== ФУНКЦИИ ДЛЯ ПОЛЬЗОВАТЕЛЬСКОГО КЛИЕНТА ==========
async def init_user_client():
    global user_client
    try:
        if user_client is None:
            user_client = TelegramClient('user_session', USER_API_ID, USER_API_HASH)
            user_client.flood_sleep_threshold = 60
            await user_client.start(phone=USER_PHONE)
            me = await user_client.get_me()
            logger.info(f"✅ Вход выполнен: {me.first_name}")
        return user_client
    except Exception as e:
        logger.error(f"❌ Ошибка подключения: {e}")
        return None

# ========== ФУНКЦИЯ ВСТУПЛЕНИЯ В ПРИВАТНЫЙ КАНАЛ ==========
async def join_private_channel(client, invite_link):
    try:
        logger.info(f"🔐 Вступление: {invite_link}")
        
        if 'joinchat/' in invite_link:
            hash_part = invite_link.split('joinchat/')[-1].split('?')[0]
        elif '+' in invite_link:
            hash_part = invite_link.split('+')[-1].split('?')[0]
        else:
            hash_part = invite_link
            
        try:
            invite = await client(CheckChatInviteRequest(hash=hash_part))
            title = getattr(invite, 'title', 'Unknown')
        except Exception as e:
            return None, f"Ошибка проверки: {e}"
        
        try:
            updates = await client(ImportChatInviteRequest(hash=hash_part))
            for chat in updates.chats:
                if hasattr(chat, 'id'):
                    channel_id = f"private_{chat.id}"
                    title = getattr(chat, 'title', 'Unknown')
                    return channel_id, title
            return None, "Не удалось получить информацию"
        except InviteHashExpiredError:
            return None, "❌ Ссылка истекла"
        except InviteHashInvalidError:
            return None, "❌ Недействительная ссылка"
        except Exception as e:
            return None, f"❌ Ошибка: {str(e)[:100]}"
    except Exception as e:
        return None, str(e)

# ========== ФУНКЦИИ АВТОМАТИЧЕСКОГО ОБУЧЕНИЯ ==========
def extract_potential_keywords(text):
    """
    Извлекает потенциальные ключевые слова из текста
    """
    global learning_stats, detected_words, auto_learned_keywords
    
    if not text:
        return []
    
    # Приводим к нижнему регистру
    text_lower = text.lower()
    
    # Удаляем знаки препинания и разбиваем на слова
    words = re.findall(r'\b[а-яa-z]+\b', text_lower)
    
    potential_keywords = []
    
    for word in words:
        learning_stats['words_analyzed'] += 1
        
        # Проверяем длину слова
        if len(word) < AUTO_LEARN_SETTINGS['min_word_length']:
            learning_stats['ignored_short'] += 1
            continue
        
        if len(word) > AUTO_LEARN_SETTINGS['max_word_length']:
            learning_stats['ignored_long'] += 1
            continue
        
        # Игнорируем общие слова
        if AUTO_LEARN_SETTINGS['ignore_common_words'] and word in COMMON_WORDS:
            learning_stats['ignored_common'] += 1
            continue
        
        # Увеличиваем счетчик для этого слова
        detected_words[word] += 1
        
        # Если слово встретилось достаточно раз, добавляем в потенциальные ключевые
        if detected_words[word] >= AUTO_LEARN_SETTINGS['auto_add_threshold']:
            if word not in QUICK_KEYWORDS and word not in auto_learned_keywords:
                potential_keywords.append(word)
                learning_stats['potential_keywords'] += 1
                auto_learned_keywords[word] = detected_words[word]
    
    return potential_keywords

def auto_add_keyword(word):
    """
    Автоматически добавляет ключевое слово
    """
    global QUICK_KEYWORDS, learning_stats
    
    # Генерируем ответ на основе слова
    # Можно настроить различные варианты ответов
    responses = [
        word,  # само слово
        f"я {word}",  # "я слово"
        f"хочу {word}",  # "хочу слово"
        f"мне {word}",  # "мне слово"
        f"дайте {word}",  # "дайте слово"
    ]
    
    # Выбираем случайный ответ
    QUICK_KEYWORDS[word] = random.choice(responses)
    learning_stats['auto_added'] += 1
    
    return QUICK_KEYWORDS[word]

# ========== УЛУЧШЕННАЯ ФУНКЦИЯ АНАЛИЗА ПОСТА ==========
def analyze_post_and_get_comment(post_text):
    """
    Анализирует текст поста и возвращает подходящий комментарий
    на основе контекста и ключевых слов
    """
    global smart_stats
    
    if not post_text:
        return None
    
    post_text_lower = post_text.lower()
    smart_stats['total_analyzed'] += 1
    
    # 1. Сначала проверяем контекстные правила (самые важные)
    for pattern, group_num, description in CONTEXT_RULES:
        match = re.search(pattern, post_text_lower)
        if match:
            logger.info(f"🎯 Найден контекст: {description}")
            smart_stats['matched_context'] += 1
            
            # Извлекаем нужное слово из группы
            if group_num <= len(match.groups()):
                word_to_send = match.group(group_num)
                logger.info(f"📝 Нужно написать слово: '{word_to_send}'")
                
                # Добавляем это слово в обучение
                if AUTO_LEARN_ENABLED:
                    detected_words[word_to_send] += 1
                    if word_to_send not in QUICK_KEYWORDS and detected_words[word_to_send] >= AUTO_LEARN_SETTINGS['auto_add_threshold']:
                        auto_add_keyword(word_to_send)
                
                return word_to_send
    
    # 2. Проверяем быстрые ключевые слова
    for keyword, response in QUICK_KEYWORDS.items():
        if keyword.lower() in post_text_lower:
            logger.info(f"🎯 Найдено ключевое слово '{keyword}'")
            smart_stats['matched_keywords'] += 1
            
            # Если response - это список, выбираем случайный
            if isinstance(response, list):
                return random.choice(response)
            return response
    
    # 3. Если ничего не найдено, возвращаем None
    return None

# ========== ФУНКЦИИ КОММЕНТИРОВАНИЯ ==========
async def leave_comment(client, channel_identifier, post_id, post_text=None):
    global comment_stats, smart_stats
    
    try:
        if isinstance(channel_identifier, str) and channel_identifier.startswith('private_'):
            numeric_id = int(channel_identifier.replace('private_', ''))
            channel = await client.get_entity(numeric_id)
        else:
            channel = await client.get_entity(channel_identifier)
        
        post = await client.get_messages(channel, ids=int(post_id))
        if not post:
            return False, None
        
        comment_stats['total'] += 1
        
        # Определяем текст комментария
        comment_to_send = COMMENT_TEXT  # По умолчанию
        
        # Если включены умные комментарии и есть текст поста, анализируем
        if SMART_COMMENT_ENABLED and post_text:
            smart_comment = analyze_post_and_get_comment(post_text)
            if smart_comment:
                comment_to_send = smart_comment
                logger.info(f"🧠 Умный комментарий: '{comment_to_send}'")
                smart_stats['manual_comments'] += 1
            else:
                logger.info(f"📝 Обычный комментарий: '{comment_to_send}'")
        
        # Пробуем отправить комментарий
        try:
            # Пробуем отправить как комментарий к посту
            await client.send_message(entity=channel, message=comment_to_send, comment_to=post.id)
            comment_stats['success'] += 1
            comment_stats['last_comment_time'] = datetime.now().isoformat()
            save_data()
            return True, comment_to_send
        except Exception as e:
            # Если не получилось как комментарий, пробуем как обычный ответ
            try:
                await client.send_message(channel, comment_to_send, reply_to=post.id)
                comment_stats['success'] += 1
                return True, comment_to_send
            except Exception as e2:
                logger.error(f"Ошибка отправки: {e2}")
                comment_stats['failed'] += 1
                return False, None
    except Exception as e:
        logger.error(f"Ошибка комментирования: {e}")
        return False, None

# ========== ФУНКЦИЯ РАССЫЛКИ СООБЩЕНИЙ ВСЕМ АДМИНАМ ==========
async def notify_all_admins(bot, text, parse_mode='Markdown'):
    """Отправляет уведомление всем администраторам"""
    for admin_id in ADMIN_IDS:
        try:
            await bot.send_message(
                chat_id=admin_id,
                text=text,
                parse_mode=parse_mode
            )
        except Exception as e:
            logger.error(f"Не удалось отправить уведомление админу {admin_id}: {e}")

# ========== ФУНКЦИЯ ВОЗВРАТА В ГЛАВНОЕ МЕНЮ ==========
async def show_main_menu(update_or_query, text="🤖 **Управление ботом-комментатором**\n\nВыберите действие:", edit=True):
    """Показывает главное меню"""
    smart_status = "✅ Включены" if SMART_COMMENT_ENABLED else "❌ Выключены"
    learn_status = "✅ Включено" if AUTO_LEARN_ENABLED else "❌ Выключено"
    
    keyboard = [
        [InlineKeyboardButton("🚀 Запустить мониторинг", callback_data='start_bot')],
        [InlineKeyboardButton("⏹ Остановить", callback_data='stop_bot')],
        [InlineKeyboardButton("📊 Статус", callback_data='status')],
        [InlineKeyboardButton("📋 Список каналов", callback_data='channels')],
        [InlineKeyboardButton("⚙️ Настройки", callback_data='settings')],
        [InlineKeyboardButton("🧠 Умные комментарии", callback_data='smart_settings')],
        [InlineKeyboardButton("📚 Автообучение", callback_data='learn_settings')],
        [InlineKeyboardButton("👥 Управление админами", callback_data='admin_management')],
        [InlineKeyboardButton("➕ Добавить канал", callback_data='add_channel_menu')]
    ]
    
    if hasattr(update_or_query, 'message'):
        # Это callback query
        await update_or_query.edit_message_text(
            text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )
    else:
        # Это сообщение
        await update_or_query.reply_text(
            text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )

# ========== ОСНОВНОЙ ОБРАБОТЧИК ==========
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Старт"""
    user_id = update.effective_user.id
    
    if not is_admin(user_id):
        await update.message.reply_text("❌ У вас нет прав доступа к этому боту")
        # Уведомляем админов о попытке доступа
        await notify_all_admins(
            context.bot,
            f"⚠️ **Попытка несанкционированного доступа**\n"
            f"Пользователь: @{update.effective_user.username or 'нет username'}\n"
            f"ID: `{user_id}`\n"
            f"Имя: {update.effective_user.full_name}",
            parse_mode='Markdown'
        )
        return
    
    await show_main_menu(update.message)

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка кнопок"""
    # Все global объявления в самом начале функции
    global waiting_for_private, waiting_for_public, waiting_for_text, waiting_for_interval, waiting_for_remove
    global waiting_for_add_admin, waiting_for_remove_admin
    global waiting_for_add_keyword, waiting_for_remove_keyword, waiting_for_add_pattern, waiting_for_remove_pattern
    global waiting_for_learn_settings
    global is_bot_running, COMMENT_TEXT, CHECK_INTERVAL, SMART_COMMENT_ENABLED, QUICK_KEYWORDS, CONTEXT_RULES
    global AUTO_LEARN_ENABLED, AUTO_LEARN_SETTINGS, learning_stats, detected_words, auto_learned_keywords
    
    query = update.callback_query
    await query.answer()
    
    user_id = update.effective_user.id
    if not is_admin(user_id):
        await query.edit_message_text("❌ У вас нет прав")
        return
    
    if query.data == 'start_bot':
        if is_bot_running:
            await query.edit_message_text("❌ Бот уже запущен!")
        else:
            is_bot_running = True
            await query.edit_message_text("🚀 Запускаю мониторинг...")
            # Запускаем мониторинг в фоне
            asyncio.create_task(run_comment_bot(context.bot))
            # Уведомляем всех админов
            await notify_all_admins(
                context.bot,
                f"🚀 **Мониторинг запущен**\n"
                f"Администратор: @{update.effective_user.username or 'нет username'}\n"
                f"🧠 Умные комментарии: {'включены' if SMART_COMMENT_ENABLED else 'выключены'}\n"
                f"📚 Автообучение: {'включено' if AUTO_LEARN_ENABLED else 'выключено'}",
                parse_mode='Markdown'
            )
            # Показываем главное меню
            await asyncio.sleep(1)
            await show_main_menu(query, "✅ **Мониторинг запущен!**\n\nВыберите действие:")
    
    elif query.data == 'stop_bot':
        is_bot_running = False
        # Уведомляем всех админов
        await notify_all_admins(
            context.bot,
            f"⏹ **Мониторинг остановлен**\n"
            f"Администратор: @{update.effective_user.username or 'нет username'}"
        )
        await show_main_menu(query, "⏹ **Бот остановлен**\n\nВыберите действие:")
    
    elif query.data == 'status':
        smart_status = "✅ Включены" if SMART_COMMENT_ENABLED else "❌ Выключены"
        learn_status = "✅ Включено" if AUTO_LEARN_ENABLED else "❌ Выключено"
        
        # Топ-10 самых частых слов
        top_words = detected_words.most_common(10)
        top_words_text = ""
        if top_words:
            for word, count in top_words:
                status = "✅" if word in QUICK_KEYWORDS else "📝"
                top_words_text += f"{status} {word}: {count} раз\n"
        else:
            top_words_text = "Нет данных"
        
        text = f"📊 **СТАТУС**\n\n"
        text += f"🟢 Работает: {'✅' if is_bot_running else '❌'}\n"
        text += f"📝 Публичных каналов: {len(CHANNELS)}\n"
        text += f"🔐 Приватных каналов: {len(PRIVATE_CHANNELS)}\n"
        text += f"👥 Администраторов: {len(ADMIN_IDS)}\n"
        text += f"🧠 Умные комментарии: {smart_status}\n"
        text += f"📚 Автообучение: {learn_status}\n"
        text += f"💬 Текст по умолчанию: '{COMMENT_TEXT}'\n"
        text += f"⏱ Интервал проверки: {CHECK_INTERVAL} сек\n\n"
        
        text += f"📈 **Статистика комментариев:**\n"
        text += f"• Всего: {comment_stats['success'] + comment_stats['failed']}\n"
        text += f"• Успешно: {comment_stats['success']}\n"
        text += f"• Ошибок: {comment_stats['failed']}\n\n"
        
        text += f"📊 **Статистика умных комментариев:**\n"
        text += f"• Проанализировано постов: {smart_stats['total_analyzed']}\n"
        text += f"• Найдено контекстов: {smart_stats['matched_context']}\n"
        text += f"• Найдено ключевых слов: {smart_stats['matched_keywords']}\n"
        text += f"• Отправлено умных: {smart_stats['manual_comments']}\n\n"
        
        text += f"📚 **Статистика обучения:**\n"
        text += f"• Проанализировано слов: {learning_stats['words_analyzed']}\n"
        text += f"• Потенциальных ключевых: {learning_stats['potential_keywords']}\n"
        text += f"• Автоматически добавлено: {learning_stats['auto_added']}\n"
        text += f"• Игнорировано общих слов: {learning_stats['ignored_common']}\n"
        text += f"• Слов в словаре: {len(detected_words)}\n\n"
        
        text += f"📌 **Топ-10 слов:**\n{top_words_text}"
        
        keyboard = [[InlineKeyboardButton("🔙 В главное меню", callback_data='back_to_menu')]]
        await query.edit_message_text(
            text, 
            parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    
    elif query.data == 'learn_settings':
        # Настройки автообучения
        text = f"📚 **АВТООБУЧЕНИЕ**\n\n"
        text += f"**Статус:** {'✅ Включено' if AUTO_LEARN_ENABLED else '❌ Выключено'}\n\n"
        text += f"**Текущие настройки:**\n"
        text += f"• Мин. длина слова: {AUTO_LEARN_SETTINGS['min_word_length']}\n"
        text += f"• Макс. длина слова: {AUTO_LEARN_SETTINGS['max_word_length']}\n"
        text += f"• Порог добавления: {AUTO_LEARN_SETTINGS['auto_add_threshold']} повторений\n"
        text += f"• Игнорировать общие слова: {'✅' if AUTO_LEARN_SETTINGS['ignore_common_words'] else '❌'}\n"
        text += f"• Макс. слов для изучения: {AUTO_LEARN_SETTINGS['max_keywords_to_learn']}\n\n"
        
        text += f"**Статистика:**\n"
        text += f"• Слов в словаре: {len(detected_words)}\n"
        text += f"• Автоматически выучено: {len(auto_learned_keywords)}\n"
        text += f"• Всего проанализировано слов: {learning_stats['words_analyzed']}\n\n"
        
        # Показываем последние выученные слова
        if auto_learned_keywords:
            recent = list(auto_learned_keywords.items())[-10:]
            text += f"**Последние выученные слова:**\n"
            for word, count in recent:
                status = "✅" if word in QUICK_KEYWORDS else "⏳"
                text += f"{status} {word} (встреч: {count})\n"
        
        keyboard = [
            [InlineKeyboardButton("🔛 Вкл/Выкл автообучение", callback_data='toggle_learn')],
            [InlineKeyboardButton("⚙️ Настроить параметры", callback_data='configure_learn')],
            [InlineKeyboardButton("📊 Применить выученные", callback_data='apply_learned')],
            [InlineKeyboardButton("🗑 Очистить словарь", callback_data='clear_detected')],
            [InlineKeyboardButton("🔙 В главное меню", callback_data='back_to_menu')]
        ]
        await query.edit_message_text(
            text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )
    
    elif query.data == 'toggle_learn':
        AUTO_LEARN_ENABLED = not AUTO_LEARN_ENABLED
        save_data()
        await query.edit_message_text(f"✅ Автообучение {'включено' if AUTO_LEARN_ENABLED else 'выключено'}")
        await asyncio.sleep(1)
        await show_main_menu(query)
    
    elif query.data == 'configure_learn':
        waiting_for_learn_settings = True
        current = AUTO_LEARN_SETTINGS
        await query.edit_message_text(
            f"⚙️ **НАСТРОЙКА АВТООБУЧЕНИЯ**\n\n"
            f"Текущие параметры:\n"
            f"1. Мин. длина слова: {current['min_word_length']}\n"
            f"2. Макс. длина слова: {current['max_word_length']}\n"
            f"3. Порог добавления: {current['auto_add_threshold']}\n"
            f"4. Игнорировать общие слова: {current['ignore_common_words']}\n"
            f"5. Макс. слов: {current['max_keywords_to_learn']}\n\n"
            f"Введите номер параметра и новое значение через пробел\n"
            f"Пример: 1 5 (установит мин. длину = 5)\n\n"
            f"Или /cancel",
            parse_mode='Markdown'
        )
    
    elif query.data == 'apply_learned':
        # Применяем все выученные слова как ключевые
        added = 0
        for word in auto_learned_keywords:
            if word not in QUICK_KEYWORDS:
                response = auto_add_keyword(word)
                added += 1
        
        save_data()
        await query.edit_message_text(f"✅ Добавлено {added} новых ключевых слов из выученных")
        await asyncio.sleep(1)
        await show_main_menu(query)
    
    elif query.data == 'clear_detected':
        detected_words.clear()
        auto_learned_keywords.clear()
        learning_stats['potential_keywords'] = 0
        learning_stats['auto_added'] = 0
        save_data()
        await query.edit_message_text("✅ Словарь обнаруженных слов очищен")
        await asyncio.sleep(1)
        await show_main_menu(query)
    
    elif query.data == 'smart_settings':
        # Список ключевых слов
        keywords_text = ""
        for i, (keyword, response) in enumerate(QUICK_KEYWORDS.items(), 1):
            if isinstance(response, list):
                response = f"[{', '.join(response)}]"
            # Отмечаем выученные слова
            learned = "📚" if keyword in auto_learned_keywords else ""
            keywords_text += f"{i}. {learned} '{keyword}' → '{response}'\n"
        
        # Список контекстных правил
        rules_text = ""
        for i, (pattern, group, desc) in enumerate(CONTEXT_RULES, 1):
            rules_text += f"{i}. [{desc}] '{pattern}' → группа {group}\n"
        
        text = f"🧠 **УМНЫЕ КОММЕНТАРИИ**\n\n"
        text += f"**Статус:** {'✅ Включены' if SMART_COMMENT_ENABLED else '❌ Выключены'}\n\n"
        text += f"**🔑 Ключевые слова ({len(QUICK_KEYWORDS)}):**\n{keywords_text or 'Нет ключевых слов'}\n\n"
        text += f"**📋 Контекстные правила ({len(CONTEXT_RULES)}):**\n{rules_text or 'Нет правил'}\n\n"
        text += f"**Статистика:**\n"
        text += f"• Найдено контекстов: {smart_stats['matched_context']}\n"
        text += f"• Найдено ключевых: {smart_stats['matched_keywords']}\n"
        text += f"• Отправлено умных: {smart_stats['manual_comments']}"
        
        keyboard = [
            [InlineKeyboardButton("🔛 Вкл/Выкл", callback_data='toggle_smart')],
            [InlineKeyboardButton("➕ Добавить ключевое слово", callback_data='add_keyword')],
            [InlineKeyboardButton("➖ Удалить ключевое слово", callback_data='remove_keyword')],
            [InlineKeyboardButton("➕ Добавить правило", callback_data='add_pattern')],
            [InlineKeyboardButton("➖ Удалить правило", callback_data='remove_pattern')],
            [InlineKeyboardButton("📊 Сбросить статистику", callback_data='reset_smart_stats')],
            [InlineKeyboardButton("🔙 В главное меню", callback_data='back_to_menu')]
        ]
        await query.edit_message_text(
            text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )
    
    elif query.data == 'toggle_smart':
        SMART_COMMENT_ENABLED = not SMART_COMMENT_ENABLED
        save_data()
        await query.edit_message_text(f"✅ Умные комментарии {'включены' if SMART_COMMENT_ENABLED else 'выключены'}")
        await asyncio.sleep(1)
        await show_main_menu(query, f"✅ **Настройки сохранены!**\n\nВыберите действие:")
    
    elif query.data == 'add_keyword':
        waiting_for_add_keyword = True
        await query.edit_message_text(
            "➕ **ДОБАВЛЕНИЕ КЛЮЧЕВОГО СЛОВА**\n\n"
            "Введите в формате: слово=ответ\n"
            "Пример: розыгрыш=участвую\n"
            "Или: конкурс=участвую\n\n"
            "Можно указать несколько вариантов ответа через запятую:\n"
            "приз=хочу приз,мне приз,дайте приз\n\n"
            "Или /cancel для отмены",
            parse_mode='Markdown'
        )
    
    elif query.data == 'remove_keyword':
        if not QUICK_KEYWORDS:
            await query.edit_message_text("❌ Нет ключевых слов для удаления")
            await asyncio.sleep(1)
            await show_main_menu(query)
            return
        
        keywords_list = "\n".join([f"{i+1}. {k} → {v}" for i, (k, v) in enumerate(QUICK_KEYWORDS.items())])
        waiting_for_remove_keyword = True
        await query.edit_message_text(
            f"➖ **УДАЛЕНИЕ КЛЮЧЕВОГО СЛОВА**\n\n"
            f"**Текущие ключевые слова:**\n{keywords_list}\n\n"
            f"Введите ключевое слово для удаления:\n"
            f"Или /cancel",
            parse_mode='Markdown'
        )
    
    elif query.data == 'add_pattern':
        waiting_for_add_pattern = True
        await query.edit_message_text(
            "➕ **ДОБАВЛЕНИЕ КОНТЕКСТНОГО ПРАВИЛА**\n\n"
            "Введите в формате: regex=описание\n"
            "Пример: (?:напиши|написать)\\s+(\\w+)=напиши слово\n"
            "Или: кто первый напишет (\\w+)=конкурс\n\n"
            "Правило автоматически использует первую группу как ответ\n\n"
            "Или /cancel для отмены",
            parse_mode='Markdown'
        )
    
    elif query.data == 'remove_pattern':
        if not CONTEXT_RULES:
            await query.edit_message_text("❌ Нет правил для удаления")
            await asyncio.sleep(1)
            await show_main_menu(query)
            return
        
        rules_list = "\n".join([f"{i+1}. [{desc}] {p}" for i, (p, g, desc) in enumerate(CONTEXT_RULES)])
        waiting_for_remove_pattern = True
        await query.edit_message_text(
            f"➖ **УДАЛЕНИЕ ПРАВИЛА**\n\n"
            f"**Текущие правила:**\n{rules_list}\n\n"
            f"Введите описание правила для удаления:\n"
            f"Или /cancel",
            parse_mode='Markdown'
        )
    
    elif query.data == 'reset_smart_stats':
        smart_stats['total_analyzed'] = 0
        smart_stats['matched_context'] = 0
        smart_stats['matched_keywords'] = 0
        smart_stats['manual_comments'] = 0
        save_data()
        await query.edit_message_text("✅ Статистика умных комментариев сброшена")
        await asyncio.sleep(1)
        await show_main_menu(query)
    
    elif query.data == 'admin_management':
        admins_list = ""
        for i, admin_id in enumerate(ADMIN_IDS, 1):
            admins_list += f"{i}. `{admin_id}`\n"
        
        text = f"👥 **УПРАВЛЕНИЕ АДМИНИСТРАТОРАМИ**\n\n"
        text += f"**Текущие администраторы:**\n{admins_list}\n"
        text += f"**Всего: {len(ADMIN_IDS)}**\n\n"
        text += f"Выберите действие:"
        
        keyboard = [
            [InlineKeyboardButton("➕ Добавить администратора", callback_data='add_admin')],
            [InlineKeyboardButton("➖ Удалить администратора", callback_data='remove_admin')],
            [InlineKeyboardButton("🔙 В главное меню", callback_data='back_to_menu')]
        ]
        await query.edit_message_text(
            text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )
    
    elif query.data == 'add_admin':
        waiting_for_add_admin = True
        await query.edit_message_text(
            "➕ **ДОБАВЛЕНИЕ АДМИНИСТРАТОРА**\n\n"
            "Отправьте числовой ID пользователя Telegram\n"
            "Например: 123456789\n\n"
            "Чтобы узнать ID, можно использовать бота @userinfobot\n\n"
            "Или /cancel для отмены",
            parse_mode='Markdown'
        )
    
    elif query.data == 'remove_admin':
        if len(ADMIN_IDS) <= 1:
            await query.edit_message_text(
                "❌ Нельзя удалить последнего администратора!\n\n"
                "Добавьте другого администратора перед удалением этого."
            )
            await asyncio.sleep(2)
            await show_main_menu(query)
            return
        
        admins_list = ""
        for i, admin_id in enumerate(ADMIN_IDS, 1):
            admins_list += f"{i}. `{admin_id}`\n"
        
        waiting_for_remove_admin = True
        await query.edit_message_text(
            f"➖ **УДАЛЕНИЕ АДМИНИСТРАТОРА**\n\n"
            f"**Текущие администраторы:**\n{admins_list}\n\n"
            f"Отправьте ID администратора для удаления\n"
            f"Или /cancel для отмены",
            parse_mode='Markdown'
        )
    
    elif query.data == 'channels':
        text = "📋 **СПИСОК КАНАЛОВ**\n\n"
        
        text += "**📢 Публичные каналы:**\n"
        if CHANNELS:
            for i, ch in enumerate(CHANNELS, 1):
                text += f"{i}. @{ch}\n"
        else:
            text += "Нет публичных каналов\n"
        
        text += "\n**🔐 Приватные каналы:**\n"
        if PRIVATE_CHANNELS:
            for i, (ch_id, link) in enumerate(PRIVATE_CHANNELS.items(), 1):
                status = "✅" if ch_id in joined_private_channels else "⏳"
                text += f"{i}. {status} {ch_id}\n"
        else:
            text += "Нет приватных каналов\n"
        
        keyboard = [
            [InlineKeyboardButton("➕ Добавить канал", callback_data='add_channel_menu')],
            [InlineKeyboardButton("➖ Удалить канал", callback_data='remove_channel_menu')],
            [InlineKeyboardButton("🔙 В главное меню", callback_data='back_to_menu')]
        ]
        await query.edit_message_text(
            text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )
    
    elif query.data == 'add_channel_menu':
        keyboard = [
            [InlineKeyboardButton("📢 Публичный канал", callback_data='add_public')],
            [InlineKeyboardButton("🔐 Приватный канал", callback_data='add_private')],
            [InlineKeyboardButton("🔙 В главное меню", callback_data='back_to_menu')]
        ]
        await query.edit_message_text(
            "➕ **ДОБАВЛЕНИЕ КАНАЛА**\n\nВыберите тип канала:",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )
    
    elif query.data == 'remove_channel_menu':
        text = "➖ **УДАЛЕНИЕ КАНАЛА**\n\n"
        text += "Отправьте username публичного канала или ID приватного канала для удаления\n"
        text += "Например: @durov или private_123456789\n\n"
        text += "Или /cancel для отмены"
        
        waiting_for_remove = True
        await query.edit_message_text(text, parse_mode='Markdown')
    
    elif query.data == 'add_public':
        waiting_for_public = True
        await query.edit_message_text(
            "📢 **ДОБАВЛЕНИЕ ПУБЛИЧНОГО КАНАЛА**\n\n"
            "Отправьте username или ссылку:\n"
            "• durov\n"
            "• @durov\n"
            "• https://t.me/durov\n\n"
            "Или /cancel для отмены",
            parse_mode='Markdown'
        )
    
    elif query.data == 'add_private':
        waiting_for_private = True
        await query.edit_message_text(
            "🔐 **ДОБАВЛЕНИЕ ПРИВАТНОГО КАНАЛА**\n\n"
            "Отправьте ссылку-приглашение:\n"
            "• https://t.me/+COBtMLnnTos5YmEy\n"
            "• https://t.me/joinchat/COBtMLnnTos5YmEy\n\n"
            "Или /cancel для отмены",
            parse_mode='Markdown'
        )
    
    elif query.data == 'settings':
        keyboard = [
            [InlineKeyboardButton("✏️ Изменить текст", callback_data='change_text')],
            [InlineKeyboardButton("⏱ Изменить интервал", callback_data='change_interval')],
            [InlineKeyboardButton("🎲 Случайный текст", callback_data='random_text')],
            [InlineKeyboardButton("🔙 В главное меню", callback_data='back_to_menu')]
        ]
        await query.edit_message_text(
            f"⚙️ **НАСТРОЙКИ**\n\n"
            f"Текущий текст: '{COMMENT_TEXT}'\n"
            f"Интервал проверки: {CHECK_INTERVAL} сек",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )
    
    elif query.data == 'random_text':
        COMMENT_TEXT = random.choice(COMMENT_TEXTS)
        save_data()
        await query.edit_message_text(f"✅ Случайный текст выбран: '{COMMENT_TEXT}'")
        await asyncio.sleep(1)
        await show_main_menu(query, f"✅ **Текст изменен на:** '{COMMENT_TEXT}'\n\nВыберите действие:")
    
    elif query.data == 'change_text':
        waiting_for_text = True
        await query.edit_message_text(
            f"✏️ **ИЗМЕНЕНИЕ ТЕКСТА**\n\n"
            f"Текущий текст: '{COMMENT_TEXT}'\n\n"
            f"Отправьте новый текст (макс. 200 символов)\n"
            f"Или /cancel",
            parse_mode='Markdown'
        )
    
    elif query.data == 'change_interval':
        waiting_for_interval = True
        await query.edit_message_text(
            f"⏱ **ИЗМЕНЕНИЕ ИНТЕРВАЛА**\n\n"
            f"Текущий интервал: {CHECK_INTERVAL} сек\n\n"
            f"Введите новое значение (минимум 10, максимум 3600)\n"
            f"Или /cancel",
            parse_mode='Markdown'
        )
    
    elif query.data == 'back_to_menu':
        await show_main_menu(query)

# ========== ИСПРАВЛЕННЫЙ ОБРАБОТЧИК СООБЩЕНИЙ ==========
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка всех сообщений"""
    # Все global объявления в самом начале функции
    global waiting_for_private, waiting_for_public, waiting_for_text, waiting_for_interval, waiting_for_remove
    global waiting_for_add_admin, waiting_for_remove_admin
    global waiting_for_add_keyword, waiting_for_remove_keyword, waiting_for_add_pattern, waiting_for_remove_pattern
    global waiting_for_learn_settings
    global COMMENT_TEXT, CHECK_INTERVAL, CHANNELS, PRIVATE_CHANNELS, joined_private_channels, ADMIN_IDS
    global QUICK_KEYWORDS, CONTEXT_RULES, AUTO_LEARN_SETTINGS
    global last_posts
    
    text = update.message.text
    user_id = update.effective_user.id
    
    if not is_admin(user_id):
        await update.message.reply_text("❌ У вас нет прав")
        # Уведомляем админов о попытке
        await notify_all_admins(
            context.bot,
            f"⚠️ **Попытка взаимодействия**\n"
            f"Пользователь: @{update.effective_user.username or 'нет username'}\n"
            f"ID: `{user_id}`\n"
            f"Текст: {text[:100]}",
            parse_mode='Markdown'
        )
        return
    
    logger.info(f"📨 Сообщение от {user_id}: {text}")
    
    # Обработка отмены
    if text == '/cancel':
        waiting_for_private = waiting_for_public = waiting_for_text = waiting_for_interval = waiting_for_remove = False
        waiting_for_add_admin = waiting_for_remove_admin = False
        waiting_for_add_keyword = waiting_for_remove_keyword = waiting_for_add_pattern = waiting_for_remove_pattern = False
        waiting_for_learn_settings = False
        await show_main_menu(update.message, "❌ Действие отменено\n\nВыберите действие:")
        return
    
    # ===== РЕЖИМ НАСТРОЙКИ АВТООБУЧЕНИЯ =====
    if waiting_for_learn_settings:
        try:
            parts = text.split()
            if len(parts) != 2:
                await update.message.reply_text("❌ Неверный формат. Введите: номер значение")
                return
            
            param_num = int(parts[0])
            value = parts[1]
            
            if param_num == 1:  # Мин. длина
                AUTO_LEARN_SETTINGS['min_word_length'] = int(value)
            elif param_num == 2:  # Макс. длина
                AUTO_LEARN_SETTINGS['max_word_length'] = int(value)
            elif param_num == 3:  # Порог добавления
                AUTO_LEARN_SETTINGS['auto_add_threshold'] = int(value)
            elif param_num == 4:  # Игнорировать общие слова
                AUTO_LEARN_SETTINGS['ignore_common_words'] = value.lower() in ['true', 'да', '1', 'yes']
            elif param_num == 5:  # Макс. слов
                AUTO_LEARN_SETTINGS['max_keywords_to_learn'] = int(value)
            else:
                await update.message.reply_text("❌ Неверный номер параметра (1-5)")
                return
            
            save_data()
            await update.message.reply_text("✅ Настройки обновлены")
            
        except ValueError:
            await update.message.reply_text("❌ Ошибка в значении")
            return
        
        waiting_for_learn_settings = False
        await asyncio.sleep(1)
        await show_main_menu(update.message, f"✅ **Настройки сохранены!**\n\nВыберите действие:")
        return
    
    # ===== РЕЖИМ ДОБАВЛЕНИЯ КЛЮЧЕВОГО СЛОВА =====
    if waiting_for_add_keyword:
        try:
            if '=' not in text:
                await update.message.reply_text("❌ Неверный формат. Используйте: слово=ответ")
                return
            
            keyword, response = text.split('=', 1)
            keyword = keyword.strip().lower()
            response = response.strip()
            
            # Проверяем, не список ли это ответов
            if ',' in response:
                responses = [r.strip() for r in response.split(',')]
                QUICK_KEYWORDS[keyword] = responses
                await update.message.reply_text(f"✅ Добавлено ключевое слово '{keyword}' с вариантами ответов: {responses}")
            else:
                QUICK_KEYWORDS[keyword] = response
                await update.message.reply_text(f"✅ Добавлено ключевое слово '{keyword}' → '{response}'")
            
            save_data()
            
            # Уведомляем всех админов
            await notify_all_admins(
                context.bot,
                f"➕ **Добавлено ключевое слово**\n"
                f"'{keyword}' → '{response}'\n"
                f"Администратор: @{update.effective_user.username or 'нет username'}",
                parse_mode='Markdown'
            )
            
        except Exception as e:
            await update.message.reply_text(f"❌ Ошибка: {e}")
            return
        
        waiting_for_add_keyword = False
        await asyncio.sleep(1)
        await show_main_menu(update.message, f"✅ **Ключевое слово добавлено!**\n\nВыберите действие:")
        return
    
    # ===== РЕЖИМ УДАЛЕНИЯ КЛЮЧЕВОГО СЛОВА =====
    if waiting_for_remove_keyword:
        keyword_to_remove = text.strip().lower()
        
        if keyword_to_remove in QUICK_KEYWORDS:
            del QUICK_KEYWORDS[keyword_to_remove]
            save_data()
            await update.message.reply_text(f"✅ Ключевое слово '{keyword_to_remove}' удалено")
            
            # Уведомляем всех админов
            await notify_all_admins(
                context.bot,
                f"➖ **Удалено ключевое слово**\n"
                f"'{keyword_to_remove}'\n"
                f"Администратор: @{update.effective_user.username or 'нет username'}",
                parse_mode='Markdown'
            )
        else:
            await update.message.reply_text(f"❌ Ключевое слово '{keyword_to_remove}' не найдено")
        
        waiting_for_remove_keyword = False
        await asyncio.sleep(1)
        await show_main_menu(update.message, f"✅ **Готово!**\n\nВыберите действие:")
        return
    
    # ===== РЕЖИМ ДОБАВЛЕНИЯ ПРАВИЛА =====
    if waiting_for_add_pattern:
        try:
            if '=' not in text:
                await update.message.reply_text("❌ Неверный формат. Используйте: regex=описание")
                return
            
            pattern, description = text.split('=', 1)
            pattern = pattern.strip()
            description = description.strip()
            
            # Добавляем правило (всегда используем группу 1)
            CONTEXT_RULES.append((pattern, 1, description))
            save_data()
            
            await update.message.reply_text(f"✅ Добавлено правило:\n'{pattern}'\n→ {description}")
            
            # Уведомляем всех админов
            await notify_all_admins(
                context.bot,
                f"➕ **Добавлено правило**\n"
                f"'{pattern}'\n"
                f"Описание: {description}\n"
                f"Администратор: @{update.effective_user.username or 'нет username'}",
                parse_mode='Markdown'
            )
            
        except Exception as e:
            await update.message.reply_text(f"❌ Ошибка: {e}")
            return
        
        waiting_for_add_pattern = False
        await asyncio.sleep(1)
        await show_main_menu(update.message, f"✅ **Правило добавлено!**\n\nВыберите действие:")
        return
    
    # ===== РЕЖИМ УДАЛЕНИЯ ПРАВИЛА =====
    if waiting_for_remove_pattern:
        desc_to_remove = text.strip()
        
        found = False
        for i, (pattern, group, desc) in enumerate(CONTEXT_RULES):
            if desc == desc_to_remove or pattern == desc_to_remove:
                del CONTEXT_RULES[i]
                found = True
                break
        
        if found:
            save_data()
            await update.message.reply_text(f"✅ Правило удалено")
            
            # Уведомляем всех админов
            await notify_all_admins(
                context.bot,
                f"➖ **Удалено правило**\n"
                f"'{desc_to_remove}'\n"
                f"Администратор: @{update.effective_user.username or 'нет username'}",
                parse_mode='Markdown'
            )
        else:
            await update.message.reply_text(f"❌ Правило не найдено")
        
        waiting_for_remove_pattern = False
        await asyncio.sleep(1)
        await show_main_menu(update.message, f"✅ **Готово!**\n\nВыберите действие:")
        return
    
    # ===== РЕЖИМ ДОБАВЛЕНИЯ АДМИНИСТРАТОРА =====
    if waiting_for_add_admin:
        try:
            new_admin_id = int(text.strip())
            
            if new_admin_id in ADMIN_IDS:
                await update.message.reply_text(f"❌ Администратор с ID {new_admin_id} уже существует")
                waiting_for_add_admin = False
                await show_main_menu(update.message, "❌ **Администратор уже существует**\n\nВыберите действие:")
                return
            
            ADMIN_IDS.append(new_admin_id)
            save_data()
            
            # Уведомляем нового администратора
            try:
                await context.bot.send_message(
                    chat_id=new_admin_id,
                    text="✅ **Вам предоставлен доступ к боту-комментатору!**\n\n"
                         "Используйте /start для управления.\n\n"
                         "Бот умеет:\n"
                         "• Автоматически комментировать новые посты\n"
                         "• Анализировать контекст и писать нужные слова\n"
                         "• Самообучаться на прочитанных постах",
                    parse_mode='Markdown'
                )
            except Exception as e:
                logger.error(f"Не удалось уведомить нового админа: {e}")
            
            # Уведомляем всех админов о новом администраторе
            await notify_all_admins(
                context.bot,
                f"➕ **Добавлен новый администратор**\n"
                f"ID: `{new_admin_id}`\n"
                f"Добавил: @{update.effective_user.username or 'нет username'}",
                parse_mode='Markdown'
            )
            
            await update.message.reply_text(f"✅ Администратор с ID {new_admin_id} добавлен")
            
        except ValueError:
            await update.message.reply_text("❌ Введите корректный числовой ID")
            return
        
        waiting_for_add_admin = False
        await asyncio.sleep(1)
        await show_main_menu(update.message, f"✅ **Администратор добавлен!**\n\nВыберите действие:")
        return
    
    # ===== РЕЖИМ УДАЛЕНИЯ АДМИНИСТРАТОРА =====
    if waiting_for_remove_admin:
        try:
            remove_id = int(text.strip())
            
            if remove_id not in ADMIN_IDS:
                await update.message.reply_text(f"❌ Администратор с ID {remove_id} не найден")
                waiting_for_remove_admin = False
                await show_main_menu(update.message, "❌ **Администратор не найден**\n\nВыберите действие:")
                return
            
            if len(ADMIN_IDS) <= 1:
                await update.message.reply_text("❌ Нельзя удалить последнего администратора!")
                waiting_for_remove_admin = False
                await show_main_menu(update.message, "❌ **Нельзя удалить последнего администратора**\n\nВыберите действие:")
                return
            
            ADMIN_IDS.remove(remove_id)
            save_data()
            
            # Уведомляем удаленного администратора
            try:
                await context.bot.send_message(
                    chat_id=remove_id,
                    text="⚠️ **Ваш доступ к боту-комментатору был отозван**",
                    parse_mode='Markdown'
                )
            except Exception as e:
                logger.error(f"Не удалось уведомить удаленного админа: {e}")
            
            # Уведомляем всех админов об удалении
            await notify_all_admins(
                context.bot,
                f"➖ **Удален администратор**\n"
                f"ID: `{remove_id}`\n"
                f"Удалил: @{update.effective_user.username or 'нет username'}",
                parse_mode='Markdown'
            )
            
            await update.message.reply_text(f"✅ Администратор с ID {remove_id} удален")
            
        except ValueError:
            await update.message.reply_text("❌ Введите корректный числовой ID")
            return
        
        waiting_for_remove_admin = False
        await asyncio.sleep(1)
        await show_main_menu(update.message, f"✅ **Администратор удален!**\n\nВыберите действие:")
        return
    
    # ===== ИСПРАВЛЕННЫЙ РЕЖИМ УДАЛЕНИЯ КАНАЛА =====
    if waiting_for_remove:
        removed = False
        removed_name = ""
        
        # Проверяем публичные каналы (точное совпадение)
        text_lower = text.lower().strip()
        text_without_at = text_lower.replace('@', '')
        
        for ch in CHANNELS[:]:
            ch_lower = ch.lower()
            if ch_lower == text_without_at or f"@{ch_lower}" == text_lower:
                CHANNELS.remove(ch)
                removed = True
                removed_name = f"@{ch}"
                # Удаляем из last_posts
                keys_to_delete = [k for k in last_posts.keys() if f"public_{ch}" in k or f"public_@{ch}" in k]
                for k in keys_to_delete:
                    del last_posts[k]
                logger.info(f"✅ Удален публичный канал: @{ch}")
                break
        
        # Проверяем приватные каналы (если еще не удалили)
        if not removed:
            for ch_id in list(PRIVATE_CHANNELS.keys()):
                if ch_id in text or str(ch_id) in text:
                    del PRIVATE_CHANNELS[ch_id]
                    if ch_id in joined_private_channels:
                        joined_private_channels.remove(ch_id)
                    removed = True
                    removed_name = ch_id
                    # Удаляем из last_posts
                    keys_to_delete = [k for k in last_posts.keys() if f"private_{ch_id}" in k]
                    for k in keys_to_delete:
                        del last_posts[k]
                    logger.info(f"✅ Удален приватный канал: {ch_id}")
                    break
        
        save_data()
        waiting_for_remove = False
        
        if removed:
            await update.message.reply_text(f"✅ Канал {removed_name} удален")
            # Уведомляем всех админов об удалении канала
            await notify_all_admins(
                context.bot,
                f"➖ **Удален канал**\n"
                f"Канал: {removed_name}\n"
                f"Администратор: @{update.effective_user.username or 'нет username'}",
                parse_mode='Markdown'
            )
        else:
            await update.message.reply_text("❌ Канал не найден. Убедитесь, что вы правильно ввели название.")
        
        # Показываем главное меню
        await asyncio.sleep(1)
        await show_main_menu(update.message, "✅ **Готово!**\n\nВыберите действие:")
        return
    
    # ===== РЕЖИМ ДОБАВЛЕНИЯ ПУБЛИЧНОГО КАНАЛА =====
    if waiting_for_public:
        username = extract_channel_username(text)
        
        if not username:
            await update.message.reply_text(
                "❌ Не удалось распознать канал\n\n"
                "Отправьте:\n• durov\n• @durov\n• https://t.me/durov"
            )
            return
        
        # Проверяем, есть ли уже такой канал
        if username in CHANNELS:
            await update.message.reply_text(f"❌ Канал @{username} уже в списке")
            waiting_for_public = False
            await show_main_menu(update.message, "❌ **Канал уже существует**\n\nВыберите действие:")
            return
        
        status = await update.message.reply_text(f"🔄 Проверяю канал @{username}...")
        
        try:
            client = await init_user_client()
            if not client:
                await status.edit_text("❌ Ошибка подключения")
                waiting_for_public = False
                await show_main_menu(update.message, "❌ **Ошибка подключения**\n\nВыберите действие:")
                return
            
            # Проверяем существование канала
            try:
                entity = await client.get_entity(username)
                title = getattr(entity, 'title', username)
                
                CHANNELS.append(username)
                save_data()
                
                await status.edit_text(
                    f"✅ **Публичный канал добавлен!**\n\n"
                    f"📢 Название: {title}\n"
                    f"🔗 Username: @{username}",
                    parse_mode='Markdown'
                )
                
                # Уведомляем всех админов о добавлении канала
                await notify_all_admins(
                    context.bot,
                    f"➕ **Добавлен публичный канал**\n"
                    f"Канал: @{username}\n"
                    f"Название: {title}\n"
                    f"Администратор: @{update.effective_user.username or 'нет username'}",
                    parse_mode='Markdown'
                )
                
            except Exception as e:
                await status.edit_text(f"❌ Канал @{username} не существует или недоступен")
                waiting_for_public = False
                await show_main_menu(update.message, f"❌ **Канал не найден**\n\nВыберите действие:")
                return
            
        except Exception as e:
            await status.edit_text(f"❌ Ошибка: {str(e)[:100]}")
            waiting_for_public = False
            await show_main_menu(update.message, f"❌ **Ошибка:** {str(e)[:50]}\n\nВыберите действие:")
            return
        
        waiting_for_public = False
        await asyncio.sleep(1)
        await show_main_menu(update.message, f"✅ **Канал @{username} добавлен!**\n\nВыберите действие:")
        return
    
    # ===== РЕЖИМ ДОБАВЛЕНИЯ ПРИВАТНОГО КАНАЛА =====
    if waiting_for_private:
        if not is_private_invite_link(text):
            await update.message.reply_text(
                "❌ Это не похоже на ссылку-приглашение\n\n"
                "Нужно: https://t.me/+COBtMLnnTos5YmEy\n"
                "Или /cancel"
            )
            return
        
        status = await update.message.reply_text("🔄 Обрабатываю ссылку...")
        
        try:
            client = await init_user_client()
            if not client:
                await status.edit_text("❌ Ошибка подключения")
                waiting_for_private = False
                await show_main_menu(update.message, "❌ **Ошибка подключения**\n\nВыберите действие:")
                return
            
            result, title = await join_private_channel(client, text)
            
            if result:
                # Проверяем, нет ли уже такого канала
                if result in PRIVATE_CHANNELS:
                    await status.edit_text(f"❌ Канал уже в списке")
                    waiting_for_private = False
                    await show_main_menu(update.message, "❌ **Канал уже существует**\n\nВыберите действие:")
                    return
                
                PRIVATE_CHANNELS[result] = text
                joined_private_channels.add(result)
                save_data()
                await status.edit_text(
                    f"✅ **Приватный канал добавлен!**\n\n"
                    f"📢 Название: {title}\n"
                    f"🔐 ID: `{result}`",
                    parse_mode='Markdown'
                )
                
                # Уведомляем всех админов о добавлении приватного канала
                await notify_all_admins(
                    context.bot,
                    f"➕ **Добавлен приватный канал**\n"
                    f"Название: {title}\n"
                    f"ID: `{result}`\n"
                    f"Администратор: @{update.effective_user.username or 'нет username'}",
                    parse_mode='Markdown'
                )
            else:
                await status.edit_text(f"❌ {title}")
                waiting_for_private = False
                await show_main_menu(update.message, f"❌ **Ошибка:** {title}\n\nВыберите действие:")
                return
                
        except Exception as e:
            await update.message.reply_text(f"❌ Ошибка: {e}")
            waiting_for_private = False
            await show_main_menu(update.message, f"❌ **Ошибка:** {str(e)[:50]}\n\nВыберите действие:")
            return
        
        waiting_for_private = False
        await asyncio.sleep(1)
        await show_main_menu(update.message, f"✅ **Приватный канал добавлен!**\n\nВыберите действие:")
        return
    
    # ===== РЕЖИМ ИЗМЕНЕНИЯ ТЕКСТА =====
    if waiting_for_text:
        if len(text) > 200:
            await update.message.reply_text("❌ Слишком длинный (макс. 200 символов)")
            return
        COMMENT_TEXT = text
        save_data()
        waiting_for_text = False
        
        # Уведомляем всех админов об изменении текста
        await notify_all_admins(
            context.bot,
            f"✏️ **Изменен текст комментария**\n"
            f"Новый текст: '{COMMENT_TEXT}'\n"
            f"Администратор: @{update.effective_user.username or 'нет username'}",
            parse_mode='Markdown'
        )
        
        await update.message.reply_text(f"✅ Текст изменен: '{COMMENT_TEXT}'")
        await asyncio.sleep(1)
        await show_main_menu(update.message, f"✅ **Текст изменен!**\n\nНовый текст: '{COMMENT_TEXT}'\n\nВыберите действие:")
        return
    
    # ===== РЕЖИМ ИЗМЕНЕНИЯ ИНТЕРВАЛА =====
    if waiting_for_interval:
        try:
            interval = int(text)
            if interval < 10:
                await update.message.reply_text("❌ Минимум 10 секунд")
                return
            if interval > 3600:
                await update.message.reply_text("❌ Максимум 3600 секунд")
                return
            CHECK_INTERVAL = interval
            save_data()
            waiting_for_interval = False
            
            # Уведомляем всех админов об изменении интервала
            await notify_all_admins(
                context.bot,
                f"⏱ **Изменен интервал проверки**\n"
                f"Новый интервал: {CHECK_INTERVAL} сек\n"
                f"Администратор: @{update.effective_user.username or 'нет username'}",
                parse_mode='Markdown'
            )
            
            await update.message.reply_text(f"✅ Интервал изменен на {CHECK_INTERVAL} сек")
            await asyncio.sleep(1)
            await show_main_menu(update.message, f"✅ **Интервал изменен!**\n\nНовый интервал: {CHECK_INTERVAL} сек\n\nВыберите действие:")
        except ValueError:
            await update.message.reply_text("❌ Введите число")
        return
    
    # Если не в режиме - показываем меню
    await show_main_menu(update.message)

# ========== ЗАПУСК МОНИТОРИНГА ==========
async def monitor_channels(client, bot):
    global is_bot_running, last_posts
    global AUTO_LEARN_ENABLED, AUTO_LEARN_SETTINGS, learning_stats, detected_words, auto_learned_keywords
    global QUICK_KEYWORDS, COMMENT_TEXT
    
    while is_bot_running:
        try:
            # Мониторинг публичных каналов
            channels_to_check = CHANNELS.copy()
            for channel in channels_to_check:
                if not is_bot_running:
                    break
                try:
                    channel_entity = await client.get_entity(channel)
                    messages = await client.get_messages(channel_entity, limit=1)
                    if messages:
                        post_id = str(messages[0].id)
                        key = f"public_{channel}"
                        
                        # Получаем текст поста для анализа
                        post_text = messages[0].text if hasattr(messages[0], 'text') else ""
                        
                        # АВТОМАТИЧЕСКОЕ ОБУЧЕНИЕ
                        if AUTO_LEARN_ENABLED and post_text:
                            potential_keywords = extract_potential_keywords(post_text)
                            
                            # Автоматически добавляем ключевые слова, если набралось достаточно
                            for word in potential_keywords:
                                if len(auto_learned_keywords) < AUTO_LEARN_SETTINGS['max_keywords_to_learn']:
                                    response = auto_add_keyword(word)
                                    logger.info(f"📚 Автоматически добавлено слово '{word}' с ответом '{response}'")
                                    
                                    # Уведомляем админов о новом выученном слове
                                    await notify_all_admins(
                                        bot,
                                        f"📚 **Автообучение: новое слово**\n"
                                        f"Слово: '{word}'\n"
                                        f"Ответ: '{response}'\n"
                                        f"Частота: {detected_words[word]}",
                                        parse_mode='Markdown'
                                    )
                        
                        if key not in last_posts:
                            last_posts[key] = post_id
                            save_data()
                        elif last_posts[key] != post_id:
                            logger.info(f"🎯 Новый пост в @{channel}")
                            logger.info(f"📝 Текст поста: {post_text[:100]}...")
                            
                            # Комментируем с анализом текста
                            success, comment_used = await leave_comment(client, channel, post_id, post_text)
                            
                            if success:
                                last_posts[key] = post_id
                                save_data()
                                
                                # Формируем сообщение с деталями
                                smart_status = "🧠 (умный)" if comment_used != COMMENT_TEXT else "📝 (обычный)"
                                await notify_all_admins(
                                    bot,
                                    f"💬 **Прокомментировано!** {smart_status}\n"
                                    f"📢 Канал: @{channel}\n"
                                    f"💭 Текст: {comment_used}\n"
                                    f"📊 Пост: {post_text[:50]}...",
                                    parse_mode='Markdown'
                                )
                except FloodWaitError as e:
                    logger.warning(f"Flood wait: {e.seconds} сек")
                    await asyncio.sleep(e.seconds)
                except Exception as e:
                    logger.error(f"Ошибка {channel}: {e}")
            
            # Мониторинг приватных каналов
            private_to_check = list(PRIVATE_CHANNELS.keys())
            for channel_id in private_to_check:
                if not is_bot_running:
                    break
                try:
                    if channel_id not in joined_private_channels:
                        continue
                    
                    numeric_id = int(channel_id.replace('private_', ''))
                    channel_entity = await client.get_entity(numeric_id)
                    messages = await client.get_messages(channel_entity, limit=1)
                    
                    if messages:
                        post_id = str(messages[0].id)
                        key = f"private_{channel_id}"
                        
                        # Получаем текст поста для анализа
                        post_text = messages[0].text if hasattr(messages[0], 'text') else ""
                        
                        # АВТОМАТИЧЕСКОЕ ОБУЧЕНИЕ для приватных каналов
                        if AUTO_LEARN_ENABLED and post_text:
                            potential_keywords = extract_potential_keywords(post_text)
                            
                            for word in potential_keywords:
                                if len(auto_learned_keywords) < AUTO_LEARN_SETTINGS['max_keywords_to_learn']:
                                    response = auto_add_keyword(word)
                                    logger.info(f"📚 Автоматически добавлено слово '{word}' с ответом '{response}'")
                                    
                                    await notify_all_admins(
                                        bot,
                                        f"📚 **Автообучение: новое слово**\n"
                                        f"Слово: '{word}'\n"
                                        f"Ответ: '{response}'\n"
                                        f"Частота: {detected_words[word]}",
                                        parse_mode='Markdown'
                                    )
                        
                        if key not in last_posts:
                            last_posts[key] = post_id
                            save_data()
                        elif last_posts[key] != post_id:
                            logger.info(f"🎯 Новый пост в приватном канале")
                            logger.info(f"📝 Текст поста: {post_text[:100]}...")
                            
                            # Комментируем с анализом текста
                            success, comment_used = await leave_comment(client, channel_id, post_id, post_text)
                            
                            if success:
                                last_posts[key] = post_id
                                save_data()
                                
                                # Формируем сообщение с деталями
                                smart_status = "🧠 (умный)" if comment_used != COMMENT_TEXT else "📝 (обычный)"
                                await notify_all_admins(
                                    bot,
                                    f"💬 **Прокомментировано в приватном канале!** {smart_status}\n"
                                    f"🔐 ID: {channel_id}\n"
                                    f"💭 Текст: {comment_used}\n"
                                    f"📊 Пост: {post_text[:50]}...",
                                    parse_mode='Markdown'
                                )
                except FloodWaitError as e:
                    logger.warning(f"Flood wait: {e.seconds} сек")
                    await asyncio.sleep(e.seconds)
                except Exception as e:
                    logger.error(f"Ошибка приватного: {e}")
            
            if is_bot_running:
                logger.info(f"💤 Ожидание {CHECK_INTERVAL} сек...")
                # Разбиваем ожидание на маленькие интервалы для более быстрой остановки
                for _ in range(CHECK_INTERVAL):
                    if not is_bot_running:
                        break
                    await asyncio.sleep(1)
                
        except Exception as e:
            logger.error(f"Ошибка в мониторинге: {e}")
            await asyncio.sleep(60)

async def run_comment_bot(bot):
    global user_client, is_bot_running
    try:
        client = await init_user_client()
        if client:
            total = len(CHANNELS) + len(PRIVATE_CHANNELS)
            # Уведомляем всех админов о запуске
            await notify_all_admins(
                bot,
                f"🚀 **Мониторинг запущен!**\n\n"
                f"Отслеживается каналов: {total}\n"
                f"Интервал проверки: {CHECK_INTERVAL} сек\n"
                f"🧠 Умные комментарии: {'включены' if SMART_COMMENT_ENABLED else 'выключены'}\n"
                f"📚 Автообучение: {'включено' if AUTO_LEARN_ENABLED else 'выключено'}\n"
                f"🔑 Ключевых слов: {len(QUICK_KEYWORDS)}\n"
                f"📋 Контекстных правил: {len(CONTEXT_RULES)}\n"
                f"📊 Слов в словаре: {len(detected_words)}",
                parse_mode='Markdown'
            )
            await monitor_channels(client, bot)
    except Exception as e:
        logger.error(f"Ошибка: {e}")
    finally:
        if is_bot_running:
            is_bot_running = False
            # Уведомляем всех админов об остановке
            await notify_all_admins(
                bot,
                "⏹ **Мониторинг остановлен**",
                parse_mode='Markdown'
            )

# ========== ГЛАВНАЯ ФУНКЦИЯ ==========
async def main():
    load_data()
    
    app = Application.builder().token(BOT_TOKEN).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("cancel", handle_message))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    await app.initialize()
    await app.start()
    await app.updater.start_polling()
    
    try:
        # Уведомляем всех админов о запуске бота
        await notify_all_admins(
            app.bot,
            "🤖 **Бот запущен!**\n"
            "Используйте /start для управления\n\n"
            f"👥 Администраторов: {len(ADMIN_IDS)}\n"
            f"🧠 Умные комментарии: {'включены' if SMART_COMMENT_ENABLED else 'выключены'}\n"
            f"📚 Автообучение: {'включено' if AUTO_LEARN_ENABLED else 'выключено'}\n"
            f"🔑 Ключевых слов: {len(QUICK_KEYWORDS)}\n"
            f"📋 Контекстных правил: {len(CONTEXT_RULES)}\n"
            f"📊 Слов в словаре: {len(detected_words)}",
            parse_mode='Markdown'
        )
    except:
        pass
    
    logger.info(f"✅ Бот запущен. Администраторов: {len(ADMIN_IDS)}")
    
    try:
        # Сохраняем данные каждые 5 минут
        while True:
            await asyncio.sleep(300)
            save_data()
    except asyncio.CancelledError:
        pass
    finally:
        global is_bot_running
        is_bot_running = False
        save_data()
        await app.updater.stop()
        await app.stop()
        await app.shutdown()
        if user_client:
            await user_client.disconnect()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("🛑 Бот остановлен")
