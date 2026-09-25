"""
Detector Temático y Extractor de Palabras Clave Local (Zero-Token Topic Modeling).
Utiliza TF-IDF con stopwords en español para identificar los temas tratados sin consumir tokens de API.
"""

import re
from typing import List, Tuple
from sklearn.feature_extraction.text import TfidfVectorizer

# Stopwords en español incluyendo modismos vacíos comunes
SPANISH_STOPWORDS = [
    "de", "la", "que", "el", "en", "y", "a", "los", "del", "se", "las", "por", "un", "para", "con", "no", "una",
    "su", "al", "lo", "como", "mas", "pero", "sus", "le", "ya", "o", "este", "si", "porque", "esta", "entre",
    "cuando", "muy", "sin", "sobre", "tambien", "me", "hasta", "hay", "donde", "quien", "desde", "todo", "nos",
    "durante", "todos", "uno", "les", "ni", "contra", "otros", "ese", "eso", "ante", "ellos", "e", "esto", "mi",
    "antes", "algunos", "que", "unos", "yo", "otro", "otras", "otra", "el", "tanto", "esa", "estos", "mucho",
    "quienes", "nada", "muchos", "cual", "poco", "ella", "estar", "estas", "algunas", "algo", "nosotros", "mi",
    "mis", "tu", "te", "ti", "tu", "tus", "ellas", "nosotras", "vosostros", "vosotras", "os", "mio", "mia", "mios",
    "mias", "tuyo", "tuya", "tuyos", "tuyas", "suyo", "suya", "suyos", "suyas", "nuestro", "nuestra", "nuestros",
    "nuestras", "vuestro", "vuestra", "vuestros", "vuestras", "esos", "esas", "estoy", "estas", "esta", "estamos",
    "estais", "estan", "este", "estes", "estemos", "esteis", "esten", "estare", "estaras", "estara", "estaremos",
    "estareis", "estaran", "estaria", "estarias", "estariamos", "estariais", "estarian", "estaba", "estabas",
    "estabamos", "estabais", "estaban", "estuve", "estuviste", "estuvo", "estuvimos", "estuvisteis", "estuvieron",
    "hubiera", "hubieras", "hubieramos", "hubierais", "hubieran", "hubiese", "hubieses", "hubiesemos", "hubieseis",
    "hubiesen", "habiendo", "habido", "habida", "habidos", "habidas", "soy", "eres", "es", "somos", "sois", "son",
    "sea", "seas", "seamos", "seais", "sean", "sere", "seras", "sera", "seremos", "sereis", "seran", "seria",
    "serias", "seriamos", "seriais", "serian", "era", "eras", "eramos", "erais", "eran", "fui", "fuiste", "fue",
    "fuimos", "fuisteis", "fueron", "tengo", "tienes", "tiene", "tenemos", "teneis", "tienen", "tenga", "tengas",
    "tengamos", "tengais", "tengan", "tendre", "tendras", "tendra", "tendremos", "tendreis", "tendran", "tendria",
    "tendrias", "tendriamos", "tendriais", "tendrian", "tenia", "tenias", "teniamos", "teniais", "tenian", "tuve",
    "tuviste", "tuvo", "tuvimos", "tuvisteis", "tuvieron",
    # Modismos de relleno conversacional
    "bo", "ta", "che", "bueno", "dale", "pará", "para", "viste", "mirá", "mira", "tipo", "o sea", "sea", "ahí", "ahi"
]


class TopicDetector:
    def __init__(self, top_n_keywords: int = 5):
        self.top_n_keywords = top_n_keywords
        self.stopwords = set(SPANISH_STOPWORDS)

    def extract_keywords(self, texts: List[str]) -> List[str]:
        """Extrae las palabras clave más representativas de un conjunto de textos mediante TF-IDF."""
        if not texts:
            return []

        joined_text = " ".join(texts).lower()
        cleaned_text = re.sub(r"[^\w\s]", " ", joined_text)

        tokens = [w for w in cleaned_text.split() if len(w) > 2 and w not in self.stopwords]
        if not tokens:
            return []

        try:
            vectorizer = TfidfVectorizer(
                stop_words=SPANISH_STOPWORDS,
                max_features=self.top_n_keywords,
                token_pattern=r"(?u)\b[a-zA-ZáéíóúÁÉÍÓÚñÑ]{3,}\b",
            )
            # Analizar el texto
            tfidf_matrix = vectorizer.fit_transform([" ".join(tokens)])
            feature_names = vectorizer.get_feature_names_out()
            scores = tfidf_matrix.toarray()[0]
            ranked = sorted(zip(feature_names, scores), key=lambda x: x[1], reverse=True)
            return [word for word, score in ranked[: self.top_n_keywords]]
        except Exception:
            # Fallback simple por conteo de frecuencias
            counts = {}
            for w in tokens:
                counts[w] = counts.get(w, 0) + 1
            sorted_counts = sorted(counts.items(), key=lambda x: x[1], reverse=True)
            return [w for w, _ in sorted_counts[: self.top_n_keywords]]

    def classify_thread_intent(self, texts: List[str]) -> str:
        """Determina la intención o dinámica conversacional predominante del hilo."""
        combined = " ".join(texts).lower()

        # 1. Patrones de chicanas afectuosas / bromas / risas (prioridad alta)
        if any(w in combined for w in ["jaja", "jeje", "jiji", "fiera", "troche", "que rico", "loco", "cabeza", "cagar"]):
            return "Broma / Chicana Afectuosa"

        # 2. Coordinación de llamada o juego
        if any(w in combined for w in ["salgamos", "entrar", "jugar", "partida", "discord", "audio", "mic"]):
            return "Coordinación de Llamada / Juego"

        # 3. Patrones de pregunta técnica o verificación
        if "?" in combined or "¿" in combined:
            if any(w in combined for w in ["anda", "funciona", "rompió", "error", "bot", "código"]):
                return "Consulta Técnica / Verificación"
            return "Pregunta / Indagación"

        if any(w in combined for w in ["por qué", "como hago", "quién es"]):
            return "Pregunta / Indagación"

        return "Charla Casual"
