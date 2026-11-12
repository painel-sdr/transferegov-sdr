"""
Robô TED · leitura do relatório do Tesouro Gerencial (SIAFI) colado na planilha BASE TED.

De onde lê: os links de CSV publicados que estiverem em config/ted_tesouro.txt (um por linha; linhas com # são ignoradas).
Cada link é uma aba publicada (Arquivo › Compartilhar › Publicar na Web › aba › CSV).

O relatório pode vir em dois formatos, o robô reconhece sozinho:
  • LARGO   : uma linha por TED e uma coluna por valor (ex.: "A comprovar", "Comprovado", "A repassar"...)
  • COMPRIDO: uma linha por TED × conta contábil, com uma coluna "Conta contábil" e uma coluna de saldo
As linhas de título e filtro que o Tesouro Gerencial põe no topo são puladas, as células mescladas
(TED só na primeira linha do grupo) são repetidas para baixo e as linhas de "Total" são ignoradas.

Uso:  python scripts/ted_tesouro.py PASTA_DE_SAIDA     (grava PASTA/ted/ted_tesouro.csv e ted_tesouro.json)
"""
import csv, glob, io, json, os, re, sys, time, unicodedata, urllib.request
from collections import OrderedDict

AQUI = os.path.dirname(os.path.abspath(__file__))
CONFIG = os.path.join(AQUI, '..', 'config', 'ted_tesouro.txt')


def na(t):
    return re.sub(r'\s+', ' ', unicodedata.normalize('NFKD', str(t or '')).encode('ascii', 'ignore').decode().upper()).strip()


def num(v):
    """'1.234,56' · 'R$ 1.234,56' · '(1.234,56)' · '1234.56' · '1.234,56-' → float; None se não for número"""
    t = str(v or '').strip().replace('R$', '').replace('\xa0', '').replace(' ', '')
    if not t or t in ('-', '—'):
        return None
    neg = t.startswith('(') and t.endswith(')') or t.endswith('-') or t.startswith('-')
    t = t.strip('()-')
    if not re.fullmatch(r'[\d.,]+', t):
        return None
    if ',' in t:
        t = t.replace('.', '').replace(',', '.')
    elif t.count('.') > 1:
        t = t.replace('.', '')
    try:
        x = float(t)
    except ValueError:
        return None
    return -x if neg else x


# textos que o Tesouro Gerencial usa no lugar de "vazio"
VAZIO_TG = re.compile(r'^(SEM INFORMACAO|CODIGO INVALIDO|NAO SE APLICA|NAO INFORMADO|-9|-8|-7|-|)$')


# devolução de crédito (NC) ou de financeiro (PF) da unidade para a SDR: pelo evento OU pela descrição
# (às vezes a unidade usa o evento errado, mas escreve "devolução" na observação)
EV_DEV = {'300301', '701202', '701459'}
def eh_devolucao(evento='', evento_nome='', obs=''):
    if str(evento or '').strip() in EV_DEV or re.search(r'\bDEV', na(evento_nome or '')):
        return True
    return bool(re.search(r'DEVOLU|RESTITU|ESTORNO DE (DESCENTRAL|REPASSE)|ANULACAO DE (DESCENTRAL|DESTAQUE)', na(obs or '')))


def chave_ted(v):
    """nº do TED como na API: '0984760' → '984760'; '7aaaqn' → '7AAAQN'; '984760 - IFMT…' → '984760'"""
    t = na(v)
    if not t or t in ('-', 'TOTAL', 'NAO SE APLICA', 'SEM INFORMACAO'):
        return ''
    t = re.split(r'\s+-\s+|\s+', t)[0]
    t = re.sub(r'[^0-9A-Z]', '', t)
    return t.lstrip('0') if t.isdigit() else t


# o que cada coluna (ou conta contábil) significa, pelas palavras do título
# o que cada coluna (ou conta contábil) significa, pelas palavras do título (contas de controle de TED do Tesouro Gerencial)
METRICAS = [(None, r'TRANSFERENCIAS FINANCEIRAS|ADIANTAMENTO|CONTROLE DE PROGRAMACAO|RP AUTORIZADO|RESTOS A PAGAR|RECEBIMENTO DE REPASSE|LIBERACAO DE REPASSE|REPASSE LIBERADO'),
            ('fir', r'FIRMAD|PACTUAD|VALOR (DO|TOTAL DO) TED|VALOR GLOBAL|CELEBRAD|TRANSFERENCIA - VALOR'),
            ('aComp', r'A COMPROVAR|PENDENTE DE COMPROVA'),
            ('aApr', r'A APROVAR'),
            ('comp', r'COMPROVAD'),
            ('apr', r'APROVAD|CONCLUID'),
            ('aRep', r'A REPASSAR|A LIBERAR|A TRANSFERIR|A DESCENTRALIZAR'),
            ('aRec', r'A RECEBER'),
            ('rep', r'REPASSAD[OA]S?$|VALOR REPASSADO|TRANSFERID'),
            ('dev', r'DEVOLV|DEVOLUC|NAO REPASSADO|ANULAD')]


def metrica(titulo):
    t = na(titulo)
    for k, rx in METRICAS:
        if re.search(rx, t):
            return k
    return ''


def baixar(url):
    for t in range(4):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers={'User-Agent': 'robo-sdr-mapa'}), timeout=120) as r:
                txt = r.read().decode('utf-8-sig', 'replace')
            if txt.lstrip().startswith('<'):
                raise ValueError('o link não devolveu CSV (a aba está publicada como CSV?)')
            return txt
        except Exception as e:
            err = e
            time.sleep(3 * (t + 1))
    raise err


def interpretar(linhas, origem=''):
    """devolve {ted: {...}} a partir das linhas de um CSV do Tesouro Gerencial"""
    linhas = [[c.strip() for c in l] for l in linhas]
    # 1. linha de títulos: a primeira (até a 40ª) que tem uma coluna de TED e é seguida de linhas com números
    rx_ted = r'\bTED\b|TRANSFERENCIA|TERMO DE EXECUCAO|INSTRUMENTO|N[OUº]?\s*DO?\s*TED'
    ih = None
    for i, l in enumerate(linhas[:40]):
        if sum(1 for c in l if c) >= 2 and any(re.search(rx_ted, na(c)) for c in l):
            ih = i
            break
    if ih is None:
        raise ValueError('não achei a coluna do nº do TED nos títulos')
    H = linhas[ih]
    # o Tesouro Gerencial às vezes põe o título da métrica numa linha e "Saldo - R$" na de baixo: junta as duas
    if ih + 1 < len(linhas) and any(re.search(r'SALDO|R\$|VALOR', na(c)) for c in linhas[ih + 1]) and not any(num(c) is not None for c in linhas[ih + 1]):
        H = [(a + ' ' + b).strip() for a, b in zip(H + [''] * len(linhas[ih + 1]), linhas[ih + 1] + [''] * len(H))]
        ih += 1
    Hn = [na(h) for h in H]
    corpo = [l + [''] * (len(H) - len(l)) for l in linhas[ih + 1:]]
    # 2. papéis das colunas
    cT = next(i for i, h in enumerate(Hn) if re.search(rx_ted, h))
    def acha(rx, evita=None):
        return next((i for i, h in enumerate(Hn) if re.search(rx, h) and i != cT and not (evita and re.search(evita, h))), None)
    # no Tesouro Gerencial a "UG Executora" é a UG da SDR que registra o TED (lado que descentraliza)
    cUe = acha(r'UG EXECUTORA COD|UG EXECUTORA$|UG.*(EMIT|RESP|CONCED|DESCENTRALIZADORA|ORIGEM)|EMITENTE|CONCEDENTE|DESCENTRALIZADORA')
    cUf = acha(r'UG.*(FAVOR|BENEF|RECEB|DESCENTRALIZADA|DESTINO)|FAVORECID|BENEFICIARI|DESCENTRALIZADA|CONVENENTE', r'UG EXECUTORA')
    cNomeF = acha(r'CONVENENTE NOM|FAVORECID.*NOM|BENEFICIARI.*NOM|DESCENTRALIZADA.*NOM')
    if cNomeF == cUf:
        cNomeF = None
    cSit = acha(r'SITUACAO')
    cIni = acha(r'INICIO VIG')
    cFim = acha(r'FINAL VIG|FIM VIG')
    cObj = acha(r'JUSTIFICATIVA|OBJETO')
    cAno = acha(r'^ANO|EXERCICIO|ANO ')
    cProc = acha(r'PROCESSO')
    # colunas de valor: as que têm número na maioria das linhas preenchidas
    def numerica(i):
        vs = [l[i] for l in corpo if l[i] and l[i].strip() not in ('-', '—') and not na(l[i]).startswith('TOTAL')]
        return len(vs) > 0 and sum(1 for v in vs if num(v) is not None) >= 0.8 * len(vs)
    # conta contábil (formato comprido): coluna de texto cujo título fala de conta
    cConta = next((i for i, h in enumerate(Hn) if re.search(r'CONTA', h) and i not in (cT, cUe, cUf, cAno, cProc) and not numerica(i)), None)
    papeis = {cT, cUe, cUf, cConta, cAno, cProc, cNomeF, cSit, cIni, cFim, cObj} - {None}
    cVal = [i for i in range(len(H)) if i not in papeis and numerica(i)]
    cTxt = [i for i in range(len(H)) if i not in papeis and i not in cVal]
    if not cVal:
        raise ValueError('não achei colunas de valor')
    comprido = cConta is not None
    # 3. linhas (repetindo para baixo as células mescladas das dimensões)
    out, ant = OrderedDict(), {}
    dims = [c for c in (cT, cUe, cUf, cConta, cAno, cProc, cNomeF, cSit, cIni, cFim, cObj) if c is not None] + cTxt
    for l in corpo:
        if not any(l):
            continue
        if any(na(c).startswith('TOTAL') for c in l[:max(dims) + 1]):
            continue
        for c in dims:
            if l[c]:
                ant[c] = l[c]
            else:
                l[c] = ant.get(c, '')
        k = chave_ted(l[cT])
        if not k:
            continue
        o = out.setdefault(k, {'ted': k, 'ted_txt': l[cT], 'ug_emit': '', 'ug_fav': '', 'ano': '', 'processo': '', 'nome_fav': '',
                               'fir': None, 'nc': None, 'rep': None, 'aRep': None, 'aComp': None, 'comp': None, 'dev': None, 'aApr': None, 'apr': None, 'aRec': None,
                               'situacao': '', 'ini': '', 'fim': '', 'objeto': '',
                               'contas': OrderedDict(), 'origem': origem})
        ug = lambda c: re.match(r'\s*(\d{6})', l[c]).group(1) if c is not None and re.match(r'\s*(\d{6})', l[c]) else ''
        o['ug_emit'] = o['ug_emit'] or ug(cUe)
        o['ug_fav'] = o['ug_fav'] or ug(cUf)
        if not o['nome_fav']:
            if cNomeF is not None and not VAZIO_TG.match(na(l[cNomeF])):
                o['nome_fav'] = l[cNomeF][:120]
            elif cUf is not None:
                o['nome_fav'] = re.sub(r'^\s*\d{6}\s*-?\s*', '', l[cUf])[:120]
        for campo, c in (('situacao', cSit), ('ini', cIni), ('fim', cFim), ('objeto', cObj)):
            if c is not None and not o.get(campo) and not VAZIO_TG.match(na(l[c])):
                o[campo] = l[c][:600]
        if cAno is not None and not o['ano']:
            m = re.search(r'20\d\d', l[cAno])
            if m:
                o['ano'] = m.group(0)
        if cProc is not None:
            o['processo'] = o['processo'] or l[cProc]
        if not o['ano']:
            m = re.match(r'(20\d\d)', o['ted'])
            if m:
                o['ano'] = m.group(1)
        rot_ = lambda h: re.sub(r'^\s*Conta Cont[aá]bil N[uú]mero\s*', '', h).strip()
        itens = [(l[cConta] + (' · ' + rot_(H[c]) if len(cVal) > 1 else ''), c) for c in cVal] if comprido else [(rot_(H[c]), c) for c in cVal]
        for rot, c in itens:
            v = num(l[c])
            if v is None:
                continue
            o['contas'][rot] = round(o['contas'].get(rot, 0) + v, 2)
            m = metrica(rot)
            if m == 'fir':      # "Valor da transferência" e "Valores firmados" são o mesmo número: fica o maior
                o['fir'] = max(o['fir'] or 0, v)
            elif m:
                o[m] = round((o.get(m) or 0) + v, 2)
    for o in out.values():
        # repassado: o Tesouro não tem uma conta só de "repassado". O que já saiu para a unidade é a comprovar + comprovado.
        # (firmado − a repassar só como último recurso: "a repassar" zerado não quer dizer que tudo foi repassado — ex.: TED 991352,
        #  firmado 10,2 Mi, a repassar 0, mas só 3 Mi repassados)
        if o.get('rep') is None:
            ks = ('aComp', 'comp', 'aApr', 'apr')   # a comprovar → comprovado → a aprovar → aprovado/concluído: tudo isso já saiu
            if any(o.get(k) is not None for k in ks):
                o['rep'] = round(sum(o.get(k) or 0 for k in ks), 2)
            elif o['fir'] is not None and o['aRep'] is not None:
                o['rep'] = round(o['fir'] - o['aRep'], 2)
    return out


def ler(pasta_saida):
    """lê os links de config/ted_tesouro.txt e grava ted/ted_tesouro.csv + ted_tesouro.json; devolve o dicionário"""
    if not os.path.exists(CONFIG):
        print('Tesouro TED: sem config/ted_tesouro.txt', flush=True)
        return {}
    urls = [l.strip() for l in open(CONFIG, encoding='utf-8') if l.strip() and not l.strip().startswith('#')]
    tudo, info = OrderedDict(), []
    for u in urls:
        try:
            linhas = list(csv.reader(io.StringIO(baixar(u))))
            d = interpretar(linhas, origem=u[-40:])
            for k, o in d.items():
                if k in tudo:   # o mesmo TED em duas abas: soma as contas
                    for rot, v in o['contas'].items():
                        tudo[k]['contas'][rot] = round(tudo[k]['contas'].get(rot, 0) + v, 2)
                    for m in ('nc', 'rep', 'aRep', 'aComp', 'aApr', 'comp', 'apr', 'aRec', 'dev'):
                        if o[m] is not None:
                            tudo[k][m] = round((tudo[k][m] or 0) + o[m], 2)
                else:
                    tudo[k] = o
            info.append({'link': u, 'teds': len(d), 'ok': True})
            print(f'Tesouro TED: {len(d)} TEDs em {u[-60:]}', flush=True)
        except Exception as e:
            info.append({'link': u, 'erro': str(e)[:200], 'ok': False})
            print(f'Tesouro TED: erro em {u[-60:]}: {e}', flush=True)
    os.makedirs(os.path.join(pasta_saida, 'ted'), exist_ok=True)
    contas = list(OrderedDict.fromkeys(r for o in tudo.values() for r in o['contas']))
    campos = ['ted', 'ted_txt', 'ug_emit', 'ug_fav', 'nome_fav', 'ano', 'processo', 'situacao', 'ini', 'fim', 'objeto',
              'fir', 'nc', 'rep', 'aRep', 'aComp', 'aApr', 'comp', 'apr', 'aRec', 'dev']
    with open(os.path.join(pasta_saida, 'ted', 'ted_tesouro.csv'), 'w', encoding='utf-8', newline='') as fh:
        w = csv.writer(fh)
        w.writerow(campos + contas)
        for o in tudo.values():
            w.writerow([o[c] if o[c] is not None else '' for c in campos] + [o['contas'].get(c, '') for c in contas])
    json.dump({'gerado_em': time.strftime('%d/%m/%Y %H:%M'), 'fontes': info, 'teds': len(tudo), 'contas': contas},
              open(os.path.join(pasta_saida, 'ted', 'ted_tesouro.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    return tudo



# ============== notas de crédito dos TEDs (relatório "Controle TED por NC e Numero Transferencia", aba TESOURO TED NC) ==============
CONFIG_NC = os.path.join(AQUI, '..', 'config', 'ted_tesouro_nc.txt')


def mapa_ptres(pasta):
    """PTRES → {acao, rp}: pelos eventos das NCs da API de TED (programa de trabalho tem a ação) e pelas notas de empenho dos instrumentos"""
    m = {}
    try:
        with open(os.path.join(pasta, 'ted', 'ted_eventos.csv'), encoding='utf-8') as fh:
            for e in csv.DictReader(fh):
                pt, pg = (e.get('cd_ptres_evento') or '').strip(), (e.get('ptres_programa_trabalho') or '').strip()
                uo = (e.get('ptres_unidade_orcamentaria') or '').strip()
                # a API às vezes liga o PTRES ao programa de trabalho de outro órgão (outro ano): só vale se a UO for do MAPA (22xxx)
                if pt and len(pg) >= 13 and uo.startswith('22') and re.fullmatch(r'\d[0-9A-Z]{3}', pg[9:13]):
                    m.setdefault(pt, {'acao': pg[9:13], 'rp': (e.get('ptres_resultado_primario') or '').strip()})
    except FileNotFoundError:
        pass
    try:
        acao = {}
        with open(os.path.join(pasta, 'instrumentos.csv'), encoding='utf-8') as fh:
            for r in csv.DictReader(fh):
                a = (r.get('acao_orcamentaria') or '').split('|')[0].strip()
                if a:
                    acao[r['nr_instrumento']] = a[-4:]
        with open(os.path.join(pasta, 'empenhos.csv'), encoding='utf-8') as fh:
            for e in csv.DictReader(fh):
                pt, a = (e.get('PTRES') or '').strip(), acao.get(e.get('NR_CONVENIO', ''))
                if pt and a and pt not in m:
                    rp = (e.get('RESULTADO_PRIMARIO') or '').strip()
                    m[pt] = {'acao': a, 'rp': ('RP ' + rp) if rp and not rp.startswith('RP') else rp}
    except FileNotFoundError:
        pass
    return m


def interpretar_nc(linhas, ptres):
    linhas = [[c.strip() for c in l] for l in linhas]
    ih = next((i for i, l in enumerate(linhas[:40]) if any(re.search(r'NC - TRANSFER', na(c)) for c in l)), None)
    if ih is None:
        raise ValueError('não achei a coluna "NC - Transferência"')
    H = [na(h) for h in linhas[ih]]
    def col(rx):
        return next((i for i, h in enumerate(H) if re.search(rx, h)), None)
    def nome(i):   # o Tesouro Gerencial põe o código numa coluna e o nome na seguinte (título vazio)
        return i + 1 if i is not None and i + 1 < len(H) and not H[i + 1] else None
    cT, cDt, cUe, cFav, cNC = col(r'NC - TRANSFER'), col(r'EMISSAO'), col(r'EMITENTE - UG'), col(r'FAVORECIDO'), col(r'^NC$')
    cND, cPI, cPT, cFt = col(r'NATUREZA'), col(r'PLANO INTERNO'), col(r'PTRES'), col(r'FONTE')
    cObs, cDesc, cVal = col(r'OBSERVACAO'), col(r'DESCRICAO'), col(r'VALOR LINHA')
    # formato novo da NC (2026 em diante): valores nas células ("NC Célula - Valor", "NC Célula - PTRES"...), uma linha por célula de DESTINO
    if cVal is None:
        cVal = col(r'CELULA - VALOR')
    cAc = col(r'ACAO GOVERNO')   # se o relatório trouxer a ação, ela vale mais que o mapa de PTRES
    cEv = col(r'EVENTO')         # relatórios de devolução (TED_NC_DEV…) trazem o evento: 300300 descentralização, 300301 devolução
    if cVal is None:   # o título do valor às vezes vem numa linha de baixo
        for l in linhas[ih + 1:ih + 4]:
            for i, c in enumerate(l):
                if re.search(r'VALOR LINHA', na(c)):
                    cVal = i
    g = lambda l, i: l[i].strip() if i is not None and i < len(l) else ''
    out, sem = [], 0
    for l in linhas[ih + 1:]:
        nc = g(l, cNC)
        if not nc or not re.search(r'NC\d', nc):
            continue
        ted = chave_ted(g(l, cT))
        if not ted or ted in ('8', '-8'):
            sem += 1
            ted = ''
        v = num(g(l, cVal))
        # o "Valor Linha" vem sempre positivo; a coluna de saldo ao lado traz o sinal: entre parênteses = estorno/anulação
        sald = next((c for c in reversed(l[(cVal or 0) + 1:]) if c.strip()), '') if cVal is not None else ''
        if v and (sald.startswith('(') or sald.startswith('-')):
            v = -abs(v)
        pt = g(l, cPT)
        info = ptres.get(pt, {})
        out.append({'ted': ted, 'data': g(l, cDt), 'nc': nc[-12:] if len(nc) > 12 else nc, 'nc_completa': nc, 'ug_emit': g(l, cUe), 'ug_fav': g(l, cFav),
                    'nome_fav': g(l, nome(cFav)), 'nd': g(l, cND), 'pi': g(l, cPI), 'pi_nome': g(l, nome(cPI)), 'ptres': pt, 'acao': (g(l, cAc) if cAc is not None and re.fullmatch(r'[0-9A-Z]{4}', g(l, cAc)) else '') or info.get('acao', ''),
                    'rp': info.get('rp', ''), 'fonte': g(l, cFt), 'obs': (g(l, cObs) or g(l, cDesc))[:400], 'valor': v if v is not None else '',
                    'evento': g(l, cEv), 'evento_nome': g(l, nome(cEv))})
    return out, sem


def ler_nc(pasta_saida):
    if not os.path.exists(CONFIG_NC):
        print('Tesouro TED NC: sem config/ted_tesouro_nc.txt', flush=True)
        return []
    urls = [l.strip() for l in open(CONFIG_NC, encoding='utf-8') if l.strip() and not l.strip().startswith('#')]
    ptres = mapa_ptres(pasta_saida)
    todas, info = [], []
    for u in urls:
        try:
            linhas = list(csv.reader(io.StringIO(baixar(u))))
            out, sem = interpretar_nc(linhas, ptres)
            todas += out
            info.append({'link': u, 'linhas': len(out), 'sem_ted': sem, 'ok': True})
            print(f'Tesouro TED NC: {len(out)} linhas de NC ({sem} sem nº de TED) em {u[-60:]}', flush=True)
        except Exception as e:
            info.append({'link': u, 'erro': str(e)[:200], 'ok': False})
            print(f'Tesouro TED NC: erro em {u[-60:]}: {e}', flush=True)
    os.makedirs(os.path.join(pasta_saida, 'ted'), exist_ok=True)
    campos = ['ted', 'data', 'nc', 'nc_completa', 'ug_emit', 'ug_fav', 'nome_fav', 'nd', 'pi', 'pi_nome', 'ptres', 'acao', 'rp', 'fonte', 'obs', 'valor', 'evento', 'evento_nome']
    with open(os.path.join(pasta_saida, 'ted', 'ted_tesouro_nc.csv'), 'w', encoding='utf-8', newline='') as fh:
        w = csv.DictWriter(fh, fieldnames=campos)
        w.writeheader()
        w.writerows(todas)
    json.dump({'gerado_em': time.strftime('%d/%m/%Y %H:%M'), 'fontes': info, 'linhas': len(todas), 'ptres_conhecidos': len(ptres)},
              open(os.path.join(pasta_saida, 'ted', 'ted_tesouro_nc.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    return todas



# ============== programações financeiras dos TEDs (relatório "TED SDR · PF", aba TESOURO TED PF) ==============
CONFIG_PF = os.path.join(AQUI, '..', 'config', 'ted_tesouro_pf.txt')


def interpretar_pf(linhas):
    linhas = [[c.strip() for c in l] for l in linhas]
    ih = next((i for i, l in enumerate(linhas[:40]) if any(na(c) == 'TRANSFERENCIA' for c in l) and any(na(c) == 'DOCUMENTO' for c in l)), None)
    if ih is None:
        raise ValueError('não achei as colunas "Transferência" e "Documento"')
    H = [na(h) for h in linhas[ih]]
    def col(rx):
        return next((i for i, h in enumerate(H) if re.search(rx, h)), None)
    def nome(i):
        return i + 1 if i is not None and i + 1 < len(H) and not H[i + 1] else None
    cT, cDoc, cDt, cFav, cObs = col(r'^TRANSFERENCIA$'), col(r'^DOCUMENTO$'), col(r'EMISSAO'), col(r'FAVORECIDO'), col(r'OBSERVACAO')
    cCat, cFt = col(r'CATEGORIA'), col(r'FONTE')
    cEv = col(r'EVENTO')
    cVal = col(r'MOVIM|SALDO|VALOR')
    g = lambda l, i: l[i].strip() if i is not None and i < len(l) else ''
    out = []
    for l in linhas[ih + 1:]:
        doc = g(l, cDoc)
        if not re.search(r'\d{4}PF\d{6}$', doc):   # só programação financeira (NS/NL de ajuste contábil, sem TED certo, ficam fora)
            continue
        ted = chave_ted(g(l, cT))
        if not ted or ted in ('8', '-8'):
            continue
        v = num(g(l, cVal))
        out.append({'ted': ted, 'data': g(l, cDt), 'doc': doc[-12:], 'tipo': doc[-8:-6], 'ug_emit': doc[:6] if len(doc) > 12 else '',
                    'ug_fav': g(l, cFav), 'nome_fav': g(l, nome(cFav)), 'categoria': g(l, cCat), 'fonte': g(l, cFt), 'obs': g(l, cObs)[:300],
                    'valor': v if v is not None else '', 'evento': g(l, cEv), 'evento_nome': g(l, nome(cEv))})
    return out


def ler_pf(pasta_saida):
    if not os.path.exists(CONFIG_PF):
        print('Tesouro TED PF: sem config/ted_tesouro_pf.txt', flush=True)
        return []
    urls = [l.strip() for l in open(CONFIG_PF, encoding='utf-8') if l.strip() and not l.strip().startswith('#')]
    todas, info = [], []
    for u in urls:
        try:
            out = interpretar_pf(list(csv.reader(io.StringIO(baixar(u)))))
            todas += out
            info.append({'link': u, 'linhas': len(out), 'ok': True})
            print(f'Tesouro TED PF: {len(out)} documentos em {u[-60:]}', flush=True)
        except Exception as e:
            info.append({'link': u, 'erro': str(e)[:200], 'ok': False})
            print(f'Tesouro TED PF: erro em {u[-60:]}: {e}', flush=True)
    os.makedirs(os.path.join(pasta_saida, 'ted'), exist_ok=True)
    campos = ['ted', 'data', 'doc', 'tipo', 'ug_emit', 'ug_fav', 'nome_fav', 'categoria', 'fonte', 'obs', 'valor', 'evento', 'evento_nome']
    with open(os.path.join(pasta_saida, 'ted', 'ted_tesouro_pf.csv'), 'w', encoding='utf-8', newline='') as fh:
        w = csv.DictWriter(fh, fieldnames=campos)
        w.writeheader()
        w.writerows(todas)
    json.dump({'gerado_em': time.strftime('%d/%m/%Y %H:%M'), 'fontes': info, 'linhas': len(todas)},
              open(os.path.join(pasta_saida, 'ted', 'ted_tesouro_pf.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    return todas

# ============== crédito recebido pela contabilidade (relatório "TED NC CONTA 2026", aba TED_NC_CONTA) ==============
# Em 2026 a NC de outro órgão não aparece nos relatórios de NC (formato novo); na contabilidade da UG da SDR ela entra como
# documento RO (ex.: 530023…2026RO001108 = 2026NC000690 do MIDR), conta 52222… (destaque recebido) ou 52221… (provisão recebida).
# O nº do TED vem na descrição ("TED Nº 995343/2026"), porque a transferência fica -9.
CONFIG_NCC = os.path.join(AQUI, '..', 'config', 'ted_tesouro_nc_conta.txt')
RX_TED_OBS = re.compile(r'TED\s*(?:N\W{0,2}|NO\.?|NUMERO)?\s*([69]\d{5}|[1-9]AA[A-Z0-9]{3})\b')


def interpretar_nc_conta(linhas):
    linhas = [[c.strip() for c in l] for l in linhas]
    ih = next((i for i, l in enumerate(linhas[:40]) if any(na(c) == 'DOCUMENTO' for c in l) and any(na(c) == 'UG EXECUTORA' for c in l)), None)
    if ih is None:
        raise ValueError('não achei as colunas "UG Executora" e "Documento"')
    H = [na(h) for h in linhas[ih]]
    col = lambda rx: next((i for i, h in enumerate(H) if re.search(rx, h)), None)
    cUG, cCt, cDt, cT, cDoc, cPt, cObs = col(r'^UG EXECUTORA$'), col(r'CONTA CONTABIL'), col(r'EMISSAO'), col(r'^TRANSFERENCIA$'), col(r'^DOCUMENTO$'), col(r'^PTRES$'), col(r'OBSERVACAO')
    cVal = col(r'MOVIM|SALDO|VALOR')
    g = lambda l, i: l[i].strip() if i is not None and i < len(l) else ''
    out = []
    for l in linhas[ih + 1:]:
        doc = g(l, cDoc)
        if not re.search(r'\d{4}[A-Z]{2}\d{6}$', doc):
            continue
        conta = next((c for c in l[(cCt or 0):(cCt or 0) + 3] if re.fullmatch(r'\d{9}', c.strip())), '')
        obs = g(l, cObs)
        ted = chave_ted(g(l, cT))
        if not ted or ted in ('8', '-8', '9', '-9'):
            m = RX_TED_OBS.search(na(obs))
            ted = m.group(1) if m else ''
        v = num(g(l, cVal))
        out.append({'ted': ted, 'data': g(l, cDt), 'doc': doc[-12:], 'doc_completo': doc, 'ug_emit': doc[:6], 'ug_fav': g(l, cUG), 'conta': conta,
                    'tipo': 'Destaque recebido' if conta.startswith('52222') else 'Provisão recebida' if conta.startswith('52221') else conta,
                    'ptres': g(l, cPt), 'obs': obs[:300], 'valor': v if v is not None else ''})
    return out


def ler_nc_conta(pasta_saida):
    if not os.path.exists(CONFIG_NCC):
        return []
    urls = [l.strip() for l in open(CONFIG_NCC, encoding='utf-8') if l.strip() and not l.strip().startswith('#')]
    todas, info = [], []
    for u in urls:
        try:
            out = interpretar_nc_conta(list(csv.reader(io.StringIO(baixar(u)))))
            todas += out
            info.append({'link': u, 'linhas': len(out), 'ok': True})
            print(f'Tesouro TED crédito recebido (conta): {len(out)} linhas em {u[-60:]}', flush=True)
        except Exception as e:
            info.append({'link': u, 'erro': str(e)[:200], 'ok': False})
            print(f'Tesouro TED crédito recebido (conta): erro em {u[-60:]}: {e}', flush=True)
    os.makedirs(os.path.join(pasta_saida, 'ted'), exist_ok=True)
    campos = ['ted', 'data', 'doc', 'doc_completo', 'ug_emit', 'ug_fav', 'conta', 'tipo', 'ptres', 'obs', 'valor']
    with open(os.path.join(pasta_saida, 'ted', 'ted_tesouro_nc_conta.csv'), 'w', encoding='utf-8', newline='') as fh:
        w = csv.DictWriter(fh, fieldnames=campos)
        w.writeheader()
        w.writerows(todas)
    json.dump({'gerado_em': time.strftime('%d/%m/%Y %H:%M'), 'fontes': info, 'linhas': len(todas)},
              open(os.path.join(pasta_saida, 'ted', 'ted_tesouro_nc_conta.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    return todas

# ---- empenhos feitos pelas unidades que receberam TED (relatório "EMPENHOS TED" · aba TESOURO TED NE)
CONFIG_NE = os.path.join(AQUI, '..', 'config', 'ted_tesouro_ne.txt')
ITENS_NE = [('emp', r'EMPENHAD'), ('rpp', r'RESTOS A PAGAR PROCESSADOS PAGOS'), ('rpnp', r'RESTOS A PAGAR NAO PROCESSADOS PAGOS'), ('liq', r'LIQUIDAD'), ('pago', r'^DESPESAS PAGAS')]


def interpretar_ne(linhas):
    linhas = [[c.strip() for c in l] for l in linhas]
    ih = next((i for i, l in enumerate(linhas[:40]) if any(na(c) == 'UG EXECUTORA' for c in l) and any(na(c) == 'NE CCOR' for c in l)), None)
    if ih is None:
        raise ValueError('não achei as colunas "UG Executora" e "NE CCor"')
    # títulos espalhados em até 3 linhas (o Tesouro põe "Natureza Despesa" na 3ª): usa o 1º não vazio de cada coluna
    nC = max(len(l) for l in linhas[ih:ih + 3])
    H = [next((na(l[i]) for l in linhas[ih:ih + 3] if i < len(l) and l[i].strip() and not re.fullmatch(r'\d+', l[i].strip())), '') for i in range(nC)]
    H = [h if not re.search(r'SALDO|DESPESAS|RESTOS A PAGAR', h) else '' for h in H]
    TT = [(i, na(c)) for l in linhas[ih:ih + 3] for i, c in enumerate(l) if c.strip()]
    col = lambda rx: next((i for i, h in TT if re.search(rx, h)), None)
    nome = lambda i: i + 1 if i is not None and i + 1 < len(H) and not H[i + 1] else None
    cUG, cAc, cDt, cNE, cFav, cDesc, cProc, cPT, cPI, cND = (col(r'^UG EXECUTORA'), col(r'^ACAO GOVERNO'), col(r'DIA EMISSAO'), col(r'^NE CCOR$'),
                                                          col(r'^NE CCOR - FAVORECIDO'), col(r'^NE CCOR - DESCRICAO'), col(r'PROCESSO'), col(r'^PTRES'), col(r'^PI$'), col(r'^NATUREZA DESPESA'))
    # itens de informação: o nome vem numa das linhas logo abaixo do título (código numa linha, nome na outra)
    itens = {}
    for l in linhas[ih:ih + 3]:
        for i, c in enumerate(l):
            for k, rx in ITENS_NE:
                if i not in itens and k not in itens.values() and re.search(rx, na(c)):
                    itens[i] = k
                    break
    if not itens:
        raise ValueError('não achei as colunas de empenhado / liquidado / pago')
    g = lambda l, i: l[i].strip() if i is not None and i < len(l) else ''
    out = {}
    for l in linhas[ih + 1:]:
        ne = g(l, cNE)
        if not re.search(r'\d{4}NE\d{6}$', ne):
            continue
        ug = g(l, cUG)
        k = (ne, g(l, cPT), g(l, cPI), g(l, cND))
        o = out.get(k)
        if not o:
            o = out[k] = {'ne': ne[-12:], 'ug': ug, 'ug_nome': g(l, nome(cUG)), 'acao': g(l, cAc), 'data': g(l, cDt), 'fav': g(l, cFav), 'fav_nome': g(l, nome(cFav)),
                          'desc': re.sub(r'\s+', ' ', g(l, cDesc))[:400], 'processo': g(l, cProc), 'ptres': g(l, cPT), 'pi': g(l, cPI), 'nd': g(l, cND),
                          'emp': 0.0, 'liq': 0.0, 'pago': 0.0, 'rpp': 0.0, 'rpnp': 0.0}
        for i, kk in itens.items():
            v = num(g(l, i))
            if v:
                o[kk] = round(o[kk] + v, 2)
    return list(out.values())


def ler_ne(pasta_saida):
    urls = [l.strip() for l in open(CONFIG_NE, encoding='utf-8') if l.strip() and not l.strip().startswith('#')] if os.path.exists(CONFIG_NE) else []
    todas, info = [], []
    for u in urls:
        try:
            out = interpretar_ne(list(csv.reader(io.StringIO(baixar(u)))))
            todas += out
            info.append({'link': u, 'linhas': len(out), 'ok': True})
            print(f'Tesouro TED NE: {len(out)} empenhos em {u[-60:]}', flush=True)
        except Exception as e:
            info.append({'link': u, 'erro': str(e)[:200], 'ok': False})
            print(f'Tesouro TED NE: erro em {u[-60:]}: {e}', flush=True)
    os.makedirs(os.path.join(pasta_saida, 'ted'), exist_ok=True)
    campos = ['ne', 'ug', 'ug_nome', 'acao', 'data', 'fav', 'fav_nome', 'desc', 'processo', 'ptres', 'pi', 'nd', 'emp', 'liq', 'pago', 'rpp', 'rpnp']
    with open(os.path.join(pasta_saida, 'ted', 'ted_tesouro_ne.csv'), 'w', encoding='utf-8', newline='') as fh:
        w = csv.DictWriter(fh, fieldnames=campos)
        w.writeheader()
        w.writerows(todas)
    json.dump({'gerado_em': time.strftime('%d/%m/%Y %H:%M'), 'fontes': info, 'linhas': len(todas)},
              open(os.path.join(pasta_saida, 'ted', 'ted_tesouro_ne.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    return todas


# ---- pagamentos dos empenhos das unidades que receberam TED (relatório "TED OB 2026" · aba TED OB) · 03/11/2026
CONFIG_OB = os.path.join(AQUI, '..', 'config', 'ted_tesouro_ob.txt')
ITENS_OB = [('rpp', r'RESTOS A PAGAR PROCESSADOS PAGOS'), ('rpnp', r'RESTOS A PAGAR NAO PROCESSADOS PAGOS'), ('pago', r'^DESPESAS PAGAS')]


def interpretar_ob(linhas):
    linhas = [[c.strip() for c in l] for l in linhas]
    ih = next((i for i, l in enumerate(linhas[:40]) if any(na(c) == 'NE CCOR' for c in l) and any(na(c) in ('OB', 'DOC - TIPO') for c in l)), None)
    if ih is None:
        raise ValueError('não achei as colunas "NE CCor" e "OB"')
    nC = max(len(l) for l in linhas[ih:ih + 3])
    H = [next((na(l[i]) for l in linhas[ih:ih + 3] if i < len(l) and l[i].strip() and not re.fullmatch(r'\d+', l[i].strip())), '') for i in range(nC)]
    H = [h if not re.search(r'SALDO|DESPESAS|RESTOS A PAGAR', h) else '' for h in H]
    TT = [(i, na(c)) for l in linhas[ih:ih + 3] for i, c in enumerate(l) if c.strip()]
    col = lambda rx: next((i for i, h in TT if re.search(rx, h)), None)
    nome = lambda i: i + 1 if i is not None and i + 1 < len(H) and not H[i + 1] else None
    cDt, cUG, cNE, cNEdt, cNEfav, cFav, cProc, cTipo, cPT, cPI, cOB, cAc = (col(r'^EMISSAO - DIA'), col(r'^UG EXECUTORA'), col(r'^NE CCOR$'), col(r'^NE CCOR - DIA EMISSAO'),
        col(r'^NE CCOR - FAVORECIDO'), col(r'^FAVORECIDO DOC'), col(r'PROCESSO'), col(r'^DOC - TIPO'), col(r'^PTRES'), col(r'^PI$'), col(r'^OB$'), col(r'^ACAO GOVERNO'))
    itens = {}
    for l in linhas[ih:ih + 3]:
        for i, c in enumerate(l):
            for k, rx in ITENS_OB:
                if i not in itens and k not in itens.values() and re.search(rx, na(c)):
                    itens[i] = k
                    break
    if not itens:
        raise ValueError('não achei as colunas de despesas pagas / restos a pagar pagos')
    g = lambda l, i: l[i].strip() if i is not None and i < len(l) else ''
    out = {}
    for l in linhas[ih + 1:]:
        ne = g(l, cNE)
        if not re.search(r'\d{4}NE\d{6}$', ne):
            continue
        doc = g(l, cOB)
        doc = doc[-12:] if re.search(r'\d{4}OB\d{6}$', doc) else ''
        k = (ne, doc, g(l, cDt), g(l, cTipo), g(l, cPT), g(l, cPI))
        o = out.get(k)
        if not o:
            o = out[k] = {'ob': doc, 'tipo': g(l, cTipo), 'data': g(l, cDt), 'ug': g(l, cUG), 'ug_nome': g(l, nome(cUG)), 'acao': g(l, cAc), 'ne': ne[-12:], 'ne_data': g(l, cNEdt),
                          'ne_fav': g(l, cNEfav), 'ne_fav_nome': g(l, nome(cNEfav)), 'fav': g(l, cFav), 'fav_nome': g(l, nome(cFav)), 'processo': g(l, cProc),
                          'ptres': g(l, cPT), 'pi': g(l, cPI), 'pago': 0.0, 'rpp': 0.0, 'rpnp': 0.0}
        for i, kk in itens.items():
            v = num(g(l, i))
            if v:
                o[kk] = round(o[kk] + v, 2)
    return [dict(o, valor=round(o['pago'] + o['rpp'] + o['rpnp'], 2)) for o in out.values()]


def ler_ob(pasta_saida):
    urls = [l.strip() for l in open(CONFIG_OB, encoding='utf-8') if l.strip() and not l.strip().startswith('#')] if os.path.exists(CONFIG_OB) else []
    todas, info = [], []
    for u in urls:
        try:
            out = interpretar_ob(list(csv.reader(io.StringIO(baixar(u)))))
            todas += out
            info.append({'link': u, 'linhas': len(out), 'ok': True})
            print(f'Tesouro TED OB: {len(out)} pagamentos em {u[-60:]}', flush=True)
        except Exception as e:
            info.append({'link': u, 'erro': str(e)[:200], 'ok': False})
            print(f'Tesouro TED OB: erro em {u[-60:]}: {e}', flush=True)
    os.makedirs(os.path.join(pasta_saida, 'ted'), exist_ok=True)
    campos = ['ob', 'tipo', 'data', 'ug', 'ug_nome', 'acao', 'ne', 'ne_data', 'ne_fav', 'ne_fav_nome', 'fav', 'fav_nome', 'processo', 'ptres', 'pi', 'pago', 'rpp', 'rpnp', 'valor']
    with open(os.path.join(pasta_saida, 'ted', 'ted_tesouro_ob.csv'), 'w', encoding='utf-8', newline='') as fh:
        w = csv.DictWriter(fh, fieldnames=campos)
        w.writeheader()
        w.writerows(todas)
    json.dump({'gerado_em': time.strftime('%d/%m/%Y %H:%M'), 'fontes': info, 'linhas': len(todas)},
              open(os.path.join(pasta_saida, 'ted', 'ted_tesouro_ob.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    return todas


# ---- ajustes da equipe (aba TED ATUALIZADA da BASE TED): fim da vigência prorrogado, fase e observação corrigidos à mão
CONFIG_AJ = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'config', 'ted_ajustes.txt')


def _data_aj(v):
    v = (v or '').strip()
    m = re.match(r'(\d{1,2})/(\d{1,2})/(\d{4})', v)
    if m:
        return f'{int(m.group(1)):02d}/{int(m.group(2)):02d}/{m.group(3)}'
    m = re.match(r'(\d{4})-(\d{2})-(\d{2})', v)
    return f'{m.group(3)}/{m.group(2)}/{m.group(1)}' if m else ''


def interpretar_aj(linhas):
    """devolve (ajustes, equipe): ajustes = fim/fase/obs da equipe; equipe = colunas "EQUIPE ·" (controle interno) + linhas só do controle"""
    ih = next((i for i, l in enumerate(linhas[:10]) if any(re.fullmatch(r'N.? TED', na(c)) for c in l)), None)
    if ih is None:
        raise ValueError('não achei o título "Nº TED" na aba TED ATUALIZADA')
    H0 = [c.strip() for c in linhas[ih]]
    H = [na(c) for c in H0]
    col = lambda rx: next((i for i, h in enumerate(H) if re.search(rx, h)), None)
    cN, cF, cS, cO = col(r'^N.? TED$'), col(r'^AJUSTE.*FIM'), col(r'^AJUSTE.*FASE'), col(r'^AJUSTE.*OBS')
    cOr = col(r'^ORIGEM DO DADO')
    cEq = [(i, re.sub(r'^EQUIPE\s*.\s*', '', H0[i])) for i, h in enumerate(H) if h.startswith('EQUIPE')]
    g = lambda l, i: (l[i] or '').strip() if i is not None and i < len(l) else ''
    aj, eq = [], []
    for l in linhas[ih + 1:]:
        ted, fim, fase, obs = g(l, cN).upper(), _data_aj(g(l, cF)), g(l, cS), g(l, cO)
        if not ted:
            continue
        if fim or fase or obs:
            aj.append({'ted': ted, 'fim': fim, 'fase': fase, 'obs': obs[:400]})
        d = {nome: g(l, i) for i, nome in cEq}
        if any(d.values()):
            eq.append({'ted': ted, 'origem': g(l, cOr), **d})
    return aj, eq


def ler_aj(pasta_saida):
    todas, info, equipe = [], [], []
    urls = [l.strip() for l in open(CONFIG_AJ, encoding='utf-8') if l.strip() and not l.strip().startswith('#')] if os.path.exists(CONFIG_AJ) else []
    for u in urls:
        try:
            a_, e_ = interpretar_aj(list(csv.reader(io.StringIO(baixar(u)))))
            todas += a_
            equipe += e_
            info.append({'link': u, 'linhas': len(todas), 'equipe': len(e_), 'ok': True})
            print(f'Ajustes TED: {len(todas)} ajustes em {u[-60:]}', flush=True)
        except Exception as e:
            info.append({'link': u, 'erro': str(e)[:200], 'ok': False})
            print(f'Ajustes TED: erro em {u[-60:]}: {e}', flush=True)
    # ajustes de vigência vindos de planilhas de outras equipes (ex.: acompanhamento da CGPI), guardados no repositório:
    # valem só para o TED que não tem ajuste na aba TED ATUALIZADA (a aba da equipe vale primeiro)
    ja = {a['ted'].upper() for a in todas}
    for extra in sorted(glob.glob(os.path.join(os.path.dirname(CONFIG_AJ), 'ted_ajustes_*.csv'))):
        try:
            for r in csv.DictReader(open(extra, encoding='utf-8')):
                t = (r.get('ted') or '').strip().upper()
                if t and t not in ja and (r.get('fim') or r.get('fase')):
                    todas.append({'ted': t, 'fim': _data_aj(r.get('fim')), 'fase': (r.get('fase') or '').strip(), 'obs': (r.get('obs') or '').strip()[:400]}); ja.add(t)
            print(f'Ajustes TED: {os.path.basename(extra)} lido', flush=True)
        except Exception as e:
            print(f'Ajustes TED: erro em {extra}: {e}', flush=True)
    os.makedirs(os.path.join(pasta_saida, 'ted'), exist_ok=True)
    with open(os.path.join(pasta_saida, 'ted', 'ted_ajustes.csv'), 'w', encoding='utf-8', newline='') as fh:
        w = csv.DictWriter(fh, fieldnames=['ted', 'fim', 'fase', 'obs'], extrasaction='ignore')
        w.writeheader()
        w.writerows(todas)
    campos = ['ted', 'origem'] + [k for k in (equipe[0].keys() if equipe else []) if k not in ('ted', 'origem')]
    with open(os.path.join(pasta_saida, 'ted', 'ted_equipe.csv'), 'w', encoding='utf-8', newline='') as fh:
        w = csv.DictWriter(fh, fieldnames=campos, extrasaction='ignore')
        w.writeheader()
        w.writerows(equipe)
    print(f'Controle interno (colunas EQUIPE): {len(equipe)} linhas', flush=True)
    return todas



# ---- controle interno direto (abas da equipe): fim da vigência como a equipe digitou
CONFIG_CTL = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'config', 'ted_controle.txt')


def data_ctl(v):
    """31/12/2026, 28/9/2026, 08/2028 (último dia do mês) ou número de série do Sheets (46387) -> dd/mm/aaaa"""
    v = (v or '').strip()
    m = re.match(r'(\d{1,2})/(\d{1,2})/(\d{4})', v)
    if m:
        return f'{int(m.group(1)):02d}/{int(m.group(2)):02d}/{m.group(3)}'
    m = re.fullmatch(r'(\d{1,2})/(\d{4})', v)
    if m and 1 <= int(m.group(1)) <= 12:
        import calendar
        a, mes = int(m.group(2)), int(m.group(1))
        return f'{calendar.monthrange(a, mes)[1]:02d}/{mes:02d}/{a}'
    m = re.fullmatch(r'(\d{5})(\.0+)?', v)
    if m and 30000 < int(m.group(1)) < 80000:
        import datetime as _dt
        d = _dt.date(1899, 12, 30) + _dt.timedelta(days=int(m.group(1)))
        return d.strftime('%d/%m/%Y')
    return ''


def ler_controle(pasta_saida):
    linhas = [l.strip() for l in open(CONFIG_CTL, encoding='utf-8') if l.strip() and not l.strip().startswith('#')] if os.path.exists(CONFIG_CTL) else []
    out = []
    for l in linhas:
        nome, url = l.split('|', 1)
        try:
            L = list(csv.reader(io.StringIO(baixar(url))))
        except Exception as e:
            print(f'Controle TED ({nome}): erro {e}', flush=True)
            continue
        ih = next((i for i, r in enumerate(L[:10]) if any(na(c) in ('PROCESSO',) for c in r)), None)
        if ih is None:
            continue
        H = [re.sub(r'[^A-Z0-9 ]+', '', na(c)).strip() for c in L[ih]]
        col = lambda *nomes: next((i for n_ in nomes for i, h in enumerate(H) if h == n_), None)
        cN, cP, cF = col('NRO', 'NR', 'NRº', 'SIAFI', 'N TED'), col('PROCESSO'), col('FIM', 'FIM VIG', 'FIM VIGENCIA')
        if cN is None:
            cN = next((i for i, h in enumerate(H) if h.startswith('NR')), None)
        for r in L[ih + 1:]:
            g = lambda i: (r[i] if i is not None and i < len(r) else '').strip()
            n, proc, fim_txt = re.split(r'[\s/]+', g(cN))[0].upper() if g(cN) else '', g(cP), g(cF)
            if not (n or proc):
                continue
            out.append({'aba': nome, 'ted': n.replace('.0', '') if re.fullmatch(r'\d+\.0', n) else n, 'processo': proc, 'fim_txt': fim_txt, 'fim': data_ctl(fim_txt)})
        print(f'Controle TED ({nome}): {len(L) - ih - 1} linhas', flush=True)
    os.makedirs(os.path.join(pasta_saida, 'ted'), exist_ok=True)
    with open(os.path.join(pasta_saida, 'ted', 'ted_controle.csv'), 'w', encoding='utf-8', newline='') as fh:
        w = csv.DictWriter(fh, fieldnames=['aba', 'ted', 'processo', 'fim_txt', 'fim'])
        w.writeheader()
        w.writerows(out)
    return out


if __name__ == '__main__':
    ler(sys.argv[1] if len(sys.argv) > 1 else 'saida')
    ler_nc(sys.argv[1] if len(sys.argv) > 1 else 'saida')
    ler_pf(sys.argv[1] if len(sys.argv) > 1 else 'saida')
    ler_nc_conta(sys.argv[1] if len(sys.argv) > 1 else 'saida')
    ler_aj(sys.argv[1] if len(sys.argv) > 1 else 'saida')
    ler_ne(sys.argv[1] if len(sys.argv) > 1 else 'saida')
    ler_ob(sys.argv[1] if len(sys.argv) > 1 else 'saida')
    try:
        ler_controle(sys.argv[1] if len(sys.argv) > 1 else 'saida')
    except Exception as e:
        print(f'Controle TED: falhou ({e})', flush=True)
