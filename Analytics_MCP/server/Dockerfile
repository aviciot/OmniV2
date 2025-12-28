FROM python:3.12-slim

# set working directory inside container
WORKDIR /app

# copy requirements first (for caching)
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# now copy all the source code (the entire server folder)
COPY . .

EXPOSE ${MCP_PORT:-9009}

# run uvicorn, hot reload included
CMD ["sh", "-c", "uvicorn server:app --host 0.0.0.0 --port ${MCP_PORT:-9009} --reload --reload-dir /app"]
