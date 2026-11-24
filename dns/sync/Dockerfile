FROM python:3.12.16-slim-trixie

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

RUN useradd --create-home --uid 1000 dnssync
WORKDIR /srv/dnssync
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
USER dnssync
CMD ["python", "shield.py"]
