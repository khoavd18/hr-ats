from io import BytesIO

import pymupdf
from docx import Document
from PIL import Image


def image_bytes(format: str = "PNG") -> bytes:
    output = BytesIO()
    Image.new("RGB", (10, 10), "white").save(output, format=format)
    return output.getvalue()


def docx_bytes() -> bytes:
    output = BytesIO()
    document = Document()
    document.core_properties.author = "Synthetic fixture"
    document.add_paragraph("CV mo phong, ky nang Python")
    document.save(output)
    return output.getvalue()


def pdf_bytes() -> bytes:
    with pymupdf.open() as document:
        page = document.new_page()
        page.insert_text((72, 72), "Synthetic CV: Python")
        return document.tobytes(no_new_id=True)


PDF = pdf_bytes()
