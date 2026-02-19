import pandas as pd
import numpy as np
import re
from datetime import datetime
import nltk
from nltk.corpus import stopwords
from collections import Counter
from textblob import TextBlob 
import os

try:
    nltk.data.find('corpora/stopwords')
except LookupError:
    nltk.download('stopwords')

stop_words = set(stopwords.words('portuguese'))
QUARANTINE_PATH = "quarentena/"

def send_to_quarantine(df, reason, entity_type):
    if df.empty: return
    if not os.path.exists(QUARANTINE_PATH):
        os.makedirs(QUARANTINE_PATH)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_reason = reason.replace(" ", "_").lower()
    filename = f"{QUARANTINE_PATH}erro_{entity_type}_{safe_reason}_{timestamp}.csv"
    df.to_csv(filename, index=False, encoding='utf-8-sig')
    print(f"⚠️ QUARENTENA (MONGO): {len(df)} registos de {entity_type} movidos para {filename}")

# --- NLP ---
def clean_text(text: str) -> str:
    if pd.isna(text): return ""
    text = str(text).lower()
    text = re.sub(r'\d+', '', text)
    text = re.sub(r'[^\w\s]', '', text)
    return text

def extract_top_terms(text: str, n=3) -> str:
    cleaned = clean_text(text)
    tokens = [word for word in cleaned.split() if word not in stop_words and len(word) > 2]
    if not tokens: return "n/a"
    most_common = Counter(tokens).most_common(n)
    return ", ".join([word for word, count in most_common])

def extract_emotions(text: str) -> str:
    analysis = TextBlob(text)
    pol = analysis.sentiment.polarity
    if pol > 0.5: return "Felicidade, Entusiasmo"
    elif pol > 0: return "Satisfação"
    elif pol < -0.5: return "Raiva, Deceção"
    elif pol < 0: return "Tristeza"
    return "Neutro"

def transform_dim_feedback(df_reviews: pd.DataFrame) -> pd.DataFrame:
    print("🧠 A processar DimFeedback (NLP)...")
    df = df_reviews.copy()
    df["feedback_id"] = range(1, len(df) + 1)
    df["top3termos"] = df["review"].apply(lambda x: extract_top_terms(x))
    df["top3emocoes"] = df["review"].apply(lambda x: extract_emotions(str(x)))
    
    df_final = df[["feedback_id", "top3termos", "top3emocoes"]].copy()
    return df_final, df[["_id", "feedback_id"]] 

# --- FACTO REVIEWS ---
def get_polarity(text):
    if pd.isna(text): return 0.0
    return TextBlob(str(text)).sentiment.polarity

def transform_tf_reviews(df_reviews, map_mongo_feedback, lookup_manager, df_dim_cliente, df_dim_zona):
    print("📊 A processar TFReviews...")
    df = df_reviews.copy()
    
    # 1. Join com Feedback ID
    df = pd.merge(df, map_mongo_feedback, on="_id", how="left")
    
    # 2. Resolver Cliente (SK) via Email
    def resolve_client(row):
        email = row.get("email")
        # NIF=0 porque Mongo não tem NIF
        return lookup_manager.get_or_create_sk(nif_input=0, email_input=email)

    df["cliente_id"] = df.apply(resolve_client, axis=1)

    # 3. Resolver Zona (O Passo Crítico)
    # A review tem cliente_id. Vamos buscar o distrito desse cliente_id à DimCliente carregada do SQL.
    
    # Fazemos merge com a DimCliente para obter o 'distrito'
    df = pd.merge(df, df_dim_cliente[["cliente_id", "distrito"]], on="cliente_id", how="left")
    
    # Agora fazemos merge com a DimZona usando esse distrito recuperado
    df = pd.merge(df, df_dim_zona, on="distrito", how="left")
    
    # VALIDAÇÃO DE ZONA:
    # Se zona_id for NaN, significa que ou o cliente é novo (stub sem distrito)
    # ou o distrito do cliente não existe no geo. Como não podemos usar -1, vai para QUARENTENA.
    
    missing_zona_mask = df["zona_id"].isna()
    if missing_zona_mask.any():
        send_to_quarantine(df[missing_zona_mask], "Cliente sem distrito ou Zona inexistente", "tf_reviews")
        df = df[~missing_zona_mask].copy()

    # 4. Tratamento Data
    df["data"] = pd.to_datetime(df["data"], dayfirst=True, errors='coerce').dt.date
    invalid_dates = df[df["data"].isna()]
    if not invalid_dates.empty:
        send_to_quarantine(invalid_dates, "Data invalida", "tf_reviews")
        df = df.dropna(subset=["data"])

    # 5. Métricas
    df["polaridade"] = df["review"].apply(get_polarity)
    df["estrelas"] = pd.to_numeric(df["rating"], errors='coerce').fillna(0).astype(int)
    
    invalid_stars = df[(df["estrelas"] < 1) | (df["estrelas"] > 5)]
    if not invalid_stars.empty:
        send_to_quarantine(invalid_stars, "Rating invalido", "tf_reviews")
        df = df[(df["estrelas"] >= 1) & (df["estrelas"] <= 5)]

    # 6. Construção Final
    tf_reviews = pd.DataFrame()
    tf_reviews["produto_id"] = df["id_produto"]
    tf_reviews["cliente_id"] = df["cliente_id"]
    tf_reviews["data"] = df["data"]
    tf_reviews["zona_id"] = df["zona_id"].astype(int) # Garantir int
    tf_reviews["feedback_id"] = df["feedback_id"]
    tf_reviews["polaridade"] = df["polaridade"]
    tf_reviews["estrelas"] = df["estrelas"]
    
    return tf_reviews