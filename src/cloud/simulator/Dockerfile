FROM python:3.12-slim

RUN pip install --no-cache-dir paho-mqtt==2.2.0

WORKDIR /app
COPY simulate.py .

# -u: Ausgaben sofort in "docker compose logs simulator" sichtbar
CMD ["python", "-u", "simulate.py"]
