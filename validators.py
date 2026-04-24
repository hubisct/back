import re
import base64

EMAIL_RE = re.compile(r'^[A-Za-z0-9_.+-]+@[A-Za-z0-9-]+\.[A-Za-z0-9-.]+$')

ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp"}
MAX_IMAGE_SIZE = 5 * 1024 * 1024  # 5MB

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
    digits = re.sub(r"\D", "", phone
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

def validate_base64_image(data_url: str) -> tuple[str, bytes]:
    if not data_url or not isinstance(data_url, str):
        raise ValueError("Invalid image data")

    if not data_url.startswith("data:image/"):
        raise ValueError("Invalid image format")

    if "," not in data_url:
        raise ValueError("Malformed image data")

    header, encoded = data_url.split(",", 1)

    mime_type = header.split(";")[0].replace("data:", "")
    if mime_type not in ALLOWED_IMAGE_TYPES:
        raise ValueError(f"Invalid image type: {mime_type}")

    try:
        file_data = base64.b64decode(encoded)
    except Exception:
        raise ValueError("Invalid base64 encoding")

    if len(file_data) > MAX_IMAGE_SIZE:
        raise ValueError("Image exceeds 5MB")

    return mime_type, file_data
