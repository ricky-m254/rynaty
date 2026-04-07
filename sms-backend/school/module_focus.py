from django.conf import settings


def module_focus_lock_enabled() -> bool:
    return bool(getattr(settings, "MODULE_FOCUS_LOCK", False))


def module_focus_keys() -> set[str]:
    raw_keys = getattr(
        settings,
        "MODULE_FOCUS_KEYS",
        ["FINANCE", "STUDENTS", "ACADEMICS", "CORE"],
    )
    if isinstance(raw_keys, str):
        raw_keys = [part.strip() for part in raw_keys.split(",") if part.strip()]
    return {str(key).strip().upper() for key in raw_keys if str(key).strip()}


def is_module_allowed(module_key: str | None) -> bool:
    if not module_key:
        return True
    if not module_focus_lock_enabled():
        return True
    return str(module_key).strip().upper() in module_focus_keys()
