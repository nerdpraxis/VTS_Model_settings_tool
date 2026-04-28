"""Default JSON keys for aligning VTS `list[dict]` rows (e.g. hotkeys)."""

# Order = preference when auto-detecting
DEFAULT_ID_KEYS: tuple[str, ...] = (
    "hotkeyID",
    "id",
    "name",
    "Name",
    "file",
    "fileName",
    "Name_EN",
    "Name_JA",
)
