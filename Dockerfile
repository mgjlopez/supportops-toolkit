FROM python:3.12-slim

# Step 1: install base dependencies
RUN apt-get update && apt-get install -y \
    curl \
    gnupg \
    gnupg2 \
    unixodbc-dev \
    apt-transport-https \
    ca-certificates \
    && apt-get clean

# Step 2: add Microsoft GPG key
RUN curl -fsSL https://packages.microsoft.com/keys/microsoft.asc \
        | gpg --dearmor -o /usr/share/keyrings/microsoft-prod.gpg

# Step 3: write the repo entry directly
RUN echo "deb [arch=amd64 signed-by=/usr/share/keyrings/microsoft-prod.gpg] https://packages.microsoft.com/debian/12/prod bookworm main" \
        > /etc/apt/sources.list.d/mssql-release.list

# Step 4: install ODBC driver
RUN apt-get update \
    && ACCEPT_EULA=Y apt-get install -y msodbcsql18 \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Make /app available as a Python package root
ENV PYTHONPATH=/app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000
