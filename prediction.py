import os
import joblib
import pandas as pd

# Global module-level model & preprocessor cache
_MODEL_CACHE = None


def get_model_path():
    """Locate the saved priority model file."""
    base_dir = os.path.dirname(os.path.abspath(__file__))
    model_path = os.path.join(base_dir, "models", "priority_model.pkl")
    if os.path.exists(model_path):
        return model_path
    return "models/priority_model.pkl"


def clear_model_cache():
    """Clear the in-memory model cache (useful for testing)."""
    global _MODEL_CACHE
    _MODEL_CACHE = None


def get_model_and_preprocessor():
    """Load and cache the model and preprocessor singleton in memory."""
    global _MODEL_CACHE
    if _MODEL_CACHE is None:
        model_path = get_model_path()
        _MODEL_CACHE = joblib.load(model_path)
    return _MODEL_CACHE["model"], _MODEL_CACHE["preprocessor"]


def predict_priority(
    days_to_deadline,
    estimated_effort,
    business_impact,
    urgency,
    dependency_count,
    task_type="General"
):
    """Predict priority for a single task using cached ML model & preprocessor."""
    model, preprocessor = get_model_and_preprocessor()

    task = pd.DataFrame([{
        "days_to_deadline": days_to_deadline,
        "estimated_effort": estimated_effort,
        "business_impact": business_impact,
        "urgency": urgency,
        "dependency_count": dependency_count,
        "task_type": task_type
    }])

    task_processed = preprocessor.transform(task)
    prediction = model.predict(task_processed)

    return prediction[0]


def predict_priority_batch(df_tasks):
    """Predict priorities for a DataFrame of multiple tasks in a single vectorized pass."""
    model, preprocessor = get_model_and_preprocessor()

    required_cols = [
        "days_to_deadline",
        "estimated_effort",
        "business_impact",
        "urgency",
        "dependency_count",
        "task_type"
    ]

    # Ensure required columns exist and order matches training pipeline
    X = df_tasks[required_cols].copy()
    X_processed = preprocessor.transform(X)
    predictions = model.predict(X_processed)

    return list(predictions)