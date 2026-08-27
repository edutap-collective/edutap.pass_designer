FROM node:lts-slim AS frontend
WORKDIR /frontend
RUN corepack enable
COPY frontend/package.json frontend/pnpm-lock.yaml ./
RUN pnpm install --frozen-lockfile
COPY frontend/ ./
# The prefix is baked in at build time, so it must be given here and must
# match PASS_DESIGNER_ROOT_PATH at run time.
ARG PASS_DESIGNER_ROOT_PATH=/
ENV PASS_DESIGNER_ROOT_PATH=${PASS_DESIGNER_ROOT_PATH}
RUN pnpm build

FROM python:3.12-slim AS build
WORKDIR /build
COPY pyproject.toml README.md ./
COPY src ./src
COPY --from=frontend /src/edutap/pass_designer/web/static ./src/edutap/pass_designer/web/static
RUN pip install --no-cache-dir build babel \
    && pybabel compile -d src/edutap/pass_designer/locales \
    && python -m build --wheel

FROM python:3.12-slim
WORKDIR /app
COPY --from=build /build/dist/*.whl /tmp/
RUN pip install --no-cache-dir /tmp/*.whl && rm /tmp/*.whl
COPY data ./data
EXPOSE 8000
CMD ["uvicorn", "edutap.pass_designer.web.app:app", "--host", "0.0.0.0", "--port", "8000"]
