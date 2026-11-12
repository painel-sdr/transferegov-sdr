"""Índice do histórico 2014–2025 por nota de empenho, para as fichas do painel (contrato e instrumento).
Lê as pastas por ano da branch "historico" (pag_ANO.csv e pag_ne_ANO.csv) e grava um arquivo por UG:
  indice/hist_UG.json.gz = {"gerado": "...", "anos": [2014, ...], "ne": {"2021NE000155": [[ano, pago_no_ano, pago_rap, [[data, documento, valor], ...]], ...]}}
Só o PAGO: o empenhado do Portal vem em notas separadas (reforço/anulação) que o Contratos.gov.br não liga ao contrato.
Uso: python scripts/historico_indice.py PASTA_HISTORICO PASTA_SAIDA
"""
import csv, collections, datetime, gzip, json, os, sys

csv.field_size_limit(10**9)
UGS = ['130010', '130141', '130255', '135098', '420013', '130005']


def n(x):
    try:
        return float(str(x).replace('.', '').replace(',', '.'))
    except ValueError:
        return 0.0


def ler(c):
    if not os.path.exists(c):
        return []
    return csv.DictReader(open(c, encoding='utf-8', newline=''))


def main(raiz, saida):
    os.makedirs(saida, exist_ok=True)
    # ne_por_ug[ug][ne][ano] = [pago, rap, {doc: valor}]
    idx = {u: collections.defaultdict(dict) for u in UGS}
    anos = []
    for a in sorted(int(d) for d in os.listdir(raiz) if d.isdigit()):
        pasta = os.path.join(raiz, str(a))
        datas = {r['Código Pagamento']: r.get('Data Emissão', '') for r in ler(os.path.join(pasta, f'pag_{a}.csv'))}
        vistos = set()
        tem = False
        for r in ler(os.path.join(pasta, f'pag_ne_{a}.csv')):
            ne_c = r.get('Código Empenho', '')
            ug, ne = ne_c[:6], ne_c[11:]
            if ug not in idx or 'NE' not in ne:
                continue
            ch = tuple(r.values())
            if ch in vistos:       # dia refeito duas vezes: não soma em dobro
                continue
            vistos.add(ch)
            pago, rap = n(r.get('Valor Pago (R$)')), n(r.get('Valor Restos a Pagar Pagos (R$)'))
            if abs(pago) < 0.005 and abs(rap) < 0.005:
                continue
            tem = True
            x = idx[ug][ne].setdefault(a, [0.0, 0.0, {}])
            x[0] += pago
            x[1] += rap
            doc = r.get('Código Pagamento', '')
            x[2][doc] = x[2].get(doc, 0.0) + pago + rap
            datas.setdefault(doc, '')
        if tem:
            anos.append(a)
        for u in idx:
            for ne, por in idx[u].items():
                if a in por:
                    por[a][2] = {d: [datas.get(d, ''), v] for d, v in por[a][2].items()}

    def dt(s):
        try:
            return datetime.datetime.strptime(s, '%d/%m/%Y')
        except ValueError:
            return datetime.datetime.min

    # notas de empenho por processo (campo "Processo" do empenho no Portal): acha as notas que o Contratos.gov.br não liga ao contrato
    proc = {u: collections.defaultdict(set) for u in UGS}
    for a in anos:
        for r in ler(os.path.join(raiz, str(a), f'emp_{a}.csv')):
            ug, ne = r.get('Código Unidade Gestora', ''), r.get('Código Empenho Resumido', '')
            dig = ''.join(ch for ch in r.get('Processo', '') if ch.isdigit())
            if ug in idx and ne in idx[ug] and len(dig) >= 10:
                proc[ug][dig].add(ne)

    gerado = (datetime.datetime.utcnow() - datetime.timedelta(hours=3)).strftime('%d/%m/%Y %H:%M')
    for u in UGS:
        out = {}
        for ne, por in idx[u].items():
            lst = []
            for a in sorted(por):
                pago, rap, docs = por[a]
                ds = sorted(([d[0], doc[11:] if len(doc) > 12 else doc, round(d[1], 2)] for doc, d in docs.items()), key=lambda z: dt(z[0]), reverse=True)
                lst.append([a, round(pago, 2), round(rap, 2), ds])
            out[ne] = lst
        c = os.path.join(saida, f'hist_{u}.json.gz')
        with gzip.open(c, 'wt', encoding='utf-8') as f:
            json.dump({'gerado': gerado, 'ug': u, 'anos': anos, 'ne': out, 'proc': {k: sorted(v) for k, v in proc[u].items()}}, f, ensure_ascii=False, separators=(',', ':'))
        print(u, len(out), 'notas ·', os.path.getsize(c) // 1024, 'KB')


if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2])
