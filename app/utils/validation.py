"""
Модуль для валидации данных
"""

import re
from datetime import datetime
from email_validator import validate_email, EmailNotValidError
from flask import current_app
import phonenumbers
from phonenumbers import NumberParseException


def validate_email_address(email):
    """
    Валидация email адреса

    Args:
        email (str): Email для валидации

    Returns:
        tuple: (is_valid, message)
    """
    if not email:
        return False, "Email обязателен"

    try:
        # Валидация email
        email_info = validate_email(email, check_deliverability=False)
        # Нормализация email
        normalized_email = email_info.normalized
        return True, normalized_email
    except EmailNotValidError as e:
        return False, str(e)


def validate_password(password):
    """
    Валидация пароля

    Args:
        password (str): Пароль для валидации

    Returns:
        tuple: (is_valid, message)
    """
    if not password:
        return False, "Пароль обязателен"

    if len(password) < 8:
        return False, "Пароль должен содержать минимум 8 символов"

    # Проверка сложности пароля
    checks = {
        'латинские буквы в нижнем регистре': r'[a-z]',
        'латинские буквы в верхнем регистре': r'[A-Z]',
        'цифры': r'\d',
        'специальные символы': r'[!@#$%^&*(),.?":{}|<>]'
    }

    failed_checks = []
    for check_name, pattern in checks.items():
        if not re.search(pattern, password):
            failed_checks.append(check_name)

    if failed_checks:
        message = f"Пароль должен содержать: {', '.join(failed_checks)}"
        return False, message

    return True, "Пароль валиден"


def validate_phone(phone_number, country_code='RU'):
    """
    Валидация номера телефона

    Args:
        phone_number (str): Номер телефона
        country_code (str): Код страны (по умолчанию RU)

    Returns:
        tuple: (is_valid, message, formatted_number)
    """
    if not phone_number:
        return True, "", None  # Телефон не обязателен

    try:
        # Парсим номер телефона
        parsed_number = phonenumbers.parse(phone_number, country_code)

        # Проверяем валидность номера
        if not phonenumbers.is_valid_number(parsed_number):
            return False, "Неверный номер телефона", None

        # Форматируем номер в международном формате
        formatted = phonenumbers.format_number(
            parsed_number,
            phonenumbers.PhoneNumberFormat.E164
        )

        return True, "Номер телефона валиден", formatted

    except NumberParseException as e:
        return False, f"Ошибка парсинга номера: {str(e)}", None


def validate_username(username):
    """
    Валидация имени пользователя

    Args:
        username (str): Имя пользователя

    Returns:
        tuple: (is_valid, message)
    """
    if not username:
        return False, "Имя пользователя обязательно"

    if len(username) < 3:
        return False, "Имя пользователя должно содержать минимум 3 символа"

    if len(username) > 64:
        return False, "Имя пользователя не должно превышать 64 символа"

    # Разрешенные символы: буквы, цифры, точка, подчеркивание, дефис
    if not re.match(r'^[a-zA-Z0-9_.-]+$', username):
        return False, "Имя пользователя может содержать только латинские буквы, цифры, точку, подчеркивание и дефис"

    # Нельзя начинать или заканчивать точкой или дефисом
    if username.startswith('.') or username.startswith('-'):
        return False, "Имя пользователя не может начинаться с точки или дефиса"

    if username.endswith('.') or username.endswith('-'):
        return False, "Имя пользователя не может заканчиваться точкой или дефисом"

    # Нельзя использовать две точки подряд
    if '..' in username:
        return False, "Имя пользователя не может содержать две точки подряд"

    return True, "Имя пользователя валидно"


def validate_full_name(first_name, last_name, patronymic=None):
    """
    Валидация полного имени

    Args:
        first_name (str): Имя
        last_name (str): Фамилия
        patronymic (str, optional): Отчество

    Returns:
        tuple: (is_valid, message)
    """
    errors = []

    # Валидация имени
    if not first_name:
        errors.append("Имя обязательно")
    elif len(first_name) < 2:
        errors.append("Имя должно содержать минимум 2 символа")
    elif len(first_name) > 64:
        errors.append("Имя не должно превышать 64 символа")
    elif not re.match(r'^[a-zA-Zа-яА-ЯёЁ\s-]+$', first_name):
        errors.append("Имя может содержать только буквы, пробелы и дефисы")

    # Валидация фамилии
    if not last_name:
        errors.append("Фамилия обязательна")
    elif len(last_name) < 2:
        errors.append("Фамилия должна содержать минимум 2 символа")
    elif len(last_name) > 64:
        errors.append("Фамилия не должна превышать 64 символа")
    elif not re.match(r'^[a-zA-Zа-яА-ЯёЁ\s-]+$', last_name):
        errors.append("Фамилия может содержать только буквы, пробелы и дефисы")

    # Валидация отчества (если указано)
    if patronymic:
        if len(patronymic) > 64:
            errors.append("Отчество не должно превышать 64 символа")
        elif not re.match(r'^[a-zA-Zа-яА-ЯёЁ\s-]+$', patronymic):
            errors.append("Отчество может содержать только буквы, пробелы и дефисы")

    if errors:
        return False, "; ".join(errors)

    return True, "Имя валидно"


def validate_date(date_string, date_format='%Y-%m-%d'):
    """
    Валидация даты

    Args:
        date_string (str): Дата в виде строки
        date_format (str): Формат даты

    Returns:
        tuple: (is_valid, message, datetime_object)
    """
    if not date_string:
        return False, "Дата обязательна", None

    try:
        date_obj = datetime.strptime(date_string, date_format)

        # Проверка, что дата не в будущем (для дат рождения)
        if date_obj > datetime.now():
            return False, "Дата не может быть в будущем", None

        return True, "Дата валидна", date_obj
    except ValueError:
        return False, f"Неверный формат даты. Ожидается: {date_format}", None


def validate_score(score, min_score=1, max_score=5):
    """
    Валидация оценки (например, оценки навыка)

    Args:
        score (int): Оценка
        min_score (int): Минимальное значение
        max_score (int): Максимальное значение

    Returns:
        tuple: (is_valid, message)
    """
    if score is None:
        return False, "Оценка обязательна"

    try:
        score_int = int(score)
    except (ValueError, TypeError):
        return False, "Оценка должна быть числом"

    if not (min_score <= score_int <= max_score):
        return False, f"Оценка должна быть в диапазоне от {min_score} до {max_score}"

    return True, "Оценка валидна"


def validate_integer(value, min_value=None, max_value=None, field_name="Значение"):
    """
    Валидация целого числа

    Args:
        value: Значение для проверки
        min_value: Минимальное значение
        max_value: Максимальное значение
        field_name: Название поля для сообщения об ошибке

    Returns:
        tuple: (is_valid, message, integer_value)
    """
    if value is None:
        return False, f"{field_name} обязательно", None

    try:
        int_value = int(value)
    except (ValueError, TypeError):
        return False, f"{field_name} должно быть целым числом", None

    if min_value is not None and int_value < min_value:
        return False, f"{field_name} не может быть меньше {min_value}", None

    if max_value is not None and int_value > max_value:
        return False, f"{field_name} не может быть больше {max_value}", None

    return True, f"{field_name} валидно", int_value


def validate_string(value, min_length=None, max_length=None, field_name="Строка"):
    """
    Валидация строки

    Args:
        value: Значение для проверки
        min_length: Минимальная длина
        max_length: Максимальная длина
        field_name: Название поля для сообщения об ошибке

    Returns:
        tuple: (is_valid, message)
    """
    if value is None:
        return False, f"{field_name} обязательна"

    if not isinstance(value, str):
        return False, f"{field_name} должна быть строкой"

    value = value.strip()

    if min_length is not None and len(value) < min_length:
        return False, f"{field_name} должна содержать минимум {min_length} символов"

    if max_length is not None and len(value) > max_length:
        return False, f"{field_name} не должна превышать {max_length} символов"

    return True, f"{field_name} валидна"


def validate_enum(value, allowed_values, field_name="Значение"):
    """
    Валидация значения из ограниченного набора

    Args:
        value: Значение для проверки
        allowed_values: Список допустимых значений
        field_name: Название поля для сообщения об ошибке

    Returns:
        tuple: (is_valid, message)
    """
    if value is None:
        return False, f"{field_name} обязательно"

    if value not in allowed_values:
        allowed_str = ", ".join(str(v) for v in allowed_values)
        return False, f"{field_name} должно быть одним из: {allowed_str}"

    return True, f"{field_name} валидно"


def validate_department_code(code):
    """
    Валидация кода отдела

    Args:
        code (str): Код отдела

    Returns:
        tuple: (is_valid, message)
    """
    if not code:
        return False, "Код отдела обязателен"

    if len(code) < 2:
        return False, "Код отдела должен содержать минимум 2 символа"

    if len(code) > 20:
        return False, "Код отдела не должен превышать 20 символов"

    # Код отдела должен состоять из заглавных букв, цифр, подчеркивания и дефиса
    if not re.match(r'^[A-Z0-9_-]+$', code):
        return False, "Код отдела может содержать только заглавные латинские буквы, цифры, подчеркивание и дефис"

    return True, "Код отдела валиден"


def validate_skill_name(name):
    """
    Валидация названия навыка

    Args:
        name (str): Название навыка

    Returns:
        tuple: (is_valid, message)
    """
    if not name:
        return False, "Название навыка обязательно"

    if len(name) < 2:
        return False, "Название навыка должно содержать минимум 2 символа"

    if len(name) > 100:
        return False, "Название навыка не должно превышать 100 символов"

    # Проверка на недопустимые символы
    if re.search(r'[<>{}[\]~`]', name):
        return False, "Название навыка содержит недопустимые символы"

    return True, "Название навыка валидно"


def validate_category_name(name):
    """
    Валидация названия категории

    Args:
        name (str): Название категории

    Returns:
        tuple: (is_valid, message)
    """
    if not name:
        return False, "Название категории обязательно"

    if len(name) < 2:
        return False, "Название категории должно содержать минимум 2 символа"

    if len(name) > 100:
        return False, "Название категории не должно превышать 100 символов"

    return True, "Название категории валидно"


def validate_hex_color(color):
    """
    Валидация HEX цвета

    Args:
        color (str): Цвет в формате HEX

    Returns:
        tuple: (is_valid, message)
    """
    if not color:
        return True, ""  # Цвет не обязателен

    # Проверка формата HEX цвета (#RGB или #RRGGBB)
    if not re.match(r'^#([A-Fa-f0-9]{6}|[A-Fa-f0-9]{3})$', color):
        return False, "Цвет должен быть в формате HEX (#RGB или #RRGGBB)"

    return True, "Цвет валиден"


def validate_url(url):
    """
    Валидация URL

    Args:
        url (str): URL для проверки

    Returns:
        tuple: (is_valid, message)
    """
    if not url:
        return True, ""  # URL не обязателен

    # Простая проверка URL
    url_pattern = re.compile(
        r'^(https?://)?'  # http:// или https://
        r'([a-zA-Z0-9-]+\.)+[a-zA-Z]{2,}'  # домен
        r'(:\d+)?'  # порт
        r'(/[/\w\.-]*)*'  # путь
        r'(\?\S*)?$'  # параметры
    )

    if not url_pattern.match(url):
        return False, "Неверный формат URL"

    return True, "URL валиден"


def validate_json(data):
    """
    Валидация JSON данных

    Args:
        data: Данные для проверки

    Returns:
        tuple: (is_valid, message, parsed_data)
    """
    import json

    if data is None:
        return True, "Данные валидны", None

    if isinstance(data, str):
        try:
            parsed = json.loads(data)
            return True, "JSON валиден", parsed
        except json.JSONDecodeError as e:
            return False, f"Невалидный JSON: {str(e)}", None
    else:
        # Если это уже dict/list, считаем валидным
        return True, "Данные валидны", data


def validate_list(value, min_items=None, max_items=None, field_name="Список"):
    """
    Валидация списка

    Args:
        value: Список для проверки
        min_items: Минимальное количество элементов
        max_items: Максимальное количество элементов
        field_name: Название поля для сообщения об ошибке

    Returns:
        tuple: (is_valid, message)
    """
    if value is None:
        return False, f"{field_name} обязателен"

    if not isinstance(value, list):
        return False, f"{field_name} должен быть списком"

    if min_items is not None and len(value) < min_items:
        return False, f"{field_name} должен содержать минимум {min_items} элементов"

    if max_items is not None and len(value) > max_items:
        return False, f"{field_name} не должен содержать более {max_items} элементов"

    return True, f"{field_name} валиден"


def validate_dict(value, required_keys=None, field_name="Словарь"):
    """
    Валидация словаря

    Args:
        value: Словарь для проверки
        required_keys: Обязательные ключи
        field_name: Название поля для сообщения об ошибке

    Returns:
        tuple: (is_valid, message)
    """
    if value is None:
        return False, f"{field_name} обязателен"

    if not isinstance(value, dict):
        return False, f"{field_name} должен быть словарем"

    if required_keys:
        missing_keys = []
        for key in required_keys:
            if key not in value:
                missing_keys.append(key)

        if missing_keys:
            return False, f"{field_name} должен содержать ключи: {', '.join(missing_keys)}"

    return True, f"{field_name} валиден"


class ValidationError(Exception):
    """Исключение для ошибок валидации"""

    def __init__(self, message, field=None):
        self.message = message
        self.field = field
        super().__init__(self.message)

    def to_dict(self):
        """Преобразование ошибки в словарь"""
        result = {'error': self.message}
        if self.field:
            result['field'] = self.field
        return result


def validate_request_data(data, validation_rules):
    """
    Валидация данных запроса по правилам

    Args:
        data (dict): Данные для валидации
        validation_rules (dict): Правила валидации в формате:
            {
                'field_name': {
                    'required': bool,
                    'type': str,  # 'string', 'integer', 'email', etc.
                    'min': int,
                    'max': int,
                    'regex': str,
                    'allowed': list,
                    'custom': function
                }
            }

    Returns:
        tuple: (is_valid, errors, validated_data)
    """
    errors = []
    validated_data = {}

    for field_name, rules in validation_rules.items():
        value = data.get(field_name)

        # Проверка обязательности
        if rules.get('required', False) and (value is None or value == ''):
            errors.append({
                'field': field_name,
                'error': f"Поле '{field_name}' обязательно"
            })
            continue

        # Если поле не обязательное и не указано, пропускаем
        if value is None or value == '':
            continue

        field_errors = []

        # Проверка типа
        field_type = rules.get('type', 'string')

        if field_type == 'string':
            is_valid, message = validate_string(
                value,
                rules.get('min_length'),
                rules.get('max_length'),
                field_name
            )
            if not is_valid:
                field_errors.append(message)

        elif field_type == 'integer':
            is_valid, message, int_value = validate_integer(
                value,
                rules.get('min'),
                rules.get('max'),
                field_name
            )
            if not is_valid:
                field_errors.append(message)
            else:
                validated_data[field_name] = int_value

        elif field_type == 'email':
            is_valid, message = validate_email_address(value)
            if not is_valid:
                field_errors.append(message)
            else:
                validated_data[field_name] = message  # normalized email

        elif field_type == 'phone':
            is_valid, message, formatted = validate_phone(
                value,
                rules.get('country_code', 'RU')
            )
            if not is_valid:
                field_errors.append(message)
            elif formatted:
                validated_data[field_name] = formatted

        elif field_type == 'score':
            is_valid, message = validate_score(
                value,
                rules.get('min', 1),
                rules.get('max', 5)
            )
            if not is_valid:
                field_errors.append(message)

        elif field_type == 'enum':
            is_valid, message = validate_enum(
                value,
                rules.get('allowed', []),
                field_name
            )
            if not is_valid:
                field_errors.append(message)

        # Проверка регулярным выражением
        if 'regex' in rules and value:
            if not re.match(rules['regex'], str(value)):
                field_errors.append(f"Поле '{field_name}' имеет неверный формат")

        # Кастомная валидация
        if 'custom' in rules and callable(rules['custom']):
            try:
                is_valid, message = rules['custom'](value)
                if not is_valid:
                    field_errors.append(message)
            except Exception as e:
                field_errors.append(f"Ошибка валидации поля '{field_name}': {str(e)}")

        # Если были ошибки, добавляем их
        if field_errors:
            errors.append({
                'field': field_name,
                'error': '; '.join(field_errors)
            })
        elif field_name not in validated_data:
            # Сохраняем исходное значение, если не было преобразований
            validated_data[field_name] = value

    return len(errors) == 0, errors, validated_data


# Декораторы для валидации
def validate_input(validation_rules):
    """
    Декоратор для валидации входных данных Flask route

    Args:
        validation_rules (dict): Правила валидации

    Returns:
        function: Декорированная функция
    """
    from functools import wraps
    from flask import request, jsonify

    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            # Получаем данные в зависимости от метода
            if request.method in ['POST', 'PUT', 'PATCH']:
                if request.is_json:
                    data = request.get_json()
                else:
                    data = request.form.to_dict()
            else:
                data = request.args.to_dict()

            # Валидируем данные
            is_valid, errors, validated_data = validate_request_data(data, validation_rules)

            if not is_valid:
                return jsonify({
                    'error': 'Validation failed',
                    'details': errors
                }), 400

            # Добавляем валидированные данные в kwargs
            kwargs['validated_data'] = validated_data
            return f(*args, **kwargs)

        return decorated_function

    return decorator
