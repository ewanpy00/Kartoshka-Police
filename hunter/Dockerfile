FROM python:3.12.16-slim-trixie

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

RUN useradd --create-home --uid 1000 hunter
WORKDIR /srv/hunter

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
USER hunter

CMD ["watchfiles", "--filter", "python", "python -m app.certstream_consumer", "app"]
