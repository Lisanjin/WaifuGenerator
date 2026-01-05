from PIL import Image,PngImagePlugin
import io
import base64

TARGET_IMG_SIZE = (512, 768)

def resize_image(image, size=TARGET_IMG_SIZE) -> Image.Image:
    img = Image.open(image)
    return img.resize(size)

def blank_image(size=TARGET_IMG_SIZE) -> Image.Image:
    return Image.new('RGB', size, color='white')

def save_png(img: Image.Image, data:str) -> bytes:
    data = base64.b64encode(data.encode("utf-8")).decode("utf-8")
    buf = io.BytesIO()
    pnginfo = None

    if data:
        pnginfo = PngImagePlugin.PngInfo()
        pnginfo.add_text("chara", data)

    img.save(buf, format="PNG", pnginfo=pnginfo)
    return buf.getvalue()