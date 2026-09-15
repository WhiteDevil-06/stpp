from flask import Flask, render_template, request, jsonify, redirect, url_for, session, flash, send_from_directory, Response
import os
import pandas as pd
from werkzeug.utils import secure_filename
from forms import TaskForm, OverrideForm, EditProfileForm, ChangePasswordForm
from database import get_db_connection
from functools import wraps
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, date
from prediction import predict_priority, predict_priority_batch
app = Flask(__name__)
# Secret key should be loaded from env in production, but for this internship project a simple string is fine
app.config['SECRET_KEY'] = 'dev-internship-secret-key'
app.config['DATABASE_PATH'] = 'task_priority.db'
app.config['UPLOAD_FOLDER'] = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'uploads')
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please log in to access this page.', 'error')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

@app.context_processor
def inject_user():
    if 'user_id' in session:
        conn = get_db_connection(app.config['DATABASE_PATH'])
        cursor = conn.cursor()
        cursor.execute("SELECT name, email FROM Users WHERE user_id = ?", (session['user_id'],))
        user = cursor.fetchone()
        conn.close()
        return dict(current_user=user)
    return dict(current_user=None)

# --- Auth Routes ---
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        name = request.form.get('name')
        email = request.form.get('email')
        password = request.form.get('password')
        
        conn = get_db_connection(app.config['DATABASE_PATH'])
        cursor = conn.cursor()
        
        cursor.execute("SELECT user_id FROM Users WHERE email = ?", (email,))
        if cursor.fetchone():
            flash('Email already registered.', 'error')
            conn.close()
            return redirect(url_for('register'))
            
        hashed_password = generate_password_hash(password)
        cursor.execute("INSERT INTO Users (name, email, password) VALUES (?, ?, ?)", (name, email, hashed_password))
        user_id = cursor.lastrowid
        conn.commit()
        conn.close()
        
        session['user_id'] = user_id
        flash('Registration successful!', 'success')
        return redirect(url_for('dashboard'))
        
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        
        conn = get_db_connection(app.config['DATABASE_PATH'])
        cursor = conn.cursor()
        cursor.execute("SELECT user_id, password FROM Users WHERE email = ?", (email,))
        user = cursor.fetchone()
        conn.close()
        
        if user and check_password_hash(user['password'], password):
            session['user_id'] = user['user_id']
            flash('Logged in successfully.', 'success')
            return redirect(url_for('dashboard'))
        else:
            flash('Invalid email or password.', 'error')
            
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.pop('user_id', None)
    flash('You have been logged out.', 'success')
    return redirect(url_for('login'))

# --- Dashboard & Task Routes ---
@app.route('/profile', methods=['GET'])
@login_required
def profile():
    conn = get_db_connection(app.config['DATABASE_PATH'])
    cursor = conn.cursor()
    user_id = session['user_id']
    
    cursor.execute("SELECT name, email FROM Users WHERE user_id = ?", (user_id,))
    user = cursor.fetchone()
    
    cursor.execute("SELECT COUNT(*) as total FROM Tasks WHERE user_id = ?", (user_id,))
    total_tasks = cursor.fetchone()['total']
    
    cursor.execute("""
        SELECT COUNT(*) as critical FROM Tasks t 
        JOIN Predictions p ON t.task_id = p.task_id 
        WHERE t.user_id = ? AND p.priority_label = 'Critical'
    """, (user_id,))
    critical_tasks = cursor.fetchone()['critical']
    
    conn.close()
    
    edit_form = EditProfileForm(name=user['name'], email=user['email'])
    password_form = ChangePasswordForm()
    
    import random
    import string
    delete_verification_code = ''.join(random.choices(string.ascii_uppercase, k=6))
    
    return render_template('profile.html', user=user, total_tasks=total_tasks, critical_tasks=critical_tasks, edit_form=edit_form, password_form=password_form, delete_verification_code=delete_verification_code)

@app.route('/profile/edit', methods=['POST'])
@login_required
def edit_profile():
    form = EditProfileForm()
    if form.validate_on_submit():
        conn = get_db_connection(app.config['DATABASE_PATH'])
        cursor = conn.cursor()
        
        # Check if email exists for other users
        cursor.execute("SELECT user_id FROM Users WHERE email = ? AND user_id != ?", (form.email.data, session['user_id']))
        if cursor.fetchone():
            flash('Email already in use by another account.', 'error')
        else:
            cursor.execute("UPDATE Users SET name = ?, email = ? WHERE user_id = ?", (form.name.data, form.email.data, session['user_id']))
            conn.commit()
            flash('Profile updated successfully!', 'success')
            
        conn.close()
    else:
        flash('Invalid form data.', 'error')
    return redirect(url_for('profile'))

@app.route('/profile/password', methods=['POST'])
@login_required
def change_password():
    form = ChangePasswordForm()
    if form.validate_on_submit():
        conn = get_db_connection(app.config['DATABASE_PATH'])
        cursor = conn.cursor()
        cursor.execute("SELECT password FROM Users WHERE user_id = ?", (session['user_id'],))
        user = cursor.fetchone()
        
        if not check_password_hash(user['password'], form.current_password.data):
            flash('Current password is incorrect.', 'error')
        else:
            hashed_password = generate_password_hash(form.new_password.data)
            cursor.execute("UPDATE Users SET password = ? WHERE user_id = ?", (hashed_password, session['user_id']))
            conn.commit()
            flash('Password changed successfully!', 'success')
            
        conn.close()
    else:
        for field, errors in form.errors.items():
            for error in errors:
                flash(f"{getattr(form, field).label.text}: {error}", 'error')
    return redirect(url_for('profile'))

@app.route('/')
@login_required
def dashboard():
    conn = get_db_connection(app.config['DATABASE_PATH'])
    cursor = conn.cursor()
    user_id = session['user_id']
    
    # Get total tasks
    cursor.execute("SELECT COUNT(*) as count FROM Tasks WHERE user_id = ?", (user_id,))
    total_tasks = cursor.fetchone()['count']
    
    # Get priority breakdown
    cursor.execute("SELECT priority_label, COUNT(*) as count FROM Predictions p JOIN Tasks t ON p.task_id = t.task_id WHERE t.user_id = ? GROUP BY priority_label", (user_id,))
    priority_counts = {row['priority_label']: row['count'] for row in cursor.fetchall()}
    
    # Get recent tasks
    cursor.execute("""
        SELECT t.*, p.priority_label as priority 
        FROM Tasks t 
        LEFT JOIN Predictions p ON t.task_id = p.task_id 
        WHERE t.user_id = ? 
        ORDER BY t.created_at DESC LIMIT 5
    """, (user_id,))
    recent_tasks = cursor.fetchall()
    conn.close()
    
    return render_template('dashboard.html', total_tasks=total_tasks, priority_counts=priority_counts, recent_tasks=recent_tasks)

@app.route('/tasks')
@login_required
def tasks_list():
    conn = get_db_connection(app.config['DATABASE_PATH'])
    cursor = conn.cursor()
    user_id = session['user_id']
    cursor.execute("""
        SELECT t.*, p.priority_label as priority, p.priority_score 
        FROM Tasks t 
        LEFT JOIN Predictions p ON t.task_id = p.task_id 
        WHERE t.user_id = ?
        ORDER BY t.deadline ASC
    """, (user_id,))
    tasks = cursor.fetchall()
    
    cursor.execute("SELECT * FROM Batches WHERE user_id = ? ORDER BY created_at DESC", (user_id,))
    batches = cursor.fetchall()
    
    conn.close()
    return render_template('tasks_list.html', tasks=tasks, batches=batches)

def calculate_priority_score(deadline_date, effort, impact, urgency, dependencies):
    days_to_deadline = (deadline_date - date.today()).days
    
    if days_to_deadline < 0:
        deadline_points = 20
    elif days_to_deadline <= 2:
        deadline_points = 15
    elif days_to_deadline <= 7:
        deadline_points = 10
    elif days_to_deadline <= 14:
        deadline_points = 7
    else:
        deadline_points = 3
        
    score = (impact * 4) + (urgency * 3) + (dependencies * 2) + deadline_points
    
    if effort < 3:
        score += 5
    elif effort > 20:
        score -= 5
        
    score = max(0, min(100, int(score)))
    
    if score >= 80:
        label = "Critical"
    elif score >= 60:
        label = "High"
    elif score >= 40:
        label = "Medium"
    else:
        label = "Low"
        
    return score, label

@app.route('/tasks/create', methods=['GET', 'POST'])
@login_required
def create_task():
    form = TaskForm()
    if form.validate_on_submit():
        deadline_date = form.deadline.data
        if deadline_date < date.today():
            flash('Deadline cannot be in the past.', 'error')
            return render_template('task_create.html', form=form)
            
        user_id = session['user_id']
        conn = get_db_connection(app.config['DATABASE_PATH'])
        cursor = conn.cursor()
            
        cursor.execute("""
            INSERT INTO Tasks (user_id, title, description, deadline, estimated_effort, business_impact, urgency, dependency_count, task_type, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            user_id, form.title.data, form.description.data, deadline_date.strftime('%Y-%m-%d'),
            form.estimated_effort.data, form.business_impact.data, form.urgency.data, form.dependencies.data,
            'General', 'Pending'
        ))
        
        task_id = cursor.lastrowid
        
        score, label = calculate_priority_score(
            deadline_date, 
            form.estimated_effort.data, 
            form.business_impact.data, 
            form.urgency.data, 
            form.dependencies.data
        )
        
        days_to_deadline = (deadline_date - date.today()).days
        try:
            ml_pred = predict_priority(
                days_to_deadline=days_to_deadline,
                estimated_effort=form.estimated_effort.data,
                business_impact=form.business_impact.data,
                urgency=form.urgency.data,
                dependency_count=form.dependencies.data,
                task_type='General'
            )
            ml_prediction = str(ml_pred)
        except Exception:
            ml_prediction = label

        cursor.execute("""
            INSERT INTO Predictions (task_id, priority_score, priority_label, model_prediction)
            VALUES (?, ?, ?, ?)
        """, (task_id, score, label, ml_prediction))
        
        conn.commit()
        conn.close()
        
        flash('Task created successfully!', 'success')
        return redirect(url_for('tasks_list'))
    return render_template('task_create.html', form=form)

@app.route('/tasks/<int:id>')
@login_required
def view_task(id):
    conn = get_db_connection(app.config['DATABASE_PATH'])
    cursor = conn.cursor()
    cursor.execute("""
        SELECT t.*, p.priority_label as priority, p.priority_score 
        FROM Tasks t 
        LEFT JOIN Predictions p ON t.task_id = p.task_id 
        WHERE t.task_id = ? AND t.user_id = ?
    """, (id, session['user_id']))
    task = cursor.fetchone()
    conn.close()
    
    if not task:
        flash("Task not found.", "error")
        return redirect(url_for('tasks_list'))
        
    override_form = OverrideForm()
    return render_template('task_detail.html', task=task, override_form=override_form)

@app.route('/tasks/<int:id>/edit', methods=['GET', 'POST'])
@login_required
def edit_task(id):
    conn = get_db_connection(app.config['DATABASE_PATH'])
    cursor = conn.cursor()
    
    form = TaskForm()
    if request.method == 'GET':
        cursor.execute("SELECT * FROM Tasks WHERE task_id = ? AND user_id = ?", (id, session['user_id']))
        task = cursor.fetchone()
        if not task:
            flash("Task not found or permission denied.", "error")
            conn.close()
            return redirect(url_for('tasks_list'))
            
        form.title.data = task['title']
        form.description.data = task['description']
        
        # Convert date string to datetime.date
        from datetime import datetime
        form.deadline.data = datetime.strptime(task['deadline'], '%Y-%m-%d').date()
        
        form.estimated_effort.data = task['estimated_effort']
        form.urgency.data = task['urgency']
        form.business_impact.data = task['business_impact']
        form.dependencies.data = task['dependency_count']
        
    if form.validate_on_submit():
        deadline_date = form.deadline.data
        if deadline_date < date.today():
            flash('Deadline cannot be in the past.', 'error')
            conn.close()
            return render_template('task_edit.html', form=form, task_id=id)
            
        cursor.execute("""
            UPDATE Tasks SET 
                title=?, description=?, deadline=?, estimated_effort=?, 
                business_impact=?, urgency=?, dependency_count=?
            WHERE task_id=? AND user_id=?
        """, (
            form.title.data, form.description.data, deadline_date.strftime('%Y-%m-%d'),
            form.estimated_effort.data, form.business_impact.data, form.urgency.data, 
            form.dependencies.data, id, session['user_id']
        ))
        
        if cursor.rowcount == 0:
            flash("Task not found or permission denied.", "error")
            conn.close()
            return redirect(url_for('tasks_list'))
        
        score, label = calculate_priority_score(
            deadline_date, 
            form.estimated_effort.data, 
            form.business_impact.data, 
            form.urgency.data, 
            form.dependencies.data
        )
        
        days_to_deadline = (deadline_date - date.today()).days
        try:
            ml_pred = predict_priority(
                days_to_deadline=days_to_deadline,
                estimated_effort=form.estimated_effort.data,
                business_impact=form.business_impact.data,
                urgency=form.urgency.data,
                dependency_count=form.dependencies.data,
                task_type='General'
            )
            ml_prediction = str(ml_pred)
        except Exception:
            ml_prediction = label

        cursor.execute("""
            UPDATE Predictions SET priority_score=?, priority_label=?, model_prediction=?
            WHERE task_id=?
        """, (score, label, ml_prediction, id))
        
        conn.commit()
        conn.close()
        flash('Task updated successfully!', 'success')
        return redirect(url_for('view_task', id=id))
    
    conn.close()
    return render_template('task_edit.html', form=form, task_id=id)

@app.route('/tasks/<int:id>/delete', methods=['POST'])
@login_required
def delete_task(id):
    conn = get_db_connection(app.config['DATABASE_PATH'])
    cursor = conn.cursor()
    cursor.execute("DELETE FROM Tasks WHERE task_id=? AND user_id=?", (id, session['user_id']))
    if cursor.rowcount > 0:
        cursor.execute("DELETE FROM Predictions WHERE task_id=?", (id,))
        flash('Task deleted successfully!', 'success')
    else:
        flash("Task not found or permission denied.", "error")
    conn.commit()
    conn.close()
    return redirect(url_for('tasks_list'))

@app.route('/tasks/<int:id>/override', methods=['POST'])
@login_required
def override_priority(id):
    override_form = OverrideForm()
    if override_form.validate_on_submit():
        conn = get_db_connection(app.config['DATABASE_PATH'])
        cursor = conn.cursor()
        
        new_priority = override_form.new_priority.data
        reason = override_form.reason.data
        
        cursor.execute("SELECT task_id FROM Tasks WHERE task_id=? AND user_id=?", (id, session['user_id']))
        if not cursor.fetchone():
            flash("Task not found or permission denied.", "error")
            conn.close()
            return redirect(url_for('tasks_list'))
            
        cursor.execute("SELECT priority_label FROM Predictions WHERE task_id=?", (id,))
        old_priority = cursor.fetchone()['priority_label']
        
        cursor.execute("UPDATE Predictions SET priority_label=? WHERE task_id=?", (new_priority, id))
        cursor.execute("""
            INSERT INTO OverrideHistory (task_id, original_priority, new_priority, reason) 
            VALUES (?, ?, ?, ?)
        """, (id, old_priority, new_priority, reason))
        
        conn.commit()
        conn.close()
        
        flash(f"Priority overridden to {new_priority}", 'success')
    else:
        flash("Failed to override priority.", 'error')
    return redirect(url_for('view_task', id=id))

# --- Prediction Routes ---
@app.route('/predict', methods=['POST'])
@login_required
def predict():
    data = request.get_json(silent=True) or request.form
    try:
        if 'deadline' in data:
            d_val = data['deadline']
            if isinstance(d_val, str):
                deadline_date = datetime.strptime(d_val, '%Y-%m-%d').date()
            else:
                deadline_date = d_val
            days_to_deadline = (deadline_date - date.today()).days
        else:
            days_to_deadline = int(data.get('days_to_deadline', 7))

        estimated_effort = float(data.get('estimated_effort', 1.0))
        business_impact = int(data.get('business_impact', 5))
        urgency = int(data.get('urgency', 5))
        dependency_count = int(data.get('dependency_count', 0))
        task_type = data.get('task_type', 'General')

        prediction = predict_priority(
            days_to_deadline,
            estimated_effort,
            business_impact,
            urgency,
            dependency_count,
            task_type
        )
        return jsonify({
            "status": "success",
            "prediction": str(prediction),
            "inputs": {
                "days_to_deadline": days_to_deadline,
                "estimated_effort": estimated_effort,
                "business_impact": business_impact,
                "urgency": urgency,
                "dependency_count": dependency_count,
                "task_type": task_type
            }
        })
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 400

@app.route('/predict/sample-csv', methods=['GET'])
@login_required
def download_sample_csv():
    sample_data = (
        "title,deadline,urgency,business_impact,estimated_effort,dependency_count,task_type\n"
        "Fix Login Security Bug,2026-09-20,9,9,4.0,1,Bug\n"
        "Design Landing Page Header,2026-09-25,5,6,3.0,0,Design\n"
        "Refactor Database Schema,2026-09-18,8,8,12.0,2,Development\n"
        "Write API Documentation,2026-09-30,3,4,2.0,0,Documentation\n"
    )
    return Response(
        sample_data,
        mimetype="text/csv",
        headers={"Content-disposition": "attachment; filename=stpp_sample_tasks.csv"}
    )

@app.route('/predict/batch', methods=['GET', 'POST'])
@login_required
def predict_batch():
    if request.method == 'GET':
        return render_template('batch_upload.html')

    if 'file' not in request.files:
        flash('No file selected.', 'error')
        return redirect(url_for('predict_batch'))

    file = request.files['file']
    if not file or file.filename == '':
        flash('No file selected.', 'error')
        return redirect(url_for('predict_batch'))

    if not file.filename.lower().endswith('.csv'):
        flash('Invalid file format. Please upload a .csv file.', 'error')
        return redirect(url_for('predict_batch'))

    try:
        df = pd.read_csv(file)
    except Exception as e:
        flash(f'Failed to read CSV file: {str(e)}', 'error')
        return redirect(url_for('predict_batch'))

    if len(df) == 0:
        flash('The uploaded CSV file is empty.', 'error')
        return redirect(url_for('predict_batch'))

    if len(df) > 500:
        flash('CSV exceeds maximum limit of 500 tasks per upload.', 'error')
        return redirect(url_for('predict_batch'))

    # Standardize column names
    df.columns = [c.strip().lower() for c in df.columns]

    col_map = {
        'deadline_date': 'deadline',
        'task_name': 'title',
        'task': 'title',
        'effort': 'estimated_effort',
        'impact': 'business_impact',
        'dependencies': 'dependency_count'
    }
    df = df.rename(columns=col_map)

    required_fields = ['title', 'deadline', 'urgency', 'business_impact', 'estimated_effort', 'dependency_count']
    missing_fields = [f for f in required_fields if f not in df.columns]
    if missing_fields:
        flash(f'Missing required CSV columns: {", ".join(missing_fields)}', 'error')
        return redirect(url_for('predict_batch'))

    if 'task_type' not in df.columns:
        df['task_type'] = 'General'

    valid_rows = []
    invalid_rows = []
    today = date.today()

    for idx, row in df.iterrows():
        row_num = idx + 2
        title = str(row.get('title', f'Task {idx+1}')).strip()

        deadline_str = str(row.get('deadline', '')).strip()
        try:
            deadline_date = datetime.strptime(deadline_str, '%Y-%m-%d').date()
        except Exception:
            invalid_rows.append({
                "row_num": row_num,
                "title": title,
                "reason": f"Invalid date format '{deadline_str}' (Expected YYYY-MM-DD)"
            })
            continue

        try:
            urgency = int(row.get('urgency'))
            if not (1 <= urgency <= 10):
                raise ValueError()
        except Exception:
            invalid_rows.append({
                "row_num": row_num,
                "title": title,
                "reason": "Urgency must be an integer between 1 and 10"
            })
            continue

        try:
            business_impact = int(row.get('business_impact'))
            if not (1 <= business_impact <= 10):
                raise ValueError()
        except Exception:
            invalid_rows.append({
                "row_num": row_num,
                "title": title,
                "reason": "Business Impact must be an integer between 1 and 10"
            })
            continue

        try:
            estimated_effort = float(row.get('estimated_effort'))
            if estimated_effort <= 0:
                raise ValueError()
        except Exception:
            invalid_rows.append({
                "row_num": row_num,
                "title": title,
                "reason": "Estimated effort must be a positive number"
            })
            continue

        try:
            dependency_count = int(row.get('dependency_count'))
            if dependency_count < 0:
                raise ValueError()
        except Exception:
            invalid_rows.append({
                "row_num": row_num,
                "title": title,
                "reason": "Dependency count must be a non-negative integer"
            })
            continue

        task_type = str(row.get('task_type', 'General')).strip() or 'General'
        days_to_deadline = (deadline_date - today).days

        score, label = calculate_priority_score(
            deadline_date, estimated_effort, business_impact, urgency, dependency_count
        )

        valid_rows.append({
            "title": title,
            "deadline": deadline_str,
            "days_to_deadline": days_to_deadline,
            "estimated_effort": estimated_effort,
            "business_impact": business_impact,
            "urgency": urgency,
            "dependency_count": dependency_count,
            "task_type": task_type,
            "priority_score": score,
            "priority_label": label
        })

    if not valid_rows:
        return render_template(
            'batch_results.html',
            results=[],
            invalid_rows=invalid_rows,
            valid_count=0,
            total_count=len(df),
            priority_counts={},
            result_filename=None
        )

    valid_df = pd.DataFrame(valid_rows)
    ml_predictions = predict_priority_batch(valid_df)

    for i, pred in enumerate(ml_predictions):
        valid_rows[i]["model_prediction"] = str(pred)

    priority_counts = {}
    for r in valid_rows:
        lbl = r["priority_label"]
        priority_counts[lbl] = priority_counts.get(lbl, 0) + 1

    result_df = pd.DataFrame(valid_rows)
    filename = f"batch_results_{session['user_id']}_{int(datetime.now().timestamp())}.csv"
    result_filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    result_df.to_csv(result_filepath, index=False)
    
    conn = get_db_connection(app.config['DATABASE_PATH'])
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO Batches (user_id, filename, task_count, result_filepath)
        VALUES (?, ?, ?, ?)
    """, (session['user_id'], secure_filename(file.filename), len(valid_rows), filename))
    conn.commit()
    conn.close()

    return render_template(
        'batch_results.html',
        results=valid_rows,
        invalid_rows=invalid_rows,
        valid_count=len(valid_rows),
        total_count=len(df),
        priority_counts=priority_counts,
        result_filename=filename
    )

@app.route('/api/batches/<int:batch_id>')
@login_required
def get_batch_results(batch_id):
    conn = get_db_connection(app.config['DATABASE_PATH'])
    cursor = conn.cursor()
    cursor.execute("SELECT result_filepath FROM Batches WHERE batch_id = ? AND user_id = ?", (batch_id, session['user_id']))
    batch = cursor.fetchone()
    conn.close()
    
    if not batch:
        return jsonify({'status': 'error', 'message': 'Batch not found'}), 404
        
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], batch['result_filepath'])
    if not os.path.exists(filepath):
        return jsonify({'status': 'error', 'message': 'Results file missing'}), 404
        
    df = pd.read_csv(filepath)
    # Ensure it's a list of dicts
    return jsonify({'status': 'success', 'data': df.to_dict(orient='records')})

@app.route('/download/<filename>')
@login_required
def download_file(filename):
    safe_name = secure_filename(filename)
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], safe_name)
    if not os.path.exists(filepath):
        flash('Requested file not found or permission denied.', 'error')
        return redirect(url_for('predict_batch'))
    return send_from_directory(app.config['UPLOAD_FOLDER'], safe_name, as_attachment=True)

@app.route('/profile/delete', methods=['POST'])
@login_required
def delete_account():
    conn = get_db_connection(app.config['DATABASE_PATH'])
    cursor = conn.cursor()
    
    # Delete all tasks associated with the user
    cursor.execute("DELETE FROM Tasks WHERE user_id = ?", (session['user_id'],))
    
    # Delete the user account
    cursor.execute("DELETE FROM Users WHERE user_id = ?", (session['user_id'],))
    
    conn.commit()
    conn.close()
    
    # Clear the session
    session.clear()
    flash('Your account and all associated data have been permanently deleted.', 'success')
    return redirect(url_for('login'))

if __name__ == '__main__':
    # Initialize the database if it hasn't been already
    from database import init_db
    init_db(app.config['DATABASE_PATH'])
    app.run(debug=True)
