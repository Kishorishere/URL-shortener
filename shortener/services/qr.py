import base64
from io import BytesIO

import qrcode
import qrcode.image.svg


def generate_qr_base64(url: str) -> str:
    qr = qrcode.QRCode(version=1, box_size=10, border=4)
    qr.add_data(url)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    buffer = BytesIO()
    img.save(buffer, format="PNG")
    return base64.b64encode(buffer.getvalue()).decode()


def generate_qr_svg(url: str) -> bytes:
    factory = qrcode.image.svg.SvgImage
    img = qrcode.make(url, image_factory=factory)
    buffer = BytesIO()
    img.save(buffer)
    return buffer.getvalue()
