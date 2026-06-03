# ---------- Base image ----------
FROM python:3.12-slim

# Prevent Python from writing .pyc files and enable unbuffered output
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DATA_DIR=/app/data

# ---------- Working directory ----------
WORKDIR /app

# ---------- Install dependencies ----------
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# ---------- Copy application code ----------
COPY app.py init_db.py models.py seed_data.py validators.py ./

# ---------- Create runtime user and writable directories ----------
RUN addgroup --system appgroup \
    && adduser --system --ingroup appgroup appuser \
    && mkdir -p /app/uploads /app/data \
    && chown -R appuser:appgroup /app

USER appuser


# ---------- Expose port ----------
EXPOSE 5174

# ---------- Initialize DB and run the app ----------
CMD ["sh", "-c", "if [ ! -f \"$DATA_DIR/.db_initialized\" ]; then python init_db.py && touch \"$DATA_DIR/.db_initialized\"; fi && python app.py"]
