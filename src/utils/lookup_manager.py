import pandas as pd
import json
import os

class CustomerLookupManager:
    def __init__(self, storage_file="lookup_state.json"):
        self.storage_file = storage_file
        
        self.nif_registry = {}   # NIF -> SK
        self.email_registry = {} # Email -> SK
        self.current_sk = 0
        
        self.load_state()

    def load_state(self):
        """Carrega o estado do disco para a memória."""
        if os.path.exists(self.storage_file):
            try:
                with open(self.storage_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.current_sk = data.get("current_sk", 0)
                    raw_nifs = data.get("nif_registry", {})
                    self.nif_registry = {int(k): v for k, v in raw_nifs.items()}
                    self.email_registry = data.get("email_registry", {})
                print(f"📂 Lookup carregado: {len(self.nif_registry)} NIFs. SK Atual: {self.current_sk}")
            except Exception as e:
                print(f"⚠️ Erro ao carregar lookup: {e}")
        else:
            print("✨ Nenhum lookup encontrado. Iniciando novo.")

    def save_state(self):
        """Salva o estado atual no disco (CHAMAR APENAS NO FINAL)."""
        print("💾 A guardar estado do Lookup no disco...")
        data = {
            "current_sk": self.current_sk,
            "nif_registry": self.nif_registry,
            "email_registry": self.email_registry
        }
        try:
            with open(self.storage_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=4)
            print("✅ Lookup salvo com sucesso!")
        except Exception as e:
            print(f"❌ Erro crítico ao salvar lookup: {e}")

    def get_or_create_sk(self, nif_input, email_input):
        """Gera SK em memória (Super Rápido)."""
        # 1. Validação
        try:
            nif = int(nif_input)
        except (ValueError, TypeError):
            nif = 0
            
        email = str(email_input).strip().lower()
        if email in ["", "nan", "none", "n/a", "sem email", "desconhecido"]:
            email = None

        found_sk = None

        # 2. Match NIF
        if nif > 0 and nif in self.nif_registry:
            found_sk = self.nif_registry[nif]

        # 3. Match Email
        if found_sk is None and email is not None and email in self.email_registry:
            found_sk = self.email_registry[email]

        # 4. Criar Novo (Se necessário)
        if found_sk is None:
            self.current_sk += 1
            found_sk = self.current_sk
        
        # 5. Atualizar Memória
        if nif > 0:
            self.nif_registry[nif] = found_sk
        if email is not None:
            self.email_registry[email] = found_sk

        # REMOVIDO: self.save_state() -> Agora salvamos só no main!
        
        return found_sk