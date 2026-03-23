# routes/admin.py
from flask import Blueprint, render_template, request, redirect, url_for, session, flash, make_response
from models import db, User, Attendance, AuditLog
from datetime import datetime
import csv
import io

# 'admin' という名前の Blueprint を定義。URLの接頭辞を /admin にします。
admin_bp = Blueprint('admin', __name__, url_prefix='/admin')

# 権限チェック用の共通関数
def check_admin():
    if 'user_id' not in session or session.get('role') != 'admin':
        return False
    return True

# routes/admin.py の dashboard 関数を修正
@admin_bp.route('/')
def dashboard():
    if not check_admin():
        return redirect(url_for('auth.login'))
    
    users = User.query.filter(User.role != 'admin').all()
    
    # --- 統計用データの作成 (全従業員の合計労働時間 - 直近7日間) ---
    from datetime import datetime, timedelta
    today = datetime.now().date()
    labels = []
    daily_totals = []
    
    for i in range(6, -1, -1):
        target_date = today - timedelta(days=i)
        labels.append(target_date.strftime('%m/%d'))
        
        # その日の全従業員の勤怠レコードを取得
        records = Attendance.query.filter_by(date=target_date).all()
        # 全員の勤務時間を合計
        total_day_hours = sum(float(r.get_duration()) for r in records)
        daily_totals.append(round(total_day_hours, 2))
        
    return render_template('admin.html', 
                           users=users, 
                           labels=labels, 
                           daily_totals=daily_totals)

@admin_bp.route('/attendance/<int:user_id>')
def user_attendance(user_id):
    if not check_admin(): return redirect(url_for('login'))
    user = User.query.get_or_404(user_id)
    attendances = Attendance.query.filter_by(user_id=user_id).order_by(Attendance.date.desc()).all()
    return render_template('admin_attendance.html', user=user, attendances=attendances)

@admin_bp.route('/attendance/<int:user_id>/add', methods=['POST'])
def add_attendance(user_id):
    if not check_admin(): return redirect(url_for('login'))
    date_str = request.form.get('date')
    start_str = request.form.get('start_time')
    end_str = request.form.get('end_time')
    break_minutes = int(request.form.get('break_minutes', 0))
    note = request.form.get('note', '')
    
    try:
        date_obj = datetime.strptime(date_str, '%Y-%m-%d').date()
        start_time = datetime.strptime(f"{date_str} {start_str}", '%Y-%m-%d %H:%M')
        end_time = datetime.strptime(f"{date_str} {end_str}", '%Y-%m-%d %H:%M') if end_str else None
        
        if end_time and end_time <= start_time:
            flash('エラー：退勤時間は出勤時間より後の時刻を入力してください')
            return redirect(url_for('admin.user_attendance', user_id=user_id))
        
        new_record = Attendance(user_id=user_id, date=date_obj, start_time=start_time, end_time=end_time, break_minutes=break_minutes, note=note)
        db.session.add(new_record)
        
        log = AuditLog(admin_id=session.get('user_id'), action='追加', target_user_name=User.query.get(user_id).username, description=f"{date_str} の勤怠データを新規作成")
        db.session.add(log)
        db.session.commit()
        flash('勤怠データを手動で追加しました')
    except ValueError:
        flash('入力された日時の形式が正しくありません')
    return redirect(url_for('admin.user_attendance', user_id=user_id))

@admin_bp.route('/attendance/edit/<int:attendance_id>')
def edit_attendance(attendance_id):
    if not check_admin(): return redirect(url_for('login'))
    record = Attendance.query.get_or_404(attendance_id)
    user = User.query.get(record.user_id)
    return render_template('admin_edit.html', record=record, user=user)

@admin_bp.route('/attendance/update/<int:attendance_id>', methods=['POST'])
def update_attendance(attendance_id):
    if not check_admin(): return redirect(url_for('login'))
    record = Attendance.query.get_or_404(attendance_id)
    date_str = request.form.get('date')
    start_str = request.form.get('start_time')
    end_str = request.form.get('end_time')
    break_minutes = int(request.form.get('break_minutes', 0))
    note = request.form.get('note', '')

    try:
        new_date = datetime.strptime(date_str, '%Y-%m-%d').date()
        new_start = datetime.strptime(f"{date_str} {start_str}", '%Y-%m-%d %H:%M')
        new_end = datetime.strptime(f"{date_str} {end_str}", '%Y-%m-%d %H:%M') if end_str else None

        if new_end and new_end <= new_start:
            flash('エラー：退勤時間は出勤時間より後の時刻を入力してください')
            return redirect(url_for('admin.edit_attendance', attendance_id=attendance_id))

        record.date, record.start_time, record.end_time = new_date, new_start, new_end
        record.break_minutes, record.note = break_minutes, note

        log = AuditLog(admin_id=session.get('user_id'), action='編集', target_user_name=User.query.get(record.user_id).username, description=f"{record.date} の勤怠データを修正")
        db.session.add(log)
        db.session.commit()
        flash('勤怠データを更新しました')
    except ValueError:
        flash('日時の形式が正しくありません')
    return redirect(url_for('admin.user_attendance', user_id=record.user_id))

@admin_bp.route('/attendance/delete/<int:attendance_id>', methods=['POST'])
def delete_attendance(attendance_id):
    if not check_admin(): return redirect(url_for('login'))
    record = Attendance.query.get_or_404(attendance_id)
    user_id = record.user_id
    log = AuditLog(admin_id=session.get('user_id'), action='削除', target_user_name=User.query.get(user_id).username, description=f"{record.date} の勤怠データを削除")
    db.session.add(log)
    db.session.delete(record)
    db.session.commit()
    flash('勤怠データを削除しました')
    return redirect(url_for('admin.user_attendance', user_id=user_id))

@admin_bp.route('/update_rate/<int:user_id>', methods=['POST'])
def update_rate(user_id):
    if not check_admin(): return redirect(url_for('login'))
    new_rate = request.form.get('hourly_rate')
    if new_rate:
        user = User.query.get_or_404(user_id)
        user.hourly_rate = int(new_rate)
        db.session.commit()
        flash(f'{user.username} さんの時給を {new_rate} 円に更新しました')
    return redirect(url_for('admin.dashboard'))

@admin_bp.route('/export_csv')
def export_csv():
    if not check_admin(): return redirect(url_for('login'))
    target_month = request.args.get('month')
    query = Attendance.query
    if target_month:
        try:
            year, month = map(int, target_month.split('-'))
            from datetime import date
            start_date = date(year, month, 1)
            end_date = date(year + 1, 1, 1) if month == 12 else date(year, month + 1, 1)
            query = query.filter(Attendance.date >= start_date, Attendance.date < end_date)
        except ValueError: pass
    
    attendances = query.order_by(Attendance.date.desc()).all()
    si = io.StringIO()
    cw = csv.writer(si)
    cw.writerow(['ユーザー名', '日付', '出勤時刻', '退勤時刻', '休憩(分)', '勤務時間', '残業時間', '深夜時間'])
    for record in attendances:
        user = User.query.get(record.user_id)
        cw.writerow([user.username, record.date.strftime('%Y/%m/%d'), record.start_time.strftime('%H:%M') if record.start_time else '', record.end_time.strftime('%H:%M') if record.end_time else '', record.break_minutes, record.get_duration(), record.get_overtime_hours(), record.get_night_shift_hours()])
    
    filename = f"attendance_{target_month if target_month else 'all'}.csv"
    output = make_response(si.getvalue().encode('utf-8-sig'))
    output.headers["Content-Disposition"], output.headers["Content-type"] = f"attachment; filename={filename}", "text/csv"
    return output

@admin_bp.route('/logs')
def view_logs():
    if not check_admin(): return redirect(url_for('login'))
    logs = AuditLog.query.order_by(AuditLog.timestamp.desc()).limit(100).all()
    return render_template('admin_logs.html', logs=logs)