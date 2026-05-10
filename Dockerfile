FROM python:3.12-slim

# Step 1: install curl and gnupg first (needed to add Microsoft repo)
RUN apt-get update && apt-get install -y \
    curl \
    gnupg \
    unixodbc-dev \
    apt-transport-https \
    ca-certificates \
    && apt-get clean

# Step 2: add Microsoft package repo and install SQL Server ODBC driver
RUN curl https://packages.microsoft.com/keys/microsoft.asc | apt-key add - \
    && curl https://packages.microsoft.com/config/debian/12/prod.list \
        > /etc/apt/sources.list.d/mssql-release.list \
    && apt-get update \
    && ACCEPT_EULA=Y apt-get install -y msodbcsql18 \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000
