
FROM python:3.12-slim

# ── METADATA ───────────────────────────────────────────────
LABEL name="email_triage_env"
LABEL version="1.0.0"
LABEL description="Email Triage RL Environment for OpenEnv Hackathon"
LABEL author="Team Exception"

# ── ENVIRONMENT VARIABLES ──────────────────────────────────
# Tell Python not to write .pyc files (keeps container clean)
ENV PYTHONDONTWRITEBYTECODE=1

# Tell Python not to buffer output (so logs appear immediately)
ENV PYTHONUNBUFFERED=1

# Set the working directory inside the container
# All our files will live here
WORKDIR /app

# ── INSTALL DEPENDENCIES ───────────────────────────────────
# First copy ONLY the requirements file
# (We do this before copying code so Docker can cache this layer)
COPY server/requirements.txt .

# Install all Python packages
# --no-cache-dir keeps the image size small
RUN pip install --no-cache-dir -r requirements.txt

# ── COPY APPLICATION CODE ──────────────────────────────────
# Copy our models.py from the root
COPY models.py .

# Copy the entire server directory
COPY server/ ./server/

# Copy the openenv.yaml metadata file
COPY openenv.yaml .

# ── EXPOSE PORT ────────────────────────────────────────────
# HuggingFace Spaces requires port 7860
# For local dev, use: uvicorn server.app:app --port 8000
EXPOSE 7860

# ── START COMMAND ──────────────────────────────────────────
# This command runs when the container starts.
# uvicorn is our web server.
# --host 0.0.0.0 means accept connections from outside
# --port 7860 is the port we listen on
# --workers 1 means one process (enough for our environment)
ENV ENABLE_WEB_INTERFACE=true
CMD ["uvicorn", "server.app:app", "--host", "0.0.0.0", "--port", "7860", "--workers", "1"]