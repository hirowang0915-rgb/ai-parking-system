import sqlite3
import random
import string
from datetime import datetime, timedelta
from flask import Flask, request, jsonify, render_template_string

app = Flask(__name__)
DB_FILE = 'parking_final.db'

# ==========================================
# 1. 資料庫初始化
# ==========================================
def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    # 在場車輛
    c.execute('CREATE TABLE IF NOT EXISTS active_cars (plate TEXT PRIMARY KEY, entry_time TEXT)')
    # 預約紀錄 (車牌, 預約時間)
    c.execute('CREATE TABLE IF NOT EXISTS reservations (plate TEXT PRIMARY KEY, res_time TEXT)')
    # 歷史紀錄 (用於車流分析)
    c.execute('CREATE TABLE IF NOT EXISTS history (id INTEGER PRIMARY KEY AUTOINCREMENT, plate TEXT, fee REAL, exit_time TEXT)')
    conn.commit()
    conn.close()

init_db()

def get_db():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn

# ==========================================
# 2. 後端核心邏輯
# ==========================================

@app.route('/api/status', methods=['GET'])
def get_status():
    conn = get_db()
    active = conn.execute('SELECT * FROM active_cars').fetchall()
    reserves = conn.execute('SELECT * FROM reservations').fetchall()
    history = conn.execute('SELECT * FROM history').fetchall()
    total_rev = sum(h['fee'] for h in history)
    return jsonify({
        "active_list": [dict(row) for row in active],
        "reserve_list": [dict(row) for row in reserves],
        "revenue": total_rev,
        "total_cars": len(history)
    })

@app.route('/api/reserve', methods=['POST'])
def api_reserve():
    plate = request.json.get('plate', '').upper()
    if not plate: return jsonify({"success": False, "msg": "請輸入車牌"})
    
    conn = get_db()
    try:
        conn.execute('INSERT INTO reservations (plate, res_time) VALUES (?, ?)', 
                     (plate, datetime.now().isoformat()))
        conn.commit()
        return jsonify({"success": True, "msg": f"車牌 {plate} 預約成功 (保留30分鐘)"})
    except:
        return jsonify({"success": False, "msg": "該車牌已有預約或在場內"})

@app.route('/api/scan', methods=['POST'])
def api_scan():
    conn = get_db()
    # 自動清理超過 30 分鐘的過期預約
    expire_time = (datetime.now() - timedelta(minutes=30)).isoformat()
    conn.execute('DELETE FROM reservations WHERE res_time < ?', (expire_time,))
    
    # 模擬 AI 辨識
    plate = f"{''.join(random.choices(string.ascii_uppercase, k=3))}-{''.join(random.choices(string.digits, k=4))}"
    
    # 檢查是否為預約車輛 (如果是，則允許進場並刪除預約)
    is_reserved = conn.execute('SELECT * FROM reservations WHERE plate = ?', (plate,)).fetchone()
    
    try:
        conn.execute('INSERT INTO active_cars (plate, entry_time) VALUES (?, ?)', 
                     (plate, datetime.now().isoformat()))
        if is_reserved:
            conn.execute('DELETE FROM reservations WHERE plate = ?', (plate,))
        conn.commit()
        status_msg = "預約客進場" if is_reserved else "一般進場成功"
        return jsonify({"plate": plate, "status": status_msg})
    except:
        return jsonify({"plate": plate, "status": "進場失敗(可能已在場)"})

@app.route('/api/exit', methods=['POST'])
def api_exit():
    plate = request.json.get('plate')
    conn = get_db()
    car = conn.execute('SELECT * FROM active_cars WHERE plate = ?', (plate,)).fetchone()
    
    if not car: return jsonify({"success": False, "msg": "查無此車"})

    # 計費邏輯：40元/小時
    duration = datetime.now() - datetime.fromisoformat(car['entry_time'])
    hours = max(1, int((duration.total_seconds() + 3599) // 3600))
    fee = hours * 40

    conn.execute('DELETE FROM active_cars WHERE plate = ?', (plate,))
    conn.execute('INSERT INTO history (plate, fee, exit_time) VALUES (?, ?, ?)',
                 (plate, fee, datetime.now().isoformat()))
    conn.commit()
    return jsonify({"success": True, "msg": f"車牌 {plate} 出場，計費 {fee} 元"})

# ==========================================
# 3. 前端網頁介面
# ==========================================
HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <style>
        :root { --bg: #FFF9C4; --primary: #FBC02D; --dark: #2c3e50; }
        body { margin:0; padding:20px; background:var(--bg); font-family:Arial; text-align:center; }
        .container { background:white; padding:30px; border-radius:12px; max-width:500px; margin:auto; box-shadow:0 4px 15px rgba(0,0,0,0.1); }
        .header { background:var(--primary); padding:15px; font-weight:bold; margin:-30px -30px 20px -30px; border-radius:12px 12px 0 0; }
        .plate-display { font-size:2.5rem; background:var(--dark); color:#f1c40f; padding:15px; border-radius:10px; margin-bottom:10px; min-height:60px; font-family:monospace; }
        .btn-group { display:flex; justify-content:center; gap:10px; margin-bottom:20px; }
        button { padding:12px; border:none; border-radius:6px; cursor:pointer; font-weight:bold; color:white; background:#3498db; }
        button.exit { background:#e74c3c; }
        button.res { background:#2ecc71; }
        .list-section { text-align:left; margin-top:20px; background:#f9f9f9; padding:10px; border-radius:8px; font-size:0.9rem; }
        .item { display:flex; justify-content:space-between; padding:8px 0; border-bottom:1px solid #eee; cursor:pointer; }
        .item:hover { color:#3498db; }
        .tag { font-size:0.7rem; padding:2px 6px; border-radius:4px; background:#ddd; }
    </style>
</head>
<body>
<div class="container">
    <div class="header">AI 停車與預約系統</div>
    <div class="plate-display" id="plate">READY</div>
    <div id="status" style="margin-bottom:15px; color:#666;">系統就緒</div>

    <div class="btn-group">
        <button onclick="scan()">進場掃描</button>
        <button class="res" onclick="makeReservation()">預約車位</button>
        <button class="exit" onclick="manualExit()">手動離場</button>
    </div>

    <div class="list-section">
        <b>場內車輛 (點擊可結帳)：</b>
        <div id="active-list"></div>
    </div>

    <div class="list-section">
        <b>預約名單：</b>
        <div id="reserve-list"></div>
    </div>

    <div style="margin-top:15px; font-size:0.8rem;">
        今日累積營收：<span id="rev">0</span> 元
    </div>
</div>

<script>
    let lastScanned = "";

    async function refresh() {
        const res = await fetch('/api/status');
        const data = await res.json();
        
        document.getElementById("rev").innerText = data.revenue;
        
        // 渲染場內
        const aList = document.getElementById("active-list");
        aList.innerHTML = data.active_list.length ? "" : "無車輛";
        data.active_list.forEach(car => {
            const div = document.createElement("div");
            div.className = "item";
            div.innerHTML = `<span>${car.plate}</span> <span class="tag">點擊結帳</span>`;
            div.onclick = () => exitCar(car.plate);
            aList.appendChild(div);
        });

        // 渲染預約
        const rList = document.getElementById("reserve-list");
        rList.innerHTML = data.reserve_list.length ? "" : "無預約";
        data.reserve_list.forEach(r => {
            const div = document.createElement("div");
            div.className = "item";
            div.innerHTML = `<span>${r.plate}</span> <span class="tag">預約中</span>`;
            rList.appendChild(div);
        });
    }

    async function scan() {
        const res = await fetch('/api/scan', {method:'POST'});
        const data = await res.json();
        document.getElementById("plate").innerText = data.plate;
        document.getElementById("status").innerText = data.status;
        lastScanned = data.plate;
        refresh();
    }

    async function makeReservation() {
        const p = prompt("請輸入預約車牌：");
        if(!p) return;
        const res = await fetch('/api/reserve', {
            method:'POST',
            headers:{'Content-Type':'application/json'},
            body: JSON.stringify({plate: p})
        });
        const data = await res.json();
        alert(data.msg);
        refresh();
    }

    function manualExit() {
        const p = prompt("請輸入離場車牌：", lastScanned);
        if(p) exitCar(p);
    }

    async function exitCar(plate) {
        const res = await fetch('/api/exit', {
            method:'POST',
            headers:{'Content-Type':'application/json'},
            body: JSON.stringify({plate: plate})
        });
        const data = await res.json();
        if(data.success) {
            document.getElementById("plate").innerText = "BYE";
            document.getElementById("status").innerText = data.msg;
            lastScanned = "";
        } else {
            alert(data.msg);
        }
        refresh();
    }

    refresh();
</script>
</body>
</html>
"""

@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5001, debug=True, use_reloader=False, threaded=False)