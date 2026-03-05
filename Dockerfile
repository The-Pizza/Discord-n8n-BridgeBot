# Use Python 3.13 on Alpine Linux
FROM python:3.13-alpine

# Set working directory
WORKDIR /app

# Copy the bot script
COPY bridge_bot.py .

# Install required Python packages
RUN pip install --no-cache-dir discord.py aiohttp

# Create a non-root user for security
RUN addgroup -g 1001 -S appgroup && \
    adduser -u 1001 -S appuser -G appgroup

# Change ownership of the app directory
RUN chown -R appuser:appgroup /app

# Switch to non-root user
USER appuser

# Define volume for persistent storage
VOLUME ["/data"]

# Environment variables (can be overridden at runtime)
ENV DISCORD_BOT_TOKEN=""
ENV N8N_WEBHOOK_URL=""
ENV PARENT_CHANNEL_ID=""
ENV LOG_LEVEL="INFO"
ENV THREADS_FILE="/data/monitored_threads.json"

# Run the bot
CMD ["python", "bridge_bot.py"]