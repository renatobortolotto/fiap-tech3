# =============================================================================
# Makefile — Tech Challenge Fase 3 (FIAP/POSTECH)
# Predição e inteligência analítica para alfabetização no Brasil
#
# Pipeline reproduzível ponta a ponta. Antes de qualquer alvo que toque o GCP:
#   export GCP_ACCESS_TOKEN=$(gcloud auth print-access-token)
# (ou rode `make auth` para ver a instrução)
# =============================================================================

PYTHON  := ./venv/bin/python
PROJECT := fiap-data-engineering

.DEFAULT_GOAL := help
.PHONY: help setup auth features features-dry dados eda modelo-a modelo-b \
        tunar interpretar aplicacao notebooks testes tudo limpar

help: ## Mostra esta ajuda (alvo padrão)
	@echo "Alvos disponíveis:"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-14s\033[0m %s\n", $$1, $$2}'

setup: ## Cria o venv e instala as dependências
	python3 -m venv venv
	$(PYTHON) -m pip install --upgrade pip
	$(PYTHON) -m pip install -r requirements.txt

auth: ## Imprime a instrução de autenticação no GCP
	@echo "Antes de rodar qualquer script que acesse o BigQuery:"
	@echo ""
	@echo "  export GCP_ACCESS_TOKEN=\$$(gcloud auth print-access-token)"
	@echo ""
	@echo "O token expira em ~1h; re-exporte se receber erro 401."

# --- Dados -------------------------------------------------------------------
features-dry: ## Valida os SQLs da feature store e estima o custo (não executa)
	$(PYTHON) -m src.preprocessing.build_features --dry-run

features: ## Materializa a feature store no BigQuery (features.*)
	$(PYTHON) -m src.preprocessing.build_features

dados: ## Baixa a ABT do BigQuery para data/processed/abt_aluno.parquet
	$(PYTHON) -c "from src.modeling.dataset import extrair_abt; extrair_abt(forcar=True)"

# --- Análise -----------------------------------------------------------------
eda: ## Análise exploratória -> images/ e reports/eda.md
	$(PYTHON) -m src.visualization.executar_eda

# --- Modelagem ---------------------------------------------------------------
modelo-a: ## Modelo A — out-of-time (treino 2023 -> teste 2024)
	$(PYTHON) -m src.modeling.train --desenho temporal

modelo-b: ## Modelo B — operacional (2024, com histórico, partição por município)
	$(PYTHON) -m src.modeling.train --desenho espacial

tunar: ## Otimização de hiperparâmetros com Optuna
	$(PYTHON) -m src.modeling.tune

interpretar: ## Importâncias, SHAP e ablação por bloco -> images/ e reports/
	$(PYTHON) -m src.evaluation.executar_interpretacao

aplicacao: ## Risco municipal, agrupamentos e risco de meta -> reports/
	$(PYTHON) -m src.evaluation.executar_aplicacao

notebooks: ## Regenera os notebooks a partir dos módulos de src/
	$(PYTHON) -m src.common.gerar_notebooks

testes: ## Testes automatizados (antivazamento e integridade da pipeline)
	$(PYTHON) -m pytest tests/ -v

tudo: features dados eda modelo-a modelo-b interpretar aplicacao ## Pipeline completa

limpar: ## Remove artefatos locais (dados e modelos são reproduzíveis)
	rm -rf data/raw/* data/interim/* data/processed/* models/*.joblib
	find . -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null || true
