import os
import random
import string
import sqlite3
import re
from datetime import datetime, timedelta
from flask import Flask, request, jsonify, render_template_string

# ==========================================
# 【套件防呆機制與車牌辨識模組載入】
# ==========================================
try:
    import cv2
    import easyocr
    import numpy as np
    OCR_AVAILABLE = True
except ImportError:
    OCR_AVAILABLE = False

class LPRModule:
    def __init__(self):
        self.reader = None
        if OCR_AVAILABLE:
            print("[模組載入] 正在初始化 EasyOCR 車牌辨識模型...")
            self.reader = easyocr.Reader(['en'], gpu=False) 
        else:
            print("[系統提示] 雲端環境將以「模擬模式」運行。")

    def preprocess_image(self, frame):
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        gray = cv2.resize(gray, None, fx=2, fy=2, interpolation=cv2.INTER_CUBIC)
        blur = cv2.bilateralFilter(gray, 11, 17, 17)
        return blur

    def recognize_text(self, frame):
        plate_chars = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-'
        processed_frame = self.preprocess_image(frame)
        result = self.reader.readtext(processed_frame, allowlist=plate_chars)
        
        if result: 
            raw_text = result[0][1].upper()
            clean_text = re.sub(r'[^A-Z0-9]', '', raw_text)
            if len(clean_text) > 7: clean_text = clean_text[:7]

            # 暴力校正字典
            if len(clean_text) >= 6:
                p1, p2 = clean_text[:3], clean_text[3:]
                p2 = p2.replace('I','1').replace('O','0').replace('B','8').replace('S','5').replace('Z','2')
                p1 = p1.replace('0','O').replace('1','I').replace('8','B').replace('5','S').replace('2','Z')
                clean_text = p1 + p2

            # 格式化輸出
            if re.match(r'^[A-Z]{2,3}[0-9]{3,4}$', clean_text):
                return f"{clean_text[:len(clean_text)-4]}-{clean_text[-4:]}"
        return "UNKNOWN"

    def scan_camera(self):
        return self.mock_scan() # 雲端環境強制使用模擬或圖片上傳

    def mock_scan(self):
        letters = ''.join(random.choices(string.ascii_uppercase, k=3))
        numbers = ''.join(random.choices(string.digits, k=4))
        return f"{letters}-{numbers}"

# ==========================================
# 【資料庫系統 - 新增 tags 表格】
# ==========================================
DB_FILE = 'parking_system.db'

def init_db():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('''CREATE TABLE IF NOT EXISTS users (plate TEXT PRIMARY KEY, balance REAL)''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS active_cars (plate TEXT PRIMARY KEY, entry_time TEXT, slot_idx INTEGER)''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS reservations (plate TEXT PRIMARY KEY, start_time TEXT)''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS history (id INTEGER PRIMARY KEY AUTOINCREMENT, plate TEXT, entry_time TEXT, exit_time TEXT, fee REAL)''')
    # 新增：黑白名單標籤表
    cursor.execute('''CREATE TABLE IF NOT EXISTS tags (plate TEXT PRIMARY KEY, tag_type TEXT)''')
    conn.commit()
    conn.close()

def query_db(query, args=(), one=False):
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row 
    cur = conn.cursor()
    cur.execute(query, args)
    rv = cur.fetchall()
    conn.close()
    return (rv[0] if rv else None) if one else rv

def execute_db(query, args=()):
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()
    cur.execute(query, args)
    conn.commit()
    conn.close()

# ==========================================
# 【核心邏輯系統 - 新增 VIP 與黑名單判斷】
# ==========================================
app = Flask(__name__)
lpr_module = LPRModule()
init_db()

TOTAL_SLOTS = 10       
RATE_PER_HOUR = 40     
TIME_OFFSET_HOURS = 0 

def get_current_time():
    return datetime.now() + timedelta(hours=TIME_OFFSET_HOURS)

class ParkingLogic:
    @staticmethod
    def get_status():
        active = query_db("SELECT * FROM active_cars")
        reserves = query_db("SELECT * FROM reservations")
        available = TOTAL_SLOTS - len(active) - len(reserves)
        return available, active, reserves

    @staticmethod
    def enter(plate):
        now = get_current_time()
        # 黑名單攔截
        tag = query_db("SELECT tag_type FROM tags WHERE plate=?", (plate,), one=True)
        if tag and tag['tag_type'] == 'BLACKLIST':
            return False, f"進場失敗：車牌 {plate} 遭系統黑名單封鎖！"

        if query_db("SELECT * FROM active_cars WHERE plate=?", (plate,), one=True):
            return False, f"車輛 {plate} 已在場內"
        
        avail, active, _ = ParkingLogic.get_status()
        if avail <= 0: return False, "車位已滿"

        occupied_slots = [c['slot_idx'] for c in active]
        free_slot = next(i for i in range(TOTAL_SLOTS) if i not in occupied_slots)

        execute_db("INSERT INTO active_cars (plate, entry_time, slot_idx) VALUES (?, ?, ?)", (plate, now.isoformat(), free_slot))
        return True, f"車輛 {plate} 進場成功 (車位 {free_slot+1})"

    @staticmethod
    def exit(plate):
        now = get_current_time()
        car = query_db("SELECT * FROM active_cars WHERE plate=?", (plate,), one=True)
        if not car: return False, "查無進場紀錄"

        entry_time = datetime.fromisoformat(car['entry_time'])
        hours = max(1, int(((now - entry_time).total_seconds() + 3599) // 3600))
        fee = hours * RATE_PER_HOUR

        # VIP 免費機制
        tag = query_db("SELECT tag_type FROM tags WHERE plate=?", (plate,), one=True)
        is_vip = tag and tag['tag_type'] == 'VIP'
        if is_vip: fee = 0

        execute_db("DELETE FROM active_cars WHERE plate=?", (plate,))
        execute_db("INSERT INTO history (plate, entry_time, exit_time, fee) VALUES (?, ?, ?, ?)", (plate, car['entry_time'], now.isoformat(), fee))
        return True, f"{'[VIP免單] ' if is_vip else ''}車牌 {plate} 出場成功，扣款 {fee} 元"

# ==========================================
# 【API 路由】
# ==========================================
@app.route('/api/status')
def api_status():
    avail, active, reserves = ParkingLogic.get_status()
    history = query_db("SELECT * FROM history ORDER BY id DESC")
    return jsonify({
        "system_time": get_current_time().strftime("%Y-%m-%d %H:%M"),
        "available": avail,
        "active_cars": [{"plate": c['plate'], "slot": c['slot_idx']} for c in active],
        "history": [{"plate": h['plate'], "fee": h['fee']} for h in history],
        "total_revenue": sum(h['fee'] for h in history)
    })

@app.route('/api/enter', methods=['POST'])
def api_enter():
    plate = request.json.get('plate')
    success, msg = ParkingLogic.enter(plate)
    return jsonify({"success": success, "message": msg})

@app.route('/api/exit', methods=['POST'])
def api_exit():
    plate = request.json.get('plate')
    success, msg = ParkingLogic.exit(plate)
    return jsonify({"success": success, "message": msg})

# 新增：設定黑白名單 API
@app.route('/api/set_tag', methods=['POST'])
def api_set_tag():
    data = request.json
    plate, t_type = data.get('plate').upper(), data.get('tag_type')
    if t_type == 'NONE': execute_db("DELETE FROM tags WHERE plate=?", (plate,))
    else: execute_db("INSERT OR REPLACE INTO tags (plate, tag_type) VALUES (?, ?)", (plate, t_type))
    return jsonify({"success": True, "message": f"{plate} 已標記為 {t_type}"})

@app.route('/api/scan', methods=['POST'])
def api_scan():
    return jsonify({"plate": lpr_module.mock_scan()})

# ==========================================
# 【網頁與啟動】
# ==========================================
@app.route('/')
def index():
    # 這裡放你原本那一長串 HTML_TEMPLATE 內容
    # 為了簡潔，我假設你已經在檔案中保留了 HTML_TEMPLATE
    return render_template_string("<h1>停車場系統已啟動</h1><p>請確認 HTML_TEMPLATE 已正確嵌入</p>")

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)