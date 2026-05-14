import io
from PIL import Image

def compress_image(image_bytes: bytes, max_size=(800, 800), quality=80) -> bytes:
    """
    Compresses an image to a maximum size and quality.
    Returns the compressed image bytes in JPEG format.
    """
    img = Image.open(io.BytesIO(image_bytes))
    
    # Convert to RGB if it's not (e.g., RGBA, CMYK) to save as JPEG
    if img.mode in ("RGBA", "P"):
        img = img.convert("RGB")
    elif img.mode != "RGB":
        img = img.convert("RGB")
        
    # Resize if larger than max_size while maintaining aspect ratio
    img.thumbnail(max_size, Image.Resampling.LANCZOS)
    
    output = io.BytesIO()
    img.save(output, format="JPEG", quality=quality, optimize=True)
    return output.getvalue()
