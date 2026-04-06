import pandas as pd
import numpy as np
import os
import unicodedata
from datetime import datetime
from sqlalchemy import text
from pathlib import Path

# ==============================================================================
# CONFIGURAÇÕES E UTILITÁRIOS
# ==============================================================================
# CORREÇÃO DE CAMINHOS: Usar Path absoluto para garantir que vai para a pasta certa
CURRENT_FILE = Path(__file__).resolve()
# Sobe 3 níveis: transforms -> scripts -> Organizado
PROJECT_ROOT = CURRENT_FILE.parent.parent.parent 
QUARANTINE_PATH = PROJECT_ROOT / "data" / "quarentena"

if not os.path.exists(QUARANTINE_PATH):
    os.makedirs(QUARANTINE_PATH)

geo = {
    "Aveiro": ["Aveiro", "Santa Maria da Feira", "Espinho", "Ovar", "Águeda", "Oliveira de Azeméis", "Estarreja", "Ílhavo" ,"Albergaria-a-Velha"],
    "Beja": ["Beja", "Odemira", "Serpa", "Mértola", "Aljustrel", "Almodôvar", "Castro Verde"],
    "Braga": ["Braga", "Guimarães", "Vila Nova de Famalicão", "Barcelos", "Fafe", "Esposende", "Vizela", "Póvoa de Lanhoso", "Terras de Bouro", "Cabeceiras de Basto"],
    "Bragança": ["Bragança", "Mirandela", "Macedo de Cavaleiros", "Vimioso", "Vila Flor", "Carrazeda de Ansiães", "Alfândega da Fé"],
    "Castelo Branco": ["Castelo Branco", "Covilhã", "Fundão", "Idanha-a-Nova", "Proença-a-Nova", "Belmonte"],
    "Coimbra": ["Coimbra", "Figueira da Foz", "Cantanhede", "Montemor-o-Velho", "Oliveira do Hospital", "Penacova"],
    "Évora": ["Évora", "Montemor-o-Novo", "Estremoz", "Vendas Novas", "Viana do Alentejo"],
    "Faro": ["Faro", "Portimão", "Loulé", "Albufeira", "Lagos", "Tavira", "Silves", "Olhão", "Vila Real de Santo António"],
    "Guarda": ["Guarda", "Seia", "Gouveia", "Celorico da Beira", "Manteigas"],
    "Leiria": ["Leiria", "Caldas da Rainha", "Alcobaça", "Marinha Grande", "Pombal"],
    "Lisboa": ["Lisboa", "Sintra", "Cascais", "Loures", "Amadora", "Oeiras", "Vila Franca de Xira", "Torres Vedras", "Mafra", "Almada", "Seixal"],
    "Portalegre": ["Portalegre", "Elvas", "Ponte de Sor", "Arronches", "Sousel"],
    "Porto": ["Porto", "Vila Nova de Gaia", "Matosinhos", "Gondomar", "Maia", "Póvoa de Varzim", "Vila do Conde"],
    "Santarém": ["Santarém", "Tomar", "Abrantes", "Torres Novas", "Entroncamento"],
    "Setúbal": ["Setúbal", "Almada", "Seixal", "Barreiro", "Palmela", "Sesimbra", "Montijo", "Sines", "Grândola"],
    "Viana do Castelo": ["Viana do Castelo", "Ponte de Lima", "Caminha", "Vila Nova de Cerveira", "Monção", "Arcos de Valdevez", "Melgaço" ,"Valença"],
    "Vila Real": ["Vila Real", "Chaves", "Peso da Régua", "Montalegre", "Alijó", "Sabrosa"],
    "Viseu": ["Viseu", "Lamego", "Tondela", "Mangualde", "Sátão", "Carregal do Sal"],
    "Madeira": ["Funchal", "Câmara de Lobos", "Santa Cruz", "Machico", "Santana", "Porto Moniz", "Ponta do Sol"],
    "Açores": ["Ponta Delgada", "Angra do Heroísmo", "Horta", "Ribeira Grande", "Vila Franca do Campo", "Lagoa"]
}

concelho_to_distrito = {concelho: distrito for distrito, concelhos in geo.items() for concelho in concelhos}

def fix_distrito(row):
    concelho = row.get('concelho')
    distrito_original = row.get('distrito')
    
    if isinstance(distrito_original, str):
         distrito_original = distrito_original.strip().title()
         
    if distrito_original in geo:
        return distrito_original
    
    found = concelho_to_distrito.get(concelho)
    if found: return found
    return "Desconhecido"

def send_to_quarantine(df, reason, entity_type):
    if df.empty: return
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_reason = reason.replace(" ", "_").lower()
    
    # Caminho absoluto
    filename = f"erro_{entity_type}_{safe_reason}_{timestamp}.csv"
    full_path = QUARANTINE_PATH / filename
    
    df_err = df.copy()
    df_err["motivo_quarentena"] = reason
    df_err["data_rejeicao"] = timestamp
    
    for col in df_err.columns:
        if df_err[col].apply(lambda x: isinstance(x, list) or isinstance(x, dict)).any():
            df_err[col] = df_err[col].astype(str)
            
    # Gravar usando o caminho completo
    df_err.to_csv(str(full_path), index=False, encoding='utf-8-sig')
    print(f"⚠️ QUARENTENA: {len(df)} registos de {entity_type} movidos para {full_path}")

def normalize_headers(df):
    new_cols = df.columns.astype(str).str.strip().str.lower()
    normalized_cols = []
    for col in new_cols:
        nfkd_form = unicodedata.normalize('NFKD', col)
        only_ascii = "".join([c for c in nfkd_form if not unicodedata.combining(c)])
        normalized_cols.append(only_ascii)
    df.columns = normalized_cols
    df.columns = df.columns.str.replace(' ', '_').str.replace('-', '_').str.replace('.', '')
    return df

def get_first_valid(series):
    valid_values = series.dropna()
    if valid_values.empty:
        return np.nan
    return valid_values.iloc[0]

# ==============================================================================
# 1. TRANSFORMAÇÃO: DIMENSÃO CLIENTE (SQL)
# ==============================================================================
def transform_dim_cliente(df_clientes: pd.DataFrame, lookup_manager) -> (pd.DataFrame, pd.DataFrame):
    df_clean = normalize_headers(df_clientes.copy())
    
    if "nif" not in df_clean.columns:
        if "nif_cliente" in df_clean.columns:
             df_clean.rename(columns={"nif_cliente": "nif"}, inplace=True)
        else:
             df_clean["nif"] = 0

    if "distrito" not in df_clean.columns: df_clean["distrito"] = "Desconhecido"
    df_clean["distrito"] = df_clean.apply(fix_distrito, axis=1)
    
    df_clean["nif"] = pd.to_numeric(df_clean["nif"], errors='coerce').fillna(0).astype(int)
    
    if "email" not in df_clean.columns: df_clean["email"] = None
    df_clean["email"] = df_clean["email"].str.lower().str.strip()
    
    df_clean.replace(["", "nan", "none", "n/a"], np.nan, inplace=True)

    df_clean["sk_cliente"] = df_clean.apply(
        lambda row: lookup_manager.get_or_create_sk(row["nif"], row["email"]), 
        axis=1
    )

    df_c = pd.DataFrame()
    df_c["cliente_id"] = df_clean["sk_cliente"]
    df_c["nome"] = df_clean["nome"].str[:45] if "nome" in df_clean.columns else "Sem Nome"
    df_c["email"] = df_clean["email"]
    
    if "data_nascimento" in df_clean.columns:
        df_c["data_nascimento"] = pd.to_datetime(df_clean["data_nascimento"], errors='coerce')
    else:
         df_c["data_nascimento"] = np.nan

    df_c["nif"] = df_clean["nif"]
    df_c["genero"] = df_clean["genero"] if "genero" in df_clean.columns else "Desconhecido"
    df_c["distrito"] = df_clean["distrito"]

    df_dim_final = df_c.groupby("cliente_id", as_index=False).agg({
        "nome": get_first_valid,
        "email": get_first_valid,
        "data_nascimento": get_first_valid,
        "nif": "max",
        "genero": get_first_valid,
        "distrito": get_first_valid
    })

    invalid_mask = df_dim_final["nome"].isna()
    if invalid_mask.any():
        send_to_quarantine(df_dim_final[invalid_mask], "Cliente SQL incompleto", "dim_cliente_sql")
        df_dim_final = df_dim_final[~invalid_mask]

    df_dim_final["email"] = df_dim_final["email"].fillna("n/a")
    df_dim_final["genero"] = df_dim_final["genero"].fillna("Desconhecido")
    df_dim_final["distrito"] = df_dim_final["distrito"].fillna("Desconhecido")
    
    possible_ids = ["cliente_id", "id", "id_cliente"]
    col_id_origem = next((c for c in possible_ids if c in df_clean.columns), None)
    
    if col_id_origem:
        map_clientes_sql = df_clean[[col_id_origem, "sk_cliente"]].copy()
        map_clientes_sql.columns = ["cliente_id_origem", "sk_cliente"]
    else:
        map_clientes_sql = pd.DataFrame(columns=["cliente_id_origem", "sk_cliente"])

    return df_dim_final, map_clientes_sql

# ==============================================================================
# 2. TRANSFORMAÇÃO: DIMENSÃO PRODUTO (SQL)
# ==============================================================================
def transform_dim_produto(df_produtos: pd.DataFrame) -> pd.DataFrame:
    df_clean = normalize_headers(df_produtos.copy())
    
    if "produto_id" not in df_clean.columns and "id" in df_clean.columns:
        df_clean.rename(columns={"id": "produto_id"}, inplace=True)
    
    if "produto_id" not in df_clean.columns:
         return pd.DataFrame() 

    valid_mask = df_clean["produto_id"].notna()
    df_clean = df_clean[valid_mask].copy()
    
    df_clean["produto_nome"] = df_clean.get("produto_nome", df_clean.get("nome", pd.Series(dtype='object'))).str[:45]
    df_clean["marca"] = df_clean.get("marca", pd.Series("")).str[:45]
    df_clean["produto_categoria"] = df_clean.get("produto_categoria", df_clean.get("categoria", pd.Series(""))).str[:45]
    df_clean["produto_subcategoria"] = df_clean.get("produto_subcategoria", df_clean.get("subcategoria", pd.Series(""))).str[:45]
    df_clean["produto_preco"] = pd.to_numeric(df_clean.get("produto_preco", df_clean.get("preco", 0)), errors='coerce')

    df_clean.replace(["", "nan", "none"], np.nan, inplace=True)

    df_final = pd.DataFrame()
    df_final["produto_id"] = df_clean["produto_id"]
    df_final["nome"] = df_clean["produto_nome"]
    df_final["marca"] = df_clean["marca"]
    df_final["categoria"] = df_clean["produto_categoria"]
    df_final["subcategoria"] = df_clean["produto_subcategoria"]
    df_final["preco"] = df_clean["produto_preco"].round(2)

    df_final["marca"] = df_final["marca"].fillna("Desconhecida")
    df_final["categoria"] = df_final["categoria"].fillna("Sem Categoria")
    df_final["subcategoria"] = df_final["subcategoria"].fillna("Sem Subcategoria")
    
    return df_final.drop_duplicates(subset=["produto_id"])

# ==============================================================================
# 3. TRANSFORMAÇÃO: DIMENSÃO ZONA (SQL)
# ==============================================================================
def transform_dim_zona(df_clientes: pd.DataFrame) -> pd.DataFrame:
    df_temp = normalize_headers(df_clientes.copy())
    
    if "distrito" not in df_temp.columns: 
        return pd.DataFrame(columns=["zona_id", "nome", "distrito"])
        
    df_temp["distrito"] = df_temp.apply(fix_distrito, axis=1)
    df_z = df_temp[["distrito"]].drop_duplicates().dropna().copy()
    df_z = df_z[df_z["distrito"] != "Desconhecido"] 
    df_z = df_z.reset_index(drop=True)
    
    df_z["zona_id"] = df_z.index + 1
    df_z["nome"] = "Zona " + df_z["distrito"]
    
    return df_z[["zona_id", "nome", "distrito"]]

# ==============================================================================
# 4. TRANSFORMAÇÃO: DIMENSÃO CALENDÁRIO
# ==============================================================================
def transform_dim_calendario(df_vendas: pd.DataFrame, dw_engine, schema: str) -> pd.DataFrame:
    print("📅 A verificar datas no Calendário...")
    
    df_v = normalize_headers(df_vendas.copy())
    col_data = next((c for c in ["data_venda", "data", "date"] if c in df_v.columns), None)
    
    if not col_data:
        print("⚠️ Nenhuma coluna de data encontrada nas vendas.")
        return pd.DataFrame()

    dates_vendas = set(pd.to_datetime(df_v[col_data]).dt.date.unique())
    
    try:
        query = text(f'SELECT "data" FROM "{schema}"."dimcalendario"')
        existing_df = pd.read_sql(query, dw_engine)
        existing_dates = set(pd.to_datetime(existing_df['data']).dt.date)
    except Exception:
        existing_dates = set()

    new_dates_list = list(dates_vendas - existing_dates)

    if not new_dates_list:
        print("✅ Calendário atualizado.")
        return pd.DataFrame()

    print(f"➕ A gerar {len(new_dates_list)} novas datas...")
    df_cal = pd.DataFrame({'data': new_dates_list})
    df_cal['data'] = pd.to_datetime(df_cal['data'])
    
    df_cal['dia_semana'] = df_cal['data'].dt.day_name()
    df_cal['semana'] = df_cal['data'].dt.isocalendar().week
    df_cal['mes'] = df_cal['data'].dt.month
    df_cal['trimestre'] = df_cal['data'].dt.quarter
    df_cal['ano'] = df_cal['data'].dt.year
    df_cal['data'] = df_cal['data'].dt.date
    
    return df_cal

# ==============================================================================
# 5. TRANSFORMAÇÃO: FACTO VENDAS (SQL) - VERSÃO DEBUG / DIAGNÓSTICO
# ==============================================================================
def transform_tf_vendas(df_vendas, df_vp, df_clientes, map_clientes_sql, df_produtos, df_dim_zona, lookup_manager):
    print(f"\n🔍 [DEBUG] Início Transformação SQL")
    print(f"   -> Vendas (Input): {len(df_vendas)} linhas")
    print(f"   -> Itens (Venda_Produto): {len(df_vp)} linhas")

    df_vendas = normalize_headers(df_vendas.copy())
    df_vp = normalize_headers(df_vp.copy())
    df_clientes = normalize_headers(df_clientes.copy())
    
    if "distrito" not in df_clientes.columns: df_clientes["distrito"] = "Desconhecido"
    df_clientes["distrito_corrigido"] = df_clientes.apply(fix_distrito, axis=1)
    col_cli_id = next((c for c in ["cliente_id", "id"] if c in df_clientes.columns), "id")

    # Agregação
    df_qtd = df_vp.groupby("venda_id").agg(
        quantidade=("produto_id", "count"),
        produto_id=("produto_id", "first")
    ).reset_index()
    print(f"   -> Vendas com Itens (após groupby): {len(df_qtd)} linhas")

    # Merge Vendas + Itens
    df_f = pd.merge(df_qtd, df_vendas, on="venda_id", how="inner")
    print(f"   -> Após Merge Vendas+Itens: {len(df_f)} linhas (Perda: {len(df_vendas) - len(df_f)})")
    
    # Stubs
    sales_client_ids = df_f["cliente_id"].unique()
    known_client_ids = map_clientes_sql["cliente_id_origem"].unique()
    unknown_ids = set(sales_client_ids) - set(known_client_ids)
    
    if unknown_ids:
        new_entries = []
        for unknown_id in unknown_ids:
            new_sk = lookup_manager.get_or_create_sk(nif_input=0, email_input=None)
            new_entries.append({"cliente_id_origem": unknown_id, "sk_cliente": new_sk})
        map_clientes_sql = pd.concat([map_clientes_sql, pd.DataFrame(new_entries)], ignore_index=True)

    # Join Clientes
    df_f = pd.merge(df_f, map_clientes_sql, left_on="cliente_id", right_on="cliente_id_origem", how="left")
    
    missing_client = df_f["sk_cliente"].isna()
    if missing_client.any():
        print(f"   ⚠️ DEBUG: {missing_client.sum()} linhas perdidas por falta de Cliente ID")
        send_to_quarantine(df_f[missing_client], "SQL: Cliente ID nao resolvido", "tf_vendas_sql")
        df_f = df_f[~missing_client].copy()

    # Join Produtos
    df_f = pd.merge(df_f, df_produtos[["produto_id", "preco"]], on="produto_id", how="left", indicator="_merge_prod")
    
    missing_prods = df_f["_merge_prod"] == "left_only"
    if missing_prods.any():
        print(f"   ⚠️ DEBUG: {missing_prods.sum()} linhas perdidas por falta de Produto na Dimensão")
        ex_ids = df_f[missing_prods]["produto_id"].unique()[:5]
        print(f"   ⚠️ Exemplo de IDs de produtos em falta: {ex_ids}")
        send_to_quarantine(df_f[missing_prods], "SQL: Produto inexistente na Dimensao", "tf_vendas_sql")
        df_f = df_f[~missing_prods].copy()

    # Join Zona
    df_f = pd.merge(df_f, df_clientes[[col_cli_id, "distrito_corrigido"]], left_on="cliente_id", right_on=col_cli_id, how="left")
    df_f = pd.merge(df_f, df_dim_zona, left_on="distrito_corrigido", right_on="distrito", how="left")
    
    if "zona_id" not in df_f.columns: df_f["zona_id"] = np.nan
    missing_zona = df_f["zona_id"].isna()
    if missing_zona.any():
         df_f = df_f[~missing_zona].copy()

    print(f"   -> Final SQL pronto a carregar: {len(df_f)} linhas")

    tf_vendas = pd.DataFrame()
    tf_vendas["venda_id"] = df_f["venda_id"]
    tf_vendas["cliente_id"] = df_f["sk_cliente"].astype(int)
    tf_vendas["produto_id"] = df_f["produto_id"].astype(int)
    tf_vendas["zona_id"] = df_f["zona_id"].astype(int)
    
    col_data = next((c for c in ["data_venda", "data", "date"] if c in df_f.columns), None)
    if col_data:
        tf_vendas["data"] = pd.to_datetime(df_f[col_data]).dt.date
    else:
        tf_vendas["data"] = None

    tf_vendas["quantidade"] = df_f["quantidade"]
    tf_vendas["precounitario"] = df_f["preco"]
    tf_vendas["fonte_id"] = 0 
    
    return tf_vendas