"""
User intent classifier. Uses Multinomial Naive Bayes to classify user queries into given labels corresponding to actions users want the LLM to perform.
"""
import os.path
from typing import Tuple

import joblib
import pandas as pd
from sklearn.calibration import CalibratedClassifierCV
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics import accuracy_score
from sklearn.model_selection import train_test_split
from sklearn.naive_bayes import MultinomialNB

TRAINING_DATA_PATH = "./training_data/"
MODEL_PATH = "./pkl/"

def sort_and_save_data(df: pd.DataFrame) -> None:
    """
    Sorts the dataframe by label and saves it to a csv file
    :param df -- dataframe to sort
    :return -- None
    """
    sorted_df = df.sort_values(by=["label"], ascending=True)
    sorted_df.to_csv(os.path.join(TRAINING_DATA_PATH, "sorted_training_data.csv"), index=False)


def train_and_validate(df_train: pd.DataFrame) -> float:
    """
    Performs training using Multinomial Naive Bayes and validates on a held-out set.
    :param df_train -- training dataframe
    :return -- accuracy score
    """
    train_df, validate_df = train_test_split(df_train, test_size=0.2, stratify=df_train["label"],random_state=42)
    train_df, validate_df = clean_data(train_df, validate_df)

    vectorizer = TfidfVectorizer(
        ngram_range=(1, 2),
        lowercase=True,
        max_features=10000,
        min_df=2
    )
    train_vectors = vectorizer.fit_transform(train_df["query"])
    validate_vectors = vectorizer.transform(validate_df["query"])

    model = MultinomialNB(alpha=0.2)
    model.fit(train_vectors, train_df["label"])

    calibrated_model = CalibratedClassifierCV(model, method="sigmoid")
    calibrated_model.fit(train_vectors, train_df["label"])

    validate_predictions = calibrated_model.predict(validate_vectors)
    accuracy = accuracy_score(validate_df["label"], validate_predictions)

    print(f"Accuracy: {accuracy:.2f}")

    joblib.dump(calibrated_model, os.path.join(MODEL_PATH, "multinomial_naive_bayes.pkl"))
    joblib.dump(vectorizer, os.path.join(MODEL_PATH, "vectorizer.pkl"))
    print(f"Model and vectorizer saved to {os.path.abspath(MODEL_PATH)}/")

    return accuracy


def clean_data(train_df: pd.DataFrame, validate_df: pd.DataFrame) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """
    Searches for duplicate queries in the training and validation data and removes them from the validation data.
    :param train_df -- training dataframe
    :param validate_df -- validation dataframe
    :return -- cleaned training and validation dataframes
    """
    train_df = train_df.drop_duplicates(subset=["query"])
    validate_df = validate_df.drop_duplicates(subset=["query"])

    common_queries = set(train_df["query"]).intersection(set(validate_df["query"]))
    if common_queries:
        print(f"Dropping {len(common_queries)} duplicate queries from validation data due to overlap with training data.")
        validate_df = validate_df[~validate_df["query"].isin(common_queries)]
        print("Validation data cleaned.")
    else:
        print("No duplicate queries found in validation data.")

    return train_df, validate_df

if __name__ == "__main__":
    df = pd.read_csv(os.path.join(TRAINING_DATA_PATH, "training_data.csv"))
    sort_and_save_data(df)
    train_and_validate(df)