FROM ubuntu:22.04

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install -y \
    curl \
    wget \
    git \
    gnupg \
    ca-certificates \
    software-properties-common \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

RUN add-apt-repository ppa:deadsnakes/ppa && \
    apt-get update && \
    apt-get install -y \
    python3.10 \
    python3.10-dev \
    python3.10-venv \
    python3-pip \
    && rm -rf /var/lib/apt/lists/*

RUN update-alternatives --install /usr/bin/python3 python3 /usr/bin/python3.10 1 && \
    update-alternatives --install /usr/bin/python python /usr/bin/python3.10 1

RUN python3 -m pip install --upgrade pip

RUN curl -fsSL https://deb.nodesource.com/setup_23.x | bash - && \
    apt-get install -y nodejs && \
    rm -rf /var/lib/apt/lists/*

RUN node --version && npm --version && python3 --version && pip3 --version && git --version

RUN apt-get update && \
    apt-get install -y default-libmysqlclient-dev && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

RUN git clone https://github.com/allen-assignment/backend.git

WORKDIR /app/backend
RUN git checkout newbranch && \
    pip3 install -r requirements.txt

WORKDIR /app
RUN git clone https://github.com/allen-assignment/frontend.git

WORKDIR /app/frontend
RUN git checkout payment && \
    npm install

RUN sed -i "s|const API_BASE_URL = 'http://localhost:8000';|const API_BASE_URL = '';|g" /app/frontend/src/services/api.ts

RUN npx vite build

RUN cp -r dist /app/backend/static

RUN sed -i 's|/assets/|/static/assets/|g' /app/backend/static/index.html

WORKDIR /app/backend

CMD ["python3", "run_app.py"]

