import re


EMAIL_RE = re.compile(r'^[A-Za-z0-9_.+-]+@[A-Za-z0-9-]+\.[A-Za-z0-9-.]+$')


def is_valid_email(email: str) -> bool:
    if not email or not isinstance(email, str):
        return False
    return EMAIL_RE.fullmatch(email) is not None


def is_valid_password(password: str) -> bool:
    if not password or not isinstance(password, str):
        return False
    return len(password) >= 10


def is_valid_brazil_phone(phone: str) -> bool:
    if not phone or not isinstance(phone, str):
        return False
    # remove non-digit chars
    digits = re.sub(r"\D", "", phone)
    # strip leading country code if present
    if digits.startswith("55"):
        digits = digits[2:]
    # valid length: 10 (landline) or 11 (mobile)
    if len(digits) not in (10, 11):
        return False
    # if 11 digits, mobile numbers in BR typically start with a 9 for the subscriber
    if len(digits) == 11 and digits[2] != "9":
        return False
    # area code cannot start with 0
    if digits[0] == "0":
        return False
    return True
