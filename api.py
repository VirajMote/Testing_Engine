# api.py — FastAPI entry point for Render deployment

from fastapi import FastAPI, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
import tempfile, os, shutil, sys

sys.path.insert(0, os.path.dirname(__file__))
from processor import process_receipt

app = FastAPI(title="Receipt Processor API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.post("/process-receipt")
async def process(
    file: UploadFile = File(...),
    bill_country: str = Form(...),
    company_country: str = Form(...),
    category: str = Form(None),
):
    suffix = os.path.splitext(file.filename)[-1]
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        shutil.copyfileobj(file.file, tmp)
        tmp_path = tmp.name
    try:
        result = process_receipt(tmp_path, bill_country, company_country, category)
    finally:
        os.unlink(tmp_path)
    return result


@app.get("/health")
def health():
    return {"status": "ok"}
