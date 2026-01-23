FROM devlikeapro/waha:latest

# Install additional dependencies for Hugging Face Spaces
USER root

# Set up Chrome/Chromium dependencies and network tools
RUN apt-get update && apt-get install -y \
    fonts-liberation \
    libasound2 \
    libatk-bridge2.0-0 \
    libatk1.0-0 \
    libatspi2.0-0 \
    libcups2 \
    libdbus-1-3 \
    libdrm2 \
    libgbm1 \
    libgtk-3-0 \
    libnspr4 \
    libnss3 \
    libwayland-client0 \
    libxcomposite1 \
    libxdamage1 \
    libxfixes3 \
    libxkbcommon0 \
    libxrandr2 \
    xdg-utils \
    dnsutils \
    iputils-ping \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Update CA certificates
RUN update-ca-certificates

# Hugging Face Spaces specific configurations
ENV WAHA_LOG_LEVEL=debug
ENV WHATSAPP_API_PORT=7860
ENV WHATSAPP_API_HOSTNAME=0.0.0.0

# Chrome/Puppeteer configurations for containerized environment
ENV CHROME_BIN=/usr/bin/chromium
ENV PUPPETEER_SKIP_CHROMIUM_DOWNLOAD=true
ENV PUPPETEER_EXECUTABLE_PATH=/usr/bin/chromium

# Disable Chrome sandbox and configure for container networking
ENV CHROME_ARGS="--no-sandbox --disable-setuid-sandbox --disable-dev-shm-usage --disable-gpu --disable-software-rasterizer --disable-dev-tools --no-zygote"

# DNS configuration
ENV NODE_OPTIONS="--dns-result-order=ipv4first"

# Create directory for sessions persistence
RUN mkdir -p /app/.sessions && chown -R node:node /app/.sessions

USER node

# Expose port 7860 (required by Hugging Face Spaces)
EXPOSE 7860

# The base image already has the entrypoint configured
