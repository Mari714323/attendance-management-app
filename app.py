# app.py
from flask import Flask
from models import db
from routes.auth import auth_bp
from routes.staff import staff_bp
from routes.admin import admin_bp

app = Flask(__name__)

# データベースの設定
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///attendance.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.secret_key = 'secretkey1234567'

# データベースの初期化
db.init_app(app)

# Blueprint の登録
app.register_blueprint(auth_bp)   # ログイン関連
app.register_blueprint(staff_bp)  # 従業員画面・打刻
app.register_blueprint(admin_bp)  # 管理者機能

if __name__ == '__main__':
    with app.app_context():
        # 必要に応じてテーブル作成
        db.create_all()
    app.run(debug=True, port=5001)