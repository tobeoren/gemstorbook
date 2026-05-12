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
CORS(app) 

def ambil_dan_buat_pdf(url_share):
    chrome_options = Options()
    chrome_options.add_argument("--headless=new")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-gpu")
    
    # Inisialisasi webdriver (Selenium 4 akan otomatis mencari driver yang tepat!)
    try:
        driver = webdriver.Chrome(options=chrome_options)
        
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
            driver.quit()
            return None

        # Unduh gambar dan satukan ke PDF
        daftar_gambar = []
        for url in url_gambar_ditemukan:
            response = requests.get(url)
            gambar = Image.open(BytesIO(response.content))
            if gambar.mode != 'RGB':
                gambar = gambar.convert('RGB')
            daftar_gambar.append(gambar)
            
        pdf_bytes = BytesIO()
        daftar_gambar[0].save(
            pdf_bytes, format="PDF", save_all=True, append_images=daftar_gambar[1:], resolution=100.0
        )
        pdf_bytes.seek(0)
        
        driver.quit()
        return pdf_bytes
        
    except Exception as e:
        print(f"Error pada Selenium/Scraping: {e}")
        # Memastikan browser ditutup meskipun terjadi error
        try:
            driver.quit()
        except:
            pass
        return None

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
        return jsonify({"error": "Gagal menemukan atau memproses gambar dari link tersebut"}), 500

if __name__ == '__main__':
    # Tidak disarankan menggunakan port 5000 hardcode di Render, kita ikuti environment PORT
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)
