# 🧠 Smart Task Priority Predictor

An intermediate-level project that helps you manage tasks and automatically predicts their priority using a **Decision Tree Classifier**.

Built with Flask + SQLite + Scikit-learn.

---

## ✨ Features

- Add, manage, and track tasks
- ML-powered priority prediction (High / Medium / Low)
- Clean web UI with Bootstrap
- SQLite database for local storage

---

## 🛠️ Tech Stack

| Layer       | Technology              |
|-------------|-------------------------|
| Backend     | Python, Flask           |
| ML Model    | Scikit-learn (Decision Tree) |
| Database    | SQLite                  |
| Data        | Pandas, NumPy           |
| Frontend    | HTML, CSS, Bootstrap    |
| Forms       | Flask-WTF               |

---

## 🚀 Getting Started

### Prerequisites
- Python 3.9 or higher
- Git

### 1. Clone the Repository

```bash
git clone https://github.com/Shree2312/stpp.git
cd stpp
```

### 2. Create a Virtual Environment

```bash
python -m venv venv
```

Activate it:

- **Windows:**
  ```bash
  venv\Scripts\activate
  ```
- **Mac / Linux:**
  ```bash
  source venv/bin/activate
  ```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Train the ML Model

Run this once before starting the app to generate the model files:

```bash
python train_model.py
```

### 5. Run the App

```bash
python app.py
```

Then open your browser and go to: **http://127.0.0.1:5000**

---

## 🧪 Running Tests

```bash
pytest tests/
```

---

## 📁 Project Structure

```
stpp/
├── app.py              # Main Flask application
├── models.py           # Database models
├── database.py         # DB setup and connection
├── forms.py            # Flask-WTF forms
├── prediction.py       # Priority prediction logic
├── preprocessing.py    # Data preprocessing
├── train_model.py      # Train the ML model
├── requirements.txt    # Python dependencies
├── templates/          # HTML templates
├── static/             # CSS, JS, images
├── models/             # Saved ML model files
├── data/               # Dataset files
└── tests/              # Unit tests
```

---

## 🤝 Contributing

1. Fork the repository
2. Create a new branch (`git checkout -b feature/your-feature`)
3. Commit your changes (`git commit -m 'Add some feature'`)
4. Push to the branch (`git push origin feature/your-feature`)
5. Open a Pull Request

---

## 📄 License

This project is for educational/internship purposes.