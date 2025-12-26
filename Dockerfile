# Hugging Face Spaces Docker
FROM python:3.11-slim

# Create user
RUN useradd -m -u 1000 user
USER user
ENV PATH="/home/user/.local/bin:$PATH"

WORKDIR /app

# Copy requirements first for caching
COPY --chown=user ./requirements.txt requirements.txt
RUN pip install --no-cache-dir --upgrade -r requirements.txt

# Copy all files
COPY --chown=user . /app

# Expose port 7860 (required by HF Spaces)
EXPOSE 7860

# Run the bot
CMD ["python", "main.py"]
