# AsliNumber backend image. Supports ROLE=api|worker|scheduler|all
# (app.roles.main), per the plan's "one codebase, several process
# roles" principle -- the same image runs every role, selected at
# container-start time via the ROLE environment variable.
FROM python:3.12-slim AS base

WORKDIR /app

# System deps for building argon2-cffi/cryptography wheels if no prebuilt
# wheel matches this platform.
RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml ./
COPY app ./app

RUN pip install --no-cache-dir .

ENV ROLE=api
ENV PYTHONUNBUFFERED=1

EXPOSE 8000

CMD ["python", "-m", "app.roles"]