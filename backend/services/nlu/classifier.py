import os
import pickle
import jieba
import yaml
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.svm import LinearSVC
from sklearn.pipeline import Pipeline

_DIR = os.path.dirname(os.path.abspath(__file__))
_DATA_PATH = os.path.join(_DIR, 'training_data.yml')
_MODEL_PATH = os.path.join(_DIR, 'model.pkl')

_pipeline = None


def _tokenize(text: str) -> str:
    return ' '.join(jieba.cut(text))


def _load_training_data():
    with open(_DATA_PATH, 'r', encoding='utf-8') as f:
        data = yaml.safe_load(f)
    texts, labels = [], []
    for intent, examples in data.items():
        for ex in examples:
            texts.append(_tokenize(ex))
            labels.append(intent)
    return texts, labels


def train():
    texts, labels = _load_training_data()
    pipe = Pipeline([
        ('tfidf', TfidfVectorizer(ngram_range=(1, 2))),
        ('clf', LinearSVC(C=1.0, max_iter=10000)),
    ])
    pipe.fit(texts, labels)
    with open(_MODEL_PATH, 'wb') as f:
        pickle.dump(pipe, f)
    return pipe


def _get_pipeline():
    global _pipeline
    if _pipeline is not None:
        return _pipeline
    if os.path.exists(_MODEL_PATH):
        with open(_MODEL_PATH, 'rb') as f:
            _pipeline = pickle.load(f)
    else:
        _pipeline = train()
    return _pipeline


def classify(text: str) -> str:
    pipe = _get_pipeline()
    tokenized = _tokenize(text)
    return pipe.predict([tokenized])[0]


def classify_with_confidence(text: str) -> tuple:
    pipe = _get_pipeline()
    tokenized = _tokenize(text)
    intent = pipe.predict([tokenized])[0]
    scores = pipe.decision_function([tokenized])[0]
    if hasattr(scores, '__len__'):
        confidence = max(scores)
    else:
        confidence = abs(scores)
    return intent, confidence
