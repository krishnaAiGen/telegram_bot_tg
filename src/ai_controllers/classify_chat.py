# src/ai_controllers/classify_chat.py
import torch
from transformers import RobertaTokenizer, RobertaForSequenceClassification
import torch.nn.functional as F

class ClassifyChat:
    """
    A class to load a pre-trained transformer model and use it for
    classifying text into 'crypto' or 'human' categories.
    """
    def __init__(self, model_path: str):
        # Automatically select GPU if available, otherwise fall back to CPU
        self.device = torch.device('cuda') if torch.cuda.is_available() else torch.device('cpu')
        print(f"Classifier using device: {self.device}")

        try:
            # Load the fine-tuned model and tokenizer from the specified path
            self.model = RobertaForSequenceClassification.from_pretrained(model_path).to(self.device)
            self.tokenizer = RobertaTokenizer.from_pretrained(model_path)
        except Exception as e:
            raise IOError(f"Failed to load model from path: {model_path}. Error: {e}")

        # Set the model to evaluation mode, which is crucial for correct predictions
        self.model.eval()
        self.label_mapping = {0: 'crypto', 1: 'human'}

    def predict(self, text: str) -> tuple[str, float]:
        """
        Predicts the class and probability for a single text input.
        This version is corrected to handle only single strings for clarity and fix previous bugs.
        """
        if not isinstance(text, str):
            raise TypeError("Input must be a single string.")

        # Tokenize the input and prepare it for the model
        encodings = self.tokenizer(text, truncation=True, padding=True, max_length=128, return_tensors='pt')
        encodings = {key: val.to(self.device) for key, val in encodings.items()}
        
        # Disable gradient calculations for faster, more memory-efficient inference
        with torch.no_grad():
            outputs = self.model(**encodings)
            logits = outputs.logits
            # Use softmax to convert raw logits into probabilities
            probs = F.softmax(logits, dim=-1)
            # Find the index with the highest probability
            prediction_idx = torch.argmax(probs, dim=-1).item()
        
        # Map the index to its label
        prediction_label = self.label_mapping[prediction_idx]
        # Get the actual probability score for the predicted label
        probability_score = probs[0][prediction_idx].item()
        
        return prediction_label, probability_score