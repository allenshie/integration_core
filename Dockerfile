FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /svc

COPY integration/requirements.txt /tmp/integration-requirements.txt
RUN pip install --upgrade pip \
    && pip install --no-cache-dir -r /tmp/integration-requirements.txt

COPY common /svc/common
COPY integration /svc/integration

ENV PYTHONPATH=/svc/integration/src:/svc
WORKDIR /svc/integration
EXPOSE 9000

CMD ["python", "main.py"]
