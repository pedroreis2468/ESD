import pandas as pd
from sqlalchemy import create_engine, text
from datetime import datetime, date
import logging
import numpy as np 

# Configuração de Logs
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')

# Configurações de DB
SOURCE_DB = {
    "host": "localhost",
    "port": 5434,
    "database": "relacional",
    "username": "relacional",
    "password": "relacional"
}

DW_DB = {
    "host": "localhost",
    "port": 5433,
    "database": "DW",
    "username": "DW",
    "password": "DW"
}

def get_engine(config):
    conn_str = f"postgresql://{config['username']}:{config['password']}@{config['host']}:{config['port']}/{config['database']}"
    return create_engine(conn_str)

def extract_sales_delta(schema="db"): 
    source_engine = get_engine(SOURCE_DB)
    dw_engine = get_engine(DW_DB)
    
    # 1. Definir janelas de tempo
    cutoff_date = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    
    # 2. Obter Watermark
    try:
        with dw_engine.connect() as conn:
            # --- CORREÇÃO AQUI ---
            # Antes: SELECT MAX("Data") FROM "DW"."TFVendas"
            # Agora: SELECT MAX("data") FROM "DW"."tfvendas" (Minúsculas para bater certo com o Postgres)
            result = conn.execute(text('SELECT MAX("data") FROM "DW"."tfvendas"')).fetchone()
            last_date_dw = result[0]
            
        if not last_date_dw:
            last_date_dw = datetime(1900, 1, 1)
        else:
            if isinstance(last_date_dw, date) and not isinstance(last_date_dw, datetime):
                last_date_dw = datetime.combine(last_date_dw, datetime.min.time())
            logging.info(f"ℹ️ Última data no DW: {last_date_dw}")
            
    except Exception as e:
        # Se a tabela não existir ou der erro, assume data antiga
        logging.warning(f"⚠️ Aviso ao ler Watermark: {e}")
        last_date_dw = datetime(1900, 1, 1)

    # 3. EXTRAÇÃO
    dataframes = {}

    logging.info(f"🔌 A conectar à origem ({SOURCE_DB['host']}:{SOURCE_DB['port']})...")
    
    with source_engine.connect() as conn:
        logging.info(f"⏳ A extrair dados do schema '{schema}'...")

        # --- A. VENDAS ---
        query_vendas = text(f"""
            SELECT * FROM {schema}.vendas 
            WHERE data_venda > :last_date AND data_venda < :cutoff_date
        """)
        df_vendas = pd.read_sql(query_vendas, conn, params={"last_date": last_date_dw, "cutoff_date": cutoff_date})
        dataframes['vendas'] = df_vendas
        logging.info(f"   -> Vendas extraídas: {len(df_vendas)}")
        
        # --- B. VENDA_PRODUTO ---
        if not df_vendas.empty:
            # 1. Obter IDs únicos (vêm como numpy.int64)
            vendas_ids_numpy = df_vendas['venda_id'].unique()
            
            # 2. CONVERSÃO EXPLÍCITA PARA PYTHON INT
            vendas_ids_list = [int(x) for x in vendas_ids_numpy]
            
            # 3. Construir string segura para SQL
            if len(vendas_ids_list) == 1:
                ids_str = f"({vendas_ids_list[0]})"
            else:
                ids_str = str(tuple(vendas_ids_list))
            
            # 4. Query
            logging.info(f"   -> A extrair itens para {len(vendas_ids_list)} vendas...")
            query_vp = text(f"SELECT * FROM {schema}.venda_produto WHERE venda_id IN {ids_str}")
            dataframes['venda_produto'] = pd.read_sql(query_vp, conn)
        else:
            dataframes['venda_produto'] = pd.DataFrame(columns=['id', 'venda_id', 'produto_id'])

        # --- C. CLIENTES ---
        logging.info("   -> A extrair Clientes...")
        dataframes['clientes'] = pd.read_sql(text(f"SELECT * FROM {schema}.clientes"), conn)
        
        # --- D. PRODUTOS ---
        logging.info("   -> A extrair Produtos...")
        dataframes['produtos'] = pd.read_sql(text(f"SELECT * FROM {schema}.produtos"), conn)
        
        return dataframes