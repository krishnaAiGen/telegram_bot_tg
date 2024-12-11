
import pandas as pd

twitter_data_csv = pd.read_csv("/Users/krishnayadav/Downloads/Merged_Twitter_Data_IDsRemoved.csv", encoding="ISO-8859-1")
twitter_data = pd.DataFrame(columns=['text'])
twitter_data['text'] = twitter_data_csv.iloc[:7000]["text"]
twitter_data['label'] = 'crypto'

human_data = df = pd.read_csv("/Users/krishnayadav/Downloads/human_chat.txt" , delimiter="\t")  # Read without headers
humn_data_cols = human_data.columns

human_data_list = list(human_data[humn_data_cols[0]]) + list(human_data[humn_data_cols[1]])

human_data = pd.DataFrame(columns=['text'])
human_data['text'] = human_data_list
human_data['label'] = 'human'


crypto_human = pd.concat([human_data, twitter_data], axis = 0)
crypto_human = crypto_human.sample(frac=1).reset_index(drop=True)

crypto_human.to_csv("/Users/krishnayadav/Downloads/crypto_human.csv")
