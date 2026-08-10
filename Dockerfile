# One image for both entry points.
#
# The default command starts the control API and scheduler, because that is
# what a container platform runs when it builds this repo. An image whose
# default is the interactive CLI comes up on a hosted deploy with no terminal
# attached, prints the welcome banner, and aborts on the first prompt — which
# looks like a crash and is not one.
#
# The CLI is still in the image; override the command to reach it:
#   docker run -it --rm --env-file .env tradingagents tradingagents analyze
FROM python:3.12-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

WORKDIR /build
COPY . .
RUN pip install --no-cache-dir ".[server]"

FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# /data is where the Railway volume mounts. Everything that must survive a
# redeploy — journal, kill-switch state, watchlist, run history, memory log —
# lives under it. Without the volume these paths still work, but the container
# filesystem is ephemeral and the kill switch would reset on every deploy.
ENV TRADINGAGENTS_CACHE_DIR=/data/cache \
    TRADINGAGENTS_RESULTS_DIR=/data/logs \
    TRADINGAGENTS_MEMORY_LOG_PATH=/data/memory/trading_memory.md

RUN useradd --create-home appuser \
 && install -d -m 0755 -o appuser -g appuser /data \
 && install -d -m 0755 -o appuser -g appuser /home/appuser/.tradingagents
USER appuser
WORKDIR /home/appuser/app

COPY --from=builder --chown=appuser:appuser /build .

EXPOSE 8000

# No ENTRYPOINT: the command must stay overridable so the same image can run
# the CLI. uvicorn reads $PORT via the module's main(); Railway injects it.
CMD ["python", "-m", "tradingagents.server.main"]
