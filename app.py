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
    def get_duration(self):
        if self.start_time and self.end_time:
            # 退勤時間から出勤時間を引く
            duration = self.end_time - self.start_time
            # 秒単位で合計時間を出し、時間に変換（3600秒 = 1時間）
            hours = duration.total_seconds() / 3600
            # 小数点第2位までで丸める（例：8.50）
            return f"{hours:.2f}"
        return "0.00"

# --- ここまでモデル定義 ---

app.secret_key = 'secretkey1234567' # セッションの暗号化に必要（適当な文字列でOK）

@app.route('/')
def index():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    user_id = session['user_id']
    today = datetime.now().date()
    
    # 1. 今日の打刻データを取得（今のボタン表示用）
    attendance = Attendance.query.filter_by(user_id=user_id, date=today).first()
    
    # 2. 過去の全履歴を取得（履歴リスト表示用）
    # .order_by(Attendance.date.desc()) を付けることで、新しい日付順に並べます
    history = Attendance.query.filter_by(user_id=user_id).order_by(Attendance.date.desc()).all()
    
    return render_template('index.html', 
                           username=session.get('username'), 
                           role=session.get('role'), 
                           attendance=attendance,
                           history=history) # historyをHTMLに渡す

@app.route('/punch', methods=['POST'])
def punch():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    action = request.form.get('action') # 'in' または 'out'
    user_id = session['user_id']
    today = datetime.now().date()
    now = datetime.now()
    today = now.date() # ローカル（日本）の日付

    # 今日の勤怠データを取得
    attendance = Attendance.query.filter_by(user_id=user_id, date=today).first()
    
    # --- ここを追加 ---
    print(f"DEBUG: user_id={user_id}, today={today}")
    print(f"DEBUG: attendance={attendance}")
    if attendance:
        print(f"DEBUG: start_time={attendance.start_time}")
    # ------------------

    if action == 'in':
        if not attendance:
            # 日付（date）を明示的に「今日の日付」で指定して作成
            new_attendance = Attendance(user_id=user_id, date=today, start_time=now)
            db.session.add(new_attendance)
        else:
            flash('既に出勤済みです')
            
    elif action == 'out':
        if attendance and not attendance.end_time:
            # 退勤時間を更新
            attendance.end_time = now
            flash('退勤しました！お疲れ様でした！')
        elif not attendance:
            flash('出勤記録がありません')
        else:
            flash('既に退勤済みです')

    db.session.commit()
    return redirect(url_for('index'))

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