"""
Утилиты приложения
"""

from .validation import (
    validate_email_address,
    validate_password,
    validate_phone,
    validate_username,
    validate_full_name,
    validate_date,
    validate_score,
    validate_integer,
    validate_string,
    validate_enum,
    validate_department_code,
    validate_skill_name,
    validate_category_name,
    validate_hex_color,
    validate_url,
    validate_json,
    validate_list,
    validate_dict,
    validate_request_data,
    ValidationError,
    validate_input
)

from .notifications import (
    create_notification,
    send_rating_confirmation_notification,
    send_rating_adjustment_notification,
    send_new_assessment_notification,
    send_manager_assigned_notification,
    send_skill_required_notification,
    send_report_ready_notification,
    send_system_notification,
    send_bulk_notification,
    mark_notification_as_read,
    mark_all_notifications_as_read,
    delete_notification,
    delete_old_notifications,
    get_unread_count,
    get_user_notifications,
    send_email_notification,
    send_websocket_notification,
    cleanup_expired_notifications,
    NotificationManager
)
