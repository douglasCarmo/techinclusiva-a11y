# TechInclusiva - Auditoria de Acessibilidade (WCAG 2.1 AA)

Auditoria automatizada com Axe CLI e relatório gerado em Python.

## Como executar
```bash
npm install
pip install reportlab
python -m http.server 8080      # terminal 1
npm run axe                     # terminal 2
npm run axe:corrigido
python parser_acessibilidade.py resultado_axe.json --depois resultado_axe_corrigido.json --html-corrigido index_corrigido.html --github URL_DO_REPO
```

## Arquivos
- `index.html`: página com falhas / `index_corrigido.html`: versão corrigida
- `resultado_axe.json`, `resultado_axe_corrigido.json`: saídas do Axe
- `parser_acessibilidade.py` (cópia em `parser.py`): gera resumo e PDF
- `relatorio_acessibilidade.pdf`: relatório de remediação