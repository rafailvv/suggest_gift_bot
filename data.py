import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import nltk
from nltk.corpus import stopwords
import re
import ssl
ssl._create_default_https_context = ssl._create_unverified_context

nltk.download('stopwords', quiet=True)
russian_stopwords = stopwords.words("russian")


class ProductSearch:
    def __init__(self, csv_file):
        # Читаем CSV с разделителем ";"
        self.df = pd.read_csv(csv_file, sep=';')
        # Предварительная очистка столбца с ценами: удаляем пробелы и заменяем запятые на точки
        self.df['price'] = self.df['price'].astype(str).str.replace(r'\s+', '', regex=True)
        self.df['price'] = self.df['price'].str.replace(',', '.')
        # Преобразуем цену к числовому значению, некорректные значения становятся NaN
        self.df['price'] = pd.to_numeric(self.df['price'], errors='coerce')
        # Если нужно, можно удалить записи с отсутствующей ценой
        self.df = self.df[self.df['price'].notnull()]

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
        # Ищем шаблон "до <число> рублей" в запросе
        price_limit = None
        price_pattern = re.compile(r'до\s*(\d+)\s*руб', re.IGNORECASE)
        price_match = price_pattern.search(query)
        if price_match:
            price_limit = float(price_match.group(1))
            # Удаляем часть запроса с фильтром цены, чтобы она не влияла на поиск по тексту
            query = price_pattern.sub('', query).strip()

        # Преобразуем запрос в вектор
        query_vec = self.vectorizer.transform([query])

        # Если указано ограничение по цене, сначала фильтруем товары
        if price_limit is not None:
            price_mask = self.df['price'].notnull() & (self.df['price'] < price_limit)
            if not price_mask.any():
                # Если нет товаров с подходящей ценой, возвращаем пустой список
                return [], True
            # Выбираем индексы товаров, удовлетворяющих условию
            filtered_indices = self.df.index[price_mask]
            # Вычисляем похожесть только для отфильтрованных товаров
            similarities = cosine_similarity(query_vec, self.tfidf_matrix[filtered_indices]).flatten()
            # Сопоставляем вычисленные похожести с исходными индексами
            sorted_idx = similarities.argsort()[::-1][:top_n]
            result_indices = filtered_indices[sorted_idx]
        else:
            # Если ограничения по цене нет, считаем похожесть для всех товаров
            similarities = cosine_similarity(query_vec, self.tfidf_matrix).flatten()
            sorted_idx = similarities.argsort()[::-1][:top_n]
            result_indices = self.df.index[sorted_idx]

        results = []
        for idx in result_indices:
            product = self.df.loc[idx]
            # Если цена отсутствует, можем пропускать или оставлять значение None
            results.append({
                'name': product['name'],
                'category': product['category'],
                'description': product['description'],
                'price': product['price'],
                'link': product['link'],
                'score': similarities[sorted_idx[list(result_indices).index(idx)]]
            })

        # Если максимальная оценка похожести ниже порога, требуется уточнение запроса
        overall_max_score = similarities.max() if len(similarities) > 0 else 0
        need_clarification = overall_max_score < threshold
        # Если максимальная оценка больше или равна 0.45, возвращаем только лучший результат
        if overall_max_score >= 0.45:
            results = results[:1]
        return results, need_clarification


# Создаем экземпляр поиска товаров (файл dataset.csv должен находиться в корне проекта)
product_search_instance = ProductSearch("dataset.csv")
