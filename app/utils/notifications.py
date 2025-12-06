"""
Модуль для работы с уведомлениями
"""

import json
from datetime import datetime
from typing import Optional, Dict, Any, List
from flask import current_app
from ..models import db, Notification, User, UserSkillRating, Skill


def create_notification(
    user_id: int,
    notification_type: str,
    title: str,
    message: str,
    data: Optional[Dict[str, Any]] = None,
    sender_id: Optional[int] = None,
    rating_id: Optional[int] = None
) -> Notification:
    """
    Создание нового уведомления

    Args:
        user_id: ID пользователя, которому отправляется уведомление
        notification_type: Тип уведомления
        title: Заголовок уведомления
        message: Текст уведомления
        data: Дополнительные данные в JSON формате
        sender_id: ID отправителя (если есть)
        rating_id: ID оценки (если связано с оценкой)

    Returns:
        Notification: Созданное уведомление
    """
    notification = Notification(
        user_id=user_id,
        type=notification_type,
        title=title,
        message=message,
        data=data if data else {},
        sender_id=sender_id,
        rating_id=rating_id
    )

    db.session.add(notification)
    db.session.commit()

    # Отправка через WebSocket (если настроено)
    send_websocket_notification(notification)

    return notification


def send_rating_confirmation_notification(
    rating_id: int,
    confirmed_by_id: int
) -> Notification:
    """
    Отправка уведомления о подтверждении оценки

    Args:
        rating_id: ID оценки
        confirmed_by_id: ID пользователя, который подтвердил оценку

    Returns:
        Notification: Созданное уведомление
    """
    rating = UserSkillRating.query.get(rating_id)
    if not rating:
        raise ValueError(f"Rating with ID {rating_id} not found")

    skill = Skill.query.get(rating.skill_id)
    confirmed_by = User.query.get(confirmed_by_id)

    title = "Оценка подтверждена"
    message = f"{confirmed_by.full_name} подтвердил вашу оценку навыка '{skill.name}'"

    data = {
        'rating_id': rating.id,
        'skill_id': skill.id,
        'skill_name': skill.name,
        'score': rating.final_score or rating.self_score,
        'confirmed_by_id': confirmed_by_id,
        'confirmed_by_name': confirmed_by.full_name
    }

    return create_notification(
        user_id=rating.user_id,
        notification_type='rating_confirmed',
        title=title,
        message=message,
        data=data,
        sender_id=confirmed_by_id,
        rating_id=rating_id
    )


def send_rating_adjustment_notification(
    rating_id: int,
    adjusted_by_id: int,
    old_score: Optional[int] = None,
    new_score: Optional[int] = None
) -> Notification:
    """
    Отправка уведомления о корректировке оценки

    Args:
        rating_id: ID оценки
        adjusted_by_id: ID пользователя, который скорректировал оценку
        old_score: Старая оценка (опционально)
        new_score: Новая оценка (опционально)

    Returns:
        Notification: Созданное уведомление
    """
    rating = UserSkillRating.query.get(rating_id)
    if not rating:
        raise ValueError(f"Rating with ID {rating_id} not found")

    skill = Skill.query.get(rating.skill_id)
    adjusted_by = User.query.get(adjusted_by_id)

    title = "Оценка скорректирована"

    if old_score and new_score:
        message = f"{adjusted_by.full_name} изменил вашу оценку навыка '{skill.name}' с {old_score} на {new_score}"
    else:
        message = f"{adjusted_by.full_name} скорректировал вашу оценку навыка '{skill.name}'"

    data = {
        'rating_id': rating.id,
        'skill_id': skill.id,
        'skill_name': skill.name,
        'old_score': old_score,
        'new_score': new_score,
        'adjusted_by_id': adjusted_by_id,
        'adjusted_by_name': adjusted_by.full_name
    }

    return create_notification(
        user_id=rating.user_id,
        notification_type='rating_adjusted',
        title=title,
        message=message,
        data=data,
        sender_id=adjusted_by_id,
        rating_id=rating_id
    )


def send_new_assessment_notification(
    rating_id: int,
    to_manager_id: int
) -> Notification:
    """
    Отправка уведомления менеджеру о новой оценке сотрудника

    Args:
        rating_id: ID новой оценки
        to_manager_id: ID менеджера

    Returns:
        Notification: Созданное уведомление
    """
    rating = UserSkillRating.query.get(rating_id)
    if not rating:
        raise ValueError(f"Rating with ID {rating_id} not found")

    user = User.query.get(rating.user_id)
    skill = Skill.query.get(rating.skill_id)

    title = "Новая оценка навыка"
    message = f"{user.full_name} оценил навык '{skill.name}' на {rating.self_score} баллов"

    data = {
        'rating_id': rating.id,
        'user_id': user.id,
        'user_name': user.full_name,
        'skill_id': skill.id,
        'skill_name': skill.name,
        'score': rating.self_score
    }

    return create_notification(
        user_id=to_manager_id,
        notification_type='new_assessment',
        title=title,
        message=message,
        data=data,
        sender_id=user.id,
        rating_id=rating_id
    )


def send_manager_assigned_notification(
    user_id: int,
    manager_id: int,
    assigned_by_id: Optional[int] = None
) -> Notification:
    """
    Отправка уведомления о назначении менеджера

    Args:
        user_id: ID сотрудника
        manager_id: ID назначенного менеджера
        assigned_by_id: ID пользователя, который назначил менеджера (опционально)

    Returns:
        Notification: Созданное уведомление
    """
    user = User.query.get(user_id)
    manager = User.query.get(manager_id)

    if not user or not manager:
        raise ValueError("User or manager not found")

    title = "Назначен новый менеджер"
    message = f"{manager.full_name} назначен вашим менеджером"

    data = {
        'user_id': user_id,
        'user_name': user.full_name,
        'manager_id': manager_id,
        'manager_name': manager.full_name,
        'assigned_by_id': assigned_by_id
    }

    return create_notification(
        user_id=user_id,
        notification_type='manager_assigned',
        title=title,
        message=message,
        data=data,
        sender_id=assigned_by_id or manager_id
    )


def send_skill_required_notification(
    user_id: int,
    skill_id: int,
    min_score: int = 3
) -> Notification:
    """
    Отправка уведомления о необходимости оценки обязательного навыка

    Args:
        user_id: ID сотрудника
        skill_id: ID обязательного навыка
        min_score: Минимальная требуемая оценка

    Returns:
        Notification: Созданное уведомление
    """
    user = User.query.get(user_id)
    skill = Skill.query.get(skill_id)

    if not user or not skill:
        raise ValueError("User or skill not found")

    title = "Требуется оценка навыка"
    message = f"Требуется оценить обязательный навык '{skill.name}' (минимум {min_score} баллов)"

    data = {
        'user_id': user_id,
        'skill_id': skill_id,
        'skill_name': skill.name,
        'min_score': min_score,
        'department_id': user.department_id
    }

    return create_notification(
        user_id=user_id,
        notification_type='skill_required',
        title=title,
        message=message,
        data=data
    )


def send_report_ready_notification(
    user_id: int,
    report_id: int,
    report_name: str,
    report_url: Optional[str] = None
) -> Notification:
    """
    Отправка уведомления о готовности отчета

    Args:
        user_id: ID пользователя
        report_id: ID отчета
        report_name: Название отчета
        report_url: URL для скачивания отчета (опционально)

    Returns:
        Notification: Созданное уведомление
    """
    title = "Отчет готов"
    message = f"Отчет '{report_name}' сформирован и готов к скачиванию"

    data = {
        'report_id': report_id,
        'report_name': report_name,
        'report_url': report_url
    }

    return create_notification(
        user_id=user_id,
        notification_type='report_ready',
        title=title,
        message=message,
        data=data
    )


def send_system_notification(
    user_id: int,
    title: str,
    message: str,
    data: Optional[Dict[str, Any]] = None
) -> Notification:
    """
    Отправка системного уведомления

    Args:
        user_id: ID пользователя
        title: Заголовок уведомления
        message: Текст уведомления
        data: Дополнительные данные

    Returns:
        Notification: Созданное уведомление
    """
    return create_notification(
        user_id=user_id,
        notification_type='system',
        title=title,
        message=message,
        data=data
    )


def send_bulk_notification(
    user_ids: List[int],
    notification_type: str,
    title: str,
    message: str,
    data: Optional[Dict[str, Any]] = None,
    sender_id: Optional[int] = None
) -> List[Notification]:
    """
    Отправка массовых уведомлений нескольким пользователям

    Args:
        user_ids: Список ID пользователей
        notification_type: Тип уведомления
        title: Заголовок уведомления
        message: Текст уведомления
        data: Дополнительные данные
        sender_id: ID отправителя

    Returns:
        List[Notification]: Список созданных уведомлений
    """
    notifications = []

    for user_id in user_ids:
        notification = Notification(
            user_id=user_id,
            type=notification_type,
            title=title,
            message=message,
            data=data if data else {},
            sender_id=sender_id
        )
        notifications.append(notification)
        db.session.add(notification)

    db.session.commit()

    # Отправка через WebSocket
    for notification in notifications:
        send_websocket_notification(notification)

    return notifications


def mark_notification_as_read(notification_id: int) -> bool:
    """
    Отметить уведомление как прочитанное

    Args:
        notification_id: ID уведомления

    Returns:
        bool: Успешно ли выполнена операция
    """
    notification = Notification.query.get(notification_id)
    if not notification:
        return False

    notification.is_read = True
    notification.read_at = datetime.utcnow()
    db.session.commit()

    return True


def mark_all_notifications_as_read(user_id: int) -> int:
    """
    Отметить все уведомления пользователя как прочитанные

    Args:
        user_id: ID пользователя

    Returns:
        int: Количество отмеченных уведомлений
    """
    count = Notification.query.filter_by(
        user_id=user_id,
        is_read=False
    ).update({
        'is_read': True,
        'read_at': datetime.utcnow()
    })

    db.session.commit()
    return count


def delete_notification(notification_id: int) -> bool:
    """
    Удаление уведомления

    Args:
        notification_id: ID уведомления

    Returns:
        bool: Успешно ли выполнена операция
    """
    notification = Notification.query.get(notification_id)
    if not notification:
        return False

    db.session.delete(notification)
    db.session.commit()

    return True


def delete_old_notifications(days_old: int = 30) -> int:
    """
    Удаление старых уведомлений

    Args:
        days_old: Удалять уведомления старше N дней

    Returns:
        int: Количество удаленных уведомлений
    """
    from datetime import timedelta

    cutoff_date = datetime.utcnow() - timedelta(days=days_old)

    # Удаляем только прочитанные уведомления
    count = Notification.query.filter(
        Notification.created_at < cutoff_date,
        Notification.is_read == True
    ).delete()

    db.session.commit()
    return count


def get_unread_count(user_id: int) -> int:
    """
    Получение количества непрочитанных уведомлений пользователя

    Args:
        user_id: ID пользователя

    Returns:
        int: Количество непрочитанных уведомлений
    """
    return Notification.query.filter_by(
        user_id=user_id,
        is_read=False
    ).count()


def get_user_notifications(
    user_id: int,
    limit: int = 20,
    offset: int = 0,
    unread_only: bool = False,
    notification_type: Optional[str] = None
) -> Dict[str, Any]:
    """
    Получение уведомлений пользователя

    Args:
        user_id: ID пользователя
        limit: Максимальное количество уведомлений
        offset: Смещение
        unread_only: Только непрочитанные
        notification_type: Фильтр по типу уведомления

    Returns:
        Dict с уведомлениями и метаданными
    """
    query = Notification.query.filter_by(user_id=user_id)

    if unread_only:
        query = query.filter_by(is_read=False)

    if notification_type:
        query = query.filter_by(type=notification_type)

    total = query.count()
    notifications = query.order_by(
        Notification.created_at.desc()
    ).offset(offset).limit(limit).all()

    return {
        'notifications': [n.to_dict() for n in notifications],
        'total': total,
        'unread_count': get_unread_count(user_id),
        'limit': limit,
        'offset': offset
    }


def send_email_notification(
    user_id: int,
    subject: str,
    body: str,
    notification_type: str = 'system'
) -> bool:
    """
    Отправка уведомления по email (если настроен email сервер)

    Args:
        user_id: ID пользователя
        subject: Тема письма
        body: Текст письма
        notification_type: Тип уведомления

    Returns:
        bool: Успешно ли отправлено письмо
    """
    try:
        user = User.query.get(user_id)
        if not user:
            return False

        # Проверяем, настроен ли email сервер
        if not current_app.config.get('MAIL_SERVER'):
            return False

        from flask_mail import Message
        from .. import mail

        msg = Message(
            subject=subject,
            recipients=[user.email],
            body=body,
            sender=current_app.config.get('MAIL_DEFAULT_SENDER')
        )

        mail.send(msg)

        # Создаем запись об уведомлении
        create_notification(
            user_id=user_id,
            notification_type=notification_type,
            title=subject,
            message=body,
            data={'email_sent': True}
        )

        return True

    except Exception as e:
        current_app.logger.error(f"Failed to send email notification: {e}")
        return False


def send_websocket_notification(notification: Notification) -> None:
    """
    Отправка уведомления через WebSocket (если настроено)

    Args:
        notification: Объект уведомления
    """
    try:
        # Проверяем, настроен ли WebSocket
        if not hasattr(current_app, 'socketio'):
            return

        from flask_socketio import emit

        # Отправляем уведомление конкретному пользователю
        emit('new_notification',
             notification.to_dict(),
             room=f'user_{notification.user_id}',
             namespace='/notifications')

    except Exception as e:
        current_app.logger.error(f"Failed to send WebSocket notification: {e}")


def cleanup_expired_notifications() -> int:
    """
    Очистка истекших уведомлений

    Returns:
        int: Количество удаленных уведомлений
    """
    try:
        # Удаляем прочитанные уведомления старше 90 дней
        count = delete_old_notifications(days_old=90)
        current_app.logger.info(f"Cleaned up {count} expired notifications")
        return count
    except Exception as e:
        current_app.logger.error(f"Failed to cleanup notifications: {e}")
        return 0


class NotificationManager:
    """
    Менеджер для работы с уведомлениями
    """

    @staticmethod
    def notify_rating_update(rating: UserSkillRating, action: str, changed_by_id: int):
        """
        Уведомление об обновлении оценки
        """
        if action == 'confirmed':
            send_rating_confirmation_notification(rating.id, changed_by_id)
        elif action == 'adjusted':
            # Нужно получить старую оценку из истории
            from ..models import RatingHistory
            history = RatingHistory.query.filter_by(
                rating_id=rating.id
            ).order_by(RatingHistory.created_at.desc()).first()

            old_score = history.old_final_score if history else None
            new_score = rating.final_score or rating.manager_score

            send_rating_adjustment_notification(
                rating.id,
                changed_by_id,
                old_score,
                new_score
            )

    @staticmethod
    def notify_new_assessment(rating: UserSkillRating):
        """
        Уведомление менеджера о новой оценке
        """
        user = User.query.get(rating.user_id)
        if user and user.manager_id:
            send_new_assessment_notification(rating.id, user.manager_id)

    @staticmethod
    def notify_manager_assignment(user_id: int, manager_id: int, assigned_by_id: int = None):
        """
        Уведомление о назначении менеджера
        """
        send_manager_assigned_notification(user_id, manager_id, assigned_by_id)

    @staticmethod
    def notify_required_skills(user_id: int, skill_ids: List[int]):
        """
        Уведомление о необходимости оценки обязательных навыков
        """
        for skill_id in skill_ids:
            send_skill_required_notification(user_id, skill_id)

    @staticmethod
    def get_user_notifications_summary(user_id: int) -> Dict[str, Any]:
        """
        Получение сводки по уведомлениям пользователя
        """
        unread_count = get_unread_count(user_id)

        # Последние 5 непрочитанных уведомлений
        recent_unread = Notification.query.filter_by(
            user_id=user_id,
            is_read=False
        ).order_by(
            Notification.created_at.desc()
        ).limit(5).all()

        # Количество по типам
        type_counts = {}
        for ntype in ['rating_confirmed', 'rating_adjusted', 'new_assessment', 'system']:
            count = Notification.query.filter_by(
                user_id=user_id,
                type=ntype,
                is_read=False
            ).count()
            if count > 0:
                type_counts[ntype] = count

        return {
            'unread_count': unread_count,
            'recent_unread': [n.to_dict() for n in recent_unread],
            'type_counts': type_counts
        }
