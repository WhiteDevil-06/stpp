# 🧠 Smart Task Priority Predictor (STPP)

An intermediate-level web application that helps users manage tasks and automatically predicts their priority (Low, Medium, High, Critical) using a **Decision Tree Classifier** and a rule-based scoring engine.

Built for final internship submission, demonstrating end-to-end integration of a Flask web application, an SQLite database, and a Scikit-Learn Machine Learning pipeline.

---

## 🎯 Problem Statement & Objectives
Modern professionals struggle with task overload and decision fatigue. Without a clear system to weigh deadlines, business impact, and effort, critical tasks can easily slip through the cracks.

**Objectives:**
- Build a secure, user-friendly task management dashboard.
- Develop a dual-layered priority engine:
  - **Rule-Based Engine**: Calculates a deterministic 0-100 score based on deadlines, effort, and impact.
  - **ML Predictor**: A Decision Tree Classifier trained on historical task data to predict the final priority category.
- Implement a robust batch processing pipeline allowing users to classify hundreds of tasks simultaneously via CSV upload.

---

## ✨ Key Features
- **User Authentication**: Secure registration, login, and session management.
- **Task Management CRUD**: Create, read, edit, and delete user-specific tasks.
- **Smart Prediction Integration**: Real-time priority assessment upon task creation/editing.
- **Manual Overrides**: Users can override ML predictions, enforcing a mandatory justification reason logged in an `OverrideHistory` audit table.
- **Batch CSV Processing**: Upload up to 500 tasks at once. The system validates rows, flags errors, predicts priorities, and generates a downloadable results file.
- **Analytics Dashboard**: Visual breakdown of task statuses and priority distributions.

---

## 🛠️ Technology Stack
| Layer | Technology |
|---|---|
| **Backend Framework** | Python, Flask, Flask-WTF |
| **Machine Learning** | Scikit-learn (Decision Tree), Pandas, Joblib |
| **Database** | SQLite3 |
| **Frontend** | HTML5, CSS3, Bootstrap 5, Jinja2 |
| **Testing** | Pytest |

---

## 🏗️ System Architecture & ML Pipeline

### ML Pipeline Structure
1. **Raw Data**: Intentionally imperfect synthetic task data (`data/tasks.csv`).
2. **Preprocessing**: Missing value imputation (medians for numerics, most-frequent for categoricals) and feature engineering (`days_to_deadline`).
3. **Training**: `train_model.py` splits the data (80/20) and trains a `DecisionTreeClassifier`.
4. **Artifact**: The pipeline and model are serialized into `models/priority_model.pkl`.
5. **Inference**: Flask routes call `prediction.py`, which loads the singleton model for O(1) real-time inference or vectorized batch inference.

### Priority Scoring Logic
- **Features Used**: `days_to_deadline`, `estimated_effort`, `business_impact`, `urgency`, `dependency_count`, `task_type`.
- **Score**: Calculated from 0-100 based on weighted feature logic.
- **Categories**: 
  - **Critical** (80-100)
  - **High** (60-79)
  - **Medium** (40-59)
  - **Low** (0-39)

---

## 📊 ML Evaluation Metrics
The model was evaluated against a 20% holdout test set using `train_model.py`:
- **Accuracy**: 74.75%
- **Precision**: 0.7496
- **Recall**: 0.7475
- **F1-Score**: 0.7405

---

## 🚀 Installation & Setup

### Prerequisites
- Python 3.9+
- Git

### 1. Clone & Setup Environment
```bash
git clone https://github.com/WhiteDevil-06/stpp.git
cd stpp
python -m venv venv

# Windows
venv\Scripts\activate
# Mac/Linux
source venv/bin/activate
```

### 2. Install Dependencies
```bash
pip install -r requirements.txt
```

### 3. Initialize Model (If required)
*The repository already includes the pre-trained `priority_model.pkl`, but to retrain locally:*
```bash
python train_model.py
```

### 4. Run the Application
```bash
python app.py
```
Access the application at: `http://127.0.0.1:5000`

---

## 🧪 Testing

The repository contains a robust automated test suite validating the entire ML integration pipeline, database persistence, and API boundaries.

Run the tests using pytest:
```bash
pytest tests/
```

### Batch CSV Upload Limits
The `/predict/batch` endpoint strictly enforces the **500-task maximum limit**. 
- Valid files generate a downloadable CSV result.
- Files exceeding 500 rows are immediately rejected with an error to prevent partial processing.
- Missing columns, invalid dates, and out-of-range numerics are safely caught and reported in a user-friendly UI table.

---

## 📁 Project Structure

```text
smart_task_priority_predictor/
├── app.py                      # Main Flask application & routing
├── database.py                 # SQLite DB initialization 
├── forms.py                    # Flask-WTF form definitions
├── prediction.py               # ML inference interface
├── preprocessing.py            # Feature engineering logic
├── train_model.py              # ML training script
├── requirements.txt            # Dependencies
├── data/
│   └── tasks.csv               # Raw dataset
├── models/
│   └── priority_model.pkl      # Serialized ML model
├── templates/                  # Jinja2 HTML templates (dashboard, batch, forms)
├── static/                     # CSS, assets, favicon
├── tests/
│   └── test_ml_integration.py  # Pytest suite
└── .agents/                    # Internal documentation & role definitions
```

---

## 🔐 Security Considerations
- **Session Protection**: Flask signed sessions with `@login_required` enforcement.
- **Passwords**: Hashes generated via `werkzeug.security`.
- **Data Isolation**: SQL queries enforce `WHERE user_id = ?` to prevent cross-account data leakage.
- **Path Traversal**: Secure filenames and path validation used for CSV result downloads.

---

## 🏁 Final Project Status
**Status: COMPLETED**  
All core Software Requirements Specification (SRS) items have been implemented, tested, and documented. The project is ready for final presentation and demo.

---

## 👥 Team Roles & Contributions

This project was built collaboratively by our team:

- **Shraavya**: Machine Learning (Phase 1). Responsible for exploratory data analysis, data cleaning, feature engineering, and the initial training of the Decision Tree Classifier.
- **Sirisha**: Machine Learning (Phase 2). Responsible for ML integration, building the Python inference pipeline (`prediction.py`), model evaluation, and backend ML unit testing.
- **Siddharth Dhanush**: UI/UX & Frontend. Responsible for the responsive visual design, templates, user experience, layout structuring, and CSS styling.
- **Rakshith**: Backend & Architecture. Responsible for Flask routing, SQLite database architecture, user authentication, and the batch prediction endpoint logic.
- **Shreyank**: QA & Documentation. Responsible for the test suite orchestration, CI integration tests, the Requirements Traceability Matrix, and this final README documentation.