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
    def get_monthly_stats(self):
        from datetime import datetime
        now = datetime.now()
        # 1. 今月の1日の日付を作成
        first_day = datetime(now.year, now.month, 1).date()
        
        # 2. このユーザーの、今月の勤怠データをすべて取得
        monthly_records = Attendance.query.filter(
            Attendance.user_id == self.id,
            Attendance.date >= first_day
        ).all()
        
        total_hours = 0
        for record in monthly_records:
            if record.start_time and record.end_time:
                duration = record.end_time - record.start_time
                # 休憩時間を引いた秒数を加算していく
                actual_seconds = duration.total_seconds() - (record.break_minutes * 60)
                total_hours += max(0, actual_seconds) / 3600    
        
        # 3. 合計時間と、時給を掛けた概算給与を返す
        total_salary = total_hours * self.hourly_rate
        return {
            'total_hours': f"{total_hours:.2f}",
            'total_salary': int(total_salary) # 給与は整数で返す
        }

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
            # 合計秒数から休憩時間（分 × 60秒）を引く
            total_seconds = duration.total_seconds() - (self.break_minutes * 60)
            # 万が一マイナスにならないよう調整
            total_seconds = max(0, total_seconds)
            # 時間に変換
            hours = total_seconds / 3600
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

@app.route('/admin')
def admin_dashboard():
    # 1. ログインチェック
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    # 2. 管理者権限チェック（管理者じゃなければトップへ戻す）
    if session.get('role') != 'admin':
        flash('このページにアクセスする権限がありません')
        return redirect(url_for('index'))
    
    # 3. 全ユーザー（従業員）のリストを取得
    # 管理者(admin)以外のユーザーをすべて取得します
    users = User.query.filter(User.role != 'admin').all()
    
    return render_template('admin.html', users=users)

@app.route('/admin/attendance/<int:user_id>')
def admin_user_attendance(user_id):
    # 管理者権限チェック
    if 'user_id' not in session or session.get('role') != 'admin':
        return redirect(url_for('login'))
    
    # 対象のユーザーを取得（いなければ404エラーを返す）
    user = User.query.get_or_404(user_id)
    
    # そのユーザーの全勤怠データを新しい順に取得
    attendances = Attendance.query.filter_by(user_id=user_id).order_by(Attendance.date.desc()).all()
    
    return render_template('admin_attendance.html', user=user, attendances=attendances)

# app.py に追加
@app.route('/admin/attendance/<int:user_id>/add', methods=['POST'])
def admin_add_attendance(user_id):
    # 管理者権限チェック
    if 'user_id' not in session or session.get('role') != 'admin':
        return redirect(url_for('login'))
    
    # フォームから送られてきたデータを取得
    date_str = request.form.get('date')       # 例: "2026-03-14"
    start_str = request.form.get('start_time') # 例: "09:00"
    end_str = request.form.get('end_time')     # 例: "18:00"
    # 休憩時間を取得（整数に変換、入力がなければ0）
    break_minutes = int(request.form.get('break_minutes', 0))
    
    try:
        # 文字列を Python の日付・時刻オブジェクトに変換
        date_obj = datetime.strptime(date_str, '%Y-%m-%d').date()
        start_time = datetime.strptime(f"{date_str} {start_str}", '%Y-%m-%d %H:%M')
        
        end_time = None
        if end_str:
            end_time = datetime.strptime(f"{date_str} {end_str}", '%Y-%m-%d %H:%M')
        
        # 新しい勤怠レコードを作成して保存
        new_record = Attendance(
            user_id=user_id,
            date=date_obj,
            start_time=start_time,
            end_time=end_time,
            break_minutes=break_minutes
        )
        db.session.add(new_record)
        db.session.commit()
        flash('勤怠データを手動で追加しました')
        
    except ValueError:
        flash('入力された日時の形式が正しくありません')
        
    # 従業員の勤怠一覧ページに戻る
    return redirect(url_for('admin_user_attendance', user_id=user_id))

# app.py に追加
@app.route('/admin/attendance/edit/<int:attendance_id>', methods=['GET'])
def admin_edit_attendance(attendance_id):
    # 管理者権限チェック
    if 'user_id' not in session or session.get('role') != 'admin':
        return redirect(url_for('login'))
    
    # 修正対象の勤怠データを1件取得
    record = Attendance.query.get_or_404(attendance_id)
    # そのデータの持ち主（従業員）の情報も取得（画面表示用）
    user = User.query.get(record.user_id)
    
    return render_template('admin_edit.html', record=record, user=user)

# app.py に追加
@app.route('/admin/attendance/update/<int:attendance_id>', methods=['POST'])
def admin_update_attendance(attendance_id):
    # 管理者権限チェック
    if 'user_id' not in session or session.get('role') != 'admin':
        return redirect(url_for('login'))
    
    # 修正対象のデータを取得
    record = Attendance.query.get_or_404(attendance_id)
    
    # フォームから送られてきた新しい値を取得
    date_str = request.form.get('date')
    start_str = request.form.get('start_time')
    end_str = request.form.get('end_time')
    # 休憩時間を取得
    break_minutes = int(request.form.get('break_minutes', 0))
    
    try:
        # 既存のレコードの値を上書きする
        record.date = datetime.strptime(date_str, '%Y-%m-%d').date()
        record.start_time = datetime.strptime(f"{date_str} {start_str}", '%Y-%m-%d %H:%M')
        
        if end_str:
            record.end_time = datetime.strptime(f"{date_str} {end_str}", '%Y-%m-%d %H:%M')
        else:
            record.end_time = None # 退勤が空の場合はNone（未打刻状態）にする

        # 休憩時間を更新
        record.break_minutes = break_minutes
            
        db.session.commit()
        flash('勤怠データを更新しました')
    except ValueError:
        flash('日時の形式が正しくありません')
        
    # 修正が終わったら、その従業員の勤怠一覧ページに戻る
    return redirect(url_for('admin_user_attendance', user_id=record.user_id))

if __name__ == '__main__':
    # 実行時にデータベースとテーブルを自動作成する
    with app.app_context():
        db.create_all()
    app.run(debug=True)