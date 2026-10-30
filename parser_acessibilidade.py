"""
parser_acessibilidade.py
------------------------
Parser de relatórios JSON do Axe-core CLI (WCAG 2.1 A/AA).

O que faz:
  1. Lê o JSON gerado pelo Axe (antes e, opcionalmente, depois da correção).
  2. Extrai as violações e classifica por severidade
     (critical, serious, moderate, minor).
  3. Mapeia cada regra para o critério de sucesso WCAG e o nível (A/AA).
  4. Lista os seletores CSS / HTML dos elementos afetados.
  5. Mostra um resumo no terminal e gera um relatório PDF com
     diagnóstico, comparativo antes/depois, HTML corrigido e link do GitHub.

Uso:
  python parser_acessibilidade.py resultado_axe.json

  python parser_acessibilidade.py resultado_axe.json ^
      --depois resultado_axe_corrigido.json ^
      --html-corrigido index_corrigido.html ^
      --github https://github.com/USUARIO/techinclusiva-a11y ^
      --integrantes "Nome 1, Nome 2" ^
      --saida relatorio_acessibilidade.pdf

(No PowerShell use a crase ` no lugar de ^ para quebrar linha.)

Dependência: pip install reportlab
"""
import argparse
import json
import re
import textwrap
from collections import Counter
from datetime import datetime
from pathlib import Path
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import (Paragraph, Preformatted, SimpleDocTemplate,
                                Spacer, Table, TableStyle)

ORDEM = ["critical", "serious", "moderate", "minor"]
COR = {
    "critical": "#b71c1c",
    "serious": "#e65100",
    "moderate": "#f9a825",
    "minor": "#1565c0",
}

# Orientação de remediação por regra do Axe (para a equipe de desenvolvimento)
REMEDIACAO = {
    "color-contrast": "Aumentar o contraste do texto para no mínimo 4,5:1 (texto normal) ou 3:1 (texto grande).",
    "document-title": "Adicionar um <title> descritivo e não vazio dentro do <head>.",
    "html-has-lang": 'Declarar o idioma da página, por exemplo <html lang="pt-BR">.',
    "image-alt": 'Incluir alt descritivo em imagens informativas; usar alt="" em imagens decorativas.',
    "link-name": "Dar texto discernível ao link (texto visível, aria-label ou alt na imagem interna).",
    "select-name": "Associar um <label for> ao <select> (ou usar aria-label).",
    "label": "Associar um <label for> ao campo de formulário.",
    "button-name": "Dar texto discernível ao botão.",
    "page-has-heading-one": "Incluir um <h1> na página.",
    "heading-order": "Manter a hierarquia de títulos sem pular níveis (h1, h2, h3...).",
}


def esc(texto):
    """Escapa caracteres especiais para uso em Paragraph do reportlab."""
    return escape(str(texto)).replace("\n", "<br/>")


def carregar(caminho):
    """Carrega o JSON. O Axe CLI salva uma lista; o axe-core puro, um dict."""
    with open(caminho, encoding="utf-8") as f:
        dados = json.load(f)
    return dados[0] if isinstance(dados, list) else dados


def tags_para_wcag(tags):
    """Converte tags como 'wcag143' em '1.4.3' e identifica o nível (A/AA)."""
    criterios, nivel = [], "N/A (boa prática)"
    for t in tags:
        m = re.fullmatch(r"wcag(\d)(\d)(\d+)", t)
        if m:
            criterios.append(".".join(m.groups()))
        if t in ("wcag2a", "wcag21a"):
            nivel = "A"
        elif t in ("wcag2aa", "wcag21aa"):
            nivel = "AA"
    return criterios, nivel


def extrair_violacoes(relatorio):
    """Retorna a lista de violações já normalizada e ordenada por severidade."""
    resultado = []
    for v in relatorio.get("violations", []):
        criterios, nivel = tags_para_wcag(v.get("tags", []))
        resultado.append({
            "id": v["id"],
            "impacto": v.get("impact") or "minor",
            "descricao": v.get("help", ""),
            "url": v.get("helpUrl", ""),
            "criterios": criterios or ["-"],
            "nivel": nivel,
            "elementos": [
                {
                    "seletor": " ".join(map(str, n.get("target", []))),
                    "html": n.get("html", ""),
                    "correcao": n.get("failureSummary", ""),
                }
                for n in v.get("nodes", [])
            ],
        })
    resultado.sort(key=lambda x: ORDEM.index(x["impacto"])
                   if x["impacto"] in ORDEM else len(ORDEM))
    return resultado


def contar_por_severidade(violacoes):
    c = Counter(v["impacto"] for v in violacoes)
    return {s: c.get(s, 0) for s in ORDEM}


def resumo_terminal(violacoes, url, titulo):
    """Imprime o resumo consolidado no terminal."""
    cont = contar_por_severidade(violacoes)
    total_elem = sum(len(v["elementos"]) for v in violacoes)
    print("=" * 70)
    print(f"{titulo} - {url}")
    print(f"Gerado em {datetime.now():%d/%m/%Y %H:%M}")
    print("=" * 70)
    print(f"Regras violadas: {len(violacoes)} | Elementos afetados: {total_elem}\n")
    for s in ORDEM:
        print(f"  {s.upper():<10} {cont[s]}")
    print("-" * 70)
    for v in violacoes:
        print(f"\n[{v['impacto'].upper()}] {v['id']} "
              f"(WCAG {', '.join(v['criterios'])} | Nível {v['nivel']})")
        print(f"  {v['descricao']}")
        for e in v["elementos"]:
            print(f"   -> {e['seletor']}")
    if not violacoes:
        print("\nNenhuma violação encontrada.")
    print()


def tabela(dados, larguras):
    t = Table(dados, colWidths=larguras)
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
    ]))
    return t


def gerar_pdf(antes, depois, url, html_corrigido, github, integrantes, caminho):
    """Monta o relatório PDF de remediação."""
    est = getSampleStyleSheet()
    doc = SimpleDocTemplate(caminho, pagesize=A4, leftMargin=2 * cm,
                            rightMargin=2 * cm, topMargin=2 * cm, bottomMargin=2 * cm)
    el = [
        Paragraph("Relatório de Remediação de Acessibilidade", est["Title"]),
        Paragraph(f"TechInclusiva - conformidade WCAG 2.1 (Níveis A e AA)<br/>"
                  f"Ferramenta: Axe CLI (axe-core)<br/>URL auditada: {esc(url)}<br/>"
                  f"Data: {datetime.now():%d/%m/%Y %H:%M}", est["Normal"]),
    ]
    if integrantes:
        el.append(Paragraph(f"Integrantes: {esc(integrantes)}", est["Normal"]))
    if github:
        el.append(Paragraph(f'Repositório GitHub: <link href="{esc(github)}" '
                            f'color="blue">{esc(github)}</link>', est["Normal"]))

    # 1. Resumo por severidade
    cont = contar_por_severidade(antes)
    el += [Spacer(1, 12), Paragraph("1. Resumo por severidade (antes da correção)", est["Heading2"]),
           tabela([["Severidade", "Regras violadas"]] + [[s, cont[s]] for s in ORDEM],
                  [6 * cm, 4 * cm]),
           Spacer(1, 6),
           Paragraph(f"Total: {len(antes)} regras violadas, "
                     f"{sum(len(v['elementos']) for v in antes)} elementos afetados.",
                     est["Normal"])]

    # 2. Comparativo antes/depois
    if depois is not None:
        n_antes = {v["id"]: len(v["elementos"]) for v in antes}
        n_depois = {v["id"]: len(v["elementos"]) for v in depois}
        linhas = [["Regra", "Antes", "Depois"]]
        for rid in list(n_antes) + [r for r in n_depois if r not in n_antes]:
            linhas.append([rid, n_antes.get(rid, 0), n_depois.get(rid, 0)])
        linhas.append(["TOTAL de elementos", sum(n_antes.values()), sum(n_depois.values())])
        el += [Spacer(1, 12), Paragraph("2. Comparativo antes e depois da correção", est["Heading2"]),
               tabela(linhas, [8 * cm, 3 * cm, 3 * cm])]

    # 3. Detalhamento
    el += [Spacer(1, 12), Paragraph("3. Detalhamento das violações", est["Heading2"])]
    for v in antes:
        cor = COR.get(v["impacto"], "#000000")
        el.append(Paragraph(
            f'<font color="{cor}"><b>[{v["impacto"].upper()}]</b></font> '
            f'<b>{esc(v["id"])}</b> - WCAG {esc(", ".join(v["criterios"]))} '
            f'(Nível {esc(v["nivel"])})', est["Heading3"]))
        el.append(Paragraph(esc(v["descricao"]), est["Normal"]))
        if v["id"] in REMEDIACAO:
            el.append(Paragraph(f"<b>Remediação:</b> {esc(REMEDIACAO[v['id']])}", est["Normal"]))
        for e in v["elementos"]:
            el.append(Paragraph(f"<b>Seletor:</b> {esc(e['seletor'])}", est["Normal"]))
            el.append(Preformatted("\n".join(textwrap.wrap(e["html"], 90)) or "-", est["Code"]))
        el.append(Spacer(1, 8))

    # 4. HTML corrigido
    if html_corrigido:
        el += [Paragraph("4. Código HTML corrigido", est["Heading2"]),
               Preformatted(html_corrigido, est["Code"])]

    # 5. Limitações
    el += [Spacer(1, 12), Paragraph("5. Observações", est["Heading2"]),
           Paragraph("Ferramentas automatizadas detectam apenas parte dos problemas de "
                     "acessibilidade (estimativa de 20% a 50%). Recomenda-se complementar "
                     "com testes manuais: navegação só por teclado, leitor de tela (NVDA) "
                     "e zoom de 200%.", est["Normal"])]
    doc.build(el)
    print(f"PDF salvo em: {caminho}")


def main():
    ap = argparse.ArgumentParser(description="Parser de relatório Axe -> terminal + PDF")
    ap.add_argument("json", nargs="?", default="resultado_axe.json",
                    help="JSON do Axe antes da correção")
    ap.add_argument("--depois", help="JSON do Axe após a correção")
    ap.add_argument("--html-corrigido", help="arquivo HTML corrigido a incluir no PDF")
    ap.add_argument("--github", help="URL do repositório no GitHub")
    ap.add_argument("--integrantes", help="nomes do grupo")
    ap.add_argument("--saida", default="relatorio_acessibilidade.pdf", help="nome do PDF")
    a = ap.parse_args()

    rel_antes = carregar(a.json)
    antes = extrair_violacoes(rel_antes)
    url = rel_antes.get("url", "http://localhost:8080/index.html")
    resumo_terminal(antes, url, "RELATÓRIO DE ACESSIBILIDADE (ANTES)")

    depois = None
    if a.depois:
        rel_depois = carregar(a.depois)
        depois = extrair_violacoes(rel_depois)
        resumo_terminal(depois, rel_depois.get("url", "-"), "RELATÓRIO DE ACESSIBILIDADE (DEPOIS)")

    html = None
    if a.html_corrigido:
        html = Path(a.html_corrigido).read_text(encoding="utf-8")

    gerar_pdf(antes, depois, url, html, a.github, a.integrantes, a.saida)


if __name__ == "__main__":
    main()