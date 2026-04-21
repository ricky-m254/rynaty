import ipaddress


def format_host_for_url(host: str) -> str:
    value = (host or "").strip()
    if value.startswith("[") and value.endswith("]"):
        value = value[1:-1].strip()
    try:
        parsed = ipaddress.ip_address(value)
    except ValueError:
        return value
    if parsed.version == 6:
        return f"[{parsed.compressed}]"
    return parsed.compressed


def infer_ip_version(value: str, default: str = "ipv4") -> str:
    raw = (value or "").strip()
    if raw.startswith("[") and raw.endswith("]"):
        raw = raw[1:-1].strip()
    try:
        parsed = ipaddress.ip_address(raw)
    except ValueError:
        return default
    return "ipv6" if parsed.version == 6 else "ipv4"
