# routes/auth.py
from flask import Blueprint, render_template, request, redirect, url_for, session, flash
from models import User
from werkzeug.security import check_password_hash
from werkzeug.security import generate_password_hash

auth_bp = Blueprint('auth', __name__)

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        user = User.query.filter_by(username=username).first()
        
        if user and check_password_hash(user.password, password):
            session['user_id'] = user.id
            session['username'] = user.username
            session['role'] = user.role
            # ログイン後は従業員トップ（staff.index）へ
            return redirect(url_for('staff.index'))
        else:
            flash('ユーザー名またはパスワードが正しくありません')
            
    return render_template('login.html')

@auth_bp.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('auth.login'))

@auth_bp.route('/change-password', methods=['GET', 'POST'])
def change_password():
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))
    
    if request.method == 'POST':
        old_password = request.form.get('old_password')
        new_password = request.form.get('new_password')
        confirm_password = request.form.get('confirm_password')
        
        from models import db, User # 関数内でインポート
        user = User.query.get(session['user_id'])
        
        # 1. 現在のパスワードが正しいかチェック
        if not check_password_hash(user.password, old_password):
            flash('現在のパスワードが正しくありません')
            return redirect(url_for('auth.change_password'))
            
        # 2. 新しいパスワードと確認用が一致するかチェック
        if new_password != confirm_password:
            flash('新しいパスワードが一致しません')
            return redirect(url_for('auth.change_password'))
            
        # 3. パスワードを更新（ハッシュ化して保存）
        user.password = generate_password_hash(new_password)
        db.session.commit()
        
        flash('パスワードを更新しました')
        return redirect(url_for('staff.index'))
        
    return render_template('change_password.html')