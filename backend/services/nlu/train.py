"""Train the NLU intent classifier and save model.pkl.

Usage:
    cd backend && python3 -m services.nlu.train
"""
from services.nlu.classifier import train


def main():
    pipe = train()
    classes = list(pipe.classes_)
    n_samples = pipe.named_steps['tfidf'].transform(
        pipe.named_steps['tfidf'].build_analyzer()(' ')
    ).shape[0] if False else '?'
    print(f'Trained on intents: {classes}')
    print('model.pkl saved.')


if __name__ == '__main__':
    main()
