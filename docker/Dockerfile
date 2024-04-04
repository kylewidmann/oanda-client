FROM python:3.12.2-slim-bookworm as base

ENV \
  PYTHONUNBUFFERED=1 \
  PYTHONDONTWRITEBYTECODE=1 \
  POETRY_VERSION=1.5.1 \
  POETRY_VIRTUALENVS_IN_PROJECT=true \
  POETRY_NO_INTERACTION=1 \
  POETRY_HOME="/opt/poetry" \
  POETRY="/opt/poetry/bin/poetry"

ENV PATH="$POETRY_HOME/bin:$PATH"

ARG PROEJCT_DIR

USER root

RUN apt-get update \
    && apt-get install --no-install-recommends -y \
    curl \
    build-essential

RUN curl -sSL https://install.python-poetry.org | python3 - \
    && chmod a+x /opt/poetry/bin/poetry

WORKDIR /app/${PROEJCT_DIR}
COPY ${PROEJCT_DIR}/pyproject.toml ${PROEJCT_DIR}/poetry.lock ./
RUN poetry install --only main

##################################################
## PRODUCTION ##
##################################################

FROM python:3.12.2-slim-bookworm as production

ARG PROEJCT_DIR

USER root

RUN apt-get update \
    && apt-get install --no-install-recommends -y \
    curl \
    build-essential

ENV PATH="/app/.venv/bin:$PATH"
ENV APP_USER app
ENV APP_GROUP app
RUN groupadd  ${APP_GROUP}
RUN useradd -g ${APP_GROUP} ${APP_USER}

WORKDIR /app
COPY --chown=${APP_USER}:${APP_GROUP} ${PROEJCT_DIR}/ ./
COPY --from=base /app .
USER ${APP_USER}

ENTRYPOINT ["/app/scripts/entrypoint.sh"]

##################################################
## DEVELOPMENT ##
##################################################

FROM base as development

ENV PATH="/app/.venv/bin:$PATH"
ENV APP_USER app
ENV APP_GROUP app
RUN groupadd  ${APP_GROUP}
RUN useradd -g ${APP_GROUP} ${APP_USER}

USER root
RUN set -ex \
    && apt-get update

WORKDIR /app
COPY --chown=${APP_USER}:${APP_GROUP} . ./
RUN poetry install
USER ${APP_USER}

ENTRYPOINT ["/app/scripts/entrypoint.sh"]