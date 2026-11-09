"""Relatório individual do instrumento: junta, por instrumento, tudo o que o painel precisa para as 3 páginas
(resumo, execução física e execução financeira) e grava em cerca de 1.000 arquivos pequenos (relatorio/NNN.json.gz, pelos 3 últimos
caracteres do número), para o painel baixar só o pedaço do instrumento pedido.
Grava também relatorio/indice.json.gz para a busca inteligente (instrumento, proposta, proponente, CNPJ, município, fornecedor).
Uso: python scripts/relatorio.py SAIDA
"""
import collections, csv, gzip, json, os, re, sys

csv.field_size_limit(10**9)
P = sys.argv[1] if len(sys.argv) > 1 else 'saida'
OUT = os.path.join(P, 'relatorio')


def ler(nome):
    caminho = os.path.join(P, nome)
    if not os.path.exists(caminho):
        print('sem', nome)
        return []
    with open(caminho, encoding='utf-8') as f:
        return list(csv.DictReader(f))


def num(s):
    s = (s or '').strip()
    if not s:
        return 0.0
    if ',' in s:
        s = s.replace('.', '').replace(',', '.')
    try:
        return round(float(s), 2)
    except ValueError:
        return 0.0


def chave(nr):
    k = re.sub(r'[^0-9A-Z]', '', str(nr).upper())
    return k[-3:].rjust(3, '0')


def pega(r, *nomes):
    for n in nomes:
        if r.get(n) not in (None, ''):
            return r[n]
    return ''


inst = ler('instrumentos.csv')
por_nr = {i['nr_instrumento']: i for i in inst}
prop_nr = {i.get('id_proposta'): i['nr_instrumento'] for i in inst if i.get('id_proposta')}


def nr_de(r):
    n = r.get('NR_CONVENIO') or ''
    if n in por_nr:
        return n
    return prop_nr.get(r.get('ID_PROPOSTA') or '', '')


R = collections.defaultdict(lambda: collections.defaultdict(list))

CAMPOS_I = ['nr_instrumento', 'ug_emitente', 'situacao', 'subsituacao', 'ano', 'nr_processo', 'data_assinatura', 'data_publicacao',
            'inicio_vigencia', 'fim_vigencia', 'fim_vigencia_original', 'limite_prestacao_contas', 'clausula_suspensiva_ate',
            'situacao_contratacao', 'valor_global', 'valor_global_original', 'valor_repasse', 'valor_contrapartida', 'valor_empenhado',
            'valor_desembolsado', 'valor_a_desembolsar', 'pct_desembolsado', 'ingresso_contrapartida', 'rendimento_aplicacao',
            'saldo_em_conta', 'ultimo_desembolso', 'dias_sem_desembolso', 'qtd_aditivos', 'qtd_prorrogacoes', 'saldo_devolvido_tesouro',
            'saldo_devolvido_convenente', 'em_processo_tce', 'inadimplente_desde', 'ugs_empenho', 'notas_empenho', 'id_proposta',
            'nr_proposta', 'ano_proposta', 'modalidade', 'cnpj_proponente', 'proponente', 'natureza_juridica', 'uf', 'municipio',
            'objeto', 'cod_programa', 'programa', 'acao_orcamentaria', 'nr_emenda', 'parlamentar', 'tipo_parlamentar', 'valor_emenda',
            'qtd_ajustes_pt', 'ultimo_ajuste_pt']
for i in inst:
    R[i['nr_instrumento']]['i'] = {k: i[k] for k in CAMPOS_I if i.get(k) not in (None, '', '0.00', '0')}

# empenho usado em cada desembolso (empenho_desembolso.csv · se não existir, fica em branco)
NE_DES = collections.defaultdict(list)
for r in ler('empenho_desembolso.csv'):
    if r.get('id_desembolso'):
        NE_DES[r['id_desembolso']].append(r.get('ne', ''))

for r in ler('desembolsos.csv'):
    n = nr_de(r)
    if n:
        R[n]['des'].append([r.get('DATA_DESEMBOLSO', ''), r.get('NR_SIAFI', ''), num(r.get('VL_DESEMBOLSADO')), ' · '.join(NE_DES.get(r.get('ID_DESEMBOLSO', ''), []))])

FORN = {}
for r in ler('pagamentos.csv'):
    n = nr_de(r)
    if not n:
        continue
    doc = ' '.join(x for x in [r.get('DESC_DL', ''), r.get('NR_DL', '')] if x)
    cnpj = r.get('IDENTIF_FORNECEDOR', '')
    R[n]['pag'].append([r.get('DATA_PAG', ''), r.get('NOME_FORNECEDOR', ''), cnpj, doc, num(r.get('VL_PAGO')), r.get('TP_MOV_FINANCEIRA', ''), r.get('DATA_EMISSAO_DL', '')])
    if cnpj:
        f = FORN.setdefault(cnpj, [r.get('NOME_FORNECEDOR', ''), set()])
        f[1].add(n)

for r in ler('cronograma_desembolso.csv'):
    n = nr_de(r)
    if n:
        R[n]['cro'].append([r.get('NR_PARCELA_CRONO_DESEMBOLSO', ''), r.get('MES_CRONO_DESEMBOLSO', ''), r.get('ANO_CRONO_DESEMBOLSO', ''),
                            r.get('TIPO_RESP_CRONO_DESEMBOLSO', ''), num(r.get('VALOR_PARCELA_CRONO_DESEMBOLSO'))])

for r in ler('aditivos.csv'):
    n = nr_de(r)
    if n:
        R[n]['ta'].append([r.get('NUMERO_TA', ''), r.get('TIPO_TA', ''), r.get('DT_ASSINATURA_TA', ''), r.get('DT_FIM_TA', ''),
                           num(r.get('VL_GLOBAL_TA')), (r.get('JUSTIFICATIVA_TA') or '')[:300]])

for r in ler('prorrogacoes.csv'):
    n = nr_de(r)
    if n:
        R[n]['pr'].append([r.get('NR_PRORROGA', ''), r.get('DT_ASSINATURA_PRORROGA', ''), r.get('DT_FIM_PRORROGA', ''), r.get('DIAS_PRORROGA', ''), r.get('SIT_PRORROGA', '')])

for r in ler('ajustes_pt.csv'):
    n = nr_de(r)
    if n:
        R[n]['aj'].append([r.get('NR_AJUSTE_PT', ''), r.get('DATA_SOLICITACAO_AJUSTE_PT', ''), r.get('SITUACAO_SOLICITACAO_AJUSTE_PT', '')])

for r in ler('painel_empenhos.csv'):
    n = r.get('nr_instrumento', '')
    if n in por_nr:
        R[n]['ne'].append([r.get('ne', ''), r.get('ug', ''), r.get('data', ''), r.get('tipo', ''), num(r.get('valor')), 1 if r.get('ns_saldo') else 0])   # 6º: cópia da transferência de saldo (NS SALDO), não soma

for r in ler('historico_situacao.csv'):
    n = nr_de(r)
    if n:
        R[n]['hist'].append([(r.get('DIA_HISTORICO_SIT') or '')[:10], r.get('HISTORICO_SIT', '')])

for r in ler('painel_obras.csv'):
    n = r.get('nr_instrumento', '')
    if n in por_nr:
        R[n]['obra'] = {k: r.get(k, '') for k in ('situacao_obra', 'pct_fisico', 'valor_obra', 'valor_realizado', 'nr_medicao', 'situacao_medicao',
                                                   'fim_ultima_medicao', 'dias_sem_medicao', 'inicio_obra', 'link_transparencia')}

# PAD: itens do plano de aplicação detalhado (ligado pela proposta)
for r in ler('pad.csv'):
    n = nr_de(r)
    if n:
        R[n]['pad'].append([pega(r, 'DESCRICAO_ITEM', 'DESC_ITEM', 'DESCRICAO'), pega(r, 'NATUREZA_DESPESA', 'COD_NATUREZA_DESPESA'),
                            pega(r, 'TIPO_DESPESA_ITEM', 'NATUREZA_AQUISICAO'), pega(r, 'QTD_ITEM', 'QUANTIDADE_ITEM'),
                            pega(r, 'UND_FORNECIMENTO_ITEM', 'UNIDADE_FORNECIMENTO'), num(pega(r, 'VALOR_UNITARIO_ITEM', 'VL_UNITARIO_ITEM')),
                            num(pega(r, 'VALOR_TOTAL_ITEM', 'VL_TOTAL_ITEM')), pega(r, 'SIT_ITEM', 'SITUACAO_ITEM'), pega(r, 'ID_META', ''), pega(r, 'ID_ETAPA', '')])

# execução do convenente: processos de execução (licitações) e contratos/subconvênios · guarda as colunas como vêm (o painel escolhe o que mostrar)
TIRA = {'NR_CONVENIO', 'ID_PROPOSTA'}
def enxuto(r):
    return {k: v for k, v in r.items() if v not in (None, '') and k not in TIRA}
lic_nr = {}
for r in ler('licitacoes.csv'):
    n = nr_de(r)
    if n:
        R[n]['lic'].append(enxuto(r))
        if r.get('ID_LICITACAO'):
            lic_nr[r['ID_LICITACAO']] = n
for r in ler('contratos_convenente.csv'):
    n = nr_de(r) or lic_nr.get(r.get('ID_LICITACAO') or '', '')
    if n:
        R[n]['ctc'].append(enxuto(r))

# metas e etapas do cronograma físico
etapas = collections.defaultdict(list)
for r in ler('etapas.csv'):
    etapas[r.get('ID_META', '')].append([pega(r, 'NR_ETAPA'), pega(r, 'DESC_ETAPA', 'ESPECIFICACAO_ETAPA'), pega(r, 'DATA_INICIO_ETAPA'), pega(r, 'DATA_FIM_ETAPA'),
                                         pega(r, 'QTD_ETAPA'), pega(r, 'UND_FORNECIMENTO_ETAPA'), num(pega(r, 'VL_ETAPA', 'VALOR_ETAPA'))])
for r in ler('metas.csv'):
    n = nr_de(r)
    if n:
        R[n]['metas'].append([pega(r, 'NR_META'), pega(r, 'DESC_META', 'ESPECIFICACAO_META'), pega(r, 'DATA_INICIO_META'), pega(r, 'DATA_FIM_META'),
                              pega(r, 'QTD_META'), pega(r, 'UND_FORNECIMENTO_META'), num(pega(r, 'VL_META', 'VALOR_META')),
                              sorted(etapas.get(r.get('ID_META', ''), []), key=lambda e: (len(e[0]), e[0]))])

# linha do tempo: em ordem de data, sem repetir a mesma situação seguida
def _d(s):
    m = re.match(r'(\d{2})/(\d{2})/(\d{4})', s or '')
    return (m.group(3) + m.group(2) + m.group(1)) if m else (s or '')
for d in R.values():
    if d.get('hist'):
        h, ult = [], None
        for x in sorted(d['hist'], key=lambda x: _d(x[0])):
            if x[1] != ult:
                h.append(x)
                ult = x[1]
        d['hist'] = h

# ---------- gravação em pedaços ----------
os.makedirs(OUT, exist_ok=True)
pedacos = collections.defaultdict(dict)
for n, d in R.items():
    if 'i' not in d:
        continue
    pedacos[chave(n)][n] = d
for k, v in pedacos.items():
    with gzip.open(os.path.join(OUT, k + '.json.gz'), 'wt', encoding='utf-8', compresslevel=9) as f:   # o painel descompacta no navegador
        json.dump(v, f, ensure_ascii=False, separators=(',', ':'))

# índice para a busca: [instrumento, proposta, proponente, CNPJ, município, UF, situação, modalidade, UG]
ind = [[i['nr_instrumento'], i.get('nr_proposta', ''), i.get('proponente', '')[:80], i.get('cnpj_proponente', ''), i.get('municipio', ''), i.get('uf', ''),
        i.get('situacao', ''), i.get('modalidade', ''), i.get('ug_emitente', '')] for i in inst]
forn = {c: [v[0][:80], sorted(v[1])] for c, v in FORN.items()}
with gzip.open(os.path.join(OUT, 'indice.json.gz'), 'wt', encoding='utf-8', compresslevel=9) as f:
    json.dump({'inst': ind, 'forn': forn}, f, ensure_ascii=False, separators=(',', ':'))
tam = sum(os.path.getsize(os.path.join(OUT, x)) for x in os.listdir(OUT))
print(f'relatório: {len(R)} instrumentos · {len(pedacos)} pedaços · {len(forn)} fornecedores · {tam/1048576:.1f} MB')
print('com processo de execução:', sum(1 for d in R.values() if d.get('lic')), '· com contrato do convenente:', sum(1 for d in R.values() if d.get('ctc')))
print('com PAD:', sum(1 for d in R.values() if d.get('pad')), '· com metas:', sum(1 for d in R.values() if d.get('metas')))
