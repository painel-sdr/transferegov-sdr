"""LGPD (Lei 13.709/2018): mascara o CPF de pessoas físicas em todos os arquivos publicados pelo robô.

Padrão do Portal da Transparência: ***.452.881-** (só os 6 dígitos do meio ficam visíveis).
CNPJ (14 dígitos), números de processo, NE/NC e valores não são alterados.
Uso: python scripts/lgpd.py saida
"""
import csv, gzip, io, json, os, re, sys

CPF = re.compile(r'(?<![\d./-])(\d{3})\.?(\d{3})\.?(\d{3})-?(\d{2})(?!\d|[.,]\d)')


def cpf_valido(d):
    """Só é CPF se os 2 dígitos verificadores batem (evita mascarar PI, códigos e números de 11 dígitos que não são CPF)."""
    if len(d) != 11 or d == d[0] * 11:
        return False
    for n in (9, 10):
        s = sum(int(d[i]) * (n + 1 - i) for i in range(n))
        if (s * 10 % 11) % 10 != int(d[n]):
            return False
    return True


def _troca(m):
    d = ''.join(m.groups())
    return f'***.{m.group(2)}.{m.group(3)}-**' if cpf_valido(d) else m.group(0)


mascara = lambda s: CPF.sub(_troca, s) if isinstance(s, str) and len(s) >= 11 else s
# colunas / chaves que são códigos orçamentários (PI, PTRES, natureza, fonte…): nunca mascarar
CODIGO = re.compile(r'^(pi|pi_nome|plano.?interno|ptres|nd|natureza|fonte|ne|nc|pf|ob|ted|ug|ug_.*|evento)$', re.I)


def anda(o):
    if isinstance(o, str):
        return mascara(o)
    if isinstance(o, list):
        return [anda(x) for x in o]
    if isinstance(o, dict):
        return {k: (v if CODIGO.match(str(k)) else anda(v)) for k, v in o.items()}
    return o


def texto_csv(t):
    out = io.StringIO()
    w = csv.writer(out, lineterminator='\n')
    pula = set()
    for i, row in enumerate(csv.reader(io.StringIO(t))):
        if i == 0:
            pula = {j for j, c in enumerate(row) if CODIGO.match(c.strip())}
            w.writerow(row); continue
        w.writerow([c if j in pula else mascara(c) for j, c in enumerate(row)])
    return out.getvalue()


def tratar(caminho):
    gz = caminho.endswith('.gz')
    base = caminho[:-3] if gz else caminho
    if not base.endswith(('.csv', '.json')):
        return False
    bruto = gzip.open(caminho, 'rb').read() if gz else open(caminho, 'rb').read()
    try:
        t = bruto.decode('utf-8-sig')
    except UnicodeDecodeError:
        return False
    if not CPF.search(t):
        return False
    if base.endswith('.json'):
        try:
            novo = json.dumps(anda(json.loads(t)), ensure_ascii=False, separators=(',', ':') if gz else None, indent=None if gz else 1)
        except ValueError:
            return False
    else:
        novo = texto_csv(t)
    if novo == t:
        return False
    dado = novo.encode('utf-8')
    if gz:
        with gzip.open(caminho, 'wb') as fh:
            fh.write(dado)
    else:
        open(caminho, 'wb').write(dado)
    return True


def main(pasta):
    n = 0
    for raiz, _, arqs in os.walk(pasta):
        for a in arqs:
            try:
                n += tratar(os.path.join(raiz, a))
            except Exception as e:
                print(f'LGPD: não tratei {a}: {e}', flush=True)
    print(f'LGPD: CPF mascarado em {n} arquivo(s)', flush=True)


if __name__ == '__main__':
    main(sys.argv[1] if len(sys.argv) > 1 else 'saida')
