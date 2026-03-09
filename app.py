from flask import Flask, render_template
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

app = Flask(__name__)

# データベースの設定（instanceフォルダ内に作成されます）
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///attendance.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# --- データベースのモデル定義 ---

# 1. ユーザー情報（管理者・従業員）
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password = db.Column(db.String(100), nullable=False) # 本来はハッシュ化が必要
    role = db.Column(db.String(20), nullable=False)     # 'admin' または 'staff'
    hourly_rate = db.Column(db.Integer, default=1000)   # アルバイト用の時給

# 2. 勤怠記録
class Attendance(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    date = db.Column(db.Date, default=datetime.utcnow().date)
    start_time = db.Column(db.DateTime)
    end_time = db.Column(db.DateTime)
    break_minutes = db.Column(db.Integer, default=0)
    note = db.Column(db.Text)

# --- ここまでモデル定義 ---

@app.route('/')
def index():
    return render_template('index.html')

if __name__ == '__main__':
    # 実行時にデータベースとテーブルを自動作成する
    with app.app_context():
        db.create_all()
    app.run(debug=True)