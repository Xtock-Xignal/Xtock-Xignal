FROM python:3.9-slim

WORKDIR /app

RUN apt-get update && apt-get install -y build-essential curl && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir torch torchvision torchaudio

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

RUN python -m nltk.downloader stopwords punkt averaged_perceptron_tagger

COPY . .

CMD ["tail", "-f", "/dev/null"]