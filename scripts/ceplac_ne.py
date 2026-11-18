"""
Robô CEPLAC · histórico das notas de empenho da UG 130010 no Tesouro Gerencial (2018 até hoje).

De onde lê: o link de CSV publicado em config/ceplac_ne.txt (aba "CEPLAC NE" da BASE TED, preenchida pelo
robô de e-mail com a assinatura "[PAINEL] CEPLAC_NE"). Também aceita um arquivo local (o CSV exportado do Tesouro).

O relatório (Invetario 2026 130010) tem uma linha por Ano Lançamento × NE × natureza × ação × PTRES e uma coluna por
Item Informação (Movim. Líquido): 29 empenhadas, 31 liquidadas, 34 pagas, 35/37/38 RAP processados inscritos/cancelados/pagos,
40/42/46 RAP não processados inscritos/cancelados/pagos.  Movimento líquido = valor do ano (pode somar os anos).

Grava PASTA/ceplac/ceplac_ne.json:
  {"gerado": "...", "pos": 2026, "ug": "130010",
   "nes": {"130010|2025NE000129": {"c": cnpj, "f": favorecido, "d": descrição, "p": processo, "n": natureza, "nn": nome natureza,
                                   "a": ação, "t": ptres, "e": "2025-05-06",
                                   "y": {"2026": [emp, liq, pago, rpp_insc, rpp_canc, rpp_pago, rpnp_insc, rpnp_canc, rpnp_pago]}}}}
Se a leitura falhar ou vier vazia, não grava nada (o passo do workflow mantém o arquivo da rodada anterior).

Uso:  python scripts/ceplac_ne.py PASTA_DE_SAIDA [arquivo.csv]
"""
import csv, io, json, os, re, sys, time, unicodedata, urllib.request
from datetime import datetime, timezone, timedelta

AQUI = os.path.dirname(os.path.abspath(__file__))
CONFIG = os.path.join(AQUI, '..', 'config', 'ceplac_ne.txt')

# código do Item Informação → posição no vetor do ano
ITENS = {'29': 0, '31': 1, '34': 2, '35': 3, '37': 4, '38': 5, '40': 6, '42': 7, '46': 8}
ITENS_NOME = [(0, r'DESPESAS EMPENHADAS'), (1, r'DESPESAS LIQUIDADAS'), (2, r'DESPESAS PAGAS'),
              (3, r'RESTOS A PAGAR PROCESSADOS INSCRITOS'), (4, r'RESTOS A PAGAR PROCESSADOS CANCELADOS'), (5, r'RESTOS A PAGAR PROCESSADOS PAGOS'),
              (6, r'RESTOS A PAGAR NAO PROCESSADOS INSCRITOS'), (7, r'RESTOS A PAGAR NAO PROCESSADOS CANCELADOS'), (8, r'RESTOS A PAGAR NAO PROCESSADOS PAGOS')]


def na(t):
    return re.sub(r'\s+', ' ', unicodedata.normalize('NFKD', str(t or '')).encode('ascii', 'ignore').decode().upper()).strip()


def num(v):
    t = str(v or '').strip().lstrip("'").replace('R$', '').replace('\xa0', '').replace(' ', '')
    if not t or t in ('-', '—'):
        return 0.0
    neg = (t.startswith('(') and t.endswith(')')) or t.endswith('-') or t.startswith('-')
    t = t.strip('()-')
    if not re.fullmatch(r'[\d.,]+', t):
        return 0.0
    if ',' in t:
        t = t.replace('.', '').replace(',', '.')
    elif t.count('.') > 1:
        t = t.replace('.', '')
    try:
        x = float(t)
    except ValueError:
        return 0.0
    return -x if neg else x


def limpa(v):
    t = str(v or '').strip().lstrip("'").strip()
    return '' if na(t) in ('-9', '-8', '-7', 'SEM INFORMACAO', 'NAO SE APLICA', 'CODIGO INVALIDO', 'NAO INFORMADO') else t


def texto_de(fonte):
    if re.match(r'https?://', fonte):
        for i in range(3):
            try:
                with urllib.request.urlopen(urllib.request.Request(fonte, headers={'User-Agent': 'painel-sdr'}), timeout=90) as r:
                    b = r.read()
                break
            except Exception as e:
                print('ceplac_ne: tentativa', i + 1, 'falhou:', e)
                time.sleep(5)
        else:
            return ''
    else:
        b = open(fonte, 'rb').read()
    for enc in ('utf-16',) if b[:2] in (b'\xff\xfe', b'\xfe\xff') else ('utf-8-sig', 'latin-1'):
        try:
            return b.decode(enc)
        except UnicodeDecodeError:
            continue
    return b.decode('latin-1', 'replace')


def linhas_de(txt):
    amostra = txt[:5000]
    sep = max([',', ';', '\t'], key=lambda s: amostra.count(s))
    return list(csv.reader(io.StringIO(txt), delimiter=sep))


def ler(txt):
    R = linhas_de(txt)
    ih = next((i for i, r in enumerate(R) if any(na(c) == 'NE CCOR' for c in r)), None)
    if ih is None:
        raise ValueError('não achei o cabeçalho (coluna "NE CCor")')
    H = [na(c) for c in R[ih]]
    # linha com os códigos (29, 31…) ou com os nomes dos itens: define a coluna de cada item
    col = {}
    i_ptres = None
    fim_cab = ih
    for j in range(ih, min(ih + 4, len(R))):
        r = [na(c) for c in R[j]]
        if 'PTRES' in r and i_ptres is None:
            i_ptres = r.index('PTRES')
        for k, c in enumerate(r):
            if c in ITENS and k not in col.values():
                col.setdefault(ITENS[c], k)
                fim_cab = max(fim_cab, j)
            for pos, rx in ITENS_NOME:
                if re.match(rx, c) and pos not in col:
                    col[pos] = k
                    fim_cab = max(fim_cab, j)
    if len(col) < 3:
        raise ValueError('não achei as colunas dos itens (29, 31, 34…)')

    def ix(nome, prox=0):
        n = na(nome)
        return H.index(n) + prox if n in H else None
    iug, iano, ine = ix('UG Executora'), ix('Ano Lançamento'), ix('NE CCor')
    iem, ifav, idesc, iproc = ix('NE CCor - Dia Emissão'), ix('NE CCor - Favorecido'), ix('NE CCor - Descrição'), ix('NE CCor - Núm. Processo')
    ind, iac = ix('Natureza Despesa Detalhada'), ix('Ação Governo')
    if i_ptres is None:
        i_ptres = ix('PTRES')
    nes, ant = {}, [''] * 40
    for r in R[fim_cab + 1:]:
        if not any(str(c).strip() for c in r):
            continue
        r = list(r) + [''] * 40
        # células mescladas (só na 1ª linha do grupo): repete o valor de cima nas colunas de atributo
        for k in range(0, min(col.values())):
            if str(r[k]).strip() == '':
                r[k] = ant[k]
        ant = r
        m = re.search(r'(\d{4}NE\d{6})', str(r[ine]))
        ug = re.sub(r'\D', '', str(r[iug]))[:6] if iug is not None else '130010'
        ano = re.sub(r'\D', '', str(r[iano]))[:4] if iano is not None else ''
        if not m or not ano or na(r[0]).startswith('TOTAL'):
            continue
        v = [0.0] * 9
        for pos, k in col.items():
            v[pos] = num(r[k])
        k = ug + '|' + m[1]
        o = nes.get(k)
        if not o:
            em = str(r[iem] or '') if iem is not None else ''
            mm = re.match(r'(\d{2})/(\d{2})/(\d{4})', em)
            o = nes[k] = {'c': re.sub(r'\D', '', limpa(r[ifav])) if ifav is not None else '', 'f': limpa(r[ifav + 1]) if ifav is not None else '',
                          'd': limpa(r[idesc])[:400] if idesc is not None else '', 'p': limpa(r[iproc]) if iproc is not None else '',
                          'n': limpa(r[ind]) if ind is not None else '', 'nn': limpa(r[ind + 1]) if ind is not None else '',
                          'a': limpa(r[iac]) if iac is not None else '', 't': limpa(r[i_ptres]) if i_ptres is not None else '',
                          'e': f'{mm[3]}-{mm[2]}-{mm[1]}' if mm else '', 'y': {}}
        y = o['y'].setdefault(ano, [0.0] * 9)
        for i in range(9):
            y[i] += v[i]
    for o in nes.values():
        for a in list(o['y']):
            o['y'][a] = [round(x, 2) for x in o['y'][a]]
            if not any(o['y'][a]):
                del o['y'][a]
    return nes


def main():
    saida = sys.argv[1] if len(sys.argv) > 1 else 'saida'
    fontes = sys.argv[2:]
    if not fontes and os.path.exists(CONFIG):
        fontes = [l.strip() for l in open(CONFIG, encoding='utf-8') if l.strip() and not l.strip().startswith('#')]
    if not fontes:
        print('ceplac_ne: nenhum link em config/ceplac_ne.txt (mantém o arquivo anterior)')
        return
    nes = {}
    for f in fontes:
        try:
            t = texto_de(f)
            n = ler(t) if t else {}
            print('ceplac_ne:', f[:80], '→', len(n), 'notas')
            nes.update(n)
        except Exception as e:
            print('ceplac_ne: erro em', f[:80], ':', e)
    if len(nes) < 50:
        print('ceplac_ne: leitura vazia ou incompleta (', len(nes), 'notas): mantém o arquivo anterior')
        return
    anos = sorted({a for o in nes.values() for a in o['y']})
    os.makedirs(os.path.join(saida, 'ceplac'), exist_ok=True)
    out = {'gerado': datetime.now(timezone(timedelta(hours=-3))).strftime('%d/%m/%Y %H:%M'), 'pos': int(anos[-1]), 'anos': anos, 'ug': '130010', 'nes': nes}
    with open(os.path.join(saida, 'ceplac', 'ceplac_ne.json'), 'w', encoding='utf-8') as fh:
        json.dump(out, fh, ensure_ascii=False, separators=(',', ':'))
    tot = [sum(o['y'].get(a, [0] * 9)[2] for o in nes.values()) for a in anos]
    print('ceplac_ne: gravado', len(nes), 'notas ·', ', '.join(f'{a}: pago {t / 1e6:.2f} Mi' for a, t in zip(anos, tot)))


if __name__ == '__main__':
    main()
