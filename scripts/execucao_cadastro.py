"""Cadastro automático do Painel de Execução Financeira: instrumentos vigentes das 5 UGs, já no formato do painel.

Lê o que o robô já gerou na pasta (contratos da API Contratos.gov.br, parcerias do Transferegov, TED) e grava:
  execucao_instrumentos.csv  um instrumento por linha (chave estável: CTR<id API> · TGV<nº instrumento> · TED<nº SIAFI>)
  execucao_previsao.csv      previsão por competência (parcerias: cronograma do concedente; TED: cronograma do plano de ação)
                             contratos não vêm aqui: o Apps Script gera a previsão pela parcela e pela vigência

Quem entra:
  Contratos  situação Ativo na API. Vigentes → condicao VIGENTE. Vencidos → VENCIDO_COM_NE (o Apps Script só importa
             se alguma NE do contrato ainda tiver saldo no Tesouro). ACT fica de fora (não tem pagamento).
  Parcerias  todas "Em execução" (as com a desembolsar entram com previsão, inclusive parcela atrasada de anos anteriores).
             A previsão do ano é o a desembolsar, limitado ao saldo das NEs, em jul/ANO (o Apps Script aplica o limite).
  TED        enviados pelas UGs da SDR, em execução.
Uso: python scripts/execucao_cadastro.py PASTA   (ANO do exercício: variável EXECUCAO_ANO, padrão 2027)
"""
import csv, io, unicodedata, urllib.request, os, re, sys, time

PASTA = sys.argv[1] if len(sys.argv) > 1 else 'saida'
ANO = int(os.environ.get('EXECUCAO_ANO', '2027'))
UGS = {'130010', '420013', '130141', '130255', '135098'}
HOJE = time.strftime('%Y-%m-%d')
INI, FIM = f'{ANO - 1}-12', f'{ANO}-12'
DEP_UG = {'130010': 'CEPLAC', '130141': 'CGPI', '130255': 'PROMAQ', '135098': 'CGPI'}
DEP_ACAO_PO = {('215A', '0005'): 'DEFLO'}   # 10/11/2026: 215A · PO 0005 (Apoio ao Desenvolvimento Territorial Rural) = DEFLO; vale antes da regra por ação
DEP_ACAO = {'20ZY': 'CEPLAC', '8593': 'DEPROS', '214Z': 'DIAGRO', '00PN': 'DIAGRO', '215A': 'DECAP', '8622': 'DECAP', '21B6': 'DECAP', '8606': 'DECAP', '2000': 'GABINETE', '20ZV': 'CGPI'}
REGIAO = {**dict.fromkeys('AC AM AP PA RO RR TO'.split(), 'Norte'), **dict.fromkeys('AL BA CE MA PB PE PI RN SE'.split(), 'Nordeste'),
          **dict.fromkeys('DF GO MS MT'.split(), 'Centro-Oeste'), **dict.fromkeys('ES MG RJ SP'.split(), 'Sudeste'), **dict.fromkeys('PR RS SC'.split(), 'Sul')}
MES = {m: i + 1 for i, m in enumerate('JAN FEV MAR ABR MAI JUN JUL AGO SET OUT NOV DEZ'.split())}
COLS = ['chave', 'condicao', 'formalizacao', 'orcamento', 'ug', 'numero', 'instrumento', 'proposta', 'processo_raiz', 'favorecido', 'cnpj',
        'modalidade', 'objeto', 'vigencia_ini', 'vigencia_fim', 'valor_global', 'valor_parcela', 'base_previsao', 'nes', 'uf', 'regiao', 'acao', 'a_desembolsar', 'sigla', 'a_desembolsar_futuro']


def ler(nome):
    c = os.path.join(PASTA, nome)
    if not os.path.exists(c):
        print(f'  (sem {nome})')
        return []
    with open(c, encoding='utf-8') as fh:
        return list(csv.DictReader(fh))


def num(v):
    s = str(v or '').strip().replace('R$', '').replace(' ', '')
    if not s:
        return 0.0
    if ',' in s:
        s = s.replace('.', '').replace(',', '.')
    try:
        return float(s)
    except ValueError:
        return 0.0


def iso(s):
    s = str(s or '').strip()
    m = re.match(r'(\d{2})/(\d{2})/(\d{4})', s)
    return f'{m.group(3)}-{m.group(2)}-{m.group(1)}' if m else s[:10]


def processo(s):
    """21000048696202672 → 21000.048696/2026-72 (formato SEI)."""
    s = str(s or '').strip()
    d = re.sub(r'\D', '', s)
    return f'{d[:5]}.{d[5:11]}/{d[11:15]}-{d[15:17]}' if len(d) == 17 else s


def cnpj(s):
    d = re.sub(r'\D', '', str(s or ''))
    return f'{d[:2]}.{d[2:5]}.{d[5:8]}/{d[8:12]}-{d[12:]}' if len(d) == 14 else str(s or '').strip()


def meses(ini, fim):
    try:
        a1, m1 = int(ini[:4]), int(ini[5:7]); a2, m2 = int(fim[:4]), int(fim[5:7])
        return max(1, (a2 - a1) * 12 + (m2 - m1))
    except (ValueError, IndexError):
        return 0


def previsao_contrato(c):
    """Parcela mensal estimada e de onde ela veio (a API costuma registrar serviço contínuo como 1 parcela = valor global)."""
    parcelas, parcela, glob = int(num(c.get('Nº parcelas')) or 0), num(c.get('Valor parcela')), num(c.get('Valor global'))
    ini, fim = iso(c.get('Início vigência')), iso(c.get('Fim vigência'))
    if parcelas > 1 and parcela and parcela < glob * 0.99:
        return round(parcela, 2), 'parcela da API'
    if c.get('Categoria') == 'Compras':
        return 0, 'compra: previsão manual'
    if not glob:
        return 0, 'sem valor: previsão manual'
    if not fim or fim >= '2090':
        return round(glob / 12, 2), 'valor global ÷ 12 (sem fim de vigência)'
    m = meses(ini, fim)
    return (round(glob / m, 2), f'valor global ÷ {m} meses de vigência') if m else (0, 'previsão manual')


def contratos(saida):
    ctr, emp = ler('contratos_api_ctr.csv'), ler('contratos_api_emp.csv')
    nes = {}
    for e in emp:
        ne = (e.get('Nota de empenho') or '').strip().upper()
        if ne and (e.get('UG da NE') == e.get('UG contrato') or e.get('UG da NE') in UGS) and ne[:4].isdigit() and int(ne[:4]) >= ANO - 3:
            nes.setdefault(e['ID contrato (API)'], []).append((ne, e.get('UG da NE')))
    tipo = {'Contrato': 'Contrato', 'Empenho': 'Não contratual', 'Outros': 'Não contratual'}
    n = {'VIGENTE': 0, 'VENCIDO_COM_NE': 0}
    for c in ctr:
        ug = c.get('UG atual', '')
        da_base = c.get('Na Base Contratos') == 'SIM'   # unidade (ex.: CEPLAC regional) sob o nosso controle, pela planilha Base Contratos
        if (ug not in UGS and not da_base) or c.get('Situação') != 'Ativo' or 'ACT' in c.get('Tipo', '') or 'Cooperação' in c.get('Tipo', ''):
            continue
        pares = nes.get(c['ID contrato (API)'], [])
        if ug not in UGS:   # contrato na UG da unidade: no painel fica a UG que paga (a da NE), se for uma das nossas
            ugs_ne = [u for _, u in pares if u in UGS]
            ug = ugs_ne[0] if ugs_ne else ug
        fim = iso(c.get('Fim vigência'))
        cond = 'VIGENTE' if not fim or fim >= HOJE else 'VENCIDO_COM_NE'
        lst = sorted({ne for ne, u in pares if u == ug})
        if cond == 'VENCIDO_COM_NE' and not lst:
            continue
        n[cond] += 1
        parcela, base = previsao_contrato(c)
        n[base] = n.get(base, 0) + 1
        saida.append({'chave': 'CTR' + c['ID contrato (API)'], 'condicao': cond, 'formalizacao': tipo.get(c.get('Tipo'), 'Contrato'),
                      'orcamento': DEP_UG.get(ug, '') or ('CEPLAC' if 'CEPLAC' in (c.get('Nome UG origem') or '').upper() else ''), 'ug': ug, 'sigla': c.get('Unidade (Base)', ''), 'numero': c.get('Nº contrato', ''), 'processo_raiz': c.get('Processo', ''),
                      'favorecido': c.get('Fornecedor', ''), 'cnpj': c.get('CNPJ/CPF', ''), 'modalidade': c.get('Modalidade', ''),
                      'objeto': (c.get('Objeto') or '').strip(), 'vigencia_ini': iso(c.get('Início vigência')), 'vigencia_fim': fim,
                      'valor_global': num(c.get('Valor global')), 'valor_parcela': parcela, 'base_previsao': base, 'nes': ','.join(lst)})
    print(f'  contratos: {n["VIGENTE"]} vigentes + {n["VENCIDO_COM_NE"]} vencidos com NE (o Apps Script confere o saldo)')
    print('    previsão: ' + ' · '.join(f'{k}: {v}' for k, v in n.items() if k not in ('VIGENTE', 'VENCIDO_COM_NE')))


# planilha de controle das parcerias (a mesma do Painel SDR): a coluna DEPARTAMENTO vale primeiro
PLANILHAS_PARCERIAS = ['https://docs.google.com/spreadsheets/d/1T1iWn9lg-WR2RBKKc27xjYh2lvp7wQRzKYbj3zxMmLg/gviz/tq?tqx=out:csv&gid=273934927&range=A:AZ&headers=1',
                       'https://docs.google.com/spreadsheets/d/e/2PACX-1vRPg0j1OKTCJGdpnRYo-hNqXqTaDnpTso9I_DEG08cCjaoFLmT5VsMkdWi9iO26gnsZ24L40glpTWAF/pub?gid=273934927&single=true&output=csv']   # as mesmas do Painel SDR (Parceria SDR)


def dep_planilha():
    """Nº do instrumento → DEPARTAMENTO da planilha BASE GERAL Convênio e Termo (vazio ou '-' não conta)."""
    sa = lambda x: ''.join(c for c in unicodedata.normalize('NFD', str(x or '')) if unicodedata.category(c) != 'Mn').upper().strip()
    rows, erro = [], ''
    for url in PLANILHAS_PARCERIAS:
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers={'User-Agent': 'painel-sdr-mapa/1.0'}), timeout=90) as r:
                rows = list(csv.reader(io.StringIO(r.read().decode('utf-8', 'ignore'))))
            if rows:
                break
        except Exception as e:
            erro = str(e)
    if not rows:
        print(f'  planilha de parcerias: não li ({erro}); departamento pela regra de UG/ação', flush=True)
        return {}
    hi = next((i for i, r in enumerate(rows[:30]) if 'DEPARTAMENTO' in [sa(c) for c in r] and any('INSTRUMENTO' in sa(c) for c in r)), -1)
    if hi < 0:
        print('  planilha de parcerias: coluna DEPARTAMENTO não encontrada', flush=True)
        return {}
    H = [sa(c) for c in rows[hi]]
    iD = H.index('DEPARTAMENTO')
    iN = next((i for i, h in enumerate(H) if re.match(r'^N\S*\s+INSTRUMENTO$', h) or h in ('NO INSTRUMENTO', 'N INSTRUMENTO')), next((i for i, h in enumerate(H) if 'INSTRUMENTO' in h), -1))
    out = {}
    for r in rows[hi + 1:]:
        n, d = (r[iN] if iN < len(r) else '').strip(), (r[iD] if iD < len(r) else '').strip().upper()
        if n and d and d != '-':
            out[re.sub(r'\D', '', n)] = d
    print(f'  planilha de parcerias: departamento de {len(out)} instrumento(s)', flush=True)
    return out


def dep_por_po(chave_instrumento):
    """Departamento pela ação + PO dos empenhos do instrumento (PTRES → ação/PO pela base de orçamento)."""
    po = {}
    for r in ler(os.path.join('orcamento', 'orcamento.csv')):
        if (r.get('ptres') or '').strip():
            po[r['ptres'].strip()] = ((r.get('acao') or '').strip(), (r.get('po') or '').strip().zfill(4))
    dep = {}
    for r in ler('painel_empenhos.csv'):
        d = DEP_ACAO_PO.get(po.get((r.get('ptres') or '').strip()))
        if d: dep.setdefault(str(r.get(chave_instrumento) or '').strip(), d)
    return dep


def parcerias(saida, prev):
    inst = [r for r in ler('painel_instrumentos.csv') if r.get('ug_emitente') in UGS and 'EM EXECU' in (r.get('situacao') or '').upper().replace('Ç', 'C')]   # todas em execução, como no Painel SDR (as já 100% desembolsadas ficam sem previsão)
    ids = {r['nr_instrumento'] for r in inst}
    crono, futuro = {}, {}
    for r in ler('cronograma_desembolso.csv'):
        if r.get('TIPO_RESP_CRONO_DESEMBOLSO') != 'Concedente' or r.get('NR_CONVENIO') not in ids:
            continue
        comp = f'{int(r["ANO_CRONO_DESEMBOLSO"]):04d}-{int(r["MES_CRONO_DESEMBOLSO"]):02d}'
        if comp > FIM:   # parcela programada para depois do exercício: não entra na previsão do ano
            futuro[r['NR_CONVENIO']] = futuro.get(r['NR_CONVENIO'], 0) + num(r.get('VALOR_PARCELA_CRONO_DESEMBOLSO'))
        if INI <= comp <= FIM:
            k = crono.setdefault(r['NR_CONVENIO'], {})
            k[comp] = k.get(comp, 0) + num(r.get('VALOR_PARCELA_CRONO_DESEMBOLSO'))
    extra = {}
    for r in ler('planilha_parcerias.csv'):
        if r.get('Nº Instrumento') in crono:
            extra[r['Nº Instrumento']] = r
    dpo, dpl = dep_por_po('nr_instrumento'), dep_planilha()
    forma = {'CONVENIO': 'Convênio', 'CONTRATO DE REPASSE': 'Contrato de Repasse', 'TERMO DE FOMENTO': 'Termo de fomento', 'TERMO DE COLABORACAO': 'Termo de colaboração'}
    n = 0
    for r in inst:
        nr = r['nr_instrumento']
        x, ug, acao = extra.get(nr, {}), r['ug_emitente'], (r.get('acao_orcamentaria') or '')[-4:]
        uf = (r.get('uf') or '').strip()
        saida.append({'chave': 'TGV' + nr, 'condicao': 'VIGENTE', 'formalizacao': forma.get((r.get('modalidade') or '').upper(), (r.get('modalidade') or '').title()),
                      'orcamento': dpl.get(re.sub(r'\D', '', nr)) or DEP_UG.get(ug) or dpo.get(nr) or DEP_ACAO.get(acao, ''), 'ug': ug, 'instrumento': nr, 'proposta': x.get('Nº Proposta', ''),
                      'processo_raiz': processo(r.get('nr_processo')), 'favorecido': r.get('proponente', ''), 'cnpj': cnpj(x.get('CNPJ', '')),
                      'modalidade': (r.get('modalidade') or '').title(), 'objeto': (r.get('objeto') or '').strip(),
                      'vigencia_ini': iso(x.get('Data Início de Vigência Conv.', '')), 'vigencia_fim': iso(r.get('fim_vigencia')),
                      'valor_global': num(r.get('valor_global')), 'valor_parcela': 0, 'base_previsao': 'a desembolsar até o fim do ano (Transferegov), em julho; depois de julho, em dezembro',
                      'nes': ','.join(sorted({n.strip().upper() for n in re.split(r'[,;\s]+', r.get('notas_empenho') or '') if n.strip()})),
                      'uf': uf, 'regiao': REGIAO.get(uf, ''), 'acao': acao, 'a_desembolsar': round(num(r.get('valor_a_desembolsar')), 2), 'a_desembolsar_futuro': round(futuro.get(nr, 0), 2)})
        for comp, v in sorted(crono.get(nr, {}).items()):
            prev.append({'chave': 'TGV' + nr, 'competencia': comp, 'valor': round(v, 2)})
        n += 1
    print(f'  parcerias: {n} em execução ({sum(1 for r in inst if num(r.get("valor_a_desembolsar")) > 0)} com saldo a desembolsar; {len(crono)} com parcela no cronograma entre {INI} e {FIM})')


def teds(saida, prev):
    ted = [t for t in ler(os.path.join('ted', 'ted_planilha.csv')) if t.get('Enviado / recebido') == 'Enviado' and t.get('UG descentralizadora') in UGS and t.get('Situação do termo') == 'EM_EXECUCAO']
    crono = {}
    for c in ler(os.path.join('ted', 'ted_cronograma.csv')):
        m = MES.get(str(c.get('mes_cronograma_plano_trabalho', '')).strip().upper()[:3])
        if not m:
            continue
        comp = f'{int(float(c["ano_cronograma_plano_trabalho"])):04d}-{m:02d}'
        if INI <= comp <= FIM:
            k = crono.setdefault(str(c.get('id_plano_acao', '')).strip(), {})
            k[comp] = k.get(comp, 0) + num(str(c.get('valor_cronograma_plano_trabalho', '0')).replace('.', ','))
    for t in ted:
        ug, acao = t['UG descentralizadora'], (t.get('Ação orçamentária') or '')[-4:]
        chave = 'TED' + t['Nº TED (SIAFI)']
        saida.append({'chave': chave, 'condicao': 'VIGENTE', 'formalizacao': 'TED', 'orcamento': DEP_UG.get(ug) or DEP_ACAO.get(acao, ''), 'ug': ug,
                      'instrumento': t['Nº TED (SIAFI)'], 'proposta': t.get('Código do plano de ação', ''), 'processo_raiz': t.get('Processo SEI', ''),
                      'favorecido': t.get('Unidade descentralizada', ''), 'cnpj': 'UG ' + t.get('UG descentralizada', ''), 'modalidade': 'Descentralização',
                      'objeto': (t.get('Objeto') or '').strip(), 'vigencia_ini': iso(t.get('Início da vigência')), 'vigencia_fim': iso(t.get('Fim da vigência')),
                      'valor_global': num(str(t.get('Valor firmado', '0')).replace('.', ',')), 'valor_parcela': 0, 'base_previsao': 'cronograma do plano de ação (TED)', 'nes': '', 'acao': acao})
        cr = crono.get(str(t.get('id_plano_acao', '')).strip(), {})
        if not cr and num(str(t.get('A repassar', '0')).replace('.', ',')) > 0:
            cr = {f'{ANO}-01': num(str(t.get('A repassar')).replace('.', ','))}   # sem cronograma no ano: o que falta repassar entra em janeiro
        for comp, v in sorted(cr.items()):
            prev.append({'chave': chave, 'competencia': comp, 'valor': round(v, 2)})
    print(f'  TED: {len(ted)} enviados em execução')


def main():
    print(f'Cadastro do Painel de Execução · exercício {ANO} · competências {INI} a {FIM}')
    inst, prev = [], []
    contratos(inst)
    parcerias(inst, prev)
    teds(inst, prev)
    for i in inst:   # uma linha por instrumento: sem quebras de linha nos textos
        for k, v in i.items():
            if isinstance(v, str):
                i[k] = re.sub(r'\s+', ' ', v).strip()
    vistos, unicos = set(), []
    for i in inst:
        if i['chave'] not in vistos:
            vistos.add(i['chave']); unicos.append(i)
    inst = unicos
    with open(os.path.join(PASTA, 'execucao_instrumentos.csv'), 'w', encoding='utf-8', newline='') as fh:
        w = csv.DictWriter(fh, fieldnames=COLS, extrasaction='ignore'); w.writeheader(); w.writerows(inst)
    with open(os.path.join(PASTA, 'execucao_previsao.csv'), 'w', encoding='utf-8', newline='') as fh:
        w = csv.DictWriter(fh, fieldnames=['chave', 'competencia', 'valor']); w.writeheader(); w.writerows(prev)
    print(f'  gravado: {len(inst)} instrumentos, {len(prev)} linhas de previsão')


if __name__ == '__main__':
    main()
