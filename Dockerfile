#Gunakan sistem Linux yang sudah terpasang Python 3.11

FROM python:3.11-slim

#Install dependensi sistem dasar

RUN apt-get update && apt-get install -y \
    wget \
    gnupg2 \
    unzip \
    ca-certificates

#Buat folder untuk menyimpan kunci keamanan (keyrings)

RUN install -m 0755 -d /etc/apt/keyrings

#Unduh kunci Google Chrome dan simpan dengan format baru

RUN wget -q -O - https://dl-ssl.google.com/linux/linux_signing_key.pub | gpg --dearmor -o /etc/apt/keyrings/google-chrome.gpg

#Tambahkan repository Chrome ke daftar sumber apt

RUN sh -c 'echo "deb [arch=amd64 signed-by=/etc/apt/keyrings/google-chrome.gpg] http://dl.google.com/linux/chrome/deb/ stable main" >> /etc/apt/sources.list.d/google-chrome.list'

#Update daftar dan install Google Chrome

RUN apt-get update && \
    apt-get install -y google-chrome-stable && \
    rm -rf /var/lib/apt/lists/*

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
