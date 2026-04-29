from flask import Flask, render_template_string

app = Flask(__name__)

HTML = """
<!DOCTYPE html>
<html>
<head>
    <title>車牌辨識系統</title>
    <style>
        body {
            margin: 0;
            padding: 0;
            background-color: #FFF8D6;
            font-family: Arial, sans-serif;
            display: flex;
            justify-content: center;
            align-items: center;
            height: 100vh;
        }

        .container {
            background-color: #FFFFFF;
            padding: 40px;
            border-radius: 20px;
            box-shadow: 0 8px 20px rgba(0,0,0,0.15);
            text-align: center;
            width: 400px;
        }

        h1 {
            color: #F4B400;
            margin-bottom: 30px;
        }

        #plate {
            font-size: 2.5rem;
            font-weight: bold;
            background-color: #2c3e50;
            color: #FFD54F;
            padding: 20px;
            border-radius: 15px;
            margin-bottom: 30px;
            letter-spacing: 5px;
        }

        button {
            background-color: #FFC107;
            color: #000;
            border: none;
            padding: 15px 30px;
            font-size: 1.2rem;
            border-radius: 10px;
            cursor: pointer;
            font-weight: bold;
        }
    </style>
</head>

<body>

    <div class="container">
        <h1>AI 車牌辨識系統</h1>

        <div id="plate">ABC-1234</div>

        <button>開始掃描</button>
    </div>

</body>
</html>
"""

@app.route('/')
def home():
    return render_template_string(HTML)

if __name__ == "__main__":
    print("打開瀏覽器：http://127.0.0.1:5000")
    app.run(debug=True)