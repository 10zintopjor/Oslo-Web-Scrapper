from botok import WordTokenizer
from botok.config import Config
from pathlib import Path
from botok import Text
import spacy

def get_tokens(wt, text):
    tokens = wt.tokenize(text, split_affixes=False)
    return tokens

def get_tibetan_tokenized_sentence(text):
    tokenized_sentence = ""
    config = Config(dialect_name="general", base_path= Path.home())
    wt = WordTokenizer(config=config)
    text = Path("sample.txt").read_text(encoding="utf-8")
    tokens = get_tokens(wt, text)
    for token in tokens:
        tokenized_sentence+=token.text
    return tokenized_sentence

def get_english_tokenized_sentence(text):
    tokenized_sentence = ""
    nlp = spacy.load("en_core_web_sm")
    doc = nlp(text)
    for token in doc:
        tokenized_sentence+=token.text
    return tokenized_sentence

def change_format(text,lang):
    if lang == "tibetan":
        new_text = get_tibetan_tokenized_sentence(text)
    elif lang == "english":
        new_text = get_english_tokenized_sentence(text)

if __name__ == "__main__":
    tokenized_sentence = ""
    config = Config(dialect_name="general", base_path= Path.home())
    wt = WordTokenizer(config=config)
    text = Path("sample.txt").read_text(encoding="utf-8")
    tokens = get_tokens(wt, text)
    for token in tokens:
        tokenized_sentence+=token.text

    Path("./new_sample.txt").write_text(tokenized_sentence)
    print(len(tokenized_sentence))
    print(len(text))