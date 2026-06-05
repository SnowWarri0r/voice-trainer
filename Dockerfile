# --- 阶段 1:构建前端 ---
FROM node:20-slim AS frontend
WORKDIR /app/frontend
COPY frontend/package.json frontend/package-lock.json* ./
RUN npm install
COPY frontend/ ./
RUN npm run build

# --- 阶段 2:Python 后端 + 托管静态产物 ---
FROM python:3.11-slim AS backend
WORKDIR /app
COPY backend/requirements.txt backend/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt
COPY backend/ backend/
COPY --from=frontend /app/frontend/dist /app/static
ENV STATIC_DIR=/app/static
WORKDIR /app/backend
EXPOSE 8000
CMD ["uvicorn", "voicetrainer.app:app", "--host", "0.0.0.0", "--port", "8000"]
