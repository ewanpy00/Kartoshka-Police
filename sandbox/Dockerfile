FROM mcr.microsoft.com/playwright/python:v1.65.2-noble

ENV PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /srv/sandbox

COPY requirements.txt .
RUN pip install --break-system-packages -r requirements.txt

COPY app app
COPY tests tests
COPY pytest.ini .

RUN mkdir /captures && chown pwuser:pwuser /captures

USER pwuser
EXPOSE 8001
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8001"]
