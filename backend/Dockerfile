# Use a base image with Python
FROM python:3.12-slim

# Install uv
RUN pip install --no-cache-dir uv

# Set the working directory for the application
WORKDIR /app

# Copy the requirements file first (to cache dependencies layer)
COPY pyproject.toml uv.lock /app/

# Install dependencies
RUN uv sync

# Copy the FastAPI application code
COPY . /app/

# Expose the port that FastAPI will run on
EXPOSE 8000

# Command to run the app using Uvicorn
CMD ["uv", "run", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
