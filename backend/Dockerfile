FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN useradd --create-home appuser && chown -R appuser /app
USER appuser

EXPOSE 8000
# Gunicorn : serveur WSGI de production. Il ne contient AUCUN debugger
# interactif, contrairement a runserver_plus/Werkzeug qui exposait une
# console Python distante en cas d'erreur.
#
# Il termine lui-meme le TLS avec le certificat de la CA locale : aucun
# canal en clair n'existe entre le navigateur et l'application.
CMD ["gunicorn", "config.wsgi:application", \
     "--bind", "0.0.0.0:8000", \
     "--workers", "3", \
     "--certfile", "/certs/server.crt", \
     "--keyfile", "/certs/server.key", \
     "--access-logfile", "-", \
     "--error-logfile", "-"]