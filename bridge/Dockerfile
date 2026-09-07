FROM python:3.12-slim-bookworm

WORKDIR /app

COPY pyproject.toml README.md ./
COPY src ./src

RUN pip install --no-cache-dir .

ENV HOST=0.0.0.0
ENV PORT=8765
ENV MAILBOX_DIR=/data/mailbox

EXPOSE 8765

CMD ["python", "-m", "pair_bridge"]
