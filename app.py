from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
import time
import requests
from PIL import Image
from io import BytesIO
import os
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from webdriver_manager.chrome import ChromeDriverManager

app = Flask(__name__)
CORS(app) # Mengizinkan web Netlify Anda untuk berkomunikasi dengan server ini

def ambil_dan_buat_pdf(url_share):
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=chrome_options)
    
    try:
        driver.get(url_share)
        time.sleep(5) 
        elemen_gambar = driver.find_elements(By.TAG_NAME, "img")
        
        url_gambar_ditemukan = []
        for img in elemen_gambar:
            src = img.get_attribute("src")
            if src and "googleusercontent.com" in src and "a-" not in src:
                if src not in url_gambar_ditemukan:
                    url_gambar_ditemukan.append(src)
                    
        if not url_gambar_ditemukan:
            return None

        # Unduh gambar dan satukan ke PDF
        daftar_gambar = []
        for url in url_gambar_ditemukan:
            response = requests.get(url)
            gambar = Image.open(BytesIO(response.content))
            if gambar.mode != 'RGB':
                gambar = gambar.convert('RGB')
            daftar_gambar.append(gambar)
            
        # Simpan ke dalam memori komputer sementara (bukan file fisik) agar mudah dikirim ke user
        pdf_bytes = BytesIO()
        daftar_gambar[0].save(
            pdf_bytes, format="PDF", save_all=True, append_images=daftar_gambar[1:], resolution=100.0
        )
        pdf_bytes.seek(0)
        return pdf_bytes
        
    except Exception as e:
        print(f"Error: {e}")
        return None
    finally:
        driver.quit()

@app.route('/api/download', methods=['POST'])
def api_download():
    data = request.json
    url_share = data.get('url')
    
    if not url_share:
        return jsonify({"error": "URL tidak diberikan"}), 400
        
    pdf_file = ambil_dan_buat_pdf(url_share)
    
    if pdf_file:
        return send_file(
            pdf_file, 
            as_attachment=True, 
            download_name='Storybook.pdf', 
            mimetype='application/pdf'
        )
    else:
        return jsonify({"error": "Gagal menemukan atau memproses gambar"}), 500

if __name__ == '__main__':
    # Menjalankan server secara lokal
    app.run(debug=True, port=5000)