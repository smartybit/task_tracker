FROM python:3.13-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY backend/requirements.deploy.txt /tmp/requirements.txt
RUN pip install --no-cache-dir --require-hashes -r /tmp/requirements.txt
COPY backend/ /app/
RUN python -c "import runpy; from gunicorn.config import Config; c=Config(); [c.set(k,v) for k,v in runpy.run_path('config/gunicorn.py').items() if k in c.settings]"
RUN mkdir -p /var/lib/task-tracker/uploads && chown 1000:1000 /var/lib/task-tracker/uploads
USER 1000:1000
CMD ["gunicorn", "--config", "config/gunicorn.py", "config.wsgi:application"]
