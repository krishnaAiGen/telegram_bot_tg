# prepare_model.py
import pandas as pd

# --- Configuration: Define file paths at the top for easy modification ---
RAW_TWITTER_DATA_PATH = "/Users/krishnayadav/Downloads/Merged_Twitter_Data_IDsRemoved.csv"
RAW_HUMAN_DATA_PATH = "/Users/krishnayadav/Downloads/human_chat.txt"
OUTPUT_CSV_PATH = "/Users/krishnayadav/Downloads/crypto_human_prepared.csv"
NUM_TWITTER_SAMPLES = 7000

def prepare_training_data():
    """
    Loads raw Twitter and human chat data, processes them, combines them,
    and saves the result as a single CSV file ready for model training.
    """
    print("--- 1. Loading and Processing Crypto (Twitter) Data ---")
    # Load only the 'text' column to save memory, handling potential encoding issues.
    raw_twitter_df = pd.read_csv(RAW_TWITTER_DATA_PATH, usecols=['text'], encoding="ISO-8859-1")
    
    # Create a new DataFrame with the required samples and label
    crypto_data = pd.DataFrame()
    crypto_data['text'] = raw_twitter_df['text'].head(NUM_TWITTER_SAMPLES)
    crypto_data['label'] = 'crypto'
    print(f"Loaded {len(crypto_data)} samples of crypto data.")

    print("\n--- 2. Loading and Processing Human Chat Data ---")
    # Load the tab-separated human chat data, assuming no header row
    raw_human_df = pd.read_csv(RAW_HUMAN_DATA_PATH, delimiter="\t", header=None)
    
    # Concatenate all columns from the human chat file into a single list of messages
    human_messages = []
    for col in raw_human_df.columns:
        # Drop missing values before adding to the list
        human_messages.extend(raw_human_df[col].dropna().tolist())

    human_data = pd.DataFrame()
    human_data['text'] = human_messages
    human_data['label'] = 'human'
    print(f"Loaded {len(human_data)} samples of human data.")

    print("\n--- 3. Combining and Shuffling Data ---")
    # Combine the two datasets
    combined_df = pd.concat([crypto_data, human_data], ignore_index=True)
    
    # Shuffle the entire dataset to ensure random distribution of samples
    # frac=1 means shuffle 100% of the rows. reset_index cleans up the index after shuffling.
    shuffled_df = combined_df.sample(frac=1).reset_index(drop=True)
    print(f"Combined and shuffled data. Total samples: {len(shuffled_df)}")

    print(f"\n--- 4. Saving Prepared Data ---")
    # Save the final prepared dataset to a new CSV file
    try:
        shuffled_df.to_csv(OUTPUT_CSV_PATH, index=False)
        print(f"Successfully saved prepared data to: {OUTPUT_CSV_PATH}")
    except Exception as e:
        print(f"Error saving file: {e}")

if __name__ == "__main__":
    prepare_training_data()