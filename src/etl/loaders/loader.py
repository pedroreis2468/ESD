import pandas as pd
from sqlalchemy import create_engine
import logging

# Configuração do DW
DW_CONFIG = {
    "host": "localhost",
    "port": 5433,
    "database": "DW",
    "username": "DW",
    "password": "DW",
    "schema": "DW"
}

def get_dw_engine():
    conn_str = f"postgresql://{DW_CONFIG['username']}:{DW_CONFIG['password']}@{DW_CONFIG['host']}:{DW_CONFIG['port']}/{DW_CONFIG['database']}"
    return create_engine(conn_str)

def load_to_dw(df: pd.DataFrame, table_name: str):
    """
    Carrega um DataFrame para a tabela destino no DW.
    Modo: 'append' (Acrescentar).
    """
    if df.empty:
        logging.info(f"   ℹ️ Nada para carregar em {table_name}.")
        return

    engine = get_dw_engine()
    
    try:
        # Garante nome em minúsculas para compatibilidade com Postgres
        table_name_clean = table_name.lower()
        
        # O SEGREDO: if_exists='append' adiciona ao fundo da tabela sem apagar o histórico
        df.to_sql(
            name=table_name_clean,
            con=engine,
            schema=DW_CONFIG['schema'],
            if_exists='append', 
            index=False,
            method='multi',  # Otimização para grandes volumes de dados
            chunksize=1000   # Insere em blocos para não bloquear a memória
        )
        logging.info(f"✅ Sucesso: {len(df)} linhas carregadas na tabela {table_name_clean}")
        
    except Exception as e:
        logging.error(f"❌ Erro ao carregar {table_name}: {e}")
        # Opcional: Se quiseres que o script pare imediatamente ao dar erro, descomenta a linha abaixo:
        # raise e