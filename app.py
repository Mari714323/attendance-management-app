import csv
import io
from flask import Flask, render_template, request, redirect, url_for, session, flash, make_response
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash

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
        first_day = datetime(now.year, now.month, 1).date()
        
        monthly_records = Attendance.query.filter(
            Attendance.user_id == self.id,
            Attendance.date >= first_day
        ).all()
        
        total_hours = 0
        total_overtime_hours = 0
        total_night_hours = 0
        
        for record in monthly_records:
            if record.start_time and record.end_time:
                # 基本の労働時間
                duration = float(record.get_duration())
                total_hours += duration
                
                # 深夜労働時間と残業時間を集計
                total_night_hours += record.get_night_shift_hours()
                total_overtime_hours += record.get_overtime_hours()
        
        # --- 給与計算ロジック ---
        # 1. 基本給（全労働時間 × 時給）
        base_pay = total_hours * self.hourly_rate
        
        # 2. 残業割増分（残業時間 × 時給 × 0.25）
        overtime_pay = total_overtime_hours * self.hourly_rate * 0.25
        
        # 3. 深夜割増分（深夜時間 × 時給 × 0.25）
        night_pay = total_night_hours * self.hourly_rate * 0.25
        
        # 合計金額
        total_salary = base_pay + overtime_pay + night_pay
        
        return {
            'total_hours': f"{total_hours:.2f}",
            'overtime_hours': f"{total_overtime_hours:.2f}",
            'night_hours': f"{total_night_hours:.2f}",
            'total_salary': int(total_salary)
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
    def get_status(self):
        status_list = []
        
        # 出勤時間が 09:00:00 より遅い場合は「遅刻」
        if self.start_time and self.start_time.time() > datetime.strptime("09:00:00", "%H:%M:%S").time():
            status_list.append("遅刻")
            
        # 退勤時間が 18:00:00 より早い場合は「早退」
        if self.end_time and self.end_time.time() < datetime.strptime("18:00:00", "%H:%M:%S").time():
            status_list.append("早退")
            
        return status_list
    # app.py の Attendance クラス内に追加
    def get_night_shift_hours(self):
        """深夜労働時間（22:00 - 05:00）を計算する"""
        if not (self.start_time and self.end_time):
            return 0.0
        
        total_night_seconds = 0
        current = self.start_time
        # 1分刻みでチェックするロジック（複雑な跨ぎにも対応）
        import datetime
        while current < self.end_time:
            # 22時以降、または5時より前かを判定
            if current.hour >= 22 or current.hour < 5:
                total_night_seconds += 60
            current += datetime.timedelta(minutes=1)
            
        # 休憩時間は通常の労働時間から引かれるため、ここでは純粋な滞在時間中の深夜枠を算出
        # 実際の運用では「休憩をどの時間帯に取ったか」が重要ですが、
        # まずはシンプルに「深夜時間帯の滞在割合」で概算します
        return round(total_night_seconds / 3600, 2)

    def get_overtime_hours(self):
        """法定外残業時間（8時間を超えた分）を計算する"""
        duration = float(self.get_duration()) # すでに実装済みの get_duration を利用
        overtime = duration - 8.0
        return round(max(0, overtime), 2)

class AuditLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    admin_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False) # 誰が
    action = db.Column(db.String(50), nullable=False)                         # 何を（編集/削除）
    target_user_name = db.Column(db.String(50), nullable=False)               # 誰のデータを
    description = db.Column(db.Text)                                          # 詳細（日付など）
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)               # いつ

    # 操作した管理者の名前を取得するためのリレーション
    admin = db.relationship('User', backref='logs')
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
        
        # 1. まずユーザー名で検索
        user = User.query.filter_by(username=username).first()
        
        # 2. ユーザーが存在し、かつハッシュ化されたパスワードが正しいかチェック
        if user and check_password_hash(user.password, password):
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
    # 備考を取得（空の場合は空文字にする）
    note = request.form.get('note', '')
    
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
            break_minutes=break_minutes,
            note=note
        )
        db.session.add(new_record)
        log = AuditLog(
            admin_id=session.get('user_id'),
            action='追加',
            target_user_name=User.query.get(user_id).username,
            description=f"{date_str} の勤怠データを新規作成"
        )
        db.session.add(log)
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
    # 備考を取得
    note = request.form.get('note', '')
    
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
        # 備考を更新
        record.note = note
        user = User.query.get(record.user_id)

        log = AuditLog(
            admin_id=session.get('user_id'),
            action='編集',
            target_user_name=user.username,
            description=f"{record.date} の勤怠データを修正"
        )
        db.session.add(log)
        db.session.commit()
        flash('勤怠データを更新しました')
    except ValueError:
        flash('日時の形式が正しくありません')
        
    # 修正が終わったら、その従業員の勤怠一覧ページに戻る
    return redirect(url_for('admin_user_attendance', user_id=record.user_id))

# app.py に追加
@app.route('/admin/attendance/delete/<int:attendance_id>', methods=['POST'])
def admin_delete_attendance(attendance_id):
    # 1. 管理者権限チェック
    if 'user_id' not in session or session.get('role') != 'admin':
        return redirect(url_for('login'))
    
    # 2. 削除対象のデータを取得
    record = Attendance.query.get_or_404(attendance_id)
    user_id = record.user_id
    user = User.query.get(record.user_id) # 名前を取得しておく
    log = AuditLog(
        admin_id=session.get('user_id'),
        action='削除',
        target_user_name=user.username,
        description=f"{record.date} の勤怠データを削除"
    )
    db.session.add(log)

    # 3. データベースから削除
    db.session.delete(record)
    db.session.commit()
    
    flash('勤怠データを削除しました')
    # 元の従業員の勤怠一覧ページに戻る
    return redirect(url_for('admin_user_attendance', user_id=user_id))

@app.route('/admin/update_rate/<int:user_id>', methods=['POST'])
def admin_update_rate(user_id):
    # 1. 管理者権限チェック
    if 'user_id' not in session or session.get('role') != 'admin':
        return redirect(url_for('login'))
    
    # 2. フォームから送られてきた新しい時給を取得
    new_rate = request.form.get('hourly_rate')
    
    if new_rate:
        # 3. 対象のユーザーを取得して時給を書き換え
        user = User.query.get_or_404(user_id)
        user.hourly_rate = int(new_rate)
        db.session.commit()
        flash(f'{user.username} さんの時給を {new_rate} 円に更新しました')
    
    # 4. 管理者パネルへ戻る
    return redirect(url_for('admin_dashboard'))

# app.py の管理者用ルート付近に追加
# app.py の admin_export_csv を修正
@app.route('/admin/export_csv')
def admin_export_csv():
    if 'user_id' not in session or session.get('role') != 'admin':
        return redirect(url_for('login'))

    # URLパラメータから月を取得 (例: "2026-03")
    target_month = request.args.get('month')

    query = Attendance.query

    # 月の指定がある場合はフィルタリング
    if target_month:
        try:
            year, month = map(int, target_month.split('-'))
            # 指定された月の1日と、翌月の1日を計算して範囲を絞る
            from datetime import date
            start_date = date(year, month, 1)
            if month == 12:
                end_date = date(year + 1, 1, 1)
            else:
                end_date = date(year, month + 1, 1)
            
            query = query.filter(Attendance.date >= start_date, Attendance.date < end_date)
        except ValueError:
            pass # 形式が正しくない場合は全件出す

    attendances = query.order_by(Attendance.date.desc()).all()

    si = io.StringIO()
    cw = csv.writer(si)
    cw.writerow(['ユーザー名', '日付', '出勤時刻', '退勤時刻', '休憩(分)', '勤務時間', '残業時間', '深夜時間'])

    for record in attendances:
        user = User.query.get(record.user_id)
        cw.writerow([
            user.username,
            record.date.strftime('%Y/%m/%d'),
            record.start_time.strftime('%H:%M') if record.start_time else '',
            record.end_time.strftime('%H:%M') if record.end_time else '',
            record.break_minutes,
            record.get_duration(),
            record.get_overtime_hours(), # 追加
            record.get_night_shift_hours() # 追加
        ])

    filename = f"attendance_{target_month if target_month else 'all'}.csv"
    output = make_response(si.getvalue().encode('utf-8-sig'))
    output.headers["Content-Disposition"] = f"attachment; filename={filename}"
    output.headers["Content-type"] = "text/csv"
    return output

@app.route('/admin/logs')
def admin_view_logs():
    if 'user_id' not in session or session.get('role') != 'admin':
        return redirect(url_for('login'))
    
    # 新しい順に100件取得
    logs = AuditLog.query.order_by(AuditLog.timestamp.desc()).limit(100).all()
    return render_template('admin_logs.html', logs=logs)

if __name__ == '__main__':
    # 実行時にデータベースとテーブルを自動作成する
    with app.app_context():
        db.create_all()
    app.run(debug=True, port=5001)