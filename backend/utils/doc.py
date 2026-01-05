import fitz
from docx import Document
import chardet
import pandas as pd

def load_excel(path) -> str:
    """
    Excel (.xls / .xlsx) → 结构化纯文本
    """
    text_blocks = []

    # 读取所有 sheet
    xls = pd.ExcelFile(path)

    for sheet_name in xls.sheet_names:
        df = xls.parse(sheet_name)

        # 丢弃全空行 / 列
        df = df.dropna(how="all")
        df = df.dropna(axis=1, how="all")

        if df.empty:
            continue

        text_blocks.append(f"### Sheet: {sheet_name}")

        # 表头
        headers = [str(h) for h in df.columns]
        text_blocks.append(" | ".join(headers))

        # 行内容
        for _, row in df.iterrows():
            values = [
                "" if pd.isna(v) else str(v).strip()
                for v in row.tolist()
            ]
            text_blocks.append(" | ".join(values))

        text_blocks.append("")  # sheet 间空行

    return "\n".join(text_blocks)

def load_text_file(path):
    with open(path, "rb") as f:
        raw = f.read()
    enc = chardet.detect(raw)["encoding"]
    return raw.decode(enc, errors="ignore")

def load_pdf(path):
    doc = fitz.open(path)
    text = ""

    for page in doc:
        t = page.get_text().strip()
        if t:
            text += t + "\n"

    # 如果提取不到文本 → OCR
    if len(text.strip()) < 50:
        text = ocr_pdf(doc)

    return text

def ocr_pdf(doc):
    import pytesseract
    from PIL import Image
    import io

    text = ""
    for page in doc:
        pix = page.get_pixmap()
        img = Image.open(io.BytesIO(pix.tobytes()))
        text += pytesseract.image_to_string(img)

    return text

def load_docx(path):
    doc = Document(path)
    return "\n".join(p.text for p in doc.paragraphs if p.text.strip())
