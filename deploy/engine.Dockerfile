FROM python:3.12-slim
ENV PYTHONUNBUFFERED=1 PIP_DISABLE_PIP_VERSION_CHECK=1 EASYOCR_MODULE_PATH=/opt/easyocr \
    OPENBOOKS_OCR_PROVIDER=tesseract
ARG PREFETCH_EASYOCR=0
WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends libglib2.0-0 libgomp1 tesseract-ocr tesseract-ocr-eng \
    && rm -rf /var/lib/apt/lists/*
RUN pip install --no-cache-dir torch torchvision --index-url https://download.pytorch.org/whl/cpu

COPY models/roles_head.pt models/roles_calibration.json models/roles_model_card.json ./models/
COPY packages/py/openbooks/ ./packages/py/openbooks/
COPY server/ ./server/
RUN pip install --no-cache-dir ./packages/py/openbooks './server[scan]' \
    && pip check \
    && tesseract --list-langs | grep -x eng \
    && useradd --system --uid 10001 openbooks \
    && install -d -o openbooks /opt/easyocr

COPY deploy/ready.py ./
USER openbooks
RUN if [ "$PREFETCH_EASYOCR" = "1" ]; then python -c "import easyocr; easyocr.Reader(['en'], gpu=False, verbose=False)"; fi
CMD ["python", "-m", "uvicorn", "openbooks_server.app:app", "--host", "0.0.0.0", "--port", "8765", "--limit-concurrency", "8"]
