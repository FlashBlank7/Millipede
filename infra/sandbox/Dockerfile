FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir \
    pandas \
    numpy \
    scikit-learn \
    matplotlib \
    seaborn \
    openpyxl \
    xlrd \
    pdfplumber \
    scipy \
    statsmodels \
    jupyter \
    ipykernel

WORKDIR /workspace
RUN mkdir -p inputs processing models reports outputs

CMD ["tail", "-f", "/dev/null"]
