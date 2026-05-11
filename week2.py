import os
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
    c.execute('CREATE TABLE IF NOT EXISTS active_cars (plate TEXT PRIMARY KEY, entry_time TEXT)')
    c.execute('CREATE TABLE IF NOT EXISTS reservations (plate TEXT PRIMARY KEY, res_time TEXT)')
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
    conn.close()
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
    # 防呆：檢查是否已在場內
    in_car = conn.execute('SELECT * FROM active_cars WHERE plate = ?', (plate,)).fetchone()
    if in_car:
        conn.close()
        return jsonify({"success": False, "msg": f"車牌 {plate} 已經在場內，無法預約！"})
    
    try:
        conn.execute('INSERT INTO reservations (plate, res_time) VALUES (?, ?)', 
                     (plate, datetime.now().isoformat()))
        conn.commit()
        return jsonify({"success": True, "msg": f"車牌 {plate} 預約成功"})
    except:
        return jsonify({"success": False, "msg": "該車牌已在預約清單中"})
    finally:
        conn.close()

@app.route('/api/scan', methods=['POST'])
def api_scan():
    conn = get_db()
    # 1. 自動清理過期預約 (30分鐘)
    expire_limit = (datetime.now() - timedelta(minutes=30)).isoformat()
    conn.execute('DELETE FROM reservations WHERE res_time < ?', (expire_limit,))
    
    # 2. 模擬 AI 掃描
    plate = f"{''.join(random.choices(string.ascii_uppercase, k=3))}-{''.join(random.choices(string.digits, k=4))}"
    
    # 3. 智慧判斷：是否已經在場內？ (若在場內則自動結帳)
    in_car = conn.execute('SELECT * FROM active_cars WHERE plate = ?', (plate,)).fetchone()
    if in_car:
        duration = datetime.now() - datetime.fromisoformat(in_car['entry_time'])
        hours = max(1, int((duration.total_seconds() + 3599) // 3600))
        fee = hours * 40
        conn.execute('DELETE FROM active_cars WHERE plate = ?', (plate,))
        conn.execute('INSERT INTO history (plate, fee, exit_time) VALUES (?, ?, ?)',
                     (plate, fee, datetime.now().isoformat()))
        conn.commit()
        conn.close()
        return jsonify({"plate": plate, "status": f"偵測到在場：自動結帳，扣款 {fee} 元"})

    # 4. 正常進場邏輯 (含預約檢查)
    is_reserved = conn.execute('SELECT * FROM reservations WHERE plate = ?', (plate,)).fetchone()
    try:
        conn.execute('INSERT INTO active_cars (plate, entry_time) VALUES (?, ?)', 
                     (plate, datetime.now().isoformat()))
        if is_reserved:
            conn.execute('DELETE FROM reservations WHERE plate = ?', (plate,))
        conn.commit()
        status_msg = "預約客歡迎進場" if is_reserved else "一般客進場成功"
        return jsonify({"plate": plate, "status": status_msg})
    except:
        return jsonify({"plate": plate, "status": "進場失敗"})
    finally:
        conn.close()

@app.route('/api/exit', methods=['POST'])
def api_exit():
    plate = request.json.get('plate')
    conn = get_db()
    car = conn.execute('SELECT * FROM active_cars WHERE plate = ?', (plate,)).fetchone()
    if not car: 
        conn.close()
        return jsonify({"success": False, "msg": "查無此車"})

    duration = datetime.now() - datetime.fromisoformat(car['entry_time'])
    hours = max(1, int((duration.total_seconds() + 3599) // 3600))
    fee = hours * 40

    conn.execute('DELETE FROM active_cars WHERE plate = ?', (plate,))
    conn.execute('INSERT INTO history (plate, fee, exit_time) VALUES (?, ?, ?)',
                 (plate, fee, datetime.now().isoformat()))
    conn.commit()
    conn.close()
    return jsonify({"success": True, "msg": f"車牌 {plate} 出場成功，計費 {fee} 元"})

# 新增：快轉功能的 API
@app.route('/api/fast_forward', methods=['POST'])
def api_fast_forward():
    conn = get_db()
    conn.execute("UPDATE reservations SET res_time = datetime(res_time, '-31 minutes')")
    conn.commit()
    conn.close()
    return jsonify({"success": True})

# ==========================================
# 3. 前端網頁介面
# ==========================================
HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>AI Parking Pro</title>
    <style>
        :root { --bg: #f0f2f5; --primary: #FBC02D; --dark: #1a1a1a; }
        body { margin:0; padding:20px; background:var(--bg); font-family:'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; text-align:center; }
        .container { background:white; padding:30px; border-radius:15px; max-width:550px; margin:auto; box-shadow:0 10px 25px rgba(0,0,0,0.1); }
        .header { background:var(--primary); padding:15px; font-weight:bold; margin:-30px -30px 20px -30px; border-radius:15px 15px 0 0; font-size: 1.3rem; }
        .plate-display { font-size:2.8rem; background:var(--dark); color:#f1c40f; padding:20px; border-radius:10px; margin-bottom:10px; font-family:monospace; box-shadow: inset 0 0 10px rgba(0,0,0,0.5); }
        .btn-group { display:flex; justify-content:center; gap:10px; margin-bottom:20px; flex-wrap: wrap; }
        button { padding:12px 18px; border:none; border-radius:8px; cursor:pointer; font-weight:bold; color:white; transition: 0.3s; background:#3498db; }
        button:hover { opacity: 0.8; transform: translateY(-2px); }
        button.exit { background:#e74c3c; }
        button.res { background:#2ecc71; }
        button.ff { background:#607d8b; }
        .list-section { text-align:left; margin-top:20px; background:#fff; border:1px solid #eee; padding:15px; border-radius:10px; }
        .item { display:flex; justify-content:space-between; padding:12px 0; border-bottom:1px solid #f0f0f0; cursor:pointer; }
        .item:last-child { border:none; }
        .tag { font-size:0.75rem; padding:3px 8px; border-radius:5px; background:#eee; color:#666; }
        .revenue-box { margin-top:20px; padding:15px; background:#e8f5e9; border-radius:10px; font-weight:bold; color:#2e7d32; }
    </style>
</head>
<body>
<div class="container">
    <div class="header">AI 智慧停車完全體系統</div>
    <div class="plate-display" id="plate">READY</div>
    <div id="status" style="margin-bottom:20px; color:#555; font-weight:500;">等待操作...</div>

    <div class="btn-group">
        <button onclick="scan()">進場掃描</button>
        <button class="res" onclick="makeReservation()">預約車位</button>
        <button class="exit" onclick="manualExit()">手動離場</button>
        <button class="ff" onclick="fastForward()">⏳ 快轉30分</button>
    </div>

    <div class="list-section">
        <b>📋 場內車輛 (點擊可快速結帳)：</b>
        <div id="active-list"></div>
    </div>

    <div class="list-section">
        <b>📅 預約名單：</b>
        <div id="reserve-list"></div>
    </div>

    <div class="revenue-box">
        今日總營收： <span id="rev">0</span> 元
    </div>
</div>

<script>
    async function refresh() {
        const res = await fetch('/api/status');
        const data = await res.json();
        document.getElementById("rev").innerText = data.revenue;
        
        const aList = document.getElementById("active-list");
        aList.innerHTML = data.active_list.length ? "" : "<div style='color:#999; padding:10px;'>目前場內無車輛</div>";
        data.active_list.forEach(car => {
            const div = document.createElement("div");
            div.className = "item";
            div.innerHTML = `<span>🚗 ${car.plate}</span> <span class="tag">點擊出場</span>`;
            div.onclick = () => exitCar(car.plate);
            aList.appendChild(div);
        });

        const rList = document.getElementById("reserve-list");
        rList.innerHTML = data.reserve_list.length ? "" : "<div style='color:#999; padding:10px;'>目前無預約</div>";
        data.reserve_list.forEach(r => {
            const div = document.createElement("div");
            div.className = "item";
            div.innerHTML = `<span>🕒 ${r.plate}</span> <span class="tag">預約保留中</span>`;
            rList.appendChild(div);
        });
    }

    async function scan() {
        const res = await fetch('/api/scan', {method:'POST'});
        const data = await res.json();
        document.getElementById("plate").innerText = data.plate;
        document.getElementById("status").innerText = data.status;
        refresh();
    }

    async function makeReservation() {
        const p = prompt("請輸入欲預約車牌：");
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

    async function fastForward() {
        if(!confirm("確定要快轉時間來測試『預約自動過期』嗎？")) return;
        await fetch('/api/fast_forward', {method:'POST'});
        alert("時空跳躍成功！下次掃描時過期名單將自動消失。");
        refresh();
    }

    async function exitCar(plate) {
        if(!confirm(`確定要為車牌 ${plate} 辦理出場結帳？`)) return;
        const res = await fetch('/api/exit', {
            method:'POST',
            headers:{'Content-Type':'application/json'},
            body: JSON.stringify({plate: plate})
        });
        const data = await res.json();
        alert(data.msg);
        refresh();
    }

    function manualExit() {
        const p = prompt("請輸入離場車牌：");
        if(p) exitCar(p);
    }

    refresh();
</script>
</body>
</html>
"""

@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)

# ==========================================
# 4. 啟動設定
# ==========================================
if __name__ == '__main__':
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port, debug=False)