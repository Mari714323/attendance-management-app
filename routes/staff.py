# routes/staff.py
from flask import Blueprint, render_template, redirect, url_for, session, request, flash
from models import db, Attendance
from datetime import datetime, timedelta

staff_bp = Blueprint('staff', __name__)

@staff_bp.route('/')
def index():
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))
    
    user_id = session['user_id']
    today = datetime.now().date()
    
    # 今日の打刻データ
    attendance = Attendance.query.filter_by(user_id=user_id, date=today).first()
    # 過去の全履歴
    history = Attendance.query.filter_by(user_id=user_id).order_by(Attendance.date.desc()).all()
    
    # --- グラフ用データ作成（直近7日間） ---
    labels = []
    graph_data = []
    for i in range(6, -1, -1):
        target_date = today - timedelta(days=i)
        record = Attendance.query.filter_by(user_id=user_id, date=target_date).first()
        
        labels.append(target_date.strftime('%m/%d'))
        if record:
            graph_data.append(float(record.get_duration()))
        else:
            graph_data.append(0.0)

    return render_template('index.html', 
                           username=session.get('username'), 
                           role=session.get('role'), 
                           attendance=attendance,
                           history=history,
                           graph_labels=labels,
                           graph_data=graph_data)

@staff_bp.route('/punch', methods=['POST'])
def punch():
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))
    
    action = request.form.get('action')
    user_id = session['user_id']
    now = datetime.now()
    today = now.date()

    attendance = Attendance.query.filter_by(user_id=user_id, date=today).first()

    if action == 'in':
        if not attendance:
            new_attendance = Attendance(user_id=user_id, date=today, start_time=now)
            db.session.add(new_attendance)
        else:
            flash('既に出勤済みです')
            
    elif action == 'out':
        if attendance and not attendance.end_time:
            attendance.end_time = now
            flash('退勤しました！お疲れ様でした！')
        elif not attendance:
            flash('出勤記録がありません')
        else:
            flash('既に退勤済みです')

    db.session.commit()
    return redirect(url_for('staff.index'))