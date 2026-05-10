import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import make_pipeline
import pickle
import string
import os

def preprocess_text(text):
    text = text.lower()
    text = text.translate(str.maketrans('', '', string.punctuation))
    return text

def train_and_save_model():
    print("Loading dataset...")
    df = pd.read_csv('dataset.csv')
    
    print("Preprocessing text...")
    df['text'] = df['text'].apply(preprocess_text)
    
    print("Training model...")
    model = make_pipeline(
        TfidfVectorizer(stop_words='english'),
        LogisticRegression(max_iter=1000)
    )
    
    model.fit(df['text'], df['department'])
    
    print("Saving model to model.pkl...")
    with open('model.pkl', 'wb') as f:
        pickle.dump(model, f)
    print("Model trained and saved successfully.")

def predict_department(text):
    if not os.path.exists('model.pkl'):
        return "Unknown", 0.0
    with open('model.pkl', 'rb') as f:
        model = pickle.load(f)
    preprocessed = preprocess_text(text)
    prediction = model.predict([preprocessed])
    
    try:
        probabilities = model.predict_proba([preprocessed])
        confidence = max(probabilities[0]) * 100
    except Exception:
        confidence = 0.0
        
    return prediction[0], round(confidence, 1)

if __name__ == '__main__':
    train_and_save_model()
