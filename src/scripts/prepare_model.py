# scripts/prepare_model.py
import pandas as pd
import os

# --- Configuration ---
# These paths point to the raw data files. They should be updated to match their location on your machine.
HOME_DIR = os.path.expanduser('~')
RAW_TWITTER_DATA_PATH = os.path.join(HOME_DIR, "Downloads", "Merged_Twitter_Data_IDsRemoved.csv")
RAW_HUMAN_DATA_PATH = os.path.join(HOME_DIR, "Downloads", "human_chat.txt")
OUTPUT_CSV_PATH = os.path.join(HOME_DIR, "Downloads", "crypto_human_prepared.csv")
NUM_TWITTER_SAMPLES = 7000

def prepare_training_data():
    """
    Loads raw Twitter and human chat data, processes them, combines them,
    shuffles the result, and saves it as a single CSV file for model training.
    This function preserves the exact data processing pipeline from the original code.
    """
    print(f"--- 1. Loading Twitter data from: {RAW_TWITTER_DATA_PATH} ---")
    try:
        raw_twitter_df = pd.read_csv(RAW_TWITTER_DATA_PATH, encoding="ISO-8859-1")
    except FileNotFoundError:
        print(f"Error: Twitter data file not found. Please check the path and run again.")
        return

    twitter_data = pd.DataFrame()
    twitter_data['text'] = raw_twitter_df['text'].head(NUM_TWITTER_SAMPLES)
    twitter_data['label'] = 'crypto'
    print(f"Processed {len(twitter_data)} samples of crypto data.")

    print(f"\n--- 2. Loading human chat data from: {RAW_HUMAN_DATA_PATH} ---")
    try:
        human_chat_df = pd.read_csv(RAW_HUMAN_DATA_PATH, delimiter="\t", header=None)
    except FileNotFoundError:
        print(f"Error: Human chat data file not found. Please check the path and run again.")
        return

    human_messages_list = []
    if len(human_chat_df.columns) > 0:
        human_messages_list.extend(human_chat_df[0].dropna().tolist())
    if len(human_chat_df.columns) > 1:
        human_messages_list.extend(human_chat_df[1].dropna().tolist())

    human_data = pd.DataFrame()
    human_data['text'] = human_messages_list
    human_data['label'] = 'human'
    print(f"Processed {len(human_data)} samples of human data.")

    print("\n--- 3. Combining, Shuffling, and Saving ---")
    combined_df = pd.concat([human_data, twitter_data], ignore_index=True)
    shuffled_df = combined_df.sample(frac=1).reset_index(drop=True)
    print(f"Combined dataset created with {len(shuffled_df)} total samples.")

    try:
        shuffled_df.to_csv(OUTPUT_CSV_PATH, index=False)
        print(f"\nSuccessfully saved prepared data to: {OUTPUT_CSV_PATH}")
    except Exception as e:
        print(f"\nError saving final CSV file: {e}")

if __name__ == "__main__":
    prepare_training_data()