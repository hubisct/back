import pytest
import base64
from validators import is_valid_email, is_valid_password, is_valid_brazil_phone, validate_base64_image

def test_is_valid_email():
    # e-mails válidos
    assert is_valid_email("test@example.com") is True
    assert is_valid_email("user.name+tag@domain.co.uk") is True
    assert is_valid_email("a@b.co") is True
    
    # e-mails inválidos
    assert is_valid_email(None) is False
    assert is_valid_email(123) is False
    assert is_valid_email("") is False
    assert is_valid_email("invalid-email") is False
    assert is_valid_email("invalid@domain") is False
    assert is_valid_email("@domain.com") is False
    assert is_valid_email("user@.com") is False

def test_is_valid_password():
    # senhas válidas (comprimento >= 10)
    assert is_valid_password("1234567890") is True
    assert is_valid_password("super_secure_password") is True
    
    # senhas inválidas
    assert is_valid_password(None) is False
    assert is_valid_password(123) is False
    assert is_valid_password("") is False
    assert is_valid_password("short") is False
    assert is_valid_password("123456789") is False

def test_is_valid_brazil_phone():
    # celular válido (11 dígitos, começa com 9 após o DDD, DDD diferente de 0)
    assert is_valid_brazil_phone("11999999999") is True
    assert is_valid_brazil_phone("(11) 99999-9999") is True
    assert is_valid_brazil_phone("11 99999 9999") is True
    
    # telefone fixo ou histórico válido (10 dígitos, DDD diferente de 0)
    assert is_valid_brazil_phone("1133333333") is True
    assert is_valid_brazil_phone("(11) 3333-3333") is True
    assert is_valid_brazil_phone("1199999999") is True # 10 dígitos iniciando com 9 é considerado um número fixo válido pela lógica atual
    
    # telefones inválidos
    assert is_valid_brazil_phone(None) is False
    assert is_valid_brazil_phone(123) is False
    assert is_valid_brazil_phone("") is False
    assert is_valid_brazil_phone("113333333") is False   # 9 dígitos (muito curto)
    assert is_valid_brazil_phone("11333333333") is False # 11 dígitos, mas o número do assinante não começa com 9
    assert is_valid_brazil_phone("01133333333") is False # DDD começa com 0
    assert is_valid_brazil_phone("119999999999") is False # 12 dígitos (muito longo)

def test_validate_base64_image():
    # imagem base64 válida (PNG pequeno 1x1 com padding correto)
    valid_png_b64 = "data:image/png;base64,iVBOR0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNkYAAAAAYAAjCB0C8AAAAASUVORK5CYII=="
    mime_type, file_data = validate_base64_image(valid_png_b64)
    assert mime_type == "image/png"
    assert len(file_data) > 0
    
    # JPEG válido
    valid_jpg_b64 = "data:image/jpeg;base64,/9j/4AAQSkZJRgABAQEASABIAAD/2wBDAP//////////////////////////////////////////////////////////////////////////////////////wgALCAABAAEBAREA/8QAFBABAAAAAAAAAAAAAAAAAAAAAP/aAAgBAQABPxA="
    mime_type, file_data = validate_base64_image(valid_jpg_b64)
    assert mime_type == "image/jpeg"
    assert len(file_data) > 0

    # casos inválidos
    with pytest.raises(ValueError, match="Invalid image data"):
        validate_base64_image(None)
        
    with pytest.raises(ValueError, match="Invalid image data"):
        validate_base64_image(123)

    with pytest.raises(ValueError, match="Invalid image format"):
        validate_base64_image("not-a-data-url")

    with pytest.raises(ValueError, match="Malformed image data"):
        validate_base64_image("data:image/png;some-random-string")

    with pytest.raises(ValueError, match="Invalid image type"):
        validate_base64_image("data:image/gif;base64,R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7")

    with pytest.raises(ValueError, match="Invalid base64 encoding"):
        validate_base64_image("data:image/png;base64,invalid!!!base64")

    # imagem excede o limite de 5MB
    large_data = "data:image/png;base64," + base64.b64encode(b"a" * (5 * 1024 * 1024 + 1)).decode('utf-8')
    with pytest.raises(ValueError, match="Image exceeds 5MB"):
        validate_base64_image(large_data)
