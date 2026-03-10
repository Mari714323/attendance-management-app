from app import app, db, User

with app.app_context():
    # 既存のデータを一度削除して作り直す（初期化用）
    db.drop_all()
    db.create_all()

    # 管理者ユーザー
    admin = User(username='admin', password='password123', role='admin', hourly_rate=0)
    # 従業員ユーザー
    staff = User(username='staff01', password='password123', role='staff', hourly_rate=1200)

    db.session.add(admin)
    db.session.add(staff)
    db.session.commit()

    print("テストユーザー（admin / staff01）を作成しました！")