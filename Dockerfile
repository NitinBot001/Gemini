FROM devlikeapro/waha:latest

# Set environment variables
ENV WAHA_LOG_LEVEL=info
ENV WHATSAPP_API_PORT=3000
ENV WHATSAPP_API_HOSTNAME=0.0.0.0

# Expose the API port
EXPOSE 3000

# The base image already has the entrypoint configured
# No need to specify CMD or ENTRYPOINT
