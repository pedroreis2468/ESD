import pandas as pd
import numpy as np
import os
import ast
import unicodedata
from datetime import datetime
from pathlib import Path
from utils.lookup_manager import CustomerLookupManager

# ==============================================================================
# CONFIGURAÇÕES E UTILITÁRIOS
# ==============================================================================
CURRENT_FILE = Path(__file__).resolve()
PROJECT_ROOT = CURRENT_FILE.parent.parent.parent 
QUARANTINE_PATH = PROJECT_ROOT / "data" / "quarentena"
os.makedirs(QUARANTINE_PATH, exist_ok=True)

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
    if found:
        return found
    return None

def send_to_quarantine(df, reason, entity_type):
    if df.empty: return
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_reason = reason.replace(" ", "_").replace(":", "").replace("/", "_").replace("\\", "_").lower()
    filename = f"erro_{entity_type}_{safe_reason}_{timestamp}.csv"
    full_path = QUARANTINE_PATH / filename
    
    df_out = df.copy()
    for col in df_out.columns:
        if df_out[col].apply(lambda x: isinstance(x, list)).any():
            df_out[col] = df_out[col].astype(str)
            
    df_out.to_csv(str(full_path), index=False, encoding='utf-8-sig')
    print(f"⚠️ QUARENTENA (CSV): {len(df)} registos de {entity_type} movidos para {full_path}")

def get_first_valid(series):
    valid_values = series.dropna()
    if valid_values.empty: return np.nan
    return valid_values.iloc[0]

def parse_list_col(val):
    try:
        if isinstance(val, str):
            return ast.literal_eval(val)
        return val if isinstance(val, list) else []
    except:
        return []

def normalize_headers(df):
    new_cols = df.columns.str.strip().str.lower()
    normalized_cols = []
    for col in new_cols:
        nfkd_form = unicodedata.normalize('NFKD', col)
        only_ascii = "".join([c for c in nfkd_form if not unicodedata.combining(c)])
        normalized_cols.append(only_ascii)
    df.columns = normalized_cols
    df.columns = df.columns.str.replace(' ', '_').str.replace('-', '_').str.replace('.', '')
    return df

# ==============================================================================
# 1. TRANSFORMAÇÃO: DIMENSÃO CLIENTE
# ==============================================================================
def transform_dim_cliente_csv(df_csv: pd.DataFrame, lookup_manager) -> (pd.DataFrame, pd.DataFrame):
    df_clean = normalize_headers(df_csv.copy())
    
    # 1. Garantir strings
    str_cols = ["primeiro_nome", "ultimo_nome", "email", "genero", "distrito", "concelho"]
    for col in str_cols:
        if col not in df_clean.columns: df_clean[col] = ""
        else: df_clean[col] = df_clean[col].fillna("").astype(str)

    # 2. Tratamento
    df_clean["nome"] = (df_clean["primeiro_nome"] + " " + df_clean["ultimo_nome"]).str.strip().str[:45]
    df_clean["nome"] = df_clean["nome"].replace("", np.nan)
    df_clean["email"] = df_clean["email"].str.lower().str.strip().replace(["", "nan", "none"], None)
    
    if "data_nascimento" not in df_clean.columns: df_clean["data_nascimento"] = np.nan
    df_clean["data_nascimento"] = pd.to_datetime(df_clean["data_nascimento"], format="%d-%m-%Y", errors='coerce')
    
    if "nif" not in df_clean.columns: df_clean["nif"] = 0
    df_clean["nif"] = pd.to_numeric(df_clean["nif"], errors='coerce').fillna(0).astype(int)
    
    df_clean["distrito"] = df_clean.apply(fix_distrito, axis=1)
    
    # 3. Lookup
    # Snapshot dos IDs existentes
    existing_ids = set(lookup_manager.nif_registry.values()) | set(lookup_manager.email_registry.values())

    def resolve_sk(row):
        nif = row.get("nif", 0)
        email = row.get("email")
        if nif > 0 and nif in lookup_manager.nif_registry:
            return lookup_manager.nif_registry[nif]
        if email is not None and email in lookup_manager.email_registry:
            return lookup_manager.email_registry[email]
        return lookup_manager.get_or_create_sk(nif, email)

    df_clean["sk_cliente"] = df_clean.apply(resolve_sk, axis=1)

    # 4. Agregação
    df_c = pd.DataFrame()
    df_c["cliente_id"] = df_clean["sk_cliente"]
    df_c["nome"] = df_clean["nome"]
    df_c["email"] = df_clean["email"]
    df_c["data_nascimento"] = df_clean["data_nascimento"]
    df_c["nif"] = df_clean["nif"]
    df_c["genero"] = df_clean["genero"].replace(["", "nan"], np.nan)
    df_c["distrito"] = df_clean["distrito"]

    df_dim_final = df_c.groupby("cliente_id", as_index=False).agg({
        "nome": get_first_valid,
        "email": get_first_valid,
        "data_nascimento": get_first_valid,
        "nif": "max",
        "genero": get_first_valid,
        "distrito": get_first_valid
    })

    # 5. Validação
    def filter_action(row):
        sk = row["cliente_id"]
        is_incomplete = (pd.isna(row["nome"]) or pd.isna(row["distrito"]) or pd.isna(row["data_nascimento"]) or pd.isna(row["genero"]))
        
        if not is_incomplete:
            return "keep"
        
        if sk in existing_ids:
            return "skip_update" 
        else:
            return "quarantine" 

    df_dim_final["action"] = df_dim_final.apply(filter_action, axis=1)

    quarantine_rows = df_dim_final[df_dim_final["action"] == "quarantine"]
    if not quarantine_rows.empty:
        send_to_quarantine(quarantine_rows, "CSV: Cliente NOVO incompleto", "dim_cliente_csv")

    df_load = df_dim_final[df_dim_final["action"] == "keep"].drop(columns=["action"])

    valid_sks = set(df_dim_final[df_dim_final["action"] != "quarantine"]["cliente_id"])
    map_clientes_csv = df_clean[df_clean["sk_cliente"].isin(valid_sks)][["cliente_id", "sk_cliente"]].copy()
    map_clientes_csv.columns = ["cliente_id_origem", "sk_cliente"]

    return df_load, map_clientes_csv

# ==============================================================================
# 2. TRANSFORMAÇÃO: DIMENSÃO PRODUTO
# ==============================================================================
def transform_dim_produto_csv(df_csv: pd.DataFrame) -> pd.DataFrame:
    df_csv = normalize_headers(df_csv.copy())
    list_cols = ["produtos_id", "produtos_nome", "marca", "produto_categoria", "produtos_preco", "produto_subcategoria"]
    for col in list_cols:
        if col in df_csv.columns:
            df_csv[col] = df_csv[col].apply(parse_list_col)

    df_exploded = df_csv.explode(list_cols)
    
    df_p = pd.DataFrame()
    df_p["produto_id"] = pd.to_numeric(df_exploded["produtos_id"], errors='coerce')
    
    for col_orig, col_dest in [("produtos_nome", "nome"), ("marca", "marca"), ("produto_categoria", "categoria"), ("produto_subcategoria", "subcategoria")]:
        if col_orig in df_exploded.columns:
            df_p[col_dest] = df_exploded[col_orig].fillna("").astype(str).str[:45].replace(["", "nan"], np.nan)
        else:
            df_p[col_dest] = np.nan

    df_p["preco"] = pd.to_numeric(df_exploded["produtos_preco"], errors='coerce')

    invalid_pk = df_p["produto_id"].isna()
    if invalid_pk.any():
        send_to_quarantine(df_p[invalid_pk], "CSV: Produto sem ID", "dim_produto_csv")
        df_p = df_p.dropna(subset=["produto_id"])
        
    df_p["produto_id"] = df_p["produto_id"].astype(int)

    df_final = df_p.groupby("produto_id", as_index=False).agg({
        "nome": get_first_valid,
        "marca": get_first_valid,
        "categoria": get_first_valid,
        "subcategoria": get_first_valid,
        "preco": get_first_valid
    })

    critical_error = df_final["nome"].isna() | df_final["preco"].isna()
    if critical_error.any():
        send_to_quarantine(df_final[critical_error], "CSV: Produto incompleto", "dim_produto_csv")
        df_final = df_final[~critical_error]

    df_final["preco"] = df_final["preco"].round(2)
    return df_final

# ==============================================================================
# 3. TRANSFORMAÇÃO: DIMENSÃO ZONA
# ==============================================================================
def transform_dim_zona_csv(df_csv: pd.DataFrame) -> pd.DataFrame:
    df_temp = normalize_headers(df_csv.copy())
    if "distrito" not in df_temp.columns: df_temp["distrito"] = ""
    df_temp["distrito"] = df_temp["distrito"].fillna("").astype(str)
    
    df_temp["distrito"] = df_temp.apply(fix_distrito, axis=1)
    df_z = df_temp[["distrito"]].drop_duplicates().dropna().copy()
    df_z = df_z.reset_index(drop=True)
    df_z["zona_id"] = df_z.index + 1
    df_z["nome"] = "Zona " + df_z["distrito"]
    return df_z[["zona_id", "nome", "distrito"]]

# ==============================================================================
# 4. TRANSFORMAÇÃO: FACTO VENDAS (CSV) - VERSÃO OTIMIZADA
# ==============================================================================
def transform_tf_vendas_csv(df_csv, map_clientes_csv, df_dim_produto, df_dim_zona, lookup_manager, valid_customer_ids=None):
    df_work = normalize_headers(df_csv.copy())

    # --- CORREÇÃO: Limpeza PRELIMINAR de datas ---
    # Antes de qualquer explode, vamos garantir que a data é válida.
    # Isto evita que lixo seja multiplicado por mil.
    if "data" in df_work.columns:
        # Converter com dayfirst=True (Formato Europeu DD-MM-YYYY)
        df_work["data_clean"] = pd.to_datetime(df_work["data"], dayfirst=True, errors='coerce').dt.date
    else:
        df_work["data_clean"] = np.nan

    # Remover logo quem não tem data, para não processar inutilmente
    missing_date_mask = df_work["data_clean"].isna()
    if missing_date_mask.any():
        # Envia as originais para quarentena (antes do explode)
        send_to_quarantine(df_work[missing_date_mask], "CSV: Data Nula ou Invalida (Pre-Explode)", "tf_vendas_csv")
        df_work = df_work[~missing_date_mask].copy()

    # --- FIM DA LIMPEZA PRELIMINAR ---

    list_cols = ["produtos_id", "produtos_preco"]
    for col in list_cols:
        if col in df_work.columns:
            df_work[col] = df_work[col].apply(parse_list_col)
    
    # Agora é seguro fazer explode
    df_exploded = df_work.explode(["produtos_id", "produtos_preco"])
    
    # Renomear e Converter
    df_exploded.rename(columns={"vendas_id": "venda_id", "produtos_id": "produto_id"}, inplace=True)
    df_exploded["produto_id"] = pd.to_numeric(df_exploded["produto_id"], errors='coerce')
    df_exploded["preco"] = pd.to_numeric(df_exploded["produtos_preco"], errors='coerce')
    
    # Usar a coluna de data já limpa
    df_exploded["data"] = df_exploded["data_clean"]

    # 1. Lookup Cliente
    df_f = pd.merge(df_exploded, map_clientes_csv, left_on="cliente_id", right_on="cliente_id_origem", how="left")
    
    # 2. FILTRAR POR IDS VÁLIDOS
    if valid_customer_ids is not None:
        invalid_cust_mask = ~df_f["sk_cliente"].isin(valid_customer_ids)
        if invalid_cust_mask.any():
            send_to_quarantine(df_f[invalid_cust_mask], "CSV: Cliente inexistente na Dimensao", "tf_vendas_csv")
            df_f = df_f[~invalid_cust_mask]

    if df_f["sk_cliente"].isna().any():
        send_to_quarantine(df_f[df_f["sk_cliente"].isna()], "CSV: Cliente ID nao resolvido", "tf_vendas_csv")
        df_f = df_f.dropna(subset=["sk_cliente"])

    # 3. Lookup Zona
    df_f["distrito_norm"] = df_f.apply(fix_distrito, axis=1)
    df_f = pd.merge(df_f, df_dim_zona, left_on="distrito_norm", right_on="distrito", how="left")
    
    missing_zona = df_f["zona_id"].isna()
    if missing_zona.any():
        # Fallback opcional: atribuir zona desconhecida ou remover
        send_to_quarantine(df_f[missing_zona], "CSV: Distrito invalido", "tf_vendas_csv")
        df_f = df_f[~missing_zona].copy()

    # 4. Lookup Produto
    df_f = pd.merge(df_f, df_dim_produto[["produto_id"]], on="produto_id", how="left", indicator=True)
    missing_prod = df_f["_merge"] == "left_only"
    if missing_prod.any():
        send_to_quarantine(df_f[missing_prod], "CSV: Produto desconhecido", "tf_vendas_csv")
        df_f = df_f[~missing_prod].copy()

    # Montagem Final
    tf_vendas = pd.DataFrame()
    tf_vendas["venda_id"] = df_f["venda_id"]
    tf_vendas["cliente_id"] = df_f["sk_cliente"].astype(int)
    tf_vendas["produto_id"] = df_f["produto_id"].astype(int)
    tf_vendas["zona_id"] = df_f["zona_id"].astype(int)
    tf_vendas["data"] = df_f["data"]
    tf_vendas["precounitario"] = df_f["preco"]
    tf_vendas["fonte_id"] = 1 
    tf_vendas["quantidade"] = 1

    tf_vendas = tf_vendas.groupby(
        ["venda_id", "cliente_id", "produto_id", "zona_id", "data", "precounitario", "fonte_id"],
        as_index=False
    ).agg({"quantidade": "sum"})

    return tf_vendas