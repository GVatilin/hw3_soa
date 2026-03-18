FROM python:3.12-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app:/app/generated

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY booking_service/requirements.txt /app/booking_service/requirements.txt
RUN pip install --no-cache-dir -r /app/booking_service/requirements.txt

COPY . /app

RUN mkdir -p /app/generated && \
    python -m grpc_tools.protoc \
      -I /app/proto \
      --python_out=/app/generated \
      --grpc_python_out=/app/generated \
      /app/proto/flight_service.proto

RUN chmod +x /app/booking_service/entrypoint.sh

CMD ["/app/booking_service/entrypoint.sh"]
