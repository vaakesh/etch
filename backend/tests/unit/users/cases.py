from uuid import UUID


USER_UUID = UUID("0198ad01-b200-7000-8000-000000000042")
USER_DATA = {
    "id": 42,
    "uuid": "0198ad01-b200-7000-8000-000000000042",
    "username": "test-user",
    "email": "test@example.com",
    "hashed_password": "hashed-test-password",
    "created_at": "2020-01-01T12:00:00Z",
    "updated_at": "2020-01-01T13:00:00Z",
}
SETTINGS_DATA = {
    "user_id": 42,
    "locale": "ru-RU",
    "theme": "system",
    "show_previews_for_long": True,
    "created_at": "2020-01-01T12:00:00Z",
    "updated_at": "2020-01-01T13:00:00Z",
}
USER_WITH_SETTINGS_DATA = {**USER_DATA, "settings": SETTINGS_DATA}
