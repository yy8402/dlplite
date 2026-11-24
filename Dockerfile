FROM ghcr.io/astral-sh/uv:0.12.3@sha256:2d890623d310b57771ce840f0da5eed5fc6d657da05ffaa45d82797b53fa3abc AS uv
FROM ghcr.io/betterleaks/betterleaks:v1.10.1@sha256:f345c1ac502abc51ec334c3d815ad18a79fb1509555fc4496b2cb88e760681b3 AS betterleaks
FROM python:3.12-slim-bookworm@sha256:935c3c5b12357a7e10caa9c1e6ca5692344d97cf229832ef584be2cec9fc03df AS python-base

FROM python-base AS build
COPY --from=uv /uv /usr/local/bin/uv
ENV UV_LINK_MODE=copy UV_PYTHON_DOWNLOADS=never
WORKDIR /opt/dlplite
COPY README.md pyproject.toml uv.lock ./
COPY dlplite/ ./dlplite/
RUN uv sync --locked --no-dev --no-editable

FROM python-base
COPY --from=build /opt/dlplite/.venv /opt/dlplite/.venv
COPY --from=betterleaks /usr/bin/betterleaks /usr/bin/betterleaks
COPY third_party/betterleaks-LICENSE /usr/share/doc/betterleaks/LICENSE
ENV PATH="/opt/dlplite/.venv/bin:$PATH" PYTHONUNBUFFERED=1
USER 10001:10001
EXPOSE 8443
ENTRYPOINT ["dlplite"]
