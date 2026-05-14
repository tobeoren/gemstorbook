from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
import time
import base64
from io import BytesIO
import os
from selenium import webdriver
from selenium.webdriver.chrome.options import Options

app = Flask(__name__)

# MENGAMANKAN SERVER (Hanya izinkan domain Netlify Anda)
ALLOWED_ORIGINS = [
    "https://gemstorbook.netlify.app",
    "http://localhost",
    "http://127.0.0.1"
]

CORS(app, resources={r"/api/*": {"origins": ALLOWED_ORIGINS}})

def ambil_dan_buat_pdf(url_share):
    chrome_options = Options()
    chrome_options.add_argument("--headless=new")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-gpu")
    
    # Mengatur ukuran jendela browser yang besar (layar komputer)
    # Agar teks dan gambar tidak sempit seperti tampilan HP
    chrome_options.add_argument("--window-size=1200,1600")
    
    try:
        # Menjalankan Chrome
        driver = webdriver.Chrome(options=chrome_options)
        driver.get(url_share)
        
        # Tunggu 5 detik agar elemen dasar HTML dimuat
        time.sleep(5) 
        
        # ==========================================
        # SCRIPT 1: SCROLL KE BAWAH PERLAHAN
        # ==========================================
        # Gemini menggunakan "Lazy Loading". Gambar yang ada di paling bawah 
        # tidak akan muncul sebelum layarnya di-scroll.
        # Script ini menyimulasikan manusia men-scroll ke bawah agar semua gambar termuat.
        driver.execute_script("""
            let totalHeight = 0;
            let distance = 100;
            let timer = setInterval(() => {
                let scrollHeight = document.body.scrollHeight;
                window.scrollBy(0, distance);
                totalHeight += distance;
                if(totalHeight >= scrollHeight - window.innerHeight){
                    clearInterval(timer);
                }
            }, 100);
        """)
        
        # Tunggu proses scroll selesai (sekitar 5 detik)
        time.sleep(5) 
        
        # ==========================================
        # SCRIPT 2: BERSIHKAN TAMPILAN (SEMBUNYIKAN UI)
        # ==========================================
        # Menyembunyikan tombol header, footer, dan menu Gemini 
        # agar PDF yang dicetak benar-benar bersih seperti buku cerita.
        driver.execute_script("""
            let style = document.createElement('style');
            style.innerHTML = `
                header, nav, button, .top-bar { display: none !important; }
                /* Paksa background agar selalu putih saat dicetak */
                body { background-color: #ffffff !important; }
            `;
            document.head.appendChild(style);
        """)
        time.sleep(1) # Tunggu sejenak agar gaya CSS baru diterapkan
        
        # ==========================================
        # MENCETAK KE PDF (Print-to-PDF Chrome)
        # ==========================================
        print_options = {
            'landscape': False,
            'displayHeaderFooter': False, # Hilangkan tulisan tanggal & URL di ujung kertas
            'printBackground': True,      # Ikut sertakan warna background
            'marginTop': 0.5,
            'marginBottom': 0.5,
            'marginLeft': 0.5,
            'marginRight': 0.5,
        }
        
        # Perintah khusus Selenium DevTools untuk mencetak halaman
        hasil_pdf = driver.execute_cdp_cmd("Page.printToPDF", print_options)
        
        # Chrome mengembalikan PDF dalam bentuk teks Base64, kita harus mengembalikannya ke bentuk File (Bytes)
        pdf_bytes = base64.b64decode(hasil_pdf['data'])
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
    # PERLINDUNGAN EKSTRA CORS Lapis Kedua
    origin = request.headers.get('Origin')
    if origin not in ALLOWED_ORIGINS:
        return jsonify({"error": "Akses Ditolak. Anda tidak diizinkan menggunakan API ini dari luar situs resmi."}), 403

    # Ambil link dari user
    data = request.json
    url_share = data.get('url')
    
    if not url_share:
        return jsonify({"error": "URL tidak diberikan"}), 400
        
    # Proses PDF (Sekarang menangkap seluruh layar web, teks + gambar)
    pdf_file = ambil_dan_buat_pdf(url_share)
    
    if pdf_file:
        return send_file(
            pdf_file, 
            as_attachment=True, 
            download_name='Storybook_Lengkap.pdf', 
            mimetype='application/pdf'
        )
    else:
        return jsonify({"error": "Gagal memproses PDF dari link tersebut. Pastikan link valid dan dapat diakses publik."}), 500

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)
