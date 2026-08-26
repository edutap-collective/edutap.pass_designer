FROM python:3.12-slim AS build
WORKDIR /build
COPY pyproject.toml README.md ./
COPY src ./src
RUN pip install --no-cache-dir build && python -m build --wheel

FROM python:3.12-slim
WORKDIR /app
COPY --from=build /build/dist/*.whl /tmp/
RUN pip install --no-cache-dir /tmp/*.whl && rm /tmp/*.whl
COPY data ./data
EXPOSE 8000
CMD ["uvicorn", "edutap.pass_designer.web.app:app", "--host", "0.0.0.0", "--port", "8000"]
