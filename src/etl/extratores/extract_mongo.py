import pandas as pd
from pymongo import MongoClient
from sqlalchemy import create_engine, text
from datetime import datetime
import logging

# Configuração de Logs
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')

# Configurações do Mongo e DW
MONGO_URI = "mongodb://mongodb:mongodb@localhost:27017/?authSource=admin"
MONGO_DB = "mongodb"
MONGO_COLLECTION = "mycollection"

DW_DB = {
    "host": "localhost",
    "port": 5433,
    "database": "DW",
    "username": "DW",
    "password": "DW"
}

def get_dw_engine():
    conn_str = f"postgresql://{DW_DB['username']}:{DW_DB['password']}@{DW_DB['host']}:{DW_DB['port']}/{DW_DB['database']}"
    return create_engine(conn_str)

def extract_reviews_delta():
    """
    Extrai reviews do MongoDB incrementalmente baseando-se na data máxima do DW.
    """
    dw_engine = get_dw_engine()
    
    # 1. Ler Watermark (Última data carregada no DW)
    last_date = datetime(1900, 1, 1) # Data muito antiga por defeito
    
    try:
        with dw_engine.connect() as conn:
            # --- CORREÇÃO FEITA AQUI: 'tfreviews' em minúsculas ---
            # O Postgres é sensível a maiúsculas quando usamos aspas
            query = text('SELECT MAX("data") FROM "DW"."tfreviews"')
            res = conn.execute(query).fetchone()
            
            if res and res[0]:
                # Converter para datetime Python
                last_date = pd.to_datetime(res[0])
                logging.info(f"ℹ️ Última review no DW: {last_date}")
            else:
                logging.info("ℹ️ DW de Reviews vazio (ou sem datas). Será feita Carga total.")
                
    except Exception as e:
        # Se a tabela não existir, assume carga total
        logging.warning(f"⚠️ Aviso ao ler Watermark Reviews: {e}")

    # 2. Conectar ao Mongo
    client = MongoClient(MONGO_URI)
    db = client[MONGO_DB]
    collection = db[MONGO_COLLECTION]

    # 3. Construir a Query Incremental
    # Converter datas para strings ISO (YYYY-MM-DD) ou datetime nativo dependendo de como está no Mongo
    # Assumindo que no Mongo guardas como string ou ISODate
    
    # Nota: Se no Mongo a data for string "YYYY-MM-DD", usamos strftime.
    # Se for objeto Date(), podes passar o datetime direto. Vamos assumir string para segurança:
    str_last_date = last_date.strftime('%Y-%m-%d')
    str_cutoff_date = datetime.now().strftime('%Y-%m-%d')
    
    query_mongo = {
        "data": {
            "$gt": str_last_date,     # Maior que a última do DW
            "$lt": str_cutoff_date    # Menor que "hoje" (para consistência)
        }
    }
    
    logging.info(f"⏳ A consultar MongoDB com filtro: {query_mongo}")
    
    # 4. Executar
    cursor = collection.find(query_mongo)
    reviews_list = list(cursor)
    
    if not reviews_list:
        logging.info("zzz Nenhuma review nova encontrada nesta janela de tempo.")
        return pd.DataFrame()

    logging.info(f"   -> Reviews extraídas: {len(reviews_list)}")
    
    # 5. Converter para DataFrame
    df = pd.DataFrame(reviews_list)
    
    # Limpeza do _id (ObjectId não é serializável facilmente)
    if "_id" in df.columns:
        df["_id"] = df["_id"].astype(str)
        
    return df