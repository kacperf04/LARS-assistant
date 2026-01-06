import joblib

classifier = joblib.load('./classifier/pkl/multinomial_naive_bayes.pkl')
vectorizer = joblib.load('./classifier/pkl/vectorizer.pkl')

if __name__ == "__main__":
    while True:
        query = input("Enter a query: ")
        query_vector = vectorizer.transform([query])
        prediction = classifier.predict(query_vector)[0]
        print(f"Prediction: {prediction}")