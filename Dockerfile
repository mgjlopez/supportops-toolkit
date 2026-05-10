FROM python:3.12-slim

# Step 1: install base dependencies (curl, gpg needed to add Microsoft repo)
RUN apt-get update && apt-get install -y \
    curl \
    gnupg \
    gnupg2 \
    unixodbc-dev \
    apt-transport-https \
    ca-certificates \
    && apt-get clean

# Step 2: add Microsoft repo using modern gpg method (apt-key is removed in Debian 12)
RUN curl -fsSL https://packages.microsoft.com/keys/microsoft.asc \
        | gpg --dearmor -o /usr/share/keyrings/microsoft-prod.gpg \
    && curl -fsSL https://packages.microsoft.com/config/debian/12/prod.list \
        | sed 's|^deb |deb [signed-by=/usr/share/keyrings/microsoft-prod.gpg] |' \
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
