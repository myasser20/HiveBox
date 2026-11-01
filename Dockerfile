FROM python:3.12-slim

WORKDIR /HiveBox

COPY app/ ./app/

RUN useradd --create-home appuser 

USER appuser

CMD ["python", "-m", "app.main"]