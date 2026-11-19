FROM ubuntu:24.04

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        python3 \
        nodejs \
        gcc \
        g++ \
        default-jdk-headless && \
    rm -rf /var/lib/apt/lists/*

RUN useradd -u 10001 -m -s /bin/bash runner

WORKDIR /work
