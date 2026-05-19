FROM python:3.12-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy all project files
COPY . .

# Ensure output directory exists
RUN mkdir -p outputs

# Default: run full pipeline with mock LLM (safe for CI/demo)
# Set ANTHROPIC_API_KEY env var to use real LLM
CMD ["python", "-m", "src.pipeline", "--mock-llm"]
