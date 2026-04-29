import random
import string
from flask import Flask, jsonify, render_template_string

# ==========================================
# 【AI 車牌辨識模組與防呆機制】
# ==========================================
try:
    import cv2
    import easyocr
    OCR_AVAILABLE = True
except ImportError:
    OCR_AVAILABLE = False

class LPRModule:
    def __init__(self):
        self.reader = None
        if OCR_AVAILABLE:
            print("[系統] 正在初始化 EasyOCR 車牌辨識模型，請稍候...")
            self.reader = easyocr.Reader(['en'], gpu=False)
            print("[系統] AI 車牌辨識模型就緒。")
        else:
            print("[警告] 未偵測到 AI 視覺套件，將啟用模擬隨機產生模式。")

    def preprocess_image(self, frame):
        """
        影像前處理：過濾雜訊並提高字體邊緣對比度，大幅提升辨識準確率。
        """
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        blur = cv2.bilateralFilter(gray, 11, 17, 17)
        return blur

    def scan_camera(self):
        """
        開啟實體攝影機擷取畫面並進行 AI 辨識。
        """
        if not OCR_AVAILABLE or not self.reader:
            return self.mock_scan()
            
        cap = cv2.VideoCapture(0)
        print("[系統] 攝影機已開啟，請按下 's' 擷取畫面並辨識，'q' 取消。")
        plate = "UNKNOWN"
        
        plate_chars = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-'
        
        while cap.isOpened():
            ret, frame = cap.read()
            if not ret: 
                break 
            
            cv2.imshow('AI License Plate Recognition (Press S to Scan, Q to Quit)', frame)
            key = cv2.waitKey(1) & 0xFF
            
            if key == ord('s'):
                print("[分析中] 正在進行影像強化與特徵提取...")
                processed_frame = self.preprocess_image(frame)
                result = self.reader.readtext(processed_frame, allowlist=plate_chars)
                
                if result: 
                    raw_text = result[0][1].replace(" ", "").upper()
                    if len(raw_text) >= 4:
                        plate = raw_text
                break
            elif key == ord('q'): 
                break 
                
        cap.release()
        cv2.destroyAllWindows()
        cv2.waitKey(1)
        cv2.waitKey(1)
        return plate

    def mock_scan(self):
        """套件缺失時的防呆模擬功能"""
        letters = ''.join(random.choices(string.ascii_uppercase, k=3))
        numbers = ''.join(random.choices(string.digits, k=4))
        return f"{letters}-{numbers}"

# ==========================================
# 【Flask 後端伺服器】
# ==========================================
app = Flask(__name__)
lpr_module = LPRModule()

@app.route('/api/scan', methods=['POST'])
def api_scan():
    """處理網頁端傳來的掃描請求"""
    is_fallback = False
    warning_msg = ""

    if not OCR_AVAILABLE:
        is_fallback = True
        warning_msg = "未偵測到 opencv-python 或 easyocr 套件，目前為模擬測試模式，輸出的車牌為隨機產生。若要測試真實 AI，請依照 README.txt 指示安裝套件。"
        plate = lpr_module.mock_scan()
    else:
        plate = lpr_module.scan_camera()
        
    return jsonify({
        "plate": plate,
        "is_fallback": is_fallback,
        "warning_msg": warning_msg
    })

# ==========================================
# 【前端展示網頁 (極簡版 HTML/CSS/JS)】
# ==========================================
HTML_TEMPLATE = r"""
<!DOCTYPE html>
<html lang="zh-TW">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>AI 車牌辨識展示系統</title>
    <style>
        :root {
            --bg-color: #FFF9C4;
            --primary-color: #FBC02D;
            --text-color: #000000;
            --panel-bg: #FFFFFF;
        }
        body {
            font-family: Arial, sans-serif;
            background-color: var(--bg-color);
            color: var(--text-color);
            margin: 0;
            padding: 60px 20px;
            display: flex;
            flex-direction: column;
            align-items: center;
        }
        .container {
            width: 100%;
            max-width: 700px;
            background-color: var(--panel-bg);
            border-radius: 10px;
            box-shadow: 0 4px 15px rgba(0,0,0,0.15);
            overflow: hidden;
            border: 1px solid #ccc;
        }
        .header {
            background-color: var(--primary-color);
            padding: 20px;
            text-align: center;
            font-size: 1.6rem;
            font-weight: bold;
            border-bottom: 2px solid #e0a800;
        }
        .content {
            padding: 40px;
            display: flex;
            flex-direction: column;
            align-items: center;
            gap: 20px;
        }
        .scan-area {
            width: 100%;
            display: flex;
            flex-direction: column;
            align-items: center;
            padding: 40px 20px;
            background-color: #f8f9fa;
            border: 2px dashed #bdc3c7;
            border-radius: 10px;
            box-sizing: border-box;
        }
        .plate-display {
            font-size: 3.5rem;
            font-weight: bold;
            letter-spacing: 6px;
            padding: 25px 50px;
            background-color: #2c3e50;
            color: #f1c40f;
            border-radius: 8px;
            border: 4px solid #34495e;
            margin-bottom: 30px;
            min-width: 320px;
            text-align: center;
        }
        button {
            padding: 15px 40px;
            font-size: 1.3rem;
            cursor: pointer;
            background-color: #3498db;
            color: white;
            border: none;
            border-radius: 5px;
            font-weight: bold;
            transition: background-color 0.3s;
        }
        button:hover { background-color: #2980b9; }
        button:disabled { background-color: #95a5a6; cursor: not-allowed; }
        
        .warning-msg {
            color: #e74c3c;
            background-color: #fadbd8;
            padding: 15px;
            border-radius: 5px;
            font-weight: bold;
            display: none;
            width: 100%;
            text-align: center;
            box-sizing: border-box;
            line-height: 1.5;
        }
    </style>
</head>
<body>

    <div class="container">
        <div class="header">AI 智慧車牌辨識核心展示</div>
        
        <div class="content">
            <div id="warning-banner" class="warning-msg"></div>

            <div class="scan-area">
                <div class="plate-display" id="plate-result">等待掃描</div>
                <button id="scan-btn" onclick="startScan()">啟動實體鏡頭掃描</button>
                <p id="status-text" style="color: #7f8c8d; margin-top: 20px; font-size: 1.1rem;">點擊上方按鈕後，請在彈出的相機視窗按下 'S' 進行辨識</p>
            </div>
        </div>
    </div>

    <script>
        async function startScan() {
            const btn = document.getElementById('scan-btn');
            const statusText = document.getElementById('status-text');
            const plateResult = document.getElementById('plate-result');
            const warningBanner = document.getElementById('warning-banner');
            
            btn.disabled = true;
            btn.innerText = "鏡頭運作與辨識中...";
            statusText.innerText = "請在彈出的相機視窗中操作...";
            plateResult.innerText = "讀取中";
            warningBanner.style.display = 'none';

            try {
                const res = await fetch('/api/scan', { method: 'POST' });
                const data = await res.json();
                
                if (data.is_fallback) {
                    warningBanner.innerText = data.warning_msg;
                    warningBanner.style.display = 'block';
                }

                if (data.plate && data.plate !== 'UNKNOWN') {
                    plateResult.innerText = data.plate;
                    statusText.innerText = "辨識完成！";
                } else {
                    plateResult.innerText = "無法辨識";
                    statusText.innerText = "請確認車牌清晰且在畫面中央，再次嘗試。";
                }
            } catch (error) {
                plateResult.innerText = "系統錯誤";
                statusText.innerText = "無法連接至後端辨識伺服器。";
            } finally {
                btn.disabled = false;
                btn.innerText = "重新啟動鏡頭掃描";
            }
        }
    </script>
</body>
</html>
"""

@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)

if __name__ == '__main__':
    print("==================================================")
    print(" AI 車牌辨識極簡展示模組啟動中...")
    print(" 請打開瀏覽器並輸入網址: http://127.0.0.1:5000")
    print("==================================================")
    app.run(debug=True, use_reloader=False, threaded=False)
