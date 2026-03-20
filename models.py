# models.py
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, date

db = SQLAlchemy()

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password = db.Column(db.String(100), nullable=False)
    role = db.Column(db.String(20), nullable=False)
    hourly_rate = db.Column(db.Integer, default=1000)

    def get_monthly_stats(self):
        """月間の給与・労働時間統計を取得（高度版）"""
        now = datetime.now()
        first_day = date(now.year, now.month, 1)
        
        monthly_records = Attendance.query.filter(
            Attendance.user_id == self.id,
            Attendance.date >= first_day
        ).all()
        
        total_hours = 0
        total_overtime_hours = 0
        total_night_hours = 0
        
        for record in monthly_records:
            if record.start_time and record.end_time:
                duration = float(record.get_duration())
                total_hours += duration
                total_night_hours += record.get_night_shift_hours()
                total_overtime_hours += record.get_overtime_hours()
        
        base_pay = total_hours * self.hourly_rate
        overtime_pay = total_overtime_hours * self.hourly_rate * 0.25
        night_pay = total_night_hours * self.hourly_rate * 0.25
        total_salary = base_pay + overtime_pay + night_pay
        
        return {
            'total_hours': f"{total_hours:.2f}",
            'overtime_hours': f"{total_overtime_hours:.2f}",
            'night_hours': f"{total_night_hours:.2f}",
            'total_salary': int(total_salary)
        }

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
            duration = self.end_time - self.start_time
            total_seconds = max(0, duration.total_seconds() - (self.break_minutes * 60))
            return f"{total_seconds / 3600:.2f}"
        return "0.00"

    def get_status(self):
        status_list = []
        if self.start_time and self.start_time.time() > datetime.strptime("09:00:00", "%H:%M:%S").time():
            status_list.append("遅刻")
        if self.end_time and self.end_time.time() < datetime.strptime("18:00:00", "%H:%M:%S").time():
            status_list.append("早退")
        return status_list

    def get_night_shift_hours(self):
        if not (self.start_time and self.end_time): return 0.0
        total_night_seconds = 0
        current = self.start_time
        import datetime as dt
        while current < self.end_time:
            if current.hour >= 22 or current.hour < 5:
                total_night_seconds += 60
            current += dt.timedelta(minutes=1)
        return round(total_night_seconds / 3600, 2)

    def get_overtime_hours(self):
        duration = float(self.get_duration())
        return round(max(0, duration - 8.0), 2)

class AuditLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    admin_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    action = db.Column(db.String(50), nullable=False)
    target_user_name = db.Column(db.String(50), nullable=False)
    description = db.Column(db.Text)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    admin = db.relationship('User', backref='logs')