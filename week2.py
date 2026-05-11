import os
import sqlite3
from datetime import datetime
from flask import Flask, request, jsonify, render_template_string

app = Flask(__name__)
DB_FILE = 'parking_system.db'
TOTAL_SLOTS = 10

# --- 資料庫初始化 ---
def init_db():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    # active_cars: 停在場內的車 / reservations: 已經預約但還沒來的車
    cursor.execute('CREATE TABLE IF NOT EXISTS active_cars (plate TEXT PRIMARY KEY, entry_time TEXT)')
    cursor.execute('CREATE TABLE IF NOT EXISTS reservations (plate TEXT PRIMARY KEY)')
    conn.commit()
    conn.close()

def execute_db(query, args=()):
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()
    cur.execute(query, args)
    conn.commit()
    conn.close()

def query_db(query, args=(), one=False):
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    rv = conn.cursor().execute(query, args).fetchall()
    conn.close()
    return (rv[0] if rv else None) if one else rv

init_db()

# --- 核心邏輯 ---

@app.route('/api/status')
def get_status():
    active_count = len(query_db("SELECT * FROM active_cars"))
    reserve_count = len(query_db("SELECT * FROM reservations"))
    available = TOTAL_SLOTS - active_count - reserve_count
    return jsonify({
        "available": available,
        "active": active_count,
        "reserved": reserve_count
    })

@app.route('/api/reserve', methods=['POST'])
def reserve_parking():
    plate = request.json.get('plate').upper()
    # 檢查是否還有空位可預約
    status = get_status().json
    if status['available'] <= 0:
        return jsonify({"success": False, "message": "目前已無空位可供預約！"})
    
    try:
        execute_db("INSERT INTO reservations (plate) VALUES (?)", (plate,))
        return jsonify({"success": True, "message": f"車牌 {plate} 預約成功，已為您保留車位。"})
    except:
        return jsonify({"success": False, "message": "此車牌已在預約清單中。"})

@app.route('/api/enter', methods=['POST'])
def car_enter():
    plate = request.json.get('plate').upper()
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    # 檢查是否為預約車輛，如果是，就移除預約轉入進場
    is_reserved = query_db("SELECT * FROM reservations WHERE plate=?", (plate,), one=True)
    if is_reserved:
        execute_db("DELETE FROM reservations WHERE plate=?", (plate,))
        msg = f"預約車 {plate} 進場成功！"
    else:
        # 非預約車要檢查當前是否有空位
        status = get_status().json
        if status['available'] <= 0:
            return jsonify({"success": False, "message": "現場已無車位！"})
        msg = f"一般車 {plate} 進場成功！"

    try:
        execute_db("INSERT INTO active_cars (plate, entry_time) VALUES (?, ?)", (plate, now))
        return jsonify({"success": True, "message": msg})
    except:
        return jsonify({"success": False, "message": "車輛已在場內。"})

@app.route('/')
def index():
    return "<h1>停車場預約系統運行中</h1><p>API 已準備就緒。</p>"

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)