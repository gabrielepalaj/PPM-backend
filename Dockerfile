FROM python:3.9-slim

WORKDIR /app

COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 5000

ENV FLASK_APP=app.py
ENV FLASK_ENV=production

# Utilizzo flask per il deploy anche se sarebbe meglio usare un server WSGI come Gunicorn
CMD ["flask", "run", "--host=0.0.0.0", "--port=5000"]
