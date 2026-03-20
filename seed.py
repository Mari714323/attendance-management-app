from app import app
from models import db, User
from werkzeug.security import generate_password_hash # 追加

with app.app_context():
    # 既存のデータを一度削除して作り直す（初期化用）
    db.drop_all()
    db.create_all()

    # 管理者ユーザー（パスワードをハッシュ化して保存）
    admin = User(
        username='admin', 
        password=generate_password_hash('password123'), 
        role='admin', 
        hourly_rate=0
    )
    # 従業員ユーザー（パスワードをハッシュ化して保存）
    staff = User(
        username='staff01', 
        password=generate_password_hash('password123'), 
        role='staff', 
        hourly_rate=1200
    )

    db.session.add(admin)
    db.session.add(staff)
    db.session.commit()

    print("ハッシュ化済みパスワードでテストユーザーを作成しました！")