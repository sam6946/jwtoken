import re

from rest_framework.exceptions import ValidationError

_CAMEROON_MOBILE = re.compile(r"^\+237[2368]\d{8}$")
_E164 = re.compile(r"^\+[1-9]\d{7,14}$")


def normalize_phone(value: str) -> str:
    raw = (value or "").strip()
    digits = re.sub(r"\D", "", raw)
    if digits.startswith("00237"):
        digits = digits[2:]
    if digits.startswith("237"):
        normalized = f"+{digits}"
    elif len(digits) == 9:
        normalized = f"+237{digits}"
    else:
        normalized = raw if raw.startswith("+") else f"+{digits}"
    if _CAMEROON_MOBILE.fullmatch(normalized):
        return normalized
    if _E164.fullmatch(normalized):
        return normalized
    raise ValidationError("Saisissez un numéro de téléphone valide avec son indicatif international.")
