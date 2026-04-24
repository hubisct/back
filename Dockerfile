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
COPY . .

# ---------- Create required directories ----------
RUN mkdir -p /app/uploads /app/data

# ---------- Expose port ----------
EXPOSE 5174

# ---------- Initialize DB and run the app ----------
CMD ["sh", "-c", "python init_db.py && python app.py"]
