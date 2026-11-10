"""Contratos.gov.br (API pública https://contratos.comprasnet.gov.br/api) das UGs da SDR — complemento da Base Contratos do painel.
Grava em PASTA (branch dados): contratos_api_ctr.csv, contratos_api_emp.csv, contratos_api_fat.csv, contratos_api_his.csv, contratos_api_res.csv
(mesmas colunas da planilha "Base API Contratos"). Consulta a API uma vez por dia; nas outras rodadas reaproveita os arquivos do dia.
Os valores financeiros da API NÃO são usados (não batem com o SIAFI): o painel usa o EXE/RAP do Tesouro.
Uso: python scripts/contratos_api.py PASTA_SAIDA"""
import csv, io, json, os, re, shutil, sys, time, unicodedata, urllib.request, urllib.parse, urllib.error
from concurrent.futures import ThreadPoolExecutor

BASE = 'https://contratos.comprasnet.gov.br'
UGS = ['130010', '130141', '130255', '135098', '420013']
OUT = sys.argv[1] if len(sys.argv) > 1 else 'saida'
ANT = os.environ.get('CONTRATOS_ANTERIOR', '')   # pasta com os arquivos da rodada anterior
HOJE = time.strftime('%d/%m/%Y')
# planilha de controle "Base Contratos" (a mesma do Painel SDR): diz quais contratos das unidades da CEPLAC estão sob o nosso controle
BASE_CONTRATOS = 'https://docs.google.com/spreadsheets/d/e/2PACX-1vRyLjeoCobYSRx7o3tiZ7fvj4-FhvKnGiSVxoA8l6yD2CqfJsUidxWN00jLuFpBMrFL6MesSdYuWnrb/pub?gid=668450794&single=true&output=csv'


def _sem_acento(x):
    return ''.join(c for c in unicodedata.normalize('NFD', str(x or '')) if unicodedata.category(c) != 'Mn').upper().strip()


def chave_num(n):
    """00012/2025 · 12/2025 · CT 012/2025 → 12/2025"""
    m = re.search(r'(\d+)\D+(\d{4})', str(n or ''))
    return f'{int(m.group(1))}/{m.group(2)}' if m else ''


def base_contratos():
    """Lê a Base Contratos publicada: números, processos, UGs citadas e a unidade (sigla) de cada contrato."""
    out = {'nums': {}, 'procs': {}, 'ugs': set(), 'numcnpj': {}}
    try:
        with urllib.request.urlopen(urllib.request.Request(BASE_CONTRATOS, headers={'User-Agent': 'painel-sdr-mapa/1.0'}), timeout=90) as r:
            rows = list(csv.reader(io.StringIO(r.read().decode('utf-8', 'ignore'))))
    except Exception as e:
        print(f'  Base Contratos: não li ({e})', flush=True)
        return out
    hi = next((i for i, r in enumerate(rows[:30]) if any('NUMERO DO CONTRATO' in _sem_acento(c) for c in r)), -1)
    if hi < 0:
        print('  Base Contratos: cabeçalho "Número do Contrato" não encontrado', flush=True)
        return out
    H = [_sem_acento(c) for c in rows[hi]]
    ach = lambda f: next((i for i, h in enumerate(H) if f(h)), -1)
    iN, iP, iU = ach(lambda h: 'NUMERO DO CONTRATO' in h), ach(lambda h: 'PROCESSO' in h), ach(lambda h: h == 'UNIDADE')
    iUG = [i for i, h in enumerate(H) if 'UNIDADE GESTORA' in h or 'UNIDADE DA COMPRA' in h or h in ('UG', 'UG RESPONSAVEL')]
    iC = ach(lambda h: h == 'CNPJ' or h.endswith(' CNPJ') or h.startswith('CNPJ'))
    for r in rows[hi + 1:]:
        g = lambda i: (r[i] if 0 <= i < len(r) else '').strip()
        k, pr, un = chave_num(g(iN)), re.sub(r'\D', '', g(iP)), g(iU)
        if not k and not pr:
            continue
        cn = re.sub(r'\D', '', g(iC))
        if k: out['nums'][k] = un
        if k and cn: out['numcnpj'][k + '|' + cn] = un
        if len(pr) >= 15: out['procs'][pr] = un
        for i in iUG:
            out['ugs'].update(re.findall(r'\b(1[0-9]{5})\b', g(i)))
    print(f"  Base Contratos: {len(out['nums'])} contratos · UGs citadas: {', '.join(sorted(out['ugs']))}", flush=True)
    return out
ARQ = {
    'ctr': ['ID contrato (API)', 'UG atual', 'UG de origem', 'Nome UG origem', 'Nº contrato', 'Tipo', 'Categoria', 'Modalidade', 'Situação', 'Fornecedor', 'CNPJ/CPF',
            'Processo', 'Objeto', 'Início vigência', 'Fim vigência', 'Valor inicial', 'Valor global', 'Valor acumulado', 'Nº parcelas', 'Valor parcela', 'Link transparência', 'Consultado em', 'Na Base Contratos', 'Unidade (Base)'],
    'emp': ['ID contrato (API)', 'UG contrato', 'Nº contrato', 'UG da NE', 'Nota de empenho', 'Plano interno', 'Data emissão'],
    'fat': ['ID contrato (API)', 'UG contrato', 'Nº contrato', 'Nº fatura', 'Emissão', 'Vencimento', 'Valor (− glosa)', 'Situação', 'Data liquidação', 'NP / documento SIAFI'],
    'his': ['ID contrato (API)', 'UG contrato', 'Nº contrato', 'Tipo do termo', 'Nº do termo', 'Data assinatura', 'Fim vigência', 'Valor global (novo)', 'Observação',
            'ID termo', 'Qualificação', 'Data publicação', 'Início vigência', 'Valor global', 'Nº parcelas', 'Valor parcela', 'Início novo valor', 'Retroativo', 'Valor retroativo'],
    # quantidade e valor de cada item do contrato em cada termo (postos antes × depois de aditivo/supressão/repactuação)
    'ith': ['ID contrato (API)', 'UG contrato', 'Nº contrato', 'ID item', 'Item', 'Tipo', 'ID termo', 'Tipo do termo', 'Data termo', 'Quantidade', 'Periodicidade', 'Valor unitário', 'Valor total'],
    'res': ['ID contrato (API)', 'UG contrato', 'Nº contrato', 'Função', 'Nome', 'Portaria', 'Situação'],
    'arq': ['ID contrato (API)', 'UG contrato', 'Nº contrato', 'Tipo', 'Descrição', 'Link PDF', 'Link SEI', 'Origem'],
    'itn': ['ID contrato (API)', 'UG contrato', 'Nº contrato', 'Item / posto', 'Tipo', 'Quantidade', 'Valor unitário', 'Valor total', 'Nº item da compra'],
    # ocorrências da fiscalização e garantias contratuais (a API não documenta os campos: pega os nomes mais comuns e guarda o texto)
    'oco': ['ID contrato (API)', 'UG contrato', 'Nº contrato', 'Nº ocorrência', 'Data', 'Situação', 'Descrição'],
    'gar': ['ID contrato (API)', 'UG contrato', 'Nº contrato', 'Tipo', 'Valor', 'Vencimento', 'Situação'],
    'cro': ['ID contrato (API)', 'UG contrato', 'Nº contrato', 'Mês ref', 'Ano ref', 'Vencimento', 'Valor', 'Tipo'],
    'pag': ['ID contrato (API)', 'UG contrato', 'Nº contrato', 'Mão de obra exclusiva', 'Total postos (decreto)', 'Total vagas reservadas', 'Percentual reserva vagas', 'Nº contratação', 'Link PNCP', 'Id contratação PNCP', 'Link edital PNCP',
            'Página lida em', 'Fim vigência na leitura', 'Valor global na leitura', 'Termos na leitura', 'Alteração depois da leitura'],
}
nome = lambda k: os.path.join(OUT, f'contratos_api_{k}.csv')


def get(caminho):
    url = BASE + caminho
    erro = ''
    for t in range(4):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers={'Accept': 'application/json', 'User-Agent': 'painel-sdr-mapa/1.0'}), timeout=90) as r:
                return json.loads(r.read())
        except urllib.error.HTTPError as e:
            if e.code in (400, 401, 404):
                return None
            erro = f'HTTP {e.code} {e.reason} · {(e.read() or b"")[:300].decode("utf-8", "ignore")}'   # 403/429/5xx: guarda o motivo para o diagnóstico
            time.sleep(5 * (t + 1))
        except Exception as e:
            erro = f'{type(e).__name__}: {e}'
            time.sleep(5 * (t + 1))
    raise RuntimeError(f'falhou: {url} · último erro: {erro}')


def pagina(i):
    """Campos que só aparecem na página de transparência do contrato (postos, mão de obra exclusiva, link do PNCP)."""
    try:
        with urllib.request.urlopen(urllib.request.Request(f'{BASE}/transparencia/contratos/{i}', headers={'User-Agent': 'Mozilla/5.0 painel-sdr-mapa'}), timeout=90) as r:
            h = r.read().decode('utf-8', 'ignore')
    except Exception:
        return {}
    def campo(rot):
        m = re.search(r'<strong>\s*' + re.escape(rot) + r'\s*</strong>\s*</td>\s*<td>(.*?)</td>', h, re.S)
        return re.sub(r'\s+', ' ', re.sub(r'<[^>]+>', ' ', m.group(1))).strip() if m else ''
    pn = re.search(r"https://pncp\.gov\.br/app/contratos/[0-9/]+", h)
    return {'mo': campo('Mao obra exclusiva'), 'postos': campo('Total postos contrato decreto'), 'vagas': campo('Total vagas reservadas'),
            'perc': campo('Percentual reserva vagas'), 'ncontr': campo('Numero contratacao'), 'pncp': pn.group(0) if pn else ''}


def compras_pncp(anos):
    """Id da contratação (edital) de cada contrato no PNCP: API de consulta, contratos do MAPA publicados nos anos pedidos.
    Devolve {numeroControlePNCP do contrato: numeroControlePncpCompra}."""
    m = {}
    for ano in sorted(anos):
        for ini, fim in [('0101', '0331'), ('0401', '0630'), ('0701', '0930'), ('1001', '1231')]:
            pg = 1
            while True:
                if sem_tempo():
                    DIAG.append(f'consulta {ano}{ini}-{fim}: sem tempo, parou'); break
                q = urllib.parse.urlencode({'dataInicial': f'{ano}{ini}', 'dataFinal': f'{ano}{fim}', 'cnpjOrgao': '00396895000125', 'pagina': pg, 'tamanhoPagina': 500})
                j = None
                for tent in range(3):   # a API do PNCP oscila: tenta 3 vezes antes de desistir da janela
                    try:
                        with urllib.request.urlopen(urllib.request.Request('https://pncp.gov.br/api/consulta/v1/contratos?' + q, headers={'Accept': 'application/json', 'User-Agent': 'painel-sdr-mapa/1.0'}), timeout=60) as r:
                            j = json.loads(r.read() or b'{}')
                        break
                    except Exception as e:
                        DIAG.append(f'consulta {ano}{ini}-{fim} pág {pg} tentativa {tent+1}: {e}')
                        time.sleep(5 * (tent + 1))
                if j is None:
                    break
                for x in j.get('data') or []:
                    if x.get('numeroControlePNCP') and x.get('numeroControlePncpCompra'):
                        m[x['numeroControlePNCP']] = x['numeroControlePncpCompra']
                if not j.get('paginasRestantes'):
                    break
                pg += 1
    return m


DIAG = []
INICIO = time.time()
PRAZO_PNCP = 18 * 60   # passou disso desde o início do script: para de consultar o PNCP (o passo do robô tem limite de 30 min)


def sem_tempo():
    return time.time() - INICIO > PRAZO_PNCP


def compra_do_contrato(link):
    """Plano B, um contrato por vez: consulta o contrato na API do PNCP e devolve o id da contratação (edital)."""
    mm = re.search(r'/app/contratos/(\d{14})/(\d{4})/0*(\d+)', link or '')
    if not mm or sem_tempo():
        return ''
    url = f'https://pncp.gov.br/api/pncp/v1/orgaos/{mm.group(1)}/contratos/{mm.group(2)}/{mm.group(3)}'
    for tent in range(2):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers={'Accept': 'application/json', 'User-Agent': 'painel-sdr-mapa/1.0'}), timeout=60) as r:
                j = json.loads(r.read() or b'{}')
            idc = j.get('numeroControlePncpCompra') or ''
            if not idc:
                oc = (j.get('orgaoEntidade') or {}).get('cnpj') or mm.group(1)
                if j.get('anoCompra') and j.get('sequencialCompra'):
                    idc = f"{oc}-1-{int(j['sequencialCompra']):06d}/{j['anoCompra']}"
            if not idc:
                DIAG.append(f'contrato {url}: sem id da compra (chaves: {", ".join(sorted(j)[:40])})')
            return idc
        except Exception as e:
            DIAG.append(f'contrato {url} tentativa {tent+1}: {e}')
            time.sleep(3)
    return ''


def link_edital(idc):
    # 10724903000179-1-000062/2025  ->  https://pncp.gov.br/app/editais/10724903000179/2025/62
    mm = re.match(r'(\d{14})-\d+-0*(\d+)/(\d{4})', idc or '')
    return f'https://pncp.gov.br/app/editais/{mm.group(1)}/{mm.group(3)}/{mm.group(2)}' if mm else ''


def num(s):
    s = str(s or '').strip()
    if not s or s in ('None', 'null'):
        return 0.0
    try:
        return float(s.replace('.', '').replace(',', '.')) if ',' in s else float(s)
    except ValueError:
        return 0.0


def br(v):
    return f'{v:.2f}'.replace('.', ',')


def gravar(k, linhas):
    with open(nome(k), 'w', encoding='utf-8', newline='') as fh:
        w = csv.writer(fh); w.writerow(ARQ[k]); w.writerows(linhas)


def reaproveitar():
    if not ANT:
        return False
    p = os.path.join(ANT, 'contratos_api_ctr.csv')
    if not os.path.exists(p):
        return False
    l = list(csv.DictReader(open(p, encoding='utf-8')))
    if not l or l[0].get('Consultado em') != HOJE:
        return False
    if any(not os.path.exists(os.path.join(ANT, f'contratos_api_{k}.csv')) or os.path.getsize(os.path.join(ANT, f'contratos_api_{k}.csv')) < 10 for k in ARQ):
        return False   # arquivo novo (ex.: arquivos do contrato) ainda não existe: consulta a API de novo
    if sum(1 for _ in open(os.path.join(ANT, 'contratos_api_pag.csv'), encoding='utf-8')) < 2:
        return False   # página dos contratos ainda não lida (postos, PNCP)
    if 'Na Base Contratos' not in open(p, encoding='utf-8').readline():
        return False   # coluna nova (contratos das unidades pela Base Contratos)
    if 'Link edital PNCP' not in open(os.path.join(ANT, 'contratos_api_pag.csv'), encoding='utf-8').readline():
        return False   # coluna nova (edital no PNCP)
    pg = list(csv.DictReader(open(os.path.join(ANT, 'contratos_api_pag.csv'), encoding='utf-8')))
    com_link = [x for x in pg if x.get('Link PNCP')]
    if com_link and sum(1 for x in com_link if x.get('Id contratação PNCP')) < 0.5 * len(com_link):
        return False   # poucos editais ligados (a API do PNCP falhou na rodada anterior): consulta de novo
    for k in ARQ:
        q = os.path.join(ANT, f'contratos_api_{k}.csv')
        if os.path.exists(q):
            shutil.copy(q, nome(k))
    print(f'Contratos.gov.br: reaproveitados os arquivos de hoje ({len(l)} contratos)', flush=True)
    remarcar_base()
    return True


def remarcar_base():
    """Refaz, no arquivo de contratos já baixado, a marca "Na Base Contratos" e a unidade (processo, ou número + CNPJ)."""
    bc = base_contratos()
    if not bc['nums']:
        return
    p = nome('ctr'); l = list(csv.DictReader(open(p, encoding='utf-8')))
    if not l or 'Na Base Contratos' not in l[0]:
        return
    n = 0
    for r in l:
        pr, nc = re.sub(r'\D', '', r.get('Processo', '')), chave_num(r.get('Nº contrato')) + '|' + re.sub(r'\D', '', r.get('CNPJ/CPF', ''))
        ok = pr in bc['procs'] or nc in bc['numcnpj']
        r['Na Base Contratos'] = 'SIM' if ok else ''
        r['Unidade (Base)'] = bc['procs'].get(pr) or bc['numcnpj'].get(nc) or (bc['nums'].get(chave_num(r.get('Nº contrato'))) if r.get('UG atual') in UGS else '') or ''
        n += ok
    with open(p, 'w', encoding='utf-8', newline='') as fh:
        w = csv.DictWriter(fh, fieldnames=ARQ['ctr']); w.writeheader(); w.writerows(l)
    print(f'  Base Contratos: {n} contrato(s) da API casados pelo processo ou número + CNPJ', flush=True)


# leitura anterior da página dos contratos (postos, PNCP, edital): usada quando a página não abre na rodada
# (1º a reserva guardada no repositório, por cima a rodada anterior: a mais recente vale)
PAG_ANT, REUSO = {}, {'pag': 0}
for _c in [os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'config', 'contratos_pag_reserva.csv'), os.path.join(ANT, 'contratos_api_pag.csv') if ANT else '']:
    try:
        if _c and os.path.exists(_c):
            _l = list(csv.reader(open(_c, encoding='utf-8')))
            if _l and 'Link edital PNCP' in _l[0]:
                _res = 'reserva' in os.path.basename(_c)
                for r in _l[1:]:
                    if not r or len(r) != len(_l[0]):
                        continue
                    r = (r + [''] * 16)[:16]
                    if _res and not r[11]:
                        r[11] = '27/10/2026'   # dia em que a cópia de reserva foi lida
                    PAG_ANT[r[0]] = r
    except Exception:
        pass


def iso_br(s):
    m = re.match(r'(\d{4})-(\d{2})-(\d{2})', str(s or ''))
    return f'{m.group(3)}/{m.group(2)}/{m.group(1)}' if m else str(s or '')


def dt_api(s):
    m = re.match(r'(\d{4})-(\d{2})-(\d{2})', str(s or ''))
    return (int(m.group(1)), int(m.group(2)), int(m.group(3))) if m else None


def dt_br(s):
    m = re.match(r'(\d{2})/(\d{2})/(\d{4})', str(s or ''))
    return (int(m.group(3)), int(m.group(2)), int(m.group(1))) if m else (9999, 0, 0)


# contratos e termos da rodada anterior: a "foto" de quando a página foi lida pela última vez
CTR_ANT, HIS_ANT = {}, {}
try:
    if ANT and os.path.exists(os.path.join(ANT, 'contratos_api_ctr.csv')):
        for r in csv.DictReader(open(os.path.join(ANT, 'contratos_api_ctr.csv'), encoding='utf-8')):
            CTR_ANT[r['ID contrato (API)']] = [r.get('Fim vigência', ''), r.get('Valor global', '')]
    if ANT and os.path.exists(os.path.join(ANT, 'contratos_api_his.csv')):
        for r in csv.DictReader(open(os.path.join(ANT, 'contratos_api_his.csv'), encoding='utf-8')):
            HIS_ANT[r['ID contrato (API)']] = HIS_ANT.get(r['ID contrato (API)'], 0) + 1
except Exception:
    pass


def ligar_editais(pag):
    """Edital (contratação) no PNCP de cada contrato: link do contrato no PNCP -> numeroControlePNCP -> id da contratação.
    pag: linhas no formato do arquivo contratos_api_pag (índice 8 = link PNCP, 9 = id da contratação, 10 = link do edital)."""
    def ctrl(link):
        mm = re.search(r'/app/contratos/(\d{14})/(\d{4})/0*(\d+)', link or '')
        return f'{mm.group(1)}-2-{int(mm.group(3)):06d}/{mm.group(2)}' if mm else ''
    ctrls = {ctrl(r[8]) for r in pag if r[8]}
    anos = {int(c[-4:]) for c in ctrls if c} | {time.localtime().tm_year}
    try:
        mp = compras_pncp(anos)
    except Exception as e:
        print(f'PNCP: falhou ({e})', flush=True); mp = {}
    plano_b = 0
    for r in pag:
        idc = mp.get(ctrl(r[8]), '') or r[9]
        if not idc and r[8]:
            idc = compra_do_contrato(r[8]); plano_b += 1 if idc else 0
        r[9], r[10] = idc, link_edital(idc)
    print(f'PNCP: {len(mp)} contratos do MAPA lidos · {plano_b} achado(s) contrato por contrato · {sum(1 for r in pag if r[9])} com edital ligado', flush=True)
    try:
        with open(os.path.join(OUT, 'pncp_diagnostico.txt'), 'a', encoding='utf-8') as fh:
            fh.write('\n'.join(DIAG[:400]) or 'PNCP: sem erros')
    except Exception:
        pass


CHAVES = {'oco': [], 'gar': []}


def main():
    if reaproveitar():
        return
    t0 = time.time()
    cs = []
    for ug in UGS:
        for ativo, cam in [(1, f'/api/contrato/ug/{ug}'), (0, f'/api/contrato/inativo/ug/{ug}')]:
            l = get(cam) or []
            for c in l if isinstance(l, list) else []:
                c['_ug'] = ug; c['_ativo'] = ativo; cs.append(c)
    # contratos das unidades (ex.: CEPLAC regionais) que estão na Base Contratos: busca na UG da unidade e fica só com os da Base
    bc = base_contratos()
    # casa pelo processo ou pelo número + CNPJ do fornecedor (só o número repete entre UGs: "12/2025" existe em várias)
    pdig = lambda c: re.sub(r'\D', '', str(c.get('processo') or ''))
    ncn = lambda c: chave_num(c.get('numero')) + '|' + re.sub(r'\D', '', str((c.get('fornecedor') or {}).get('cnpj_cpf_idgener') or ''))
    na_base = lambda c: pdig(c) in bc['procs'] or ncn(c) in bc['numcnpj']
    unid = lambda c: bc['procs'].get(pdig(c)) or bc['numcnpj'].get(ncn(c)) or (bc['nums'].get(chave_num(c.get('numero'))) if c.get('_ug') in UGS else '') or ''
    for c in cs:
        c['_base'], c['_unid'] = na_base(c), unid(c)
    print(f"  na Base, entre os das 5 UGs: {sum(1 for c in cs if c['_base'])}", flush=True)
    ja = {c['id'] for c in cs}; extra = 0
    for ug in sorted(bc['ugs'] - set(UGS)):
        for c in (get(f'/api/contrato/ug/{ug}') or []):
            if isinstance(c, dict) and c.get('id') not in ja and na_base(c):
                c['_ug'], c['_ativo'], c['_base'], c['_unid'] = ug, 1, True, unid(c); cs.append(c); ja.add(c['id']); extra += 1
    print(f'Contratos.gov.br: {len(cs)} contratos ({extra} das unidades, pela Base Contratos)', flush=True)

    def det(c):
        i = c['id']
        d = {k: (get(f'/api/contrato/{i}/{k}') or []) for k in ['empenhos', 'faturas', 'historico', 'responsaveis', 'arquivos', 'itens', 'cronograma', 'ocorrencias', 'garantias']}
        d['pagina'] = pagina(i) if c.get('_ativo') else {}
        return c, d
    with ThreadPoolExecutor(4) as ex:
        D = list(ex.map(det, cs))
    L = {k: [] for k in ARQ}
    for c, d in D:
        o = c['contratante']['orgao_origem']['unidade_gestora_origem']
        ch = [c['id'], c['_ug'], c.get('numero')]
        L['ctr'].append([c['id'], c['_ug'], o.get('codigo'), o.get('nome_resumido'), c.get('numero'), c.get('tipo'), c.get('categoria'), c.get('modalidade'), c.get('situacao'),
                         c['fornecedor'].get('nome'), c['fornecedor'].get('cnpj_cpf_idgener'), c.get('processo'), (c.get('objeto') or '').strip(), c.get('vigencia_inicio'), c.get('vigencia_fim'),
                         br(num(c.get('valor_inicial'))), br(num(c.get('valor_global'))), br(num(c.get('valor_acumulado'))), c.get('num_parcelas'), br(num(c.get('valor_parcela'))),
                         f"https://contratos.comprasnet.gov.br/transparencia/contratos/{c['id']}", HOJE, 'SIM' if c.get('_base') else '', c.get('_unid', '')])
        for e in d['empenhos'] if isinstance(d['empenhos'], list) else []:
            L['emp'].append(ch + [e.get('unidade_gestora'), e.get('numero'), (e.get('planointerno') or '')[:60], e.get('data_emissao')])
        for f in d['faturas'] if isinstance(d['faturas'], list) else []:
            L['fat'].append(ch + [f.get('numero'), f.get('emissao'), f.get('vencimento'), br(num(f.get('valor')) - num(f.get('glosa'))), f.get('situacao'), f.get('data_liquidacao'), f.get('sfadrao_id')])
        for h in sorted(d['historico'] if isinstance(d['historico'], list) else [], key=lambda h: h.get('data_assinatura') or ''):
            ql = ' · '.join(q.get('descricao', '') for q in (h.get('qualificacao_termo') or []) if isinstance(q, dict) and q.get('descricao') and q.get('descricao') != 'INFORMATIVO')
            L['his'].append(ch + [h.get('tipo'), h.get('numero'), h.get('data_assinatura'), h.get('vigencia_fim'), br(num(h.get('novo_valor_global') or h.get('valor_global'))), (h.get('observacao') or '')[:400],
                                  h.get('id'), ql, h.get('data_publicacao') or '', h.get('vigencia_inicio') or '', br(num(h.get('valor_global'))), h.get('num_parcelas') or '', br(num(h.get('valor_parcela'))),
                                  h.get('data_inicio_novo_valor') or '', h.get('retroativo') or '', br(num(h.get('retroativo_valor')))])
        for r in d['responsaveis'] if isinstance(d['responsaveis'], list) else []:
            L['res'].append(ch + [r.get('funcao_id'), re.sub(r'^[\d\*\.\-]+\s*-\s*', '', r.get('usuario') or ''), r.get('portaria') or '', r.get('situacao')])
        for a in d['arquivos'] if isinstance(d['arquivos'], list) else []:
            sei = a.get('link_sei') or ''
            L['arq'].append(ch + [a.get('tipo'), (a.get('descricao') or '')[:200], a.get('path_arquivo') or '', '' if sei in ('null', 'None') else sei, a.get('origem') or ''])
        for x in d['itens'] if isinstance(d['itens'], list) else []:
            L['itn'].append(ch + [(x.get('descricao_complementar') or x.get('catmatseritem_id') or '')[:200], x.get('tipo_id'), x.get('quantidade'), br(num(x.get('valorunitario'))), br(num(x.get('valortotal'))), x.get('numero_item_compra')])
            for hi in x.get('historico_item') or [] if isinstance(x.get('historico_item'), list) else []:
                L['ith'].append(ch + [x.get('id'), (x.get('descricao_complementar') or x.get('catmatseritem_id') or '')[:200], x.get('tipo_id'), hi.get('contrato_historico_id'), hi.get('tipo_historico'),
                                      hi.get('data_termo'), hi.get('quantidade'), hi.get('periodicidade'), br(num(hi.get('valor_unitario'))), br(num(hi.get('valor_total')))])
        pk = lambda x, *ks: next((str(x[k]) for k in ks if isinstance(x, dict) and x.get(k) not in (None, '')), '')
        for x in d.get('ocorrencias') if isinstance(d.get('ocorrencias'), list) else []:
            if not CHAVES['oco'] and isinstance(x, dict): CHAVES['oco'] = sorted(x)
            L['oco'].append(ch + [pk(x, 'numero', 'numeroocorrencia', 'numero_ocorrencia', 'id'), pk(x, 'data', 'data_ocorrencia', 'dataocorrencia', 'created_at'),
                                  pk(x, 'situacao', 'situacao_ocorrencia', 'situacaoocorrencia', 'status'), pk(x, 'ocorrencia', 'descricao', 'texto', 'observacao')[:400]])
        for x in d.get('garantias') if isinstance(d.get('garantias'), list) else []:
            if not CHAVES['gar'] and isinstance(x, dict): CHAVES['gar'] = sorted(x)
            L['gar'].append(ch + [pk(x, 'tipo', 'tipo_garantia', 'modalidade'), br(num(pk(x, 'valor', 'valor_garantia'))), pk(x, 'vencimento', 'data_vencimento', 'validade', 'vigencia_fim'), pk(x, 'situacao', 'status')])
        for x in d['cronograma'] if isinstance(d['cronograma'], list) else []:
            L['cro'].append(ch + [x.get('mesref'), x.get('anoref'), x.get('vencimento'), br(num(x.get('valor'))), x.get('tipo')])
        pg = d.get('pagina') or {}
        his_ = d['historico'] if isinstance(d['historico'], list) else []
        fimA, vgA = c.get('vigencia_fim') or '', br(num(c.get('valor_global')))
        if pg:
            L['pag'].append(ch + [pg.get('mo'), pg.get('postos'), pg.get('vagas'), pg.get('perc'), pg.get('ncontr'), pg.get('pncp'), '', '',
                                  HOJE, fimA, vgA, str(len(his_)), ''])
        elif str(ch[0]) in PAG_ANT:   # a página de transparência não abriu hoje: fica a leitura anterior (postos, link do PNCP e edital)
            r = list(PAG_ANT[str(ch[0])]); REUSO['pag'] += 1
            r[12] = r[12] or CTR_ANT.get(str(ch[0]), ['', ''])[0]
            r[13] = r[13] or CTR_ANT.get(str(ch[0]), ['', ''])[1]
            r[14] = r[14] or (str(HIS_ANT.get(str(ch[0]), '')) if str(ch[0]) in HIS_ANT else '')
            mud = []
            if r[12] and fimA and fimA != r[12]:
                mud.append(f'vigência {iso_br(r[12])} → {iso_br(fimA)}')
            if r[13] and vgA != r[13]:
                mud.append(f'valor global R$ {r[13]} → R$ {vgA}')
            lida = r[11]
            novos = [h for h in his_ if lida and dt_api(h.get('data_assinatura')) and dt_api(h.get('data_assinatura')) > dt_br(lida)]
            if r[14].isdigit() and len(his_) > int(r[14]) and not novos:
                novos = his_[int(r[14]):]
            for h in novos[:3]:
                mud.append(f"{h.get('tipo') or 'termo'} {h.get('numero') or ''} assinado em {iso_br(h.get('data_assinatura'))}".replace('  ', ' '))
            r[15] = '; '.join(mud)
            L['pag'].append(ch + r[3:])
    if REUSO['pag']:
        print(f"Contratos.gov.br: página de {REUSO['pag']} contrato(s) não abriu hoje · mantida a leitura anterior", flush=True)
    for k in ARQ:   # grava já: se o PNCP travar e o passo for interrompido, os contratos do dia ficam salvos
        gravar(k, L[k])
    ligar_editais(L['pag'])
    gravar('pag', L['pag'])
    print('Contratos.gov.br: ' + ' · '.join(f'{k} {len(v)}' for k, v in L.items()) + f' · {time.time()-t0:.0f}s', flush=True)
    print(f"Contratos.gov.br: campos das ocorrências {CHAVES['oco']} · das garantias {CHAVES['gar']}", flush=True)


if __name__ == '__main__':
    try:
        main()
    except Exception as e:
        import traceback
        print(f'Contratos.gov.br: falhou ({e}); mantendo os arquivos anteriores', flush=True)
        try:
            with open(os.path.join(OUT, 'pncp_diagnostico.txt'), 'w', encoding='utf-8') as fh:
                fh.write('FALHOU: ' + traceback.format_exc() + '\n' + '\n'.join(DIAG[:400]))
        except Exception:
            pass
        if ANT:
            for k in ARQ:
                q = os.path.join(ANT, f'contratos_api_{k}.csv')
                if os.path.exists(q):
                    shutil.copy(q, nome(k))
            try:   # mesmo sem o Contratos.gov.br, liga os editais do PNCP no arquivo anterior
                with open(nome('pag'), encoding='utf-8') as fh:
                    rows = list(csv.reader(fh))
                if rows and len(rows[0]) >= 11:
                    corpo = [r + [''] * (11 - len(r)) for r in rows[1:]]
                    ligar_editais(corpo)
                    with open(nome('pag'), 'w', encoding='utf-8', newline='') as fh:
                        w = csv.writer(fh); w.writerow(rows[0]); w.writerows(corpo)
            except Exception as e2:
                print(f'PNCP: falhou no arquivo anterior ({e2})', flush=True)
