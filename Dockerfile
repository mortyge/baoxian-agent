FROM python:3.11-slim
WORKDIR /srv
COPY pyproject.toml README.md ./
COPY app ./app
COPY data/policies ./data/policies
RUN pip install --no-cache-dir .
ENV INSURANCE_AGENT_DB_PATH=/srv/state/insurance.sqlite3
RUN mkdir -p /srv/state
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
