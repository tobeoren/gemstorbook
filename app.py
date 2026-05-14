from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
import time
import base64
from io import BytesIO
import os
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.common.print_page_options import PrintOptions

app = Flask(__name__)

# MENGAMANKAN SERVER: Hanya izinkan permintaan (request) dari domain Netlify Anda
ALLOWED_ORIGINS = [
    "https://gemstorbook.netlify.app",
    "http://localhost",  # (Opsional) untuk testing lokal
    "http://127.0.0.1"   # (Opsional) untuk testing lokal
]

CORS(app, resources={r"/api/*": {"origins": ALLOWED_ORIGINS}})

def ambil_dan_buat_pdf(url_share):
    chrome_options = Options()
    chrome_options.add_argument("--headless=new")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-gpu")
    # Tambahan perintah untuk menghemat RAM (Mematikan fitur Chrome yang tidak perlu)
    chrome_options.add_argument("--disable-software-rasterizer")
    chrome_options.add_argument("--js-flags=--expose-gc")
    
    try:
        # Menjalankan Chrome menggunakan built-in Selenium Manager
        driver = webdriver.Chrome(options=chrome_options)
        
        # Buka URL yang diberikan
        driver.get(url_share)
        
        # ==========================================
        # SCRIPT 1: AUTO-SCROLL (Memuat Gambar)
        # ==========================================
        time.sleep(3) 
        driver.execute_script("""
            var totalHeight = 0;
            var distance = 300;
            var timer = setInterval(() => {
                var scrollHeight = document.body.scrollHeight;
                window.scrollBy(0, distance);
                totalHeight += distance;
                if(totalHeight >= scrollHeight){
                    clearInterval(timer);
                }
            }, 150);
        """)
        # Tunggu sampai proses scroll ke bawah selesai
        time.sleep(6) 
        
        # ==========================================
        # SCRIPT 2: BERSIHKAN TAMPILAN (SEMBUNYIKAN UI)
        # ==========================================
        # Menyembunyikan tombol header, footer, dan menu Gemini 
        # agar PDF yang dicetak benar-benar bersih seperti buku cerita.
        driver.execute_script("""
            let style = document.createElement('style');
            style.innerHTML = `
                header, nav, button, .top-bar, .side-nav { display: none !important; }
                /* Hapus animasi background Gemini yang bikin berat memori */
                .background-animation, canvas { display: none !important; }
                /* Paksa background agar selalu putih saat dicetak */
                body { background-color: #ffffff !important; }
            `;
            document.head.appendChild(style);
        """)
        time.sleep(2) # Tunggu sejenak agar gaya CSS baru diterapkan
        
        # ==========================================
        # MENCETAK KE PDF (Menggunakan Native Selenium)
        # ==========================================
        print_options = PrintOptions()
        print_options.background = True
        print_options.margin_top = 0.5
        print_options.margin_bottom = 0.5
        
        # Fitur print_page bawaan Selenium 4 lebih stabil dalam mengelola RAM
        pdf_base64 = driver.print_page(print_options)
        
        # Mengembalikan teks Base64 ke bentuk File PDF (Bytes)
        pdf_bytes = base64.b64decode(pdf_base64)
        pdf_buffer = BytesIO(pdf_bytes)
        
        # Reset posisi pembacaan memori ke awal
        pdf_buffer.seek(0)
        
        driver.quit()
        return pdf_buffer
        
    except Exception as e:
        print(f"Error pada Selenium/Scraping: {e}")
        try:
            driver.quit()
        except:
            pass
        return None

@app.route('/api/download', methods=['POST'])
def api_download():
    # PERLINDUNGAN EKSTRA: Mengecek Header Origin secara manual
    origin = request.headers.get('Origin')
    if origin and origin not in ALLOWED_ORIGINS:
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
        return jsonify({"error": "Memori Server Render (RAM) tidak kuat untuk memproses PDF ini. Coba lagi nanti."}), 502

if __name__ == '__main__':
    # Render menggunakan variabel environment PORT
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)
