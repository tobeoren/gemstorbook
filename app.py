from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
import time
import requests
from PIL import Image
from io import BytesIO
import os
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By

app = Flask(__name__)

# MENGAMANKAN SERVER: Hanya izinkan permintaan (request) dari domain Netlify Anda
ALLOWED_ORIGINS = [
    "https://gemstorbook.netlify.app",
    "http://localhost",  # (Opsional) jika Anda masih ingin mengujinya di komputer sendiri
    "http://127.0.0.1"   # (Opsional) jika Anda masih ingin mengujinya di komputer sendiri
]

CORS(app, resources={r"/api/*": {"origins": ALLOWED_ORIGINS}})

def ambil_dan_buat_pdf(url_share):
    chrome_options = Options()
    chrome_options.add_argument("--headless=new")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-gpu")
    
    try:
        # Menjalankan Chrome menggunakan built-in Selenium Manager
        driver = webdriver.Chrome(options=chrome_options)
        
        # Buka URL yang diberikan
        driver.get(url_share)
        
        # Tunggu beberapa detik agar Javascript selesai memuat gambar
        time.sleep(5) 
        
        # Cari semua elemen gambar
        elemen_gambar = driver.find_elements(By.TAG_NAME, "img")
        
        url_gambar_ditemukan = []
        for img in elemen_gambar:
            src = img.get_attribute("src")
            # Filter URL: Hanya ambil gambar utama storybook dari server Google
            if src and "googleusercontent.com" in src and "a-" not in src:
                if src not in url_gambar_ditemukan:
                    url_gambar_ditemukan.append(src)
                    
        # Jika tidak ada gambar, tutup browser dan kembalikan None
        if not url_gambar_ditemukan:
            driver.quit()
            return None

        daftar_gambar = []
        for url in url_gambar_ditemukan:
            response = requests.get(url)
            gambar = Image.open(BytesIO(response.content))
            
            # Ubah mode gambar ke RGB untuk komparibilitas PDF
            if gambar.mode != 'RGB':
                gambar = gambar.convert('RGB')
                
            daftar_gambar.append(gambar)
            
        pdf_bytes = BytesIO()
        daftar_gambar[0].save(
            pdf_bytes, format="PDF", save_all=True, append_images=daftar_gambar[1:], resolution=100.0
        )
        # Reset pointer memori ke awal agar bisa dibaca oleh Flask
        pdf_bytes.seek(0)
        
        driver.quit()
        return pdf_bytes
        
    except Exception as e:
        print(f"Error pada Selenium/Scraping: {e}")
        try:
            driver.quit()
        except:
            pass
        return None

@app.route('/api/download', methods=['POST'])
def api_download():
    # PERLINDUNGAN EKSTRA: Mengecek Header Origin secara manual (untuk mencegah bypass CORS)
    origin = request.headers.get('Origin')
    if origin not in ALLOWED_ORIGINS:
        # Jika ada yang menembak API dari luar Netlify Anda, blokir!
        return jsonify({"error": "Akses Ditolak. Anda tidak diizinkan menggunakan API ini dari luar situs resmi."}), 403

    # Ambil data JSON dari permintaan
    data = request.json
    url_share = data.get('url')
    
    # Validasi input
    if not url_share:
        return jsonify({"error": "URL tidak diberikan"}), 400
        
    # Proses URL untuk mendapatkan PDF
    pdf_file = ambil_dan_buat_pdf(url_share)
    
    if pdf_file:
        return send_file(
            pdf_file, 
            as_attachment=True, 
            download_name='Storybook.pdf', 
            mimetype='application/pdf'
        )
    else:
        return jsonify({"error": "Gagal menemukan atau memproses gambar dari link tersebut"}), 500

if __name__ == '__main__':
    # Render menggunakan variabel environment PORT
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)
