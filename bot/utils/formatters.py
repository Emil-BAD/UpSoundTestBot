def format_duration(seconds: int) -> str:
    if seconds < 0:
        seconds = 0

    minutes, remaining_seconds = divmod(seconds, 60)
    return f"{minutes}:{remaining_seconds:02d}"
