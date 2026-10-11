FROM python:3.11-slim

# Upgrade pip and install Poetry
RUN pip install --upgrade pip && pip install poetry

# Install system dependencies required for psycopg2
RUN apt-get update && apt-get install -y libpq-dev gcc && rm -rf /var/lib/apt/lists/*

# Set the working directory
WORKDIR /nepali_news_scrapers

# Copy dependency descriptors first for caching
COPY pyproject.toml poetry.lock* ./ 
COPY README.md .  
COPY .env .env

# Install dependencies via Poetry (without creating a virtualenv)
RUN poetry config virtualenvs.create false && poetry install --no-interaction --no-ansi --no-root

# Copy the rest of the project files after dependencies
COPY . .

RUN ls -al /nepali_news_scrapers

EXPOSE 8000

# Run the scraper using the module command
ENTRYPOINT ["python", "-u", "-m", "nepali_news_scrapers.main"]
