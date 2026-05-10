from flask import Flask, render_template, request, redirect, url_for, session, flash, send_from_directory, jsonify, Response
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import joinedload
from flask_socketio import SocketIO, emit, join_room, leave_room
from flask_migrate import Migrate
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
import os
import uuid
import datetime
import csv
from io import StringIO
import smtplib
from email.mime.text import MIMEText
from itsdangerous import URLSafeTimedSerializer
from model import predict_department
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer

# Initialize sentiment analyzer
analyzer = SentimentIntensityAnalyzer()

def get_sentiment(text):
    scores = analyzer.polarity_scores(text)
    compound = scores['compound']
    if compound <= -0.5:
        return 'Angry'
    elif compound <= -0.1:
        return 'Frustrated'
    elif compound >= 0.5:
        return 'Positive'
    else:
        return 'Neutral'

app = Flask(__name__)
app.config['SECRET_KEY'] = 'supersecretkey123'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///database.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = os.path.join(app.root_path, 'static', 'uploads', 'complaints')
app.config['MAX_CONTENT_LENGTH'] = 10 * 1024 * 1024 # 10MB limit
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'pdf', 'docx'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def get_reset_token(user_id, expires_sec=1800):
    s = URLSafeTimedSerializer(app.config['SECRET_KEY'])
    return s.dumps({'user_id': user_id})

def verify_reset_token(token, expires_sec=1800):
    s = URLSafeTimedSerializer(app.config['SECRET_KEY'])
    try:
        data = s.loads(token, max_age=expires_sec)
    except:
        return None
    return User.query.get(data['user_id'])

db = SQLAlchemy(app)
migrate = Migrate(app, db, render_as_batch=True)
socketio = SocketIO(app)

# Models
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(100), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    role = db.Column(db.String(20), default='User') # User, Admin, Department
    dept_id = db.Column(db.Integer, db.ForeignKey('department.id'), nullable=True)

class Department(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    users = db.relationship('User', backref='department', lazy=True)
    complaints = db.relationship('Complaint', backref='department', lazy=True)

class Complaint(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    user = db.relationship('User', backref=db.backref('complaints', lazy=True))
    text = db.Column(db.Text, nullable=False)
    department_id = db.Column(db.Integer, db.ForeignKey('department.id'), nullable=False, index=True)
    status = db.Column(db.String(50), default='Pending', index=True) # Pending, In Progress, Resolved
    remarks = db.Column(db.Text, nullable=True)
    date = db.Column(db.DateTime, default=datetime.datetime.utcnow, index=True)
    priority = db.Column(db.String(20), default='Normal', index=True) # Normal, High
    confidence_score = db.Column(db.Float, nullable=True)
    sentiment = db.Column(db.String(20), nullable=True, index=True)
    sla_deadline = db.Column(db.DateTime, nullable=True, index=True)
    sla_status = db.Column(db.String(50), default='Within SLA')
    escalation_level = db.Column(db.Integer, default=0)
    resolved_at = db.Column(db.DateTime, nullable=True)
    attachments = db.relationship('Attachment', backref='complaint', lazy=True)

class Attachment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    filename = db.Column(db.String(255), nullable=False)
    original_filename = db.Column(db.String(255), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    complaint_id = db.Column(db.Integer, db.ForeignKey('complaint.id'), nullable=False)
    upload_timestamp = db.Column(db.DateTime, default=datetime.datetime.utcnow)

class Message(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    complaint_id = db.Column(db.Integer, db.ForeignKey('complaint.id'), nullable=False)
    sender_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    text = db.Column(db.Text, nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.datetime.utcnow)
    is_read = db.Column(db.Boolean, default=False)
    
    sender = db.relationship('User', backref='messages')

class Notification(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True) # Null = Dept wide
    department_id = db.Column(db.Integer, db.ForeignKey('department.id'), nullable=True)
    message = db.Column(db.String(255), nullable=False)
    category = db.Column(db.String(50), default='INFO') # INFO, WARNING, SUCCESS, URGENT
    timestamp = db.Column(db.DateTime, default=datetime.datetime.utcnow)
    is_read = db.Column(db.Boolean, default=False)
    link_url = db.Column(db.String(255), nullable=True)

# Helper to check priority
def detect_priority(text):
    urgent_words = ['urgent', 'emergency', 'immediate', 'asap', 'broken', 'leaking', 'blue screen', 'stuck']
    if any(word in text.lower() for word in urgent_words):
        return 'High'
    return 'Normal'

def send_notification_email(to_email, department_name, complaint_text, priority):
    print(f"\n--- [SIMULATED EMAIL] ---")
    print(f"To: {to_email}")
    print(f"Subject: New {priority} Priority Complaint for {department_name} Department")
    print(f"Body:\nA new complaint has been routed to your department.\n\nDetails:\n{complaint_text}")
    print(f"-------------------------\n")
    # For actual email sending, configure SMTP here:
    # msg = MIMEText(f"A new complaint has been routed to your department.\n\nDetails:\n{complaint_text}")
    # msg['Subject'] = f"New {priority} Priority Complaint"
    # msg['From'] = "noreply@helpdesk.com"
    # msg['To'] = to_email
    # try:
    #     server = smtplib.SMTP('smtp.example.com', 587)
    #     server.starttls()
    #     server.login("your_email", "your_password")
    #     server.send_message(msg)
    #     server.quit()
    # except Exception as e:
    #     print(f"Email error: {e}")

# Routes

@app.route('/')
def index():
    if 'user_id' in session:
        if session['role'] == 'Admin':
            return redirect(url_for('admin_dashboard'))
        elif session['role'] == 'Department':
            return redirect(url_for('dept_dashboard'))
        else:
            return redirect(url_for('submit_complaint'))
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        selected_role = request.form.get('role')
        
        user = User.query.filter_by(email=email).first()
        if user and check_password_hash(user.password, password):
            # Validate selected role
            role_valid = False
            if selected_role == 'User' and user.role == 'User':
                role_valid = True
            elif selected_role == 'Admin' and user.role == 'Admin':
                role_valid = True
            elif user.role == 'Department':
                if user.department and user.department.name == selected_role:
                    role_valid = True
            
            if not role_valid:
                flash(f'Invalid role selected for this account.', 'danger')
                return render_template('login.html')

            session['user_id'] = user.id
            session['role'] = user.role
            session['user_name'] = user.name
            
            flash(f'Welcome back, {user.name}!', 'success')
            if user.role == 'Admin':
                return redirect(url_for('admin_dashboard'))
            elif user.role == 'Department':
                return redirect(url_for('dept_dashboard'))
            else:
                return redirect(url_for('submit_complaint'))
        else:
            flash('Invalid credentials. Please try again.', 'danger')
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        name = request.form['name']
        email = request.form['email']
        password = generate_password_hash(request.form['password'])
        
        if User.query.filter_by(email=email).first():
            flash('Email already registered!', 'danger')
            return redirect(url_for('register'))
            
        new_user = User(name=name, email=email, password=password)
        db.session.add(new_user)
        db.session.commit()
        flash('Registration successful! Please login.', 'success')
        return redirect(url_for('login'))
    return render_template('register.html')

@app.route('/logout')
def logout():
    session.clear()
    flash('You have been logged out.', 'info')
    return redirect(url_for('login'))

@app.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    if request.method == 'POST':
        name = request.form.get('name')
        user = User.query.filter_by(name=name).first()
        if user:
            token = get_reset_token(user.id)
            flash('User verified. Please reset your password below.', 'info')
            return redirect(url_for('reset_password', token=token))
        else:
            flash(f'User with name "{name}" not found.', 'danger')
    return render_template('forgot_password.html')

@app.route('/reset-password/<token>', methods=['GET', 'POST'])
def reset_password(token):
    user = verify_reset_token(token)
    if not user:
        flash('That is an invalid or expired token.', 'warning')
        return redirect(url_for('forgot_password'))
        
    if request.method == 'POST':
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')
        
        if password != confirm_password:
            flash('Passwords do not match.', 'danger')
        else:
            user.password = generate_password_hash(password)
            db.session.commit()
            flash('Your password has been updated! You can now log in.', 'success')
            return redirect(url_for('login'))
            
    return render_template('reset_password.html', token=token, user=user)

# USER ROUTES
@app.route('/user/submit', methods=['GET', 'POST'])
def submit_complaint():
    if 'user_id' not in session or session['role'] != 'User':
        return redirect(url_for('login'))
        
    if request.method == 'POST':
        text = request.form['text']
        
        predicted_dept_name, confidence_score = predict_department(text)
        dept = Department.query.filter_by(name=predicted_dept_name).first()
        
        if not dept:
            dept = Department.query.first()

        priority = detect_priority(text)
        sentiment_val = get_sentiment(text)
        
        # Auto-boost priority for negative sentiment
        if sentiment_val in ['Angry', 'Frustrated']:
            priority = 'High'
        
        # SLA Logic
        sla_hours = 48
        if dept.name == 'IT':
            sla_hours = 24
        elif dept.name == 'Finance':
            sla_hours = 72
            
        if priority == 'High':
            sla_hours = sla_hours // 2
            
        sla_deadline = datetime.datetime.utcnow() + datetime.timedelta(hours=sla_hours)
        
        new_complaint = Complaint(
            user_id=session['user_id'],
            text=text,
            department_id=dept.id,
            status='Pending',
            priority=priority,
            confidence_score=confidence_score,
            sentiment=sentiment_val,
            sla_deadline=sla_deadline,
            sla_status='Within SLA'
        )
        db.session.add(new_complaint)
        db.session.commit()
        
        # Handle File Upload
        if 'attachment' in request.files:
            file = request.files['attachment']
            if file and file.filename != '' and allowed_file(file.filename):
                original_filename = secure_filename(file.filename)
                ext = original_filename.rsplit('.', 1)[1].lower()
                new_filename = f"{uuid.uuid4().hex}.{ext}"
                file_path = os.path.join(app.config['UPLOAD_FOLDER'], new_filename)
                file.save(file_path)
                
                new_attachment = Attachment(
                    filename=new_filename,
                    original_filename=original_filename,
                    user_id=session['user_id'],
                    complaint_id=new_complaint.id
                )
                db.session.add(new_attachment)
                db.session.commit()
        
        # Trigger Notification
        trigger_notification(None, dept.id, f"New Complaint #{new_complaint.id} created: {priority} Priority", category='URGENT' if priority == 'High' else 'INFO', link_url=f"/department/dashboard")
        
        # Send email notification
        dept_users = User.query.filter_by(dept_id=dept.id).all()
        for d_user in dept_users:
            send_notification_email(d_user.email, dept.name, text, priority)
            
        flash(f'Complaint submitted! Routed to {dept.name} ({confidence_score}% confidence). Sentiment: {sentiment_val}.', 'success')
        return redirect(url_for('view_status'))
        
    return render_template('submit.html')

@app.route('/user/status')
def view_status():
    if 'user_id' not in session or session['role'] != 'User':
        return redirect(url_for('login'))
    
    complaints = Complaint.query.options(joinedload(Complaint.department)).filter_by(user_id=session['user_id']).order_by(Complaint.date.desc()).all()
    return render_template('status.html', complaints=complaints, now=datetime.datetime.utcnow())

@app.route('/user/feedback/<int:complaint_id>', methods=['POST'])
def add_feedback(complaint_id):
    if 'user_id' not in session or session['role'] != 'User':
        return redirect(url_for('login'))
    
    complaint = Complaint.query.get_or_404(complaint_id)
    if complaint.user_id == session['user_id'] and complaint.status == 'Resolved':
        feedback = request.form.get('feedback', '')
        if feedback:
            complaint.remarks = (complaint.remarks or '') + f"\n[User Feedback]: {feedback}"
            db.session.commit()
            flash('Feedback submitted! Thank you.', 'success')
    return redirect(url_for('view_status'))
    
# ADMIN ROUTES
@app.route('/admin/dashboard')
def admin_dashboard():
    if 'user_id' not in session or session['role'] != 'Admin':
        return redirect(url_for('login'))
        
    complaints = Complaint.query.options(joinedload(Complaint.department), joinedload(Complaint.user)).order_by(Complaint.date.desc()).all()
    departments = Department.query.all()
    users = User.query.all()
    
    return render_template('dashboard_admin.html', complaints=complaints, departments=departments, users=users, now=datetime.datetime.utcnow())

@app.route('/admin/analytics')
def analytics_dashboard():
    if 'user_id' not in session or session['role'] != 'Admin':
        return redirect(url_for('login'))
    return render_template('analytics.html', now=datetime.datetime.utcnow())

@app.route('/api/analytics/data')
def analytics_data():
    if 'user_id' not in session or session['role'] != 'Admin':
        return jsonify({'error': 'Unauthorized'}), 403
        
    complaints = Complaint.query.all()
    
    total = len(complaints)
    pending = sum(1 for c in complaints if c.status == 'Pending')
    resolved = sum(1 for c in complaints if c.status == 'Resolved')
    overdue = sum(1 for c in complaints if c.sla_deadline and c.sla_deadline < datetime.datetime.utcnow() and c.status != 'Resolved')
    
    sentiments = {'Angry': 0, 'Frustrated': 0, 'Positive': 0, 'Neutral': 0}
    for c in complaints:
        if c.sentiment in sentiments:
            sentiments[c.sentiment] += 1
            
    depts = Department.query.all()
    dept_counts = {d.name: sum(1 for c in complaints if c.department_id == d.id) for d in depts}
    
    return jsonify({
        'kpis': {
            'total': total,
            'pending': pending,
            'resolved': resolved,
            'overdue': overdue
        },
        'sentiments': sentiments,
        'departments': dept_counts
    })

@app.route('/admin/export/csv')
def export_csv():
    if 'user_id' not in session or session['role'] != 'Admin':
        return redirect(url_for('login'))
        
    complaints = Complaint.query.options(joinedload(Complaint.department), joinedload(Complaint.user)).order_by(Complaint.date.desc()).all()
    
    si = StringIO()
    cw = csv.writer(si)
    cw.writerow(['ID', 'Date', 'User', 'Department', 'Description', 'Priority', 'Status', 'Sentiment', 'SLA Deadline'])
    
    for c in complaints:
        cw.writerow([
            c.id, 
            c.date.strftime('%Y-%m-%d %H:%M:%S'), 
            c.user.name, 
            c.department.name, 
            c.text.replace('\n', ' '), 
            c.priority, 
            c.status, 
            c.sentiment, 
            c.sla_deadline.strftime('%Y-%m-%d %H:%M:%S') if c.sla_deadline else 'N/A'
        ])
        
    output = si.getvalue()
    return Response(output, mimetype='text/csv', headers={"Content-Disposition": "attachment;filename=smartroute_export.csv"})

@app.route('/admin/department/add', methods=['POST'])
def add_department():
    if 'user_id' not in session or session['role'] != 'Admin':
        return redirect(url_for('login'))
    name = request.form['name']
    if not Department.query.filter_by(name=name).first():
        db.session.add(Department(name=name))
        db.session.commit()
        flash('Department added.', 'success')
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/department/delete/<int:dept_id>')
def delete_department(dept_id):
    if 'user_id' not in session or session['role'] != 'Admin':
        return redirect(url_for('login'))
    dept = Department.query.get_or_404(dept_id)
    db.session.delete(dept)
    db.session.commit()
    flash('Department deleted.', 'success')
    return redirect(url_for('admin_dashboard'))

# DEPARTMENT ROUTES
@app.route('/department/dashboard')
def dept_dashboard():
    if 'user_id' not in session or session['role'] != 'Department':
        return redirect(url_for('login'))
    
    user = User.query.get(session['user_id'])
    complaints = Complaint.query.options(joinedload(Complaint.user)).filter_by(department_id=user.dept_id).order_by(Complaint.priority.desc(), Complaint.sla_deadline.asc()).all()
    
    return render_template('dashboard_dept.html', complaints=complaints, dept_name=user.department.name if user.department else "Unknown", now=datetime.datetime.utcnow())

@app.route('/department/update/<int:complaint_id>', methods=['POST'])
def update_status(complaint_id):
    if 'user_id' not in session or session['role'] != 'Department':
        return redirect(url_for('login'))
        
    complaint = Complaint.query.get_or_404(complaint_id)
    user = User.query.get(session['user_id'])
    
    if complaint.department_id == user.dept_id:
        status = request.form['status']
        remarks = request.form['remarks']
        
        complaint.status = status
        if remarks:
            timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
            old_remarks = complaint.remarks + "\n" if complaint.remarks else ""
            complaint.remarks = f"{old_remarks}[{timestamp}] {remarks}"
            
        db.session.commit()
        
        # Trigger Notification
        trigger_notification(complaint.user_id, None, f"Status of Complaint #{complaint.id} updated to {status}", category='SUCCESS' if status == 'Resolved' else 'INFO', link_url=f"/status")
        
        flash('Complaint updated successfully.', 'success')
        
    return redirect(url_for('dept_dashboard'))

@app.route('/download/<int:attachment_id>')
def download_attachment(attachment_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
        
    attachment = Attachment.query.get_or_404(attachment_id)
    complaint = Complaint.query.get(attachment.complaint_id)
    
    user = User.query.get(session['user_id'])
    if user.role == 'Admin' or user.id == attachment.user_id or (user.role == 'Department' and user.dept_id == complaint.department_id):
        return send_from_directory(app.config['UPLOAD_FOLDER'], attachment.filename, as_attachment=True, download_name=attachment.original_filename)
    else:
        flash('Unauthorized access.', 'danger')
        return redirect(url_for('login'))

def trigger_notification(user_id, department_id, message, category='INFO', link_url=None):
    new_notif = Notification(user_id=user_id, department_id=department_id, message=message, category=category, link_url=link_url)
    db.session.add(new_notif)
    db.session.commit()
    
    room = None
    if user_id:
        room = f"user_{user_id}"
    elif department_id:
        room = f"dept_{department_id}"
        
    if room:
        socketio.emit('new_notification', {
            'message': message,
            'category': category,
            'link_url': link_url,
            'timestamp': new_notif.timestamp.strftime("%Y-%m-%d %H:%M:%S")
        }, room=room)

@socketio.on('connect')
def handle_connect():
    if 'user_id' not in session:
        return False
    user_id = session['user_id']
    join_room(f"user_{user_id}")
    
    user = User.query.get(user_id)
    if user.role == 'Department' and user.dept_id:
        join_room(f"dept_{user.dept_id}")

@socketio.on('join_chat')
def handle_join_chat(data):
    if 'user_id' not in session:
        return False
    complaint_id = data.get('complaint_id')
    user = User.query.get(session['user_id'])
    complaint = Complaint.query.get(complaint_id)
    
    if user.role == 'Admin' or complaint.user_id == user.id or (user.role == 'Department' and user.dept_id == complaint.department_id):
        join_room(f"complaint_{complaint_id}")

@socketio.on('send_message')
def handle_send_message(data):
    if 'user_id' not in session:
        return False
    complaint_id = data.get('complaint_id')
    text = data.get('text')
    user = User.query.get(session['user_id'])
    complaint = Complaint.query.get(complaint_id)
    
    if user.role == 'Admin' or complaint.user_id == user.id or (user.role == 'Department' and user.dept_id == complaint.department_id):
        msg = Message(complaint_id=complaint_id, sender_id=user.id, text=text)
        db.session.add(msg)
        db.session.commit()
        
        emit('new_message', {
            'text': text,
            'sender_id': user.id,
            'sender_name': user.name,
            'sender_role': user.role,
            'timestamp': msg.timestamp.strftime("%H:%M")
        }, room=f"complaint_{complaint_id}")
        
        if user.role == 'User':
            trigger_notification(None, complaint.department_id, f"New message from {user.name} on Ticket #{complaint_id}", link_url=f"/chat/{complaint_id}")
        else:
            trigger_notification(complaint.user_id, None, f"New message from Staff on Ticket #{complaint_id}", link_url=f"/chat/{complaint_id}")

@app.route('/chat/<int:complaint_id>')
def chat(complaint_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
        
    user = User.query.get(session['user_id'])
    complaint = Complaint.query.get_or_404(complaint_id)
    
    if user.role != 'Admin' and complaint.user_id != user.id and (user.role != 'Department' or user.dept_id != complaint.department_id):
        flash('Unauthorized access.', 'danger')
        return redirect(url_for('login'))
        
    messages = Message.query.filter_by(complaint_id=complaint_id).order_by(Message.timestamp.asc()).all()
    return render_template('chat.html', complaint=complaint, messages=messages, current_user=user)

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        
        # Seed initial departments
        default_depts = ['IT', 'Maintenance', 'HR', 'Finance']
        for dept in default_depts:
            if not Department.query.filter_by(name=dept).first():
                db.session.add(Department(name=dept))
        
        # Seed Admin user
        if not User.query.filter_by(email='vsraut2004@gmail.com').first():
            db.session.add(User(
                name='Vaishnavi Raut',
                email='vsraut2004@gmail.com',
                password=generate_password_hash('vaishnavi123'),
                role='Admin'
            ))
            
        # Seed Department Users
        for dept in default_depts:
            dept_obj = Department.query.filter_by(name=dept).first()
            if dept_obj and not User.query.filter_by(email=f'{dept.lower()}@helpdesk.com').first():
                db.session.add(User(
                    name=f'{dept} User',
                    email=f'{dept.lower()}@helpdesk.com',
                    password=generate_password_hash(f'{dept.lower()}123'),
                    role='Department',
                    dept_id=dept_obj.id
                ))
                
        db.session.commit()
    socketio.run(app, debug=True, host='0.0.0.0', port=5000)
