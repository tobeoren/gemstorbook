#!/usr/bin/env bash
    # exit on error
    set -o errexit

    # Install Python dependencies
    pip install -r requirements.txt

    # Install Chrome and necessary dependencies
    apt-get update
    apt-get install -y wget gnupg2 apt-transport-https ca-certificates curl software-properties-common
    
    # Menambahkan repository Google Chrome
    wget -q -O - https://dl-ssl.google.com/linux/linux_signing_key.pub | apt-key add -
    echo "deb [arch=amd64] http://dl.google.com/linux/chrome/deb/ stable main" >> /etc/apt/sources.list.d/google-chrome.list
    
    # Install Chrome
    apt-get update
    apt-get install -y google-chrome-stable
    ```
    *Catatan: Setelah membuat file `render-build.sh`, Anda perlu memastikan file ini bisa dieksekusi (executable). Jika Anda menggunakan Linux/Mac sebelum push ke GitHub, jalankan `chmod +x render-build.sh` di terminal.*

### 2. Mengisi Form di Render.com (Berdasarkan Gambar)

Sekarang, mari kita isi form di Render sesuai dengan gambar yang Anda kirim:

*   **Name:** `gemstorbook` (Biarkan seperti ini, atau ganti sesuai keinginan Anda).
*   **Language:** `Python 3` (Biarkan seperti ini).
*   **Branch:** `main` (Atau cabang apa pun yang Anda gunakan di GitHub, biasanya `main` atau `master`).
*   **Region:** `Singapore (Southeast Asia)` (Pilihan bagus untuk latensi rendah di Indonesia).
*   **Root Directory:** *Biarkan kosong.*
*   **Build Command:**
    *   Ubah dari `$ pip install -r requirements.txt` menjadi:
        `./render-build.sh`
    *   *(Ini sangat penting agar Render menjalankan skrip instalasi Chrome kita, bukan hanya menginstal paket Python).*
*   **Start Command:**
    *   Ubah dari `$ gunicorn your_application.wsgi` menjadi:
        `gunicorn app:app`
    *   *(Ini memberi tahu Render untuk menggunakan Gunicorn untuk menjalankan aplikasi Flask kita yang bernama `app.py`, di mana variabel aplikasinya juga bernama `app`).*

### 3. Instance Type

*   Pilih **Free** (jika Anda ingin mencoba secara gratis).
    *   **Peringatan Penting tentang Tier "Free" Render:** Tier gratis Render memiliki RAM yang sangat terbatas (512 MB). Menjalankan Selenium (Chrome *headless*) membutuhkan memori yang cukup besar. Sangat mungkin aplikasi akan sering *crash* atau *timeout* (kehabisan waktu) di tier gratis ini, terutama jika halaman Gemini yang dibuka cukup berat.
    *   Jika aplikasi sering *error* atau gagal mengunduh, Anda mungkin perlu mempertimbangkan *upgrade* ke instance berbayar (misal "Starter") atau mencari alternatif arsitektur lain.

### 4. Environment Variables (Sangat Penting)

Anda perlu menambahkan variabel lingkungan agar Selenium tahu lokasi *binary* Chrome yang baru saja diinstal oleh skrip kita.

Klik tombol **"+ Add Environment Variable"** dan tambahkan baris berikut:

*   **Key:** `PYTHON_VERSION`
*   **Value:** `3.10.13` *(Atau versi Python 3 yang kompatibel dengan versi yang Anda gunakan saat pengembangan. Ini mencegah Render menggunakan versi default yang mungkin sudah usang).*

*   **Key:** `CHROME_BIN`
*   **Value:** `/usr/bin/google-chrome` *(Memberitahu Selenium di mana mencari Chrome).*

*   **Key:** `CHROMEDRIVER_PATH`
*   **Value:** `/opt/render/project/src/.chromedriver/bin/chromedriver` *(Opsional, tergantung konfigurasi webdriver-manager, tapi aman untuk ditambahkan).*

### Penyesuaian `app.py` untuk Render

Terakhir, pastikan file `app.py` Anda sudah diatur untuk menangani lingkungan server (headless Chrome) dengan benar. Pastikan bagian inisialisasi *driver* Selenium Anda terlihat seperti ini:

```python
# Di dalam app.py

# ... import lainnya ...
import os # Tambahkan ini jika belum ada

def ambil_dan_buat_pdf(url_share):
    chrome_options = Options()
    chrome_options.add_argument("--headless=new") # Gunakan mode headless baru
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-gpu")
    
    # Membaca lokasi Chrome dari Environment Variable yang kita set di Render
    chrome_bin = os.environ.get('CHROME_BIN')
    if chrome_bin:
        chrome_options.binary_location = chrome_bin

    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=chrome_options)
    # ... sisa kode ...