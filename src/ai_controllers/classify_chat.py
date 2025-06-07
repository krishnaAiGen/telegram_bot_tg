# classify_chat.py
import torch
from transformers import RobertaTokenizer, RobertaForSequenceClassification
import torch.nn.functional as F

class ClassifyChat:
    def __init__(self, model_path='./trained_model'):
        self.device = torch.device('cuda') if torch.cuda.is_available() else torch.device('cpu')
        self.model = RobertaForSequenceClassification.from_pretrained(model_path).to(self.device)
        self.tokenizer = RobertaTokenizer.from_pretrained(model_path)
        self.model.eval()
        self.label_mapping = {0: 'crypto', 1: 'human'}

    def predict(self, text: str):
        """
        Predicts the class (crypto/human) and probability for a single text.
        Returns a tuple: (prediction_label, probability)
        """
        if not isinstance(text, str):
            raise TypeError("Input must be a string.")

        encodings = self.tokenizer(text, truncation=True, padding=True, max_length=128, return_tensors='pt')
        encodings = {key: val.to(self.device) for key, val in encodings.items()}
        
        with torch.no_grad():
            outputs = self.model(**encodings)
            logits = outputs.logits
            probs = F.softmax(logits, dim=-1)
            prediction_idx = torch.argmax(probs, dim=-1).item()
        
        prediction_label = self.label_mapping[prediction_idx]
        probability = probs[0][prediction_idx].item()
        
        return prediction_label, probability