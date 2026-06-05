FROM nvidia/cuda:12.1.1-cudnn8-runtime-ubuntu22.04

ARG DEBIAN_FRONTEND=noninteractive
ARG FOOOCUS_REPO=https://github.com/lllyasviel/Fooocus.git
ARG FOOOCUS_REF=main

ENV PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    FOOOCUS_HOME=/opt/fooocus \
    FOOOCUS_PORT=7865 \
    FOOOCUS_LISTEN=0.0.0.0 \
    FOOOCUS_ARGS="--preset realistic"

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
      git \
      python3 \
      python3-venv \
      python3-pip \
      libgl1 \
      libglib2.0-0 \
      libsm6 \
      libxext6 \
      libxrender1 \
      ffmpeg \
      ca-certificates \
    && rm -rf /var/lib/apt/lists/*

RUN git clone --depth 1 --branch "${FOOOCUS_REF}" "${FOOOCUS_REPO}" "${FOOOCUS_HOME}"

WORKDIR ${FOOOCUS_HOME}

RUN python3 -m venv /opt/fooocus-venv \
    && /opt/fooocus-venv/bin/python -m pip install --upgrade pip wheel setuptools \
    && /opt/fooocus-venv/bin/pip install -r requirements_versions.txt

COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

EXPOSE 7865

ENTRYPOINT ["/entrypoint.sh"]
