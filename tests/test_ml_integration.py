import pytest
import os
import sys
import sqlite3
import joblib
from datetime import date, timedelta

# Ensure parent directory is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import app
from database import init_db, get_db_connection
from prediction import predict_priority


@pytest.fixture
def client():
    app.config['TESTING'] = True
    app.config['WTF_CSRF_ENABLED'] = False
    app.config['DATABASE_PATH'] = 'test_task_priority.db'
    app.config['SECRET_KEY'] = 'test-secret-key'
    
    # Initialize fresh test database
    if os.path.exists('test_task_priority.db'):
        try:
            os.remove('test_task_priority.db')
        except OSError:
            pass
    init_db('test_task_priority.db')

    with app.test_client() as client:
        with app.app_context():
            # Create a test user in DB
            conn = get_db_connection('test_task_priority.db')
            cursor = conn.cursor()
            from werkzeug.security import generate_password_hash
            cursor.execute(
                "INSERT INTO Users (name, email, password) VALUES (?, ?, ?)",
                ("Test User", "test@example.com", generate_password_hash("password123"))
            )
            user_id = cursor.lastrowid
            conn.commit()
            conn.close()

            # Set session user_id
            with client.session_transaction() as sess:
                sess['user_id'] = user_id

            yield client

    # Cleanup test database after tests
    if os.path.exists('test_task_priority.db'):
        try:
            os.remove('test_task_priority.db')
        except OSError:
            pass


def test_model_direct_inference():
    """Test that predict_priority directly returns a valid string priority label."""
    prediction = predict_priority(
        days_to_deadline=2,
        estimated_effort=8.0,
        business_impact=9,
        urgency=9,
        dependency_count=2,
        task_type='General'
    )
    assert isinstance(prediction, str)
    assert prediction in ['Low', 'Medium', 'High', 'Critical']


def test_predict_endpoint_json(client):
    """Test the /predict HTTP endpoint with JSON payload."""
    payload = {
        "days_to_deadline": 3,
        "estimated_effort": 5.0,
        "business_impact": 8,
        "urgency": 8,
        "dependency_count": 1,
        "task_type": "General"
    }
    response = client.post('/predict', json=payload)
    assert response.status_code == 200
    data = response.get_json()
    assert data['status'] == 'success'
    assert 'prediction' in data
    assert data['prediction'] in ['Low', 'Medium', 'High', 'Critical']


def test_task_creation_saves_ml_prediction_to_sqlite(client):
    """Test creating a task via Flask and verifying ML prediction in SQLite."""
    future_date = (date.today() + timedelta(days=5)).strftime('%Y-%m-%d')
    task_data = {
        "title": "Integration Test Task",
        "description": "Testing ML priority integration",
        "deadline": future_date,
        "urgency": 9,
        "business_impact": 9,
        "estimated_effort": 4.0,
        "dependencies": 1
    }
    response = client.post('/tasks/create', data=task_data, follow_redirects=True)
    assert response.status_code == 200

    conn = get_db_connection('test_task_priority.db')
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM Predictions ORDER BY prediction_id DESC LIMIT 1")
    row = cursor.fetchone()
    conn.close()

    assert row is not None
    assert row['model_prediction'] in ['Low', 'Medium', 'High', 'Critical']


def test_task_edit_updates_ml_prediction_in_sqlite(client):
    """Test editing a task via Flask and verifying ML prediction updates in SQLite."""
    future_date = (date.today() + timedelta(days=2)).strftime('%Y-%m-%d')
    task_data = {
        "title": "Initial Task",
        "description": "Initial description",
        "deadline": future_date,
        "urgency": 5,
        "business_impact": 5,
        "estimated_effort": 2.0,
        "dependencies": 1
    }
    client.post('/tasks/create', data=task_data, follow_redirects=True)

    # Fetch created task ID
    conn = get_db_connection('test_task_priority.db')
    cursor = conn.cursor()
    cursor.execute("SELECT task_id FROM Tasks LIMIT 1")
    task_id = cursor.fetchone()['task_id']
    conn.close()

    # Edit task with urgent details
    urgent_date = (date.today() + timedelta(days=1)).strftime('%Y-%m-%d')
    updated_data = {
        "title": "Updated Urgent Task",
        "description": "Updated description",
        "deadline": urgent_date,
        "urgency": 10,
        "business_impact": 10,
        "estimated_effort": 10.0,
        "dependencies": 3
    }
    response = client.post(f'/tasks/{task_id}/edit', data=updated_data, follow_redirects=True)
    assert response.status_code == 200

    conn = get_db_connection('test_task_priority.db')
    cursor = conn.cursor()
    cursor.execute("SELECT model_prediction FROM Predictions WHERE task_id = ?", (task_id,))
    row = cursor.fetchone()
    conn.close()

    assert row is not None
    assert row['model_prediction'] in ['Low', 'Medium', 'High', 'Critical']


def test_predict_endpoint_form_encoded(client):
    """Test the /predict HTTP endpoint with form-encoded payload."""
    form_payload = {
        "days_to_deadline": "10",
        "estimated_effort": "2.5",
        "business_impact": "4",
        "urgency": "3",
        "dependency_count": "0",
        "task_type": "Bug"
    }
    response = client.post('/predict', data=form_payload)
    assert response.status_code == 200
    data = response.get_json()
    assert data['status'] == 'success'
    assert 'prediction' in data
    assert data['prediction'] in ['Low', 'Medium', 'High', 'Critical']


def test_predict_endpoint_invalid_inputs(client):
    """Test /predict endpoint with invalid/malformed date input."""
    invalid_payload = {
        "deadline": "invalid-date-string",
        "estimated_effort": "not-a-number"
    }
    response = client.post('/predict', json=invalid_payload)
    assert response.status_code == 400
    data = response.get_json()
    assert data['status'] == 'error'
    assert 'message' in data


def test_model_singleton_caching():
    """Verify joblib.load is called exactly once across multiple predictions."""
    from unittest.mock import patch
    from prediction import clear_model_cache, predict_priority

    clear_model_cache()

    with patch('joblib.load', wraps=joblib.load) as mock_load:
        for _ in range(10):
            res = predict_priority(
                days_to_deadline=5,
                estimated_effort=4.0,
                business_impact=7,
                urgency=8,
                dependency_count=1,
                task_type='General'
            )
            assert res in ['Low', 'Medium', 'High', 'Critical']

        # Assert joblib.load was called ONLY once despite 10 prediction calls
        assert mock_load.call_count == 1


def test_predict_priority_batch():
    """Verify vectorized batch prediction works efficiently for multiple rows."""
    import pandas as pd
    from prediction import predict_priority_batch, predict_priority

    df_tasks = pd.DataFrame([
        {
            "days_to_deadline": 1,
            "estimated_effort": 10.0,
            "business_impact": 10,
            "urgency": 10,
            "dependency_count": 3,
            "task_type": "Bug"
        },
        {
            "days_to_deadline": 15,
            "estimated_effort": 2.0,
            "business_impact": 2,
            "urgency": 2,
            "dependency_count": 0,
            "task_type": "General"
        }
    ])

    batch_preds = predict_priority_batch(df_tasks)
    assert len(batch_preds) == 2

    # Verify batch results match individual predictions
    single_pred_1 = predict_priority(1, 10.0, 10, 10, 3, "Bug")
    single_pred_2 = predict_priority(15, 2.0, 2, 2, 0, "General")

    assert batch_preds[0] == single_pred_1
    assert batch_preds[1] == single_pred_2


def test_batch_prediction_route_get(client):
    """Test GET /predict/batch renders batch upload template."""
    response = client.get('/predict/batch')
    assert response.status_code == 200
    assert b'CSV Batch Prediction' in response.data


def test_download_sample_csv_endpoint(client):
    """Test downloading the sample CSV template."""
    response = client.get('/predict/sample-csv')
    assert response.status_code == 200
    assert response.mimetype == 'text/csv'
    assert b'title,deadline,urgency' in response.data


def test_batch_prediction_route_post_valid_csv(client):
    """Test POST /predict/batch with valid CSV file."""
    import io
    csv_data = (
        "title,deadline,urgency,business_impact,estimated_effort,dependency_count,task_type\n"
        "Critical Fix,2026-09-18,9,9,4.0,1,Bug\n"
        "Doc Task,2026-09-30,2,3,1.0,0,Documentation\n"
    )
    data = {
        'file': (io.BytesIO(csv_data.encode('utf-8')), 'test_tasks.csv')
    }
    response = client.post('/predict/batch', data=data, content_type='multipart/form-data')
    assert response.status_code == 200
    assert b'Batch Processing Results' in response.data
    assert b'Critical Fix' in response.data
    assert b'Download Results CSV' in response.data


def test_batch_prediction_route_post_over_500_rows(client):
    """Test POST /predict/batch enforces max 500 rows limit."""
    import io
    lines = ["title,deadline,urgency,business_impact,estimated_effort,dependency_count,task_type\n"]
    for i in range(501):
        lines.append(f"Task {i},2026-09-20,5,5,2.0,0,General\n")
    csv_data = "".join(lines)

    data = {
        'file': (io.BytesIO(csv_data.encode('utf-8')), 'too_many_tasks.csv')
    }
    response = client.post('/predict/batch', data=data, content_type='multipart/form-data', follow_redirects=True)
    assert response.status_code == 200
    assert b'CSV exceeds maximum limit of 500 tasks' in response.data


def test_batch_prediction_route_invalid_rows_report(client):
    """Test POST /predict/batch identifies and reports invalid rows."""
    import io
    csv_data = (
        "title,deadline,urgency,business_impact,estimated_effort,dependency_count,task_type\n"
        "Valid Task,2026-09-20,5,5,2.0,0,General\n"
        "Bad Date Task,not-a-date,5,5,2.0,0,General\n"
        "Bad Urgency Task,2026-09-20,99,5,2.0,0,General\n"
    )
    data = {
        'file': (io.BytesIO(csv_data.encode('utf-8')), 'mixed_tasks.csv')
    }
    response = client.post('/predict/batch', data=data, content_type='multipart/form-data')
    assert response.status_code == 200
    assert b'Invalid Rows Identified' in response.data
    assert b'Bad Date Task' in response.data
    assert b'Bad Urgency Task' in response.data


def test_download_file_path_traversal_prevention(client):
    """Test GET /download/<filename> handles safe downloads and blocks path traversal."""
    response = client.get('/download/..%2Fapp.py', follow_redirects=True)
    assert response.status_code in [404, 400, 302]

