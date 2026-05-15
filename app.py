from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
import time
import requests
from PIL import Image
from io import BytesIO
import os
import zipfile
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By

# Import Rate Limiter untuk Keamanan Server
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

app = Flask(__name__)

# MENGAMANKAN SERVER: Hanya izinkan permintaan dari domain Netlify dan Localhost
ALLOWED_ORIGINS = [
    "https://gemstorbook.netlify.app",
    "http://localhost:5500",
    "http://127.0.0.1:5500"
]

CORS(app, resources={r"/api/*": {"origins": ALLOWED_ORIGINS}})

# KONFIGURASI RATE LIMITER (Maksimal 5 kali unduh per 10 Menit per IP)
limiter = Limiter(
    get_remote_address,
    app=app,
    default_limits=["5 per 10 minute"],
    storage_uri="memory://",
)

# Pesan kustom jika user terkena batas limit
@app.errorhandler(429)
def ratelimit_handler(e):
    return jsonify(error="Server sibuk / batas unduhan tercapai. Harap tunggu beberapa menit sebelum mencoba lagi."), 429

def proses_storybook(url_share, settings):
    chrome_options = Options()
    chrome_options.add_argument("--headless=new")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-gpu")
    
    # Memaksa robot merender dalam resolusi tinggi (Retina HD / 2x Scale)
    chrome_options.add_argument("--force-device-scale-factor=2")
    chrome_options.add_argument("--high-dpi-support=1")
    
    # Menyamarkan identitas robot
    chrome_options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36")
    chrome_options.add_argument("--window-size=2560,2560") 
    
    try:
        driver = webdriver.Chrome(options=chrome_options)
        print(f"Membuka URL: {url_share}")
        driver.get(url_share)
        
        print("Menunggu elemen buku dimuat sepenuhnya...")
        try:
            WebDriverWait(driver, 20).until(
                EC.presence_of_element_located((By.TAG_NAME, "storybook-page"))
            )
            time.sleep(3) 
        except Exception as wait_err:
            print(f"Peringatan kelambatan: {wait_err}")
        
        # FASE 1: EKSTRAKSI DATA MENTAH
        print("Memulai proses ekstraksi data mentah dari halaman buku...")
        pages_data_mentah = []
        seen_content = set()
        halaman_ke = 1
        
        for i in range(30):
            try:
                spread_data = driver.execute_script("""
                    let pages = Array.from(document.querySelectorAll('storybook-page')).filter(el => {
                        let rect = el.getBoundingClientRect();
                        let style = window.getComputedStyle(el);
                        return rect.width > 20 && rect.left >= -50 && rect.right <= (window.innerWidth + 50) && style.visibility !== 'hidden' && style.opacity !== '0';
                    });
                    
                    pages.sort((a, b) => a.getBoundingClientRect().left - b.getBoundingClientRect().left);
                    
                    let authorEl = document.querySelector('.header-author');
                    let authorName = authorEl ? authorEl.innerText.trim() : 'Storybook';
                    
                    let result = [];
                    pages.forEach(p => {
                        let img = p.querySelector('img[src*="googleusercontent"]:not([src*="a-"])');
                        let txt = p.querySelector('.story-text-container');
                        
                        if (img && img.src) {
                            result.push({type: 'image', content: img.src});
                        }
                        if (txt && txt.innerText.trim() !== '') {
                            result.push({type: 'text', content: txt.innerText.trim(), author: authorName});
                        }
                    });
                    
                    return result;
                """)
                
                if spread_data:
                    for item in spread_data:
                        if item['content'] not in seen_content:
                            seen_content.add(item['content'])
                            pages_data_mentah.append(item)
                            print(f"Berhasil mengekstrak 1 halaman {item['type']} baru.")
                
            except Exception as e:
                print(f"Gagal mengekstrak bentangan {halaman_ke}: {e}")
                break

            bisa_lanjut = driver.execute_script("""
                let btns = Array.from(document.querySelectorAll('button'));
                let nextBtn = btns.find(b => 
                    b.textContent.includes('chevron_right') || 
                    b.getAttribute('aria-label') === 'Next page' || 
                    b.getAttribute('aria-label') === 'Next' || 
                    b.getAttribute('aria-label') === 'Halaman berikutnya'
                );
                
                if (nextBtn && !nextBtn.disabled && nextBtn.getAttribute('aria-disabled') !== 'true') {
                    nextBtn.click();
                    return true;
                }
                return false;
            """)
            
            if not bisa_lanjut:
                print("Telah mencapai akhir buku.")
                break
                
            time.sleep(1.5)
            halaman_ke += 1
            
        if not pages_data_mentah:
            print("Gagal menemukan isi buku.")
            driver.quit()
            return None
            
        # 3. SOLUSI URUTAN HALAMAN: Memisahkan Gambar & Teks, lalu merajutnya sesuai urutan novel
        print("Menyusun ulang urutan halaman (Cover -> Gambar -> Teks)...")
        all_images = [p for p in pages_data_mentah if p['type'] == 'image']
        all_texts = [p for p in pages_data_mentah if p['type'] == 'text']
        
        pages_data = []
        
        if all_images:
            pages_data.append(all_images[0]) # Memasukkan Cover Utama
            
        max_len = max(len(all_images) - 1, len(all_texts))
        for i in range(max_len):
            if i + 1 < len(all_images):
                pages_data.append(all_images[i + 1]) # Memasukkan Gambar Ilustrasi
            if i < len(all_texts):
                pages_data.append(all_texts[i])      # Memasukkan Teks Cerita pasangannya
                
        # FASE 2: RENDER DINAMIS BERDASARKAN PENGATURAN USER
        print("Proses ekstraksi selesai. Merender ulang data menjadi halaman E-book...")
        daftar_gambar_halaman = []
        
        UKURAN_KERTAS = (800, 1131) # Standar fallback
        for page in pages_data:
            if page['type'] == 'image':
                try:
                    resp = requests.get(page['content'])
                    img_temp = Image.open(BytesIO(resp.content))
                    UKURAN_KERTAS = (img_temp.width, img_temp.height)
                    break
                except:
                    pass
        
        # Kualitas Kertas: HD (2x lipat)
        UKURAN_KERTAS_HD = (UKURAN_KERTAS[0] * 2, UKURAN_KERTAS[1] * 2)
        
        nomor_halaman_teks = 1
        
        for idx, page in enumerate(pages_data):
            print(f"Merender lembar {idx+1}/{len(pages_data)}...")
            
            if page['type'] == 'image':
                try:
                    response = requests.get(page['content'])
                    img_asli = Image.open(BytesIO(response.content)).convert('RGB')
                    img_asli = img_asli.resize(UKURAN_KERTAS_HD, Image.Resampling.LANCZOS)
                    daftar_gambar_halaman.append(img_asli)
                except Exception as e:
                    print(f"Gagal mengunduh gambar: {e}")
                
            elif page['type'] == 'text':
                driver.get("about:blank")
                author_name = page.get('author', 'Storybook')
                
                # INJEKSI CSS DINAMIS SESUAI PAYLOAD
                driver.execute_script("""
                    let text = arguments[0];
                    let pageNum = arguments[1];
                    let width = arguments[2];
                    let height = arguments[3];
                    let author = arguments[4];
                    let align = arguments[5];
                    let fontFam = arguments[6];
                    let sizeCat = arguments[7];
                    let useTexture = arguments[8];
                    let useIndent = arguments[9];
                    
                    // Indentasi (Tab)
                    let textIndent = useIndent ? "2.5em" : "0";
                    let htmlText = text.split('\\n').filter(p => p.trim() !== '').map(p => '<p style="margin: 0 0 0.8em 0; text-indent: ' + textIndent + ';">' + p + '</p>').join('');
                    
                    // Ukuran Font Dinamis (Perkalian Rasio Lebar Kertas)
                    let sizeMultiplier = 0.028;
                    if(sizeCat === 'small') sizeMultiplier = 0.022;
                    if(sizeCat === 'large') sizeMultiplier = 0.035;
                    if(sizeCat === 'xlarge') sizeMultiplier = 0.045;
                    let fontSize = Math.floor(width * sizeMultiplier);

                    // Tekstur dan Background
                    let bgStyle = "background-color: white; color: #111111;";
                    if (useTexture) {
                        bgStyle = `
                            background-color: #FDFBF7;
                            background-image: 
                                linear-gradient(90deg, rgba(0,0,0,0.08) 0%, rgba(0,0,0,0.03) 3%, transparent 10%),
                                url('data:image/svg+xml,%3Csvg viewBox=\"0 0 200 200\" xmlns=\"http://www.w3.org/2000/svg\"%3E%3Cfilter id=\"noiseFilter\"%3E%3CfeTurbulence type=\"fractalNoise\" baseFrequency=\"0.7\" numOctaves=\"3\" stitchTiles=\"stitch\"/%3E%3C/filter%3E%3Crect width=\"100%25\" height=\"100%25\" filter=\"url(%23noiseFilter)\" opacity=\"0.04\"/%3E%3C/svg%3E');
                            color: #2D2B26;
                        `;
                    }
                    
                    document.body.style.margin = '0';
                    document.body.style.padding = '0';
                    document.body.style.background = 'white';
                    
                    document.body.innerHTML = `
                        <div id="capture-area" style="
                            width: ${width}px;
                            height: ${height}px;
                            padding: 12% 7% 12% 7%;
                            box-sizing: border-box;
                            ${bgStyle}
                            font-family: ${fontFam}; 
                            position: relative;
                            display: flex;
                            flex-direction: column;
                            justify-content: center;
                        ">
                            <div style="position: absolute; top: 6%; left: 0; width: 100%; text-align: center; font-size: ${Math.floor(width * 0.018)}px; opacity: 0.6; font-family: 'Arial', sans-serif; letter-spacing: 0.15em; text-transform: uppercase;">
                                ${author}
                            </div>
                            
                            <div style="
                                width: 100%; 
                                font-size: ${fontSize}px;
                                line-height: 1.6;
                                text-align: ${align};
                                max-height: 100%; 
                                overflow: hidden;
                            ">
                                ${htmlText}
                            </div>
                            
                            <div style="position: absolute; bottom: 6%; left: 0; width: 100%; text-align: center; font-size: ${Math.floor(width * 0.02)}px; opacity: 0.6; font-family: ${fontFam};">
                                ${pageNum}
                            </div>
                        </div>
                    `;
                """, page['content'], nomor_halaman_teks, UKURAN_KERTAS[0], UKURAN_KERTAS[1], author_name, settings['align'], settings['fontFamily'], settings['fontSize'], settings['texture'], settings['indent'])
                
                time.sleep(1)
                
                element = driver.find_element(By.ID, "capture-area")
                png_bytes = element.screenshot_as_png
                img_teks = Image.open(BytesIO(png_bytes)).convert('RGB')
                
                img_teks = img_teks.resize(UKURAN_KERTAS_HD, Image.Resampling.LANCZOS)
                daftar_gambar_halaman.append(img_teks)
                nomor_halaman_teks += 1

        driver.quit()
        
        # FASE 3: PILIHAN PENYIMPANAN (PDF vs ZIP)
        print("Menyatukan semua halaman sesuai format pilihan...")
        output_bytes = BytesIO()
        
        if settings['format'] == 'zip':
            # Jika user minta ZIP, simpan dalam bentuk kumpulan file gambar
            with zipfile.ZipFile(output_bytes, 'w') as zf:
                for idx, img in enumerate(daftar_gambar_halaman):
                    img_byte_arr = BytesIO()
                    img.save(img_byte_arr, format='JPEG', quality=95)
                    zf.writestr(f"Halaman_{idx+1:02d}.jpg", img_byte_arr.getvalue())
            
            output_bytes.seek(0)
            return output_bytes, 'application/zip', 'Storybook_Lengkap.zip'
            
        else:
            # Jika user minta PDF (Default)
            daftar_gambar_halaman[0].save(
                output_bytes, 
                format="PDF", 
                save_all=True, 
                append_images=daftar_gambar_halaman[1:], 
                resolution=200.0
            )
            output_bytes.seek(0)
            return output_bytes, 'application/pdf', 'Storybook_Lengkap.pdf'
        
    except Exception as e:
        print(f"Error pada sistem utama: {e}")
        try:
            driver.quit()
        except:
            pass
        return None

@app.route('/api/download', methods=['POST'])
@limiter.limit("5 per 10 minute")  # Aturan limit terpasang di endpoint ini
def api_download():
    origin = request.headers.get('Origin')
    if origin and origin not in ALLOWED_ORIGINS:
        return jsonify({"error": "Akses Ditolak."}), 403

    data = request.json
    url_share = data.get('url')
    
    if not url_share:
        return jsonify({"error": "URL tidak diberikan"}), 400
        
    # Menangkap payload JSON pengaturan dari HTML
    settings = {
        'format': data.get('format', 'pdf'),
        'align': data.get('align', 'justify'),
        'fontFamily': data.get('fontFamily', 'Georgia, serif'),
        'fontSize': data.get('fontSize', 'medium'),
        'texture': data.get('texture', True),
        'indent': data.get('indent', True)
    }
        
    hasil = proses_storybook(url_share, settings)
    
    if hasil:
        file_bytes, mime_type, filename = hasil
        return send_file(
            file_bytes, 
            as_attachment=True, 
            download_name=filename, 
            mimetype=mime_type
        )
    else:
        return jsonify({"error": "Gagal memproses halaman. Pastikan link valid dan terbuka untuk publik."}), 502

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 10000))
    print(f"Menjalankan server di http://0.0.0.0:{port}")
    app.run(host='0.0.0.0', port=port)
