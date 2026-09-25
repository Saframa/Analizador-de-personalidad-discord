"""
Normalizador de texto para síntesis de voz (TTS) con dialecto Rioplatense y Uruguayo.
Prepara el texto del chat para una pronunciación natural y previene anomalías en vocoders.
"""

import re
from typing import List


def normalize_text_for_tts(text: str) -> str:
    """
    Normaliza texto de chat informal para sintetizadores de voz en español.
    
    1. Estandariza vocales alargadas de énfasis (ej. 'boooo' -> 'bo', 'taaaa' -> 'ta').
    2. Expande abreviaciones coloquiales frecuentes en Discord.
    3. Reemplaza símbolos matemáticos y comerciales por sus nombres fonéticos.
    4. Remueve emojis y secuencias de caracteres que puedan generar ruido en el vocoder.
    """
    if not text:
        return ""

    # 1. Normalización de modismos uruguayos con vocales estiradas
    text = re.sub(r"\bbo+\b", "bo", text, flags=re.IGNORECASE)
    text = re.sub(r"\bta+\b", "ta", text, flags=re.IGNORECASE)
    text = re.sub(r"\bche+\b", "che", text, flags=re.IGNORECASE)
    text = re.sub(r"\bs[iíÍ]+\b", "sí", text, flags=re.IGNORECASE)
    text = re.sub(r"\bno+\b", "no", text, flags=re.IGNORECASE)

    # 2. Expansión de abreviaciones comunes de chat
    replacements = [
        (r"\bxq\b", "porque"),
        (r"\bx\s*que\b", "porque"),
        (r"\bporfa\b", "por favor"),
        (r"\bxfa\b", "por favor"),
        (r"\bdnd\b", "de nada"),
        (r"\btmb\b", "también"),
        (r"\btb\b", "también"),
        (r"\bq\b", "que"),
        (r"\bk\b", "que"),
        (r"\bmsg\b", "mensaje"),
        (r"\bwsp\b", "whatsapp"),
    ]
    for pattern, repl in replacements:
        text = re.sub(pattern, repl, text, flags=re.IGNORECASE)

    # 3. Expansión de símbolos a palabras fonéticas
    text = text.replace("%", " por ciento ")
    text = text.replace("&", " y ")
    text = text.replace("+", " más ")
    text = text.replace("/", " o ")
    text = text.replace("@", " arroba ")

    # 4. Remover URLs o menciones tipo Discord
    text = re.sub(r"<@!?[0-9]+>", "", text)  # menciones <@12345>
    text = re.sub(r"https?://\S+", "", text)  # links

    # 5. Filtrar emojis y caracteres extraños, manteniendo puntuación y letras en español
    # Mantener: a-z, A-Z, 0-9, tildes (áéíóúÁÉÍÓÚñÑüÜ), signos de puntuación básicos
    text = re.sub(r"[^\w\s,.\?!¡¿:;\-—'\"]", " ", text)

    # 6. Colapsar signos de puntuación repetidos (ej. '....' -> '.', '???' -> '?')
    text = re.sub(r"\.{2,}", ".", text)
    text = re.sub(r"\?{2,}", "?", text)
    text = re.sub(r"!{2,}", "!", text)

    # 7. Normalizar espacios múltiples
    text = re.sub(r"\s+", " ", text).strip()

    return text


def chunk_text_by_sentences(text: str, max_words_per_chunk: int = 30) -> List[str]:
    """
    Divide un texto extenso en fragmentos lógicos delimitados por oraciones o puntuación,
    evitando que fragmentos individuales superen `max_words_per_chunk`.
    Esto optimiza la prosodia de los modelos de difusión y previene cortes de respiración.
    """
    text = text.strip()
    if not text:
        return []

    # Separar por delimitadores de fin de oración preservando el signo
    raw_sentences = re.split(r"(?<=[.!?])\s+", text)
    chunks: List[str] = []

    for sentence in raw_sentences:
        sentence = sentence.strip()
        if not sentence:
            continue

        words = sentence.split()
        if len(words) <= max_words_per_chunk:
            chunks.append(sentence)
        else:
            # Si una sola oración es muy larga, intentamos subdividir por comas o punto y coma
            sub_clauses = re.split(r"(?<=[,;])\s+", sentence)
            current_clause = ""
            for clause in sub_clauses:
                clause = clause.strip()
                if not clause:
                    continue
                combined = f"{current_clause} {clause}".strip() if current_clause else clause
                if len(combined.split()) <= max_words_per_chunk:
                    current_clause = combined
                else:
                    if current_clause:
                        chunks.append(current_clause)
                    current_clause = clause
            if current_clause:
                chunks.append(current_clause)

    return chunks if chunks else [text]
