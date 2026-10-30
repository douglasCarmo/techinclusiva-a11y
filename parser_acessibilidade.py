"""
Parser de relatórios do Axe-core CLI.
Lê resultado_axe.json, classifica violações por severidade,
mapeia para critérios WCAG 2.1 e gera resumo no terminal + PDF.
"""
import json
import re
import sys
from collections import defaultdict
from datetime import datetime

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

ARQUIVO_JSON = "resultado_axe.json"
ARQUIVO_PDF = "relatorio_acessibilidade.pdf"
ORDEM = ["critical", "serious", "moderate", "minor"]
COR = {
    "critical": colors.HexColor("#b71c1c"),
    "serious": colors.HexColor("#e65100"),
    "moderate": colors.HexColor("#f9a825"),
    "minor": colors.HexColor("#1565c0"),
}


def carregar(caminho):
    """Carrega o JSON; o Axe CLI salva uma lista, o axe-core puro um dict."""
    with open(caminho, encoding="utf-8") as f:
        dados = json.load(f)
    return dados[0] if isinstance(dados, list) else dados


def tags_para_wcag(tags):
    """Converte tags tipo 'wcag143' em '1.4.3' e extrai o nível (A/AA)."""
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
    resultado = []
    for v in relatorio.get("violations", []):
        criterios, nivel = tags_para_wcag(v.get("tags", []))
        resultado.append({
            "id": v["id"],
            "impacto": v.get("impact") or "minor",
            "descricao": v.get("help", ""),
            "detalhe": v.get("description", ""),
            "url": v.get("helpUrl", ""),
            "criterios": criterios or ["-"],
            "nivel": nivel,
            "elementos": [
                {
                    "seletor": " ".join(n.get("target", [])),
                    "html": n.get("html", ""),
                    "correcao": n.get("failureSummary", ""),
                }
                for n in v.get("nodes", [])
            ],
        })
    resultado.sort(key=lambda x: ORDEM.index(x["impacto"]))
    return resultado


def resumo_terminal(violacoes, url):
    contagem = defaultdict(int)
    for v in violacoes:
        contagem[v["impacto"]] += 1
    total_elem = sum(len(v["elementos"]) for v in violacoes)

    print("=" * 70)
    print(f"RELATÓRIO DE ACESSIBILIDADE - {url}")
    print(f"Gerado em {datetime.now():%d/%m/%Y %H:%M}")
    print("=" * 70)
    print(f"Regras violadas: {len(violacoes)} | Elementos afetados: {total_elem}\n")
    for sev in ORDEM:
        print(f"  {sev.upper():<10} {contagem[sev]}")
    print("-" * 70)
    for v in violacoes:
        print(f"\n[{v['impacto'].upper()}] {v['id']} (WCAG {', '.join(v['criterios'])} | Nível {v['nivel']})")
        print(f"  {v['descricao']}")
        for e in v["elementos"]:
            print(f"   -> {e['seletor']}")


def gerar_pdf(violacoes, url, caminho):
    est = getSampleStyleSheet()
    doc = SimpleDocTemplate(caminho, pagesize=A4, leftMargin=2*cm, rightMargin=2*cm)
    el = [
        Paragraph("Relatório de Remediação de Acessibilidade", est["Title"]),
        Paragraph(f"TechInclusiva - WCAG 2.1 (A/AA)<br/>URL auditada: {url}<br/>"
                  f"Data: {datetime.now():%d/%m/%Y %H:%M}", est["Normal"]),
        Spacer(1, 12),
        Paragraph("Resumo por severidade", est["Heading2"]),
    ]

    contagem = defaultdict(int)
    for v in violacoes:
        contagem[v["impacto"]] += 1
    tabela = Table([["Severidade", "Regras violadas"]] +
                   [[s, contagem[s]] for s in ORDEM], colWidths=[6*cm, 4*cm])
    tabela.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
    ]))
    el += [tabela, Spacer(1, 12), Paragraph("Detalhamento", est["Heading2"])]

    for v in violacoes:
        cor = COR[v["impacto"]].hexval()[2:]
        el.append(Paragraph(
            f'<font color="#{cor}"><b>[{v["impacto"].upper()}]</b></font> '
            f'<b>{v["id"]}</b> - WCAG {", ".join(v["criterios"])} (Nível {v["nivel"]})',
            est["Heading3"]))
        el.append(Paragraph(v["descricao"], est["Normal"]))
        for e in v["elementos"]:
            html = e["html"].replace("<", "&lt;").replace(">", "&gt;")
            corr = e["correcao"].replace("\n", "<br/>").replace("<", "&lt;")
            el.append(Paragraph(f"<b>Seletor:</b> {e['seletor']}", est["Normal"]))
            el.append(Paragraph(f"<font face='Courier' size=8>{html}</font>", est["Normal"]))
            el.append(Paragraph(f"<i>Correção:</i> {corr}", est["Normal"]))
            el.append(Spacer(1, 4))
        el.append(Spacer(1, 8))
    doc.build(el)
    print(f"\nPDF salvo em: {caminho}")


if __name__ == "__main__":
    arquivo = sys.argv[1] if len(sys.argv) > 1 else ARQUIVO_JSON
    rel = carregar(arquivo)
    viol = extrair_violacoes(rel)
    url = rel.get("url", "http://localhost:8080/index.html")
    resumo_terminal(viol, url)
    gerar_pdf(viol, url, ARQUIVO_PDF)