#Gunakan sistem Linux yang sudah terpasang Python 3.11
FROM python:3.11.18-slim

#Install dependensi sistem dan Google Chrome
RUN apt-get update && apt-get install -y \
    wget \
    gnupg2 \
    unzip \
    && wget -q -O - https://dl-ssl.google.com/linux/linux_signing_key.pub | apt-key add - \
    && sh -c 'echo "deb [arch=amd64] http://dl.google.com/linux/chrome/deb/ stable main" >> /etc/apt/sources.list.d/google.list' \
    && apt-get update \
    && apt-get install -y google-chrome-stable \
    && rm -rf /var/lib/apt/lists/*

#Atur folder kerja di dalam server
WORKDIR /app

#Salin file requirements dan install library Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

#Salin seluruh kode aplikasi Anda (app.py)
COPY . .

#Beri tahu server port berapa yang digunakan
ENV PORT=10000
EXPOSE $PORT

#Jalankan server Gunicorn dengan tambahan waktu tunggu (timeout) karena Selenium butuh waktu
CMD gunicorn app:app --bind 0.0.0.0:$PORT --timeout 120