"""Viagens a serviço (SCDP) das UGs da SDR · Portal da Transparência.
O Portal publica um zip por ano com a data no nome (ex.: viagens/2026_20261110_Viagens.zip): o robô procura o mais recente.
Uma viagem é nossa quando as diárias foram pagas por uma das UGs abaixo (passagens e seguro são pagos de forma central pela 130005).
Uso: python scripts/viagens.py SAIDA [GASTOS_ANTERIOR.json]
  ->  SAIDA/viagens/viagens_ANO.json  (viagens, com as passagens por trecho)
  ->  SAIDA/viagens/gastos_ANO.json   (pagamentos de diárias com a nota de empenho: ordem bancária do SCDP "PCDP 000487/26 P/ PGTO. DE 2,5 DIARIAS")
      leitura incremental dos arquivos diários de Despesas do Portal: guarda até que dia já leu e só baixa os dias novos
"""
import csv, datetime, io, json, os, re, sys, zipfile
sys.path.insert(0, os.path.dirname(__file__))
from historico_portal import CDN, baixar, log, linhas, idx

UGS = {'130010', '130141', '130255', '135098', '420013'}
UF = {'Acre': 'AC', 'Alagoas': 'AL', 'Amapá': 'AP', 'Amazonas': 'AM', 'Bahia': 'BA', 'Ceará': 'CE', 'Distrito Federal': 'DF', 'Espírito Santo': 'ES',
      'Goiás': 'GO', 'Maranhão': 'MA', 'Mato Grosso': 'MT', 'Mato Grosso do Sul': 'MS', 'Minas Gerais': 'MG', 'Pará': 'PA', 'Paraíba': 'PB', 'Paraná': 'PR',
      'Pernambuco': 'PE', 'Piauí': 'PI', 'Rio de Janeiro': 'RJ', 'Rio Grande do Norte': 'RN', 'Rio Grande do Sul': 'RS', 'Rondônia': 'RO', 'Roraima': 'RR',
      'Santa Catarina': 'SC', 'São Paulo': 'SP', 'Sergipe': 'SE', 'Tocantins': 'TO'}
PEQ = {'De', 'Da', 'Do', 'Das', 'Dos', 'E'}


def num(x):
    try: return float(str(x or '0').replace('.', '').replace(',', '.') or 0)
    except ValueError: return 0.0


def titulo(s):
    s = (s or '').strip()
    return ' '.join(w if i == 0 or w not in PEQ else w.lower() for i, w in enumerate(s.title().split()))


def achar_zip(ano, hoje):
    """Tenta as datas de hoje para trás (o nome do arquivo traz a data da geração)."""
    for d in range(0, 40):
        dt = hoje - datetime.timedelta(days=d)
        url = f'{CDN}viagens/{ano}_{dt:%Y%m%d}_Viagens.zip'
        z = baixar(url, tentativas=2)
        if isinstance(z, bytes):
            log(f'  viagens {ano}: {url.rsplit("/", 1)[1]} ({len(z) / 1048576:.1f} MB)')
            return z, dt
    return None, None


def ler(z, nome):
    n = next((x for x in z.namelist() if x.endswith(nome)), None)
    if not n: return []
    txt = z.read(n).decode('latin1')
    r = csv.reader(io.StringIO(txt), delimiter=';')
    cab = [c.strip() for c in next(r)]
    return [dict(zip(cab, l)) for l in r]


def lugar(pais, uf, cid):
    if pais and pais != 'Brasil': return cid, '', True
    s = UF.get(uf, '')
    return (cid + '/' + s) if s else cid, s, False


def processar(zb, ano):
    z = zipfile.ZipFile(io.BytesIO(zb))
    pag = {}
    for r in ler(z, '_Pagamento.csv'):
        ug = r.get('Código da unidade gestora pagadora', '').strip()
        if ug in UGS and 'DI' in r.get('Tipo de pagamento', '').upper():
            pag.setdefault(r['Identificador do processo de viagem'], ug)
    log(f'  viagens {ano}: {len(pag)} com diárias pagas pelas UGs SDR')
    tre, pas = {}, {}
    for r in ler(z, '_Trecho.csv'):
        i = r.get('Identificador do processo de viagem', '').strip()
        if i in pag: tre.setdefault(i, []).append(r)
    for r in ler(z, '_Passagem.csv'):
        i = r['Identificador do processo de viagem']
        if i in pag: pas.setdefault(i, []).append(r)
    out = []
    for r in ler(z, '_Viagem.csv'):
        i = r['Identificador do processo de viagem']
        if i not in pag: continue
        tr = sorted(tre.get(i, []), key=lambda t: int(t.get('Sequência Trecho') or 0))
        orig = destC = destUF = ''; ext = False
        if tr:
            t0 = tr[0]
            tm = next((t for t in tr if t.get('Missao?', '').strip().lower().startswith('s')), t0)     # trecho da missão = destino principal
            orig = lugar(t0['Origem - País'], t0['Origem - UF'], t0['Origem - Cidade'])[0]
            destC, destUF, ext = lugar(tm['Destino - País'], tm['Destino - UF'], tm['Destino - Cidade'])
            ext = ext or any(t['Destino - País'] not in ('Brasil', '') for t in tr)
        ps = pas.get(i, [])
        psg = [[p['Data da emissão/compra'], (p['Cidade - Origem ida'] or '') + ' → ' + (p['Cidade - Destino ida'] or ''), round(num(p['Valor da passagem']) + num(p['Taxa de serviço']), 2), p.get('Meio de transporte', '')] for p in ps]
        out.append({'ug': pag[i], 'pcdp': r['Número da Proposta (PCDP)'], 'sit': r['Situação'], 'urg': r['Viagem Urgente'],
                    'just': r['Justificativa Urgência Viagem'].strip(), 'nome': titulo(r['Nome']), 'cargo': titulo(r['Cargo']) or 'Sem Cargo Informado',
                    'ini': r['Período - Data de início'], 'fim': r['Período - Data de fim'], 'dest': r['Destinos'], 'motivo': r['Motivo'][:200],
                    'diar': num(r['Valor diárias']), 'pass': num(r['Valor passagens']), 'dev': num(r['Valor devolução']), 'outros': num(r['Valor outros gastos']),
                    'orig': orig, 'ext': ext, 'destC': destC, 'destUF': destUF, 'emis': [p['Data da emissão/compra'] for p in ps],
                    'ndi': round(sum(num(t.get('Número Diárias')) for t in tr), 2), 'taxa': round(sum(num(p['Taxa de serviço']) for p in ps), 2), 'psg': psg})
    out.sort(key=lambda d: d['ini'][6:] + d['ini'][3:5] + d['ini'][:2])
    return out


# ---------- pagamentos de diárias (Despesas do Portal, arquivo diário) ----------
RX_PCDP = re.compile(r'PCDP\s*N?[º°.]*\s*(\d{6}/\d{2}(?:-\d[A-Z])?)', re.I)


def gastos(saida, ano, anterior):
    """Estado: {ano, ate (último dia lido, aaaammdd), ob: {cód. OB: [pcdp, data, ug, doc, favorecido]}, obne: [[cód. OB, cód. NE, valor]], ne: {cód. NE: [ne, ug, data, ação, PO, elemento, observação]}}"""
    E = {'ano': ano, 'ate': f'{ano - 1}1231', 'ob': {}, 'obne': [], 'ne': {}}
    try:
        a = json.load(open(anterior, encoding='utf-8'))
        if a.get('ano') == ano and a.get('ate'):
            E = a
    except Exception:
        pass
    d = datetime.datetime.strptime(E['ate'], '%Y%m%d').date() + datetime.timedelta(days=1)
    fim = min(datetime.date(ano, 12, 31), datetime.date.today() - datetime.timedelta(days=1))
    MAX = int(os.environ.get('VIAG_DIAS_MAX', '400'))
    lidos = 0
    vistos = {(x[0], x[1]) for x in E['obne']}
    while d <= fim and lidos < MAX:
        dia = d.strftime('%Y%m%d')
        z = baixar(f'{CDN}despesas/{dia}_Despesas.zip', tentativas=4)
        if z == 'falhou':
            log(f'  gastos {dia}: download falhou · para aqui e tenta de novo na próxima rodada')
            break
        if z is None and (fim - d).days < 6:
            break      # arquivo do dia ainda não publicado: tenta de novo na próxima rodada
        if isinstance(z, bytes):
            zz = zipfile.ZipFile(io.BytesIO(z)); nomes = zz.namelist()
            nE = next((n for n in nomes if n.endswith('_Despesas_Empenho.csv')), None)
            if nE:
                it = linhas(zz, nE); cab = next(it)
                iu, ic, ir, idt, ia, ipo, iel, iob = (idx(cab, 'Código Unidade Gestora'), idx(cab, 'Código Empenho'), idx(cab, 'Código Empenho Resumido'), idx(cab, 'Data Emissão'),
                                                      idx(cab, 'Código Ação'), idx(cab, 'Código Plano Orçamentário'), idx(cab, 'Código Elemento de Despesa'), idx(cab, 'Observação'))
                for r in it:
                    if len(r) > iu and r[iu].strip() in UGS:
                        E['ne'][r[ic]] = [r[ir], r[iu].strip(), r[idt], r[ia], r[ipo], r[iel], (r[iob] or '')[:160]]
            nP = next((n for n in nomes if n.endswith('_Despesas_Pagamento.csv')), None)
            novos = set()
            if nP:
                it = linhas(zz, nP); cab = next(it)
                iu, ic, ir, idt, ifv, iob = (idx(cab, 'Código Unidade Gestora'), idx(cab, 'Código Pagamento'), idx(cab, 'Código Pagamento Resumido'), idx(cab, 'Data Emissão'), idx(cab, 'Favorecido'), idx(cab, 'Observação'))
                for r in it:
                    if len(r) > iu and r[iu].strip() in UGS:
                        m = RX_PCDP.search(r[iob] or '')
                        if m:
                            E['ob'][r[ic]] = [m[1].upper(), r[idt], r[iu].strip(), r[ir], r[ifv]]
                            novos.add(r[ic])
            nI = next((n for n in nomes if n.endswith('_Despesas_Pagamento_EmpenhosImpactados.csv')), None)
            if nI and novos:
                it = linhas(zz, nI); cab = next(it)
                ic, ine, iv, irp = idx(cab, 'Código Pagamento'), idx(cab, 'Código Empenho'), idx(cab, 'Valor Pago (R$)'), idx(cab, 'Valor Restos a Pagar Pagos (R$)')
                for r in it:
                    if r and r[ic] in novos and (r[ic], r[ine]) not in vistos:
                        v = num(r[iv]) + (num(r[irp]) if irp is not None and irp < len(r) else 0)
                        if abs(v) > 0.004:
                            E['obne'].append([r[ic], r[ine], round(v, 2)]); vistos.add((r[ic], r[ine]))
        E['ate'] = dia
        lidos += 1
        if lidos % 30 == 0:
            log(f'  gastos: {lidos} dias lidos (até {dia}) · {len(E["ob"])} ordens bancárias do SCDP')
        d += datetime.timedelta(days=1)
    E['gerado_em'] = datetime.datetime.now().strftime('%d/%m/%Y %H:%M')
    json.dump(E, open(os.path.join(saida, 'viagens', f'gastos_{ano}.json'), 'w', encoding='utf-8'), ensure_ascii=False, separators=(',', ':'))
    log(f'  gastos {ano}: lido até {E["ate"]} ({lidos} dia(s) novos) · {len(E["ob"])} OB do SCDP · {len(E["obne"])} ligações OB × NE · {len(E["ne"])} notas de empenho')


# ---------- Tesouro Gerencial · relatório VIAGENS NE (empenhado, liquidado e pago de cada nota de viagem) ----------
CONFIG_TES = os.path.join(os.path.dirname(__file__), '..', 'config', 'viagens_tesouro_ne.txt')
ATRIB = [('acao', r'^ACAO GOVERNO'), ('po', r'^PLANO ORCAMENTARIO'), ('ug', r'^UG EXECUTORA'), ('ugr', r'^UG RESPONSAVEL'), ('ptres', r'^PTRES'), ('pi', r'^PI$'),
         ('nd', r'^NATUREZA DESPESA DETALHADA'), ('ne', r'^NE CCOR$'), ('data', r'^NE CCOR - DIA EMISSAO'), ('fav', r'^NE CCOR - FAVORECIDO'), ('desc', r'^NE CCOR - DESCRICAO'), ('proc', r'^NE CCOR - NUM. PROCESSO|^NE CCOR - PROCESSO')]
ITENS = [('emp', r'EMPENHAD'), ('rpp', r'RESTOS A PAGAR PROCESSADOS PAGOS'), ('rpnp', r'RESTOS A PAGAR NAO PROCESSADOS PAGOS'), ('liq', r'LIQUIDAD'), ('pago', r'^\d*:?\s*DESPESAS PAGAS')]
VIAG_ND = re.compile(r'^(339014|339033|33903602|33903603|33903969)')


def _na(t):
    import unicodedata
    return re.sub(r'\s+', ' ', unicodedata.normalize('NFD', str(t or '')).encode('ascii', 'ignore').decode().upper()).strip()


def _numT(v):
    from ted_tesouro import num as n_
    return n_(v)


def tesouro_ne(linhas):
    L = [[c.strip() for c in l] for l in linhas]
    ih = next((i for i, l in enumerate(L[:60]) if any(_na(c) == 'UG EXECUTORA' for c in l) and any(_na(c) == 'NE CCOR' for c in l)), None)
    if ih is None:
        raise ValueError('não achei as colunas "UG Executora" e "NE CCor"')
    # títulos podem estar em até 3 linhas (ex.: "NE CCor - Núm. Processo" fica na 3ª, embaixo de "Item Informação")
    HH = [[_na(c) for c in l] for l in L[ih:ih + 3]]
    def achar(rx):
        for H in HH:
            j = next((j for j, h in enumerate(H) if re.search(rx, h)), None)
            if j is not None:
                return j
        return None
    pos = sorted((i, k) for k, rx in ATRIB for i in [achar(rx)] if i is not None)
    itens = {}
    for l in L[max(0, ih - 4): ih + 4]:
        for i, c in enumerate(l):
            for k, rx in ITENS:
                if i not in itens and k not in itens.values() and re.search(rx, _na(c)):
                    itens[i] = k; break
    if not itens:
        raise ValueError('não achei as colunas de empenhado / liquidado / pago')
    fimAtr = min(itens) if itens else len(H)
    spans = [(k, i, (pos[n + 1][0] if n + 1 < len(pos) else fimAtr)) for n, (i, k) in enumerate(pos)]
    curto = lambda v: bool(v) and ' ' not in v and len(v) <= 12
    out = {}
    for l in L[ih + 1:]:
        vals = {}
        for k, a, b in spans:
            cel = [c for c in l[a:b] if c]
            if not cel:
                vals[k] = ('', ''); continue
            if k == 'po':      # 22101 · 20 · 122 · 0032 · 2000 · 000H · nome: o código do PO é o último código antes do nome
                cods = [c for c in cel if curto(c)]; nome = next((c for c in cel if not curto(c)), '')
                vals[k] = (cods[-1] if cods else '', nome)
            else:
                vals[k] = (cel[0], next((c for c in cel[1:] if not curto(c)), cel[1] if len(cel) > 1 else ''))
        ne = vals.get('ne', ('', ''))[0]
        if not re.search(r'\d{4}NE\d{6}$', ne):
            continue
        nd = vals.get('nd', ('', ''))[0]
        if not VIAG_ND.match(nd):
            continue
        k = (ne, nd, vals.get('ptres', ('', ''))[0], vals.get('pi', ('', ''))[0])
        o = out.get(k)
        if not o:
            o = out[k] = {'ne': ne[-12:], 'ug': vals.get('ug', ('', ''))[0], 'ug_nome': vals.get('ug', ('', ''))[1], 'ugr': vals.get('ugr', ('', ''))[0], 'acao': vals.get('acao', ('', ''))[0],
                          'po': vals.get('po', ('', ''))[0], 'ptres': k[2], 'pi': k[3], 'nd': nd, 'nd_nome': vals.get('nd', ('', ''))[1], 'data': vals.get('data', ('', ''))[0],
                          'fav': vals.get('fav', ('', ''))[0], 'fav_nome': vals.get('fav', ('', ''))[1], 'desc': re.sub(r'\s+', ' ', vals.get('desc', ('', ''))[0])[:300],
                          'proc': vals.get('proc', ('', ''))[0], 'emp': 0.0, 'liq': 0.0, 'pago': 0.0, 'rpp': 0.0, 'rpnp': 0.0}
        for i, kk in itens.items():
            v = (_numT(l[i]) or 0) if i < len(l) else 0
            if v:
                o[kk] = round(o[kk] + v, 2)
    return list(out.values())


def ler_tesouro(saida, ano):
    import urllib.request
    urls = [l.strip() for l in open(CONFIG_TES, encoding='utf-8') if l.strip() and not l.strip().startswith('#')] if os.path.exists(CONFIG_TES) else []
    todas, info = [], []
    for u in urls:
        try:
            with urllib.request.urlopen(urllib.request.Request(u, headers={'User-Agent': 'robo-sdr-mapa'}), timeout=120) as r:
                txt = r.read().decode('utf-8-sig', 'replace')
            if txt.lstrip().startswith('<'):
                raise ValueError('o link não devolveu CSV')
            L = tesouro_ne(list(csv.reader(io.StringIO(txt))))
            todas += L; info.append({'link': u, 'linhas': len(L), 'ok': True})
            log(f'  tesouro viagens: {len(L)} notas de viagem em {u[-50:]}')
        except Exception as e:
            info.append({'link': u, 'erro': str(e)[:200], 'ok': False})
            log(f'  tesouro viagens: erro em {u[-50:]}: {e}')
    if todas:
        json.dump({'gerado_em': datetime.datetime.now().strftime('%d/%m/%Y %H:%M'), 'fontes': info, 'nes': todas},
                  open(os.path.join(saida, 'viagens', f'tesouro_ne_{ano}.json'), 'w', encoding='utf-8'), ensure_ascii=False, separators=(',', ':'))


def main():
    saida = sys.argv[1] if len(sys.argv) > 1 else 'saida'
    pasta = os.path.join(saida, 'viagens'); os.makedirs(pasta, exist_ok=True)
    hoje = datetime.date.today()
    anos = [hoje.year] + ([hoje.year - 1] if hoje.month <= 2 else [])
    for ano in anos:
        zb, dt = achar_zip(ano, hoje)
        if not zb:
            log(f'  viagens {ano}: arquivo não encontrado no Portal'); continue
        lin = processar(zb, ano)
        json.dump({'ano': ano, 'posicao': f'{dt:%d/%m/%Y}', 'fonte': 'Portal da Transparência · Viagens a Serviço', 'ugs': sorted(UGS), 'viagens': lin},
                  open(os.path.join(pasta, f'viagens_{ano}.json'), 'w', encoding='utf-8'), ensure_ascii=False, separators=(',', ':'))
        log(f'  viagens {ano}: {len(lin)} viagens gravadas')
        try:
            ler_tesouro(saida, ano)
        except Exception as e:
            log(f'  tesouro viagens: erro {str(e)[:200]}')
        try:
            gastos(saida, ano, sys.argv[2] if len(sys.argv) > 2 else '')
        except Exception as e:
            log(f'  gastos {ano}: erro {str(e)[:200]}')


if __name__ == '__main__':
    main()
