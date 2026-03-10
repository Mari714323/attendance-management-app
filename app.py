from flask import Flask, render_template, request, redirect, url_for, session, flash
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

app.secret_key = 'secretkey1234567' # セッションの暗号化に必要（適当な文字列でOK）

@app.route('/')
def index():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    return render_template('index.html', username=session.get('username'), role=session.get('role'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        user = User.query.filter_by(username=username, password=password).first()
        
        if user:
            session['user_id'] = user.id
            session['username'] = user.username
            session['role'] = user.role
            return redirect(url_for('index'))
        else:
            flash('ユーザー名またはパスワードが正しくありません')
            
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

if __name__ == '__main__':
    # 実行時にデータベースとテーブルを自動作成する
    with app.app_context():
        db.create_all()
    app.run(debug=True)