# src/ai_controllers/prepare_model.py
import pandas as pd
import os

# --- Configuration ---
# All file paths are now defined at the top for easy modification.
# Using os.path.expanduser('~') makes the paths relative to the user's home directory,
# which is more portable than a fully hard-coded path.
HOME_DIR = os.path.expanduser('~')
RAW_TWITTER_DATA_PATH = os.path.join(HOME_DIR, "Downloads", "Merged_Twitter_Data_IDsRemoved.csv")
RAW_HUMAN_DATA_PATH = os.path.join(HOME_DIR, "Downloads", "human_chat.txt")
OUTPUT_CSV_PATH = os.path.join(HOME_DIR, "Downloads", "crypto_human_prepared.csv")
NUM_TWITTER_SAMPLES = 7000

def prepare_training_data():
    """
    Loads raw Twitter and human chat data, processes them, combines them,
    shuffles the result, and saves it as a single CSV file ready for model training.
    This function preserves the original data processing logic.
    """
    # --- 1. Loading and Processing Crypto (Twitter) Data ---
    # This section preserves the logic for loading the Twitter CSV.
    print(f"--- Loading Twitter data from: {RAW_TWITTER_DATA_PATH} ---")
    try:
        raw_twitter_df = pd.read_csv(RAW_TWITTER_DATA_PATH, encoding="ISO-8859-1")
    except FileNotFoundError:
        print(f"Error: Twitter data file not found. Please check the path.")
        return

    twitter_data = pd.DataFrame()
    twitter_data['text'] = raw_twitter_df['text'].head(NUM_TWITTER_SAMPLES)
    twitter_data['label'] = 'crypto'
    print(f"Processed {len(twitter_data)} samples of crypto data.")

    # --- 2. Loading and Processing Human Chat Data ---
    # This section preserves the logic for loading the tab-delimited human chat file.
    print(f"\n--- Loading human chat data from: {RAW_HUMAN_DATA_PATH} ---")
    try:
        human_chat_df = pd.read_csv(RAW_HUMAN_DATA_PATH, delimiter="\t", header=None)
    except FileNotFoundError:
        print(f"Error: Human chat data file not found. Please check the path.")
        return

    # This preserves the logic of combining the first two columns into a single list.
    human_chat_columns = human_chat_df.columns
    human_messages_list = []
    if len(human_chat_columns) > 0:
        human_messages_list.extend(human_chat_df[human_chat_columns[0]].dropna().tolist())
    if len(human_chat_columns) > 1:
        human_messages_list.extend(human_chat_df[human_chat_columns[1]].dropna().tolist())

    human_data = pd.DataFrame()
    human_data['text'] = human_messages_list
    human_data['label'] = 'human'
    print(f"Processed {len(human_data)} samples of human data.")

    # --- 3. Combining, Shuffling, and Saving ---
    # This preserves the final steps of your data pipeline.
    print("\n--- Combining and shuffling data ---")
    combined_df = pd.concat([human_data, twitter_data], ignore_index=True)
    
    # Shuffling is a crucial step for training a balanced model.
    shuffled_df = combined_df.sample(frac=1).reset_index(drop=True)
    print(f"Combined dataset created with {len(shuffled_df)} total samples.")

    try:
        shuffled_df.to_csv(OUTPUT_CSV_PATH, index=False)
        print(f"\nSuccessfully saved prepared data to: {OUTPUT_CSV_PATH}")
    except Exception as e:
        print(f"\nError saving final CSV file: {e}")

if __name__ == "__main__":
    prepare_training_data()