import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import nltk
from nltk.corpus import stopwords

nltk.download('stopwords', quiet=True)
russian_stopwords = stopwords.words("russian")


class ProductSearch:
    def __init__(self, csv_file):
        # Читаем CSV с разделителем ";"
        self.df = pd.read_csv(csv_file, sep=';')
        # Объединяем название, описание и категорию для поиска
        self.df['text'] = (
            self.df['name'].fillna('') + " " +
            self.df['description'].fillna('') + " " +
            self.df['category'].fillna('')
        )
        # Создаем TF-IDF матрицу с использованием русского списка стоп-слов
        self.vectorizer = TfidfVectorizer(stop_words=russian_stopwords)
        self.tfidf_matrix = self.vectorizer.fit_transform(self.df['text'])

    def search(self, query, threshold=0.2, top_n=3):
        query_vec = self.vectorizer.transform([query])
        similarities = cosine_similarity(query_vec, self.tfidf_matrix).flatten()
        top_indices = similarities.argsort()[::-1][:top_n]
        results = []
        for idx in top_indices:
            product = self.df.iloc[idx]
            results.append({
                'name': product['name'],
                'category': product['category'],
                'description': product['description'],
                'price': product['price'],
                'link': product['link'],
                'score': similarities[idx]
            })
        # Если максимальная оценка похожести ниже порога, требуется уточнение запроса
        need_clarification = similarities.max() < threshold
        return results, need_clarification


# Создаем экземпляр поиска товаров (файл dataset.csv должен находиться в корне проекта)
product_search_instance = ProductSearch("dataset.csv")
