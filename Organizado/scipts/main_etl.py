import time
import pandas as pd
from sqlalchemy import create_engine, text
import logging

# --- IMPORTAÇÕES ---
from extratores.extract_sql import extract_sales_delta
from extratores.extract_mongo import extract_reviews_delta
from extratores.extract_csv import extract_vendas 

from transforms.transform_sql import transform_dim_cliente, transform_dim_produto, transform_dim_zona, transform_dim_calendario, transform_tf_vendas
from transforms.transform_mongo import transform_dim_feedback, transform_tf_reviews
from transforms.transform_csv import transform_dim_cliente_csv, transform_dim_produto_csv, transform_dim_zona_csv, transform_tf_vendas_csv

from utils.lookup_manager import CustomerLookupManager 
from loaders.loader import load_to_dw 

# Configuração de Logs
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')

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

# --- FUNÇÕES AUXILIARES DE FILTRAGEM ---

def filter_existing_dimensions(df, table_name, key_col, engine, schema="DW"):
    """
    Remove do DataFrame as linhas cujo ID já existe na tabela de destino.
    """
    if df.empty: return df

    try:
        # CORREÇÃO: table_name e key_col devem bater certo com o PostgreSQL (minúsculas)
        query = text(f'SELECT "{key_col}" FROM "{schema}"."{table_name}"')
        existing_ids = pd.read_sql(query, engine)
        
        if existing_ids.empty:
            return df
            
        # Converter para string para garantir comparação correta
        existing_set = set(existing_ids[key_col].astype(str))
        
        # Filtrar o DataFrame de entrada
        # Verifica se o ID (convertido para string) NÃO está no set de existentes
        df_filtered = df[~df[key_col].astype(str).isin(existing_set)]
        
        diff = len(df) - len(df_filtered)
        if diff > 0:
            print(f"   🔹 Dimensão {table_name}: {diff} registos ignorados (já existiam).")
            
        return df_filtered
        
    except Exception as e:
        # Se a tabela não existir, assume que tudo é novo
        # print(f"DEBUG: Erro ao filtrar dimensão {table_name}: {e}")
        return df

def filter_existing_facts(df, table_name, key_cols, engine, schema="DW"):
    if df.empty: return df
    
    try:
        cols_str = ', '.join([f'"{c}"' for c in key_cols])
        query = text(f'SELECT {cols_str} FROM "{schema}"."{table_name}"')
        existing = pd.read_sql(query, engine)
        
        if existing.empty: return df

        def create_key(row):
            return "_".join([str(row[c]) for c in key_cols])

        existing['combined_key'] = existing.apply(create_key, axis=1)
        df['combined_key'] = df.apply(create_key, axis=1)
        
        df_filtered = df[~df['combined_key'].isin(existing['combined_key'])].copy()
        df_filtered.drop(columns=['combined_key'], inplace=True)
        
        diff = len(df) - len(df_filtered)
        if diff > 0:
            print(f"   🔹 Facto {table_name}: {diff} duplicados ignorados.")
            
        return df_filtered

    except Exception as e:
        return df

# --- PIPELINE PRINCIPAL ---

def run_pipeline():
    print(f"\n🔔 Ciclo ETL iniciado: {time.ctime()}")
    
    lookup_manager = CustomerLookupManager()
    dw_engine = get_dw_engine()
    
    # 1. VERIFICAÇÃO DO CSV (CARGA INICIAL)
    is_dw_empty = False
    try:
        with dw_engine.connect() as conn:
            # CORREÇÃO CRÍTICA: Nome da tabela em minúsculas "tfvendas"
            # Se usares "TFVendas", o Postgres diz que não existe e ativa o modo Carga Total
            res = conn.execute(text('SELECT COUNT(*) FROM "DW"."tfvendas"')).fetchone()
            if res[0] == 0:
                is_dw_empty = True
                print("ℹ️ A tabela de Factos existe mas está vazia.")
            else:
                print(f"ℹ️ DW detetado com {res[0]} vendas. Modo: Incremental.")

    except Exception as e:
        print(f"⚠️ Tabela tfvendas não encontrada ({e}). Assumindo Carga Inicial.")
        is_dw_empty = True 
    
    # --- 1. EXTRAÇÃO ---
    print("\n--- 1. EXTRAÇÃO ---")
    
    # Nota: Verifica se dentro de 'extract_sales_delta' também corrigiste para 'tfvendas'
    data_sql = extract_sales_delta(schema="db") 
    data_mongo = extract_reviews_delta()
    
    data_csv = pd.DataFrame()
    if is_dw_empty:
        print("📂 DW Vazio/Inexistente: A extrair histórico CSV...")
        data_csv = extract_vendas()
    else:
        print("✅ Histórico já carregado. CSV ignorado.")

    # --- 2. DIMENSÕES ---
    print("\n--- 2. DIMENSÕES ---")
    
    # --- 2.1 CLIENTES ---
    df_cli_sql, map_cli_sql = transform_dim_cliente(data_sql['clientes'], lookup_manager)
    
    df_cli_csv = pd.DataFrame()
    map_cli_csv = {}
    if not data_csv.empty:
        df_cli_csv, map_cli_csv = transform_dim_cliente_csv(data_csv, lookup_manager)
    
    df_dim_cliente_final = pd.concat([df_cli_sql, df_cli_csv])
    if not df_dim_cliente_final.empty:
        df_dim_cliente_final = df_dim_cliente_final.drop_duplicates(subset=["cliente_id"], keep='first')
        
        # CORREÇÃO: Passar "dimcliente" em minúsculas
        df_to_load = filter_existing_dimensions(df_dim_cliente_final, "dimcliente", "cliente_id", dw_engine)
        if not df_to_load.empty:
            load_to_dw(df_to_load, "dimcliente")

    # --- 2.2 PRODUTOS ---
    df_prod_sql = transform_dim_produto(data_sql['produtos'])
    df_prod_csv = pd.DataFrame()
    if not data_csv.empty:
        df_prod_csv = transform_dim_produto_csv(data_csv)
        
    df_dim_prod_final = pd.concat([df_prod_sql, df_prod_csv]).drop_duplicates(subset=["produto_id"], keep='first')
    
    # CORREÇÃO: Passar "dimproduto" em minúsculas
    df_prod_to_load = filter_existing_dimensions(df_dim_prod_final, "dimproduto", "produto_id", dw_engine)
    
    if not df_prod_to_load.empty:
        load_to_dw(df_prod_to_load, "dimproduto")
    else:
        print("   (Produtos) Nada de novo para inserir.")

    # --- 2.3 ZONAS ---
    df_zona_sql = transform_dim_zona(data_sql['clientes'])
    df_zona_csv = pd.DataFrame()
    if not data_csv.empty:
        df_zona_csv = transform_dim_zona_csv(data_csv)

    df_dim_zona_final = pd.concat([df_zona_sql, df_zona_csv])
    if not df_dim_zona_final.empty:
        df_dim_zona_final = df_dim_zona_final.drop_duplicates(subset=["distrito"]).reset_index(drop=True)
        # Recalcular IDs 
        df_dim_zona_final["zona_id"] = df_dim_zona_final.index + 1
        
        # CORREÇÃO: Passar "dimzona" em minúsculas
        df_zona_to_load = filter_existing_dimensions(df_dim_zona_final, "dimzona", "distrito", dw_engine)
        if not df_zona_to_load.empty:
            load_to_dw(df_zona_to_load, "dimzona") 

# --- 2.4 CALENDÁRIO ---
    # Usa datas do SQL, do CSV e do Mongo
    dates_sql = data_sql['vendas'] if not data_sql['vendas'].empty else pd.DataFrame(columns=['data_venda'])
    dates_csv = data_csv if not data_csv.empty else pd.DataFrame(columns=['data'])
    dates_mongo = data_mongo if not data_mongo.empty else pd.DataFrame(columns=['data'])
    
    # Normalizar nomes
    d1 = dates_sql[['data_venda']].rename(columns={'data_venda': 'data'})
    
    # Preparar datas CSV (COM CORREÇÃO DAYFIRST)
    d2 = pd.DataFrame(columns=['data'])
    if 'data' in dates_csv.columns and not dates_csv.empty:
        d2 = dates_csv[['data']].copy()
        # O segredo está aqui: dayfirst=True para alinhar com o transform_csv
        d2['data'] = pd.to_datetime(d2['data'], dayfirst=True, errors='coerce')

    # Preparar datas Mongo
    d3 = pd.DataFrame(columns=['data'])
    if 'data' in dates_mongo.columns and not dates_mongo.empty:
        d3 = dates_mongo[['data']].copy()
        d3['data'] = pd.to_datetime(d3['data'], errors='coerce')

    # Juntar tudo
    df_all_dates = pd.concat([d1, d2, d3]).dropna().drop_duplicates()
    
    if not df_all_dates.empty:
        # Garante que passamos apenas a data (sem horas)
        df_all_dates['data'] = pd.to_datetime(df_all_dates['data']).dt.date
        df_cal = transform_dim_calendario(df_all_dates, dw_engine, DW_CONFIG["schema"])
        if not df_cal.empty:
            load_to_dw(df_cal, "dimcalendario")

    # --- 3. FACTOS ---
    print("\n--- 3. FACTOS ---")
    
    # 3.1 Facto Vendas SQL (Incremental)
    if not data_sql['vendas'].empty:
        df_tf_vendas_sql = transform_tf_vendas(
            df_vendas=data_sql['vendas'], 
            df_vp=data_sql['venda_produto'], 
            df_clientes=data_sql['clientes'], 
            map_clientes_sql=map_cli_sql, 
            df_produtos=df_dim_prod_final, 
            df_dim_zona=df_dim_zona_final, 
            lookup_manager=lookup_manager
        )
        
        # CORREÇÃO: Passar "tfvendas" em minúsculas
        df_sql_clean = filter_existing_facts(df_tf_vendas_sql, "tfvendas", ["venda_id", "produto_id"], dw_engine)
        
        if not df_sql_clean.empty:
            load_to_dw(df_sql_clean, "tfvendas")
            print(f"   ✅ Inseridas {len(df_sql_clean)} novas vendas SQL.")

# 3.2 Facto Vendas CSV (Carga Inicial)
    if not data_csv.empty:
        # --- CORREÇÃO CRÍTICA AQUI ---
        # Temos de recolher TODOS os IDs válidos que acabámos de processar (SQL + CSV)
        # Se não fizermos isto, a função de validação vai rejeitar tudo!
        
        all_valid_ids = set()
        
        # 1. Adicionar IDs do SQL
        if not df_dim_cliente_final.empty:
             all_valid_ids.update(df_dim_cliente_final["cliente_id"].unique())
             
        # 2. Adicionar IDs que já existiam no DW (caso seja carga incremental mista)
        # (Opcional, mas seguro)
        try:
            with dw_engine.connect() as conn:
                existing = pd.read_sql(text('SELECT "cliente_id" FROM "DW"."dimcliente"'), conn)
                all_valid_ids.update(existing["cliente_id"].values)
        except:
            pass

        print(f"ℹ️ Total de Clientes Válidos para validação do CSV: {len(all_valid_ids)}")

        df_tf_vendas_csv = transform_tf_vendas_csv(
            df_csv=data_csv,
            map_clientes_csv=map_cli_csv,
            df_dim_produto=df_dim_prod_final,
            df_dim_zona=df_dim_zona_final,
            lookup_manager=lookup_manager,
            valid_customer_ids=all_valid_ids # <--- AGORA SIM, TEMOS A LISTA COMPLETA
        )
        
        if not df_tf_vendas_csv.empty:
            load_to_dw(df_tf_vendas_csv, "tfvendas")
            print(f"   ✅ Histórico CSV carregado: {len(df_tf_vendas_csv)} linhas.")
        else:
            print("   ⚠️ Todas as linhas do CSV foram rejeitadas (ver quarentena).")

    # 3.3 Reviews (Mongo)
    if not data_mongo.empty:
        print("\n--- 3.3 Reviews (Mongo) ---")
        df_dim_feedback, map_mongo_feedback = transform_dim_feedback(data_mongo)
        
        # Ajuste Incremental de IDs para Feedback
        try:
            with dw_engine.connect() as conn:
                # CORREÇÃO: "dimfeedback" e "feedback_id" em minúsculas
                res = conn.execute(text('SELECT MAX("feedback_id") FROM "DW"."dimfeedback"')).fetchone()
                last_id = res[0] if res[0] is not None else 0
        except Exception:
            last_id = 0
            
        df_dim_feedback["feedback_id"] += last_id
        map_mongo_feedback["feedback_id"] += last_id
        
        load_to_dw(df_dim_feedback, "dimfeedback")

        df_tf_reviews = transform_tf_reviews(
            df_reviews=data_mongo,
            map_mongo_feedback=map_mongo_feedback,
            lookup_manager=lookup_manager,
            df_dim_cliente=df_dim_cliente_final,
            df_dim_zona=df_dim_zona_final
        )
        
        if not df_tf_reviews.empty:
            load_to_dw(df_tf_reviews, "tfreviews")

    lookup_manager.save_state()
    print("\n🏁 Pipeline concluído.")

if __name__ == "__main__":
    run_pipeline()