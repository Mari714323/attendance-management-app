from flask import Flask, render_template

app = Flask(__name__)

@app.route('/')
def index():
    # 後でここにログインチェックなどを入れますが、まずは表示だけ
    return render_template('index.html')

if __name__ == '__main__':
    # 開発用サーバーを起動（debug=Trueでコード変更が即反映されます）
    app.run(debug=True)