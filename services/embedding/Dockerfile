# Embedding sidecar (BGE-m3). Tách khỏi backend để API nghiệp vụ không gánh torch.
FROM python:3.11-slim

WORKDIR /app

# Cache HuggingFace để model BGE-m3 (~2.2GB) chỉ tải 1 lần (bền qua restart nhờ volume).
ENV HF_HOME=/opt/hf_cache
RUN mkdir -p /opt/hf_cache

COPY requirements.txt .
# Cài torch CPU-only TRƯỚC (từ index riêng của PyTorch) để tránh kéo bản CUDA ~6GB.
# sentence-transformers sau đó thấy torch đã có nên không cài lại bản nặng.
RUN pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu \
 && pip install --no-cache-dir -r requirements.txt

COPY app.py .

# Chạy non-root + có quyền ghi cache.
RUN useradd -m appuser && chown -R appuser:appuser /opt/hf_cache /app
USER appuser

EXPOSE 8001

HEALTHCHECK --interval=30s --timeout=10s --start-period=120s --retries=5 \
    CMD python -c "import urllib.request,json,os; port=os.getenv('PORT', '8001'); r=json.load(urllib.request.urlopen(f'http://localhost:{port}/health')); exit(0 if r['status']=='ready' else 1)" || exit 1

CMD ["sh", "-c", "uvicorn app:app --host 0.0.0.0 --port ${PORT:-8001}"]
