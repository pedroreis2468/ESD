import pandas as pd
import logging
import os
from pathlib import Path

logger = logging.getLogger(__name__)

CURRENT_FILE = Path(__file__).resolve()
PROJECT_ROOT = CURRENT_FILE.parent.parent.parent 
CSV_FILE_NAME = "csv.csv" # Confirma se é vendas.csv ou csv.csv
CSV_PATH = PROJECT_ROOT / "data" / "csv" / CSV_FILE_NAME

CSV_CONFIG = {
    "vendas": str(CSV_PATH)
}

def extract_vendas() -> pd.DataFrame:
    if not os.path.exists(CSV_CONFIG["vendas"]):
        error_msg = f"❌ CSV não encontrado: {CSV_CONFIG['vendas']}"
        logger.error(error_msg)
        raise FileNotFoundError(error_msg)

    try:
        # Tenta detetar automaticamente o separador lendo a primeira linha
        with open(CSV_CONFIG["vendas"], 'r', encoding='utf-8') as f:
            first_line = f.readline()
            sep = ';' if ';' in first_line else ','

        df = pd.read_csv(CSV_CONFIG["vendas"], encoding='utf-8', sep=sep)
        logger.info(f"✅ Vendas CSV: {df.shape[0]} linhas. Colunas: {list(df.columns)}")
        return df
        
    except Exception as e:
        logger.error(f"Erro ao ler CSV: {e}")
        raise e