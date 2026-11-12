"""
Robô Transferegov · SDR/MAPA — páginas prontas do painel (Obras e Prestação de contas)
Lê os CSV que o processar.py gravou na pasta de saída e grava pagina_obras.html e pagina_prestacao.html
(dados embutidos; o Painel SDR abre essas páginas dentro da aba Parceria SDR).

Uso:  python scripts/paginas.py PASTA_DE_SAIDA
"""
import csv, json, os, re, sys, datetime, unicodedata, collections

csv.field_size_limit(10**9)
AQUI = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'paginas')


def na(t):
    return unicodedata.normalize('NFKD', t or '').encode('ascii', 'ignore').decode().upper()


def f(x):
    try:
        return round(float(x or 0), 2)
    except ValueError:
        return 0.0


def d(s):
    try:
        return datetime.datetime.strptime((s or '')[:10], '%d/%m/%Y').date()
    except ValueError:
        return None


def ler(pasta, nome):
    caminho = os.path.join(pasta, nome)
    if not os.path.exists(caminho):
        return []
    with open(caminho, encoding='utf-8') as fh:
        return list(csv.DictReader(fh))


# objeto resumido: tipo de obra pelas palavras do objeto
REGRAS = [('Pontes e passagens molhadas', r'PONTE|PASSAGE[MN]S? MOLHAD|BUEIRO'),
          ('Pavimentação', r'PAVIMENT|CALCAMENT|ASFALT'),
          ('Estradas vicinais', r'ESTRADA|VICINA|HORA MAQUINA|RODOVI|MATA.?BURRO|EROSAO'),
          ('Mercados e feiras', r'MERCADO|FEIRA|COMERCIALIZ|CENTRO DE ABAST'),
          ('Abatedouros e agroindústria', r'ABATEDOURO|MATADOURO|AGROINDUSTRIA|FRIGORIF|LATICINIO'),
          ('Suporte hídrico e irrigação', r'HIDRIC|AGUA|ACUDE|POCO|IRRIGA|BARRAGEM|BARRAGINHA|CISTERNA'),
          ('Energia', r'ENERGIA|ELETRIF'),
          ('Parques de exposição', r'EXPOSIC|PARQUE'),
          ('Máquinas e equipamentos', r'MAQUINA|EQUIPAMENTO|PATRULHA|TRATOR|VEICULO|MECANIZ'),
          ('Galpões, armazéns e currais', r'GALP|ARMAZEN|ENTREPOSTO|CURRAL|PAVILH|SILO|BALANCA'),
          ('Fomento agropecuário (genérico)', r'FOMENTO AOS? SETOR|AGROPECUARI')]


def objeto_resumido(o):
    t = na(o)
    for nome, rx in REGRAS:
        if re.search(rx, t):
            return nome
    return 'Outros'


def montar(tpl, dados, data_carga):
    h = open(os.path.join(AQUI, tpl), encoding='utf-8').read()
    h = h.replace('__CSS__', open(os.path.join(AQUI, 'estilo.css'), encoding='utf-8').read())
    h = h.replace('<script>__MAPA__', '<script>' + open(os.path.join(AQUI, 'busca.js'), encoding='utf-8').read() + '\n__MAPA__', 1)
    h = h.replace('__MAPA__', open(os.path.join(AQUI, 'mapa.js'), encoding='utf-8').read())
    h = h.replace('__DATA__', data_carga)
    h = h.replace('__FILTRO__', open(os.path.join(AQUI, 'filtro.js'), encoding='utf-8').read())
    h = h.replace('__KPI__', open(os.path.join(AQUI, 'kpi.js'), encoding='utf-8').read())
    from lgpd import anda as _lgpd   # LGPD: CPF de pessoa física mascarado (***.452.881-**)
    return h.replace('__DADOS__', json.dumps(_lgpd(dados), ensure_ascii=False, separators=(',', ':')).replace('</', '<\\/'))


def main(pasta):
    hoje = datetime.date.today()
    meta = {}
    try:
        meta = json.load(open(os.path.join(pasta, 'atualizacao.json'), encoding='utf-8'))
    except Exception:
        pass
    data_carga = str(meta.get('data_carga') or meta.get('gerado_em') or hoje.strftime('%d/%m/%Y'))[:16]
    inst = {r['nr_instrumento']: r for r in ler(pasta, 'instrumentos.csv')}

    # ------------------------------------------------------------ Obras
    med = collections.defaultdict(list)
    for r in ler(pasta, 'obras_medicoes.csv'):
        med[r.get('ID_PROPOSTA', '')].append([r.get('NUMERO_MEDICAO_ACOMPANHAMENTO_OBRA', ''), r.get('SITUACAO_MEDICAO_ACOMPANHAMENTO_OBRA', ''),
                                              r.get('DATA_INICIO_MEDICAO_OBJETO_ACOMPANHAMENTO_OBRA', ''), r.get('DATA_FIM_MEDICAO_OBJETO_ACOMPANHAMENTO_OBRA', '')])
    obras = []
    for o in ler(pasta, 'painel_obras.csv'):
        i = inst.get(o['nr_instrumento'], {})
        m = sorted(med.get(i.get('id_proposta', ''), []), key=lambda x: (x[3] or '', x[0]))[-6:]
        obras.append(dict(n=o['nr_instrumento'], so=o['situacao_obra'], cr=o['criterio'], pf=f(o['pct_fisico']), vo=f(o['valor_obra']), vr=f(o['valor_realizado']),
                          dsm=o['dias_sem_medicao'], um=o['fim_ultima_medicao'], nm=o['nr_medicao'], sm=o['situacao_medicao'], io=o['inicio_obra'], emp=o['cnpj_empresa'],
                          si=o['situacao_instrumento'], ug=o['ug_emitente'], mod=o['modalidade'], fv=o['fim_vigencia'], rep=f(o['valor_repasse']), des=f(o['valor_desembolsado']),
                          pd=f(o['pct_desembolsado']), prop=o['proponente'], uf=o['uf'], mun=na(o['municipio']).strip(), munN=o['municipio'],
                          parl=o['parlamentar'] or '(sem parlamentar)', tp=i.get('tipo_parlamentar', '') or '(sem emenda)', obj=o['objeto'], objr=objeto_resumido(o['objeto']),
                          ano=i.get('ano_proposta', ''), np=i.get('nr_proposta', ''), nj=i.get('natureza_juridica', ''), emd=i.get('nr_emenda', ''),
                          ne=i.get('notas_empenho', ''), prog=i.get('programa', ''), link=o['link_transparencia'], med=m))
    with open(os.path.join(pasta, 'pagina_obras.html'), 'w', encoding='utf-8') as fh:
        fh.write(montar('obras.html', obras, data_carga))
    print(f'pagina_obras.html · {len(obras)} obras', flush=True)

    # ------------------------------------------------------------ Prestação de contas
    hist = collections.defaultdict(list)
    rej = {}
    for h in ler(pasta, 'historico_situacao.csv'):
        n, s = h.get('NR_CONVENIO', ''), h.get('HISTORICO_SIT', '')
        dt = d(h.get('DIA_HISTORICO_SIT'))
        hist[n].append((dt or datetime.date.min, (h.get('DIA_HISTORICO_SIT') or '')[:10], s.replace('_', ' ').capitalize()))
        if s == 'PRESTACAO_CONTAS_REJEITADA' and dt and (n not in rej or dt > rej[n][0]):
            rej[n] = (dt, (h.get('DIA_HISTORICO_SIT') or '')[:10])
    FASE = {'Aguardando Prestação de Contas': 'Aguardando PC', 'Prestação de Contas enviada para Análise': 'Enviada para análise',
            'Prestação de Contas em Análise': 'Em análise', 'Prestação de Contas Comprovada em Análise': 'Em análise',
            'Prestação de Contas em Complementação': 'Em complementação', 'Prestação de Contas Iniciada Por Antecipação': 'Iniciada por antecipação',
            'Prestação de Contas Rejeitada': 'Rejeitada', 'Inadimplente': 'Inadimplente'}
    pcs = []
    for n, r in inst.items():
        fa = FASE.get(r['situacao'])
        ja_ruim = bool(r.get('inadimplente_desde')) or n in rej
        if not fa and not ja_ruim:
            continue
        lim, fv = d(r['limite_prestacao_contas']), d(r['fim_vigencia'])
        if fa == 'Aguardando PC':
            fa = 'Aguardando PC · prazo vencido' if lim and lim < hoje else 'Aguardando PC · no prazo'
        if not fa:
            fa = 'Encerrada (já foi rejeitada/inadimplente)'
        tl = []
        for x in sorted(hist.get(n, [])):
            if not tl or tl[-1][1] != x[2]:
                tl.append((x[1], x[2]))
        pcs.append(dict(n=n, ug=r['ug_emitente'], fase=fa, sit=r['situacao'], sub=r['subsituacao'], ano=r['ano_proposta'], fv=r['fim_vigencia'], lim=r['limite_prestacao_contas'],
                        dfv=(hoje - fv).days if fv else None, dlim=(hoje - lim).days if lim else None, rep=f(r['valor_repasse']), des=f(r['valor_desembolsado']), emp=f(r['valor_empenhado']),
                        sc=f(r['saldo_em_conta']), rend=f(r['rendimento_aplicacao']), cp=f(r['ingresso_contrapartida']),
                        dt=f(r.get('saldo_devolvido_tesouro')), dc=f(r.get('saldo_devolvido_convenente')),
                        tce=r.get('em_processo_tce') == 'SIM', inad=r.get('inadimplente_desde', ''), rej=rej[n][1] if n in rej else '',
                        mod=r['modalidade'], prop=r['proponente'], uf=r['uf'], mun=na(r['municipio']).strip(), munN=r['municipio'],
                        parl=r['parlamentar'] or '(sem parlamentar)', tp=r['tipo_parlamentar'] or '(sem emenda)', nj=r['natureza_juridica'], obj=r['objeto'],
                        np=r['nr_proposta'], ne=r['notas_empenho'], prog=r['programa'], emd=r['nr_emenda'], link=r['link_proposta'], ultd=r['ultimo_desembolso'], tl=tl[-10:]))
    with open(os.path.join(pasta, 'pagina_prestacao.html'), 'w', encoding='utf-8') as fh:
        fh.write(montar('prestacao.html', pcs, data_carga))
    print(f'pagina_prestacao.html · {len(pcs)} instrumentos', flush=True)
    propostas(pasta, data_carga)
    execucao(pasta, data_carga)
    try:
        ted(pasta)
    except Exception as e:  # a falta dos TEDs não pode derrubar as outras páginas
        print('página de TED não gerada:', e, flush=True)
    try:
        repasse(pasta, data_carga)
    except Exception as e:
        print('página de contrato de repasse não gerada:', e, flush=True)
    try:
        orcamento_pag(pasta)
    except Exception as e:
        print('página de orçamento não gerada:', e, flush=True)


def propostas(pasta, data_carga):
    """Página Propostas: anos recentes embutidos; anos anteriores em propostas_pag/AAAA.json, que a página carrega em seguida."""
    import glob
    hoje = datetime.date.today()
    anomin = hoje.year - 3
    anos = collections.defaultdict(lambda: [0, 0])
    pacotes = collections.defaultdict(lambda: {'dic': {}, 'rows': []})

    def ix(dic, k, v):
        d = dic.setdefault(k, {})
        if v not in d:
            d[v] = len(d)
        return d[v]
    # empenho do instrumento já criado para a proposta (o Transferegov registra a NE antes da assinatura): nº e valor
    empInst = {}
    for r in ler(pasta, 'instrumentos.csv'):
        if r.get('nr_instrumento'):
            empInst[r['nr_instrumento']] = (round(f(r.get('valor_empenhado'))), (r.get('notas_empenho') or '')[:120])
    for arq in sorted(glob.glob(os.path.join(pasta, 'propostas_por_ano', '*.csv'))):
        for r in ler(os.path.dirname(arq), os.path.basename(arq)):
            a = r.get('ano_proposta', '')
            if not a.isdigit():
                continue
            cel = r.get('celebrada') == 'SIM'
            anos[a][0] += 1
            anos[a][1] += 1 if cel else 0
            pk = pacotes['recentes' if int(a) >= anomin else a]
            dic = pk['dic']
            pk['rows'].append([int(a), ix(dic, 's', r['situacao_proposta']), ix(dic, 'm', r['modalidade']), ix(dic, 'u', r['uf']), ix(dic, 'g', (r['programa'] or '')[:120]),
                               ix(dic, 'p', r['parlamentar']), ix(dic, 't', r['tipo_parlamentar']), ix(dic, 'j', r['natureza_juridica']), 1 if cel else 0,
                               round(f(r['valor_repasse_proposta'])), round(f(r['valor_global_proposta'])), r['nr_proposta'], r['nr_instrumento'],
                               ix(dic, 'r', r['proponente']), ix(dic, 'c', r['municipio']), int(r['id_proposta'] or 0), r['nr_emenda'],
                               (r['objeto'] or '')[:220 if int(a) >= anomin else 120],
                               r.get('ug_emitente', ''), r.get('inicio_vigencia_proposta', ''), r.get('fim_vigencia_proposta', ''), r.get('cnpj_proponente', ''),
                               ix(dic, 'a', ' | '.join(sorted({x.strip()[-4:] for x in (r.get('acao_orcamentaria') or '').split('|') if x.strip()}))),
                               *empInst.get(r['nr_instrumento'], (0, ''))])
    emp = lambda pk: {'d': {k: list(v) for k, v in pk['dic'].items()}, 'r': pk['rows']}
    os.makedirs(os.path.join(pasta, 'propostas_pag'), exist_ok=True)
    antigos = sorted(a for a in pacotes if a != 'recentes')
    for a in antigos:
        with open(os.path.join(pasta, 'propostas_pag', a + '.json'), 'w', encoding='utf-8') as fh:
            json.dump(emp(pacotes[a]), fh, ensure_ascii=False, separators=(',', ':'))
    dados = emp(pacotes['recentes'])
    dados.update({'anos': [[a, n, c] for a, (n, c) in sorted(anos.items())], 'anomin': anomin, 'antigos': antigos})
    h = montar('propostas.html', dados, data_carga).replace('__ANOMIN__', str(anomin))
    with open(os.path.join(pasta, 'pagina_propostas.html'), 'w', encoding='utf-8') as fh:
        fh.write(h)
    print(f'pagina_propostas.html · {len(dados["r"])} propostas desde {anomin} + {len(antigos)} anos em propostas_pag/ · {sum(n for n, c in anos.values())} no total', flush=True)


def execucao(pasta, data_carga):
    """Páginas Empenho/Desembolso, Programas/Emendas e Movimentação financeira (instrumentos vigentes + os com movimento no ano)."""
    hoje = datetime.date.today()
    ano = hoje.year
    inst = {r['nr_instrumento']: r for r in ler(pasta, 'instrumentos.csv')}
    agrupa = lambda lista: collections.defaultdict(list, {})
    emp, des, pag, cro, eme = (collections.defaultdict(list) for _ in range(5))
    for e in ler(pasta, 'empenhos.csv'):
        emp[e['NR_CONVENIO']].append(e)
    for d_ in ler(pasta, 'desembolsos.csv'):
        des[d_['NR_CONVENIO']].append(d_)
    for p_ in ler(pasta, 'pagamentos.csv'):
        pag[p_['NR_CONVENIO']].append(p_)
    for c in ler(pasta, 'cronograma_desembolso.csv'):
        cro[c['NR_CONVENIO']].append(c)
    for e in ler(pasta, 'emendas.csv'):
        eme[e['ID_PROPOSTA']].append(e)
    pag_ano = collections.Counter()
    linhas = []
    for n, r in inst.items():
        ds = [(d(x.get('DATA_DESEMBOLSO')), f(x.get('VL_DESEMBOLSADO')), x.get('NR_SIAFI', '')) for x in des.get(n, [])]
        ps = [(d(x.get('DATA_PAG')), f(x.get('VL_PAGO')), x.get('IDENTIF_FORNECEDOR', ''), x.get('NOME_FORNECEDOR', ''), x.get('TP_MOV_FINANCEIRA', ''), x.get('DESC_DL', ''), x.get('NR_DL', '')) for x in pag.get(n, [])]
        for x in ps:
            if x[0]:
                pag_ano[x[0].year] += 1
        mov_ano = any(x[0] and x[0].year == ano for x in ds) or any(x[0] and x[0].year == ano for x in ps)
        if r['situacao'] != 'Em execução' and not mov_ano:
            continue
        rpc = collections.Counter((e.get('RESULTADO_PRIMARIO') or '').strip() for e in emp.get(n, []) if (e.get('RESULTADO_PRIMARIO') or '').strip())
        nes = [[e.get('NR_EMPENHO', ''), e.get('UG_EMITENTE', ''), e.get('DATA_EMISSAO', ''), f(e.get('VALOR_EMPENHO')), e.get('DESC_TIPO_NOTA', ''), 1 if 'NSSALDO' in (e.get('OBSERVACAO_EMPENHO') or '').upper().replace(' ', '') else 0] for e in emp.get(n, [])]   # 6º: cópia da transferência de saldo (NS SALDO)
        ult_p = max((x[0] for x in ps if x[0]), default=None)
        forn = collections.defaultdict(lambda: [0.0, 0, ''])
        for x in ps:
            k = x[2] or x[3]
            forn[k][0] += x[1]
            forn[k][1] += 1
            forn[k][2] = x[3]
        fv = d(r['fim_vigencia'])
        crono = collections.Counter()
        for c in cro.get(n, []):
            if (c.get('TIPO_RESP_CRONO_DESEMBOLSO') or '').lower().startswith('concedente') and (c.get('ANO_CRONO_DESEMBOLSO') or '').isdigit():
                crono[f"{c['ANO_CRONO_DESEMBOLSO']}-{int(c.get('MES_CRONO_DESEMBOLSO') or 0):02d}"] += f(c.get('VALOR_PARCELA_CRONO_DESEMBOLSO'))
        ems = eme.get(r.get('id_proposta', ''), [])
        linhas.append(dict(
            n=n, ug=r['ug_emitente'], sit=r['situacao'], mod=r['modalidade'], prop=r['proponente'], cnpj=r['cnpj_proponente'], uf=r['uf'], mun=na(r['municipio']).strip(), munN=r['municipio'],
            parl=r['parlamentar'] or '(sem parlamentar)', tp=r['tipo_parlamentar'] or '(sem emenda)', nj=r['natureza_juridica'], ano=r['ano_proposta'], anoAss=(r['data_assinatura'] or '')[-4:],
            fv=r['fim_vigencia'], dv=(fv - hoje).days if fv else None, rep=f(r['valor_repasse']), des=f(r['valor_desembolsado']), aDes=f(r['valor_a_desembolsar']), emp=f(r['valor_empenhado']),
            sc=f(r['saldo_em_conta']), rend=f(r['rendimento_aplicacao']), cp=f(r['ingresso_contrapartida']), glob=f(r['valor_global']),
            dt=f(r.get('saldo_devolvido_tesouro')), dc=f(r.get('saldo_devolvido_convenente')),
            repProp=f(r.get('valor_repasse_proposta')), globOrig=f(r.get('valor_global_original')), supTA=f(r.get('supressao_repasse_ta')),
            reduRep=f(r.get('reducao_repasse')), nAjPT=int(r.get('qtd_ajustes_pt') or 0), ultAjPT=r.get('ultimo_ajuste_pt', ''), adt=(r.get('aditivos_valor') or '')[:300],
            prog=(r['programa'] or '(sem programa)')[:120], acao=' | '.join(sorted({x.strip()[-4:] for x in (r.get('acao_orcamentaria') or '').split('|') if x.strip()})) or '(sem ação)',
            emd=r['nr_emenda'], vEm=round(sum(f(e.get('VALOR_REPASSE_EMENDA')) for e in ems), 2), nEm=len({e.get('NR_EMENDA') for e in ems if e.get('NR_EMENDA')}),
            ems=[[e.get('NR_EMENDA', ''), e.get('NOME_PARLAMENTAR', ''), e.get('TIPO_PARLAMENTAR', ''), f(e.get('VALOR_REPASSE_EMENDA')), e.get('IND_IMPOSITIVO', '')] for e in ems][:8],
            rp=(rpc.most_common(1)[0][0] if rpc else ''), objr=objeto_resumido(r['objeto']), obj=(r['objeto'] or '')[:300], link=r['link_proposta'],
            dsd=int(r['dias_sem_desembolso']) if (r['dias_sem_desembolso'] or '').isdigit() else None, ultd=r['ultimo_desembolso'], nes=nes[:20],
            desAno=[[x[0].strftime('%d/%m/%Y'), x[1], x[2]] for x in sorted(ds, key=lambda x: x[0] or datetime.date.min) if x[0] and x[0].year == ano],
            crono=sorted(crono.items()),
            pg=round(sum(x[1] for x in ps), 2), nPg=len(ps), pgAno=round(sum(x[1] for x in ps if x[0] and x[0].year == ano), 2),
            pgObtv=round(sum(x[1] for x in ps if 'OBTV' in (x[4] or '')), 2),
            ultP=ult_p.strftime('%d/%m/%Y') if ult_p else '', dsp=(hoje - ult_p).days if ult_p else None,
            forn=[[k, v[2], round(v[0], 2), v[1]] for k, v in sorted(forn.items(), key=lambda kv: -kv[1][0])[:6]],
            pags=[[x[0].strftime('%d/%m/%Y') if x[0] else '', x[3], x[1], x[5], x[6]] for x in sorted(ps, key=lambda x: x[0] or datetime.date.min, reverse=True)[:8]]))
    meta = {'ano': ano, 'pagAno': sorted([a, c] for a, c in pag_ano.items() if a >= 2008)}
    for aba, nome in (('emp', 'pagina_empenho.html'), ('prog', 'pagina_programas.html'), ('mov', 'pagina_movimentacao.html')):
        h = montar('execucao.html', {'linhas': linhas, 'meta': meta}, data_carga).replace('__ABA__', aba)
        with open(os.path.join(pasta, nome), 'w', encoding='utf-8') as fh:
            fh.write(h)
    print(f'páginas de execução · {len(linhas)} instrumentos', flush=True)



def repasse(pasta, data_carga):
    """Página Contrato de Repasse: todos os contratos de repasse (Caixa), com obra, prestação de contas, inadimplência e emendas."""
    hoje = datetime.date.today()
    inst = [r for r in ler(pasta, 'instrumentos.csv') if 'REPASSE' in (r.get('modalidade') or '').upper()]
    obra = {o['nr_instrumento']: o for o in ler(pasta, 'painel_obras.csv')}
    og = {o['nr_instrumento']: o for o in ler(pasta, 'obrasgov_complemento.csv')}   # complemento da API do Obrasgov (obras ativas)
    emp = collections.defaultdict(list)
    for e in ler(pasta, 'empenhos.csv'):
        emp[e['NR_CONVENIO']].append((e.get('NR_EMPENHO', ''), e.get('UG_EMITENTE', '')))

    def grupo(s):
        u = (s or '').upper()
        if u == 'EM EXECUÇÃO': return 'Em execução'
        if 'INADIMPLENTE' in u: return 'Inadimplente'
        if 'PRESTAÇÃO DE CONTAS APROVADA' in u or 'PRESTAÇÃO DE CONTAS CONCLUÍDA' in u: return 'Concluído'
        if 'PRESTAÇÃO DE CONTAS' in u: return 'Em prestação de contas'
        if 'ANULADO' in u or 'RESCINDIDO' in u or 'CANCELADO' in u or 'EXTINTO' in u: return 'Anulado / rescindido'
        if 'PROPOSTA' in u or 'PLANO DE TRABALHO' in u or 'ASSINATURA' in u: return 'Aguardando início'
        return 'Outros'
    out = []
    for r in inst:
        n = r['nr_instrumento']
        sg = grupo(r['situacao'] or r.get('situacao_proposta', ''))
        ativo = sg in ('Em execução', 'Aguardando início', 'Em prestação de contas', 'Inadimplente')
        fv, lim = d(r['fim_vigencia']), d(r['limite_prestacao_contas'])
        o = obra.get(n, {})
        m = re.search(r'idProposta=(\d+)', r.get('link_proposta') or '')
        x = dict(n=n, ug=r['ug_emitente'], si=r['situacao'] or r.get('situacao_proposta', '') or '-', sg=sg, ano=r['ano_proposta'], uf=r['uf'],
                 mun=na(r['municipio']).strip(), munN=r['municipio'], prop=r['proponente'], nj=r['natureza_juridica'],
                 parl=r['parlamentar'] or '(sem parlamentar)', tp=r['tipo_parlamentar'] or '(sem emenda)', emd=r['nr_emenda'],
                 rep=f(r['valor_repasse']), des=f(r['valor_desembolsado']), aDes=f(r['valor_a_desembolsar']), sc=f(r['saldo_em_conta']),
                 fv=r['fim_vigencia'], dv=(fv - hoje).days if fv else None, lim=r['limite_prestacao_contas'], dlim=(hoje - lim).days if lim else None,
                 dsd=int(r['dias_sem_desembolso']) if (r['dias_sem_desembolso'] or '').isdigit() else None, ultd=r['ultimo_desembolso'],
                 lj='Liminar judicial' if 'LIMINAR' in (r.get('situacao_contratacao') or '').upper() else ('Cláusula suspensiva' if 'SUSPENSIVA' in (r.get('situacao_contratacao') or '').upper() else 'Normal'),
                 tce=1 if r.get('em_processo_tce') == 'SIM' else 0, inad=r.get('inadimplente_desde', ''),
                 adt=int(r.get('qtd_aditivos') or 0), prr=int(r.get('qtd_prorrogacoes') or 0),
                 acao=' | '.join(sorted({y.strip()[-4:] for y in (r.get('acao_orcamentaria') or '').split('|') if y.strip()})) or '(sem ação)',
                 obj=(r['objeto'] or '')[:160 if ativo else 80], id=m.group(1) if m else '',
                 so=o.get('situacao_obra', '') or '(sem obra no Obrasgov)', pf=f(o.get('pct_fisico')), vo=f(o.get('valor_obra')), dsm=o.get('dias_sem_medicao', ''))
        if ativo:
            x['nes'] = [[a, b] for a, b in emp.get(n, []) if a][:15]
        g = og.get(n)
        if g:
            x['og'] = {k: v for k, v in dict(id=g['id_projeto'], s=g['situacao_api'], pf=g['pct_fisico_api'], at=g['atualizacao_fisica'],
                       ps=g['paralisacao_situacao'], pd=g['paralisacao_data'], pj=g['paralisacao_justificativa'], tr=g['tratativas'], ft=g['fase_tratativas'],
                       cn=g['contrato_numero'], cf=g['contrato_fornecedor'], cc=g['contrato_cnpj'], cv=g['contrato_valor'], cfv=g['contrato_fim_vigencia'],
                       cl=g['contrato_link'], dt=g['consultado_em']).items() if v}
        out.append(x)
    # campos repetitivos viram índice de dicionário (a página fica ~3x menor); a página decodifica
    cat = ['ug', 'si', 'sg', 'ano', 'uf', 'mun', 'munN', 'prop', 'nj', 'parl', 'tp', 'lj', 'acao', 'so', 'ultd', 'fv', 'lim', 'inad']
    dic = {k: {} for k in cat}
    for x in out:
        for k in cat:
            x[k] = dic[k].setdefault(x[k], len(dic[k]))
    cols = list(dict.fromkeys(k for x in out for k in x))
    dados = dict(dic={k: list(v) for k, v in dic.items()}, c=cols, r=[[x.get(k) for k in cols] for x in out])
    with open(os.path.join(pasta, 'pagina_repasse.html'), 'w', encoding='utf-8') as fh:
        fh.write(montar('repasse.html', dados, data_carga))
    print(f'pagina_repasse.html · {len(out)} contratos de repasse', flush=True)


UGS_SDR = {'130010', '130141', '130255', '135098', '420013'}
UGN_PY = {'130010': '130010 · CEPLAC', '130141': '130141 · CGPI/SDR', '130255': '130255 · CGMAP/SDR', '135098': '135098 · Caixa/MA', '420013': '420013 · SDR'}


def ted(pasta):
    """Página TED API: termos de execução descentralizada das UGs da SDR (arquivos que o ted.py grava em PASTA/ted)."""
    tp = os.path.join(pasta, 'ted')
    planos = ler(tp, 'ted_planilha.csv')
    if not planos:
        print('página de TED: sem ted/ted_planilha.csv', flush=True)
        return
    meta = {}
    try:
        meta = json.load(open(os.path.join(tp, 'ted_atualizacao.json'), encoding='utf-8'))
    except Exception:
        pass
    ncs, pfs, cro, par, met = (collections.defaultdict(list) for _ in range(5))
    dt = lambda s: (s or '')[8:10] + '/' + (s or '')[5:7] + '/' + (s or '')[:4] if s and len(s) >= 10 else ''
    for x in ler(tp, 'ted_notas_credito.csv'):
        ncs[x['id_plano_acao']].append([x['tx_numero_nota'] or x['tx_minuta_nota'], dt(x['dt_emissao_nota']), x['cd_ug_emitente_nota'], x['cd_ug_favorecida_nota'],
                                        f(x['valor_eventos']), x['ptres'], x['plano_interno'], x['natureza'], x['resultado_primario'], x['tx_situacao_nota'], x['autor_emenda']])
    for x in ler(tp, 'ted_programacoes.csv'):
        pfs[x['id_plano_acao']].append([x['tx_numero_programacao'] or x['tx_minuta_programacao'], dt(x['dh_recebimento_programacao']), x['ug_emitente_programacao'],
                                        x['ug_favorecida_programacao'], f(x['valor_trf']), x['tx_situacao_programacao'], (x['tx_observacao_programacao'] or '')[:160]])
    MES = {m: i for i, m in enumerate(['JAN', 'FEV', 'MAR', 'ABR', 'MAI', 'JUN', 'JUL', 'AGO', 'SET', 'OUT', 'NOV', 'DEZ'], 1)}
    for x in ler(tp, 'ted_cronograma.csv'):
        cro[x['id_plano_acao']].append([x['ano_cronograma_plano_trabalho'], MES.get(x['mes_cronograma_plano_trabalho'], 0), f(x['valor_cronograma_plano_trabalho'])])
    for x in ler(tp, 'ted_analises_pareceres.csv'):
        # análise: resultado + situação + justificativa · parecer: tipo do parecer + resultado + texto + data (antes vinha vazio)
        if (x.get('tipo') or '').lower().startswith('parecer'):
            par[x['id_plano_acao']].append(['parecer', x.get('resultado_parecer') or '', x.get('tp_analise_parecer') or '', (x.get('tx_parecer') or '')[:6000], dt(x.get('dt_data_parecer'))])
        else:
            par[x['id_plano_acao']].append(['análise', x['resultado_analise'], x['tx_situacao_analise'], (x['tx_justificativa_analise'] or '')[:6000], ''])
    for x in ler(tp, 'ted_metas.csv'):
        met[x['id_plano_acao']].append([x['nr_numero_meta'], x['tx_nome_meta'][:160], x['nr_quantidade_meta'], x['tp_unidade_meta'], f(x['vl_valor_unitario_meta']),
                                        dt(x['dt_inicio_vigencia_meta']), dt(x['dt_fim_vigencia_meta'])])
    hoje = datetime.date.today()
    linhas = []
    for r in planos:
        g = lambda k: (r.get(k) or '').strip()
        sp, st = g('Situação do plano de ação'), g('Situação do termo')
        dias = int(g('Dias para o fim')) if re.fullmatch(r'-?\d+', g('Dias para o fim')) else None
        if st.startswith('CUMPRIMENTO_OBJETO_APROVADO'):
            fase = 'Concluído'
        elif st.startswith('CUMPRIMENTO_OBJETO'):
            fase = 'Prestação de contas'
        elif st == 'EM_EXECUCAO':
            fase = 'Vigência vencida' if dias is not None and dias < 0 else 'Em execução'
        elif st or g('Nº TED (SIAFI)'):
            fase = 'Em formalização'
        elif sp == 'REJEITADO':
            fase = 'Plano rejeitado'
        else:
            fase = 'Plano em análise'
        i = g('id_plano_acao')
        cr = sorted(cro.get(i, []))
        prox = next((c for c in cr if (int(c[0] or 0), c[1]) >= (hoje.year, hoje.month)), None)
        linhas.append(dict(
            id=i, n=g('Nº TED (SIAFI)'), ano=g('Ano do TED') or '(sem ano)', cod=g('Código do plano de ação'), er=g('Enviado / recebido'),
            ugd=g('UG descentralizadora'), und=g('Unidade descentralizadora'), ugr=g('UG descentralizada'), unr=g('Unidade descentralizada') or '(não informada)',
            orr=g('Órgão descentralizado') or '(não informado)', ord=g('Órgão descentralizador'), uge=g('UG executora'), prog=g('Programa'), acao=g('Ação orçamentária') or '(sem ação)',
            obj=g('Objeto')[:600], sp=sp or '(sem situação)', st=st or '(sem termo)', fase=fase, sei=g('Processo SEI'), ass=g('Data de assinatura'),
            ini=g('Início da vigência'), fim=g('Fim da vigência'), dias=dias, fir=f(g('Valor firmado')), nc=f(g('Descentralizado (notas de crédito)')),
            op=f(g('Orçamento pendente')), pf=f(g('Repassado (programação financeira)')), ar=f(g('A repassar')),
            rp=g('Resultado primário'), emd=g('Emenda (autor)'), ult=g('Último parecer / análise'), link=g('Link do termo'), ns=g('Nº da NS do termo'),
            ncs=ncs.get(i, [])[:40], pfs=pfs.get(i, [])[:40], cro=cr[:36], prox=[prox[0], prox[1], prox[2]] if prox else None,
            par=par.get(i, [])[-8:], met=met.get(i, [])[:20]))
    # ---- cruzamento com o relatório do Tesouro Gerencial (ted/ted_tesouro.csv, gravado pelo ted_tesouro.py)
    import ted_tesouro
    tes_lin = ler(tp, 'ted_tesouro.csv')
    tes_meta = {}
    try:
        tes_meta = json.load(open(os.path.join(tp, 'ted_tesouro.json'), encoding='utf-8'))
    except Exception:
        pass
    fx = lambda v: f(v) if (v or '').strip() != '' else None
    base_c = {'ted', 'ted_txt', 'ug_emit', 'ug_fav', 'nome_fav', 'ano', 'processo', 'situacao', 'ini', 'fim', 'objeto',
              'fir', 'nc', 'rep', 'aRep', 'aComp', 'aApr', 'comp', 'apr', 'aRec', 'dev'}
    tes = {}
    for x in tes_lin:
        tes[x['ted']] = dict(fir=fx(x['fir']), nc=fx(x['nc']), rep=fx(x['rep']), aRep=fx(x['aRep']), aComp=fx(x['aComp']), comp=fx(x['comp']), dev=fx(x['dev']),
                             aApr=fx(x.get('aApr')), apr=fx(x.get('apr')), sit=x.get('situacao', ''), ini=x.get('ini', ''), fim=x.get('fim', ''), obj=x.get('objeto', ''),
                             ugE=x['ug_emit'], ugF=x['ug_fav'], nome=x['nome_fav'], ano=x['ano'], proc=x['processo'],
                             contas=[[k, f(v)] for k, v in x.items() if k not in base_c and (v or '').strip() not in ('', '0', '0.0')])
    # notas de crédito do Tesouro (ted/ted_tesouro_nc.csv): completam as NCs, a ação e o resultado primário que a API não traz
    # PTRES → ação: a base de orçamento do Tesouro (orcamento/orcamento.csv) vale mais que a API de TED, que às vezes traz o programa de trabalho de outro órgão
    ac_orc = {}
    for x in ler(os.path.join(pasta, 'orcamento'), 'orcamento.csv'):
        if x.get('ptres') and x.get('acao'):
            ac_orc.setdefault(x['ptres'].strip(), x['acao'].strip().zfill(4) if x['acao'].strip().isdigit() else x['acao'].strip())
    ncT = collections.defaultdict(list)
    semTED, acoesSDR = [], set()   # NCs que outros órgãos mandaram para a SDR sem nº de TED
    ncProc = collections.defaultdict(list)   # NCs da SDR sem nº de TED, pelo nº do processo (só dígitos)
    # o relatório de NC repete o mesmo item da nota uma vez para cada "Ação Governo" ligada ao PTRES (ex.: 2022NC800053 em 20ZV e 8593),
    # o que dobrava o valor descentralizado. Fica uma linha por item: a ação do PTRES na base de orçamento, senão a mais vista nesse PTRES
    nc_lin = ler(tp, 'ted_tesouro_nc.csv')
    grp = collections.OrderedDict()
    for x in nc_lin:
        grp.setdefault((x['nc_completa'] or x['nc'], x['ted'], x['ug_emit'], x['ug_fav'], x['nd'], x['pi'], x['ptres'], x['fonte'], x['valor'], x['data']), []).append(x)
    freq = collections.Counter((g[0]['ptres'].strip(), g[0]['acao']) for g in grp.values() if len({y['acao'] for y in g}) == 1)
    nc_uni, n_dup = [], 0
    for g in grp.values():
        acs = []
        for y in sorted(g, key=lambda y: not y.get('evento')):   # a mesma NC vem em mais de um relatório: fica a que traz o evento
            if y['acao'] not in [a['acao'] for a in acs]:
                acs.append(y)
        if len(acs) > 1:
            pt = acs[0]['ptres'].strip()
            n_dup += len(acs) - 1
            acs.sort(key=lambda y: (y['acao'] != ac_orc.get(pt), -freq[(pt, y['acao'])]))
        nc_uni.append(acs[0])
    print(f'NC do Tesouro: {len(nc_lin)} linhas, {n_dup} repetidas por ação descartadas', flush=True)
    # devolução de crédito da unidade para a SDR (relatórios TED_NC_DEV…): evento 300301 ou "devolução" na descrição → entra NEGATIVA no TED
    dev_sem_ted = []
    for x in nc_uni:
        x['dev'] = x['ug_fav'] in UGS_SDR and x['ug_emit'] not in UGS_SDR and ted_tesouro.eh_devolucao(x.get('evento'), x.get('evento_nome'), x.get('obs'))
        if x['dev']:
            x['valor'] = -abs(f(x['valor']))
    for x in nc_uni:
        if not x['acao'] and x['ptres'].strip() in ac_orc:   # sem ação no relatório nem no mapa da API: usa a base de orçamento
            x['acao'] = ac_orc[x['ptres'].strip()]
        if x['dev'] and not x['ted']:
            dev_sem_ted.append(x)   # liga depois: pelo processo da descrição ou pela NC de envio (mesma unidade, PTRES, PI e ND)
            continue
        if x['ted']:
            ncT[x['ted']].append([x['nc'], x['data'], x['ug_emit'], x['ug_fav'], f(x['valor']), x['ptres'], x['pi'], x['nd'], x['rp'], 'Tesouro', x.get('evento') or '', x['acao'], x['obs'][:200]])
        elif x['ug_fav'] in UGS_SDR and x['ug_emit'] not in UGS_SDR:
            semTED.append(x)
        if x['ug_emit'] in UGS_SDR:
            acoesSDR.add(x['acao'])
        if not x['ted'] and x['ug_emit'] in UGS_SDR:   # NC da SDR sem nº de TED (dispensa de TED): liga pelo processo escrito na observação
            for pr in re.findall(r'\d{5}\.?\d{6}/?\d{4}-?\d{2}', x['obs'] or ''):
                ncProc[re.sub(r'\D', '', pr)].append([x['nc'], x['data'], x['ug_emit'], x['ug_fav'], f(x['valor']), x['ptres'], x['pi'], x['nd'], x['rp'], 'Tesouro', x.get('evento') or '', x['acao'], x['obs'][:200]])
    # devoluções sem nº de TED: 1º processo citado na descrição · 2º a NC de envio da SDR para a mesma unidade com mesmo PTRES, PI e ND
    envio = collections.defaultdict(set)
    for x in nc_uni:
        if x['ug_emit'] in UGS_SDR and not x['dev']:
            prs = [re.sub(r'\D', '', pr) for pr in re.findall(r'\d{5}\.?\d{6}/?\d{4}-?\d{2}', x['obs'] or '')]
            for dono in ([('ted', x['ted'])] if x['ted'] else []) + [('proc', pr) for pr in prs]:
                envio[(x['ug_fav'], x['ptres'].strip(), x['pi'].strip(), x['nd'].strip())].add(dono)
    n_dev = [0, 0]
    for x in dev_sem_ted:
        lin = [x['nc'], x['data'], x['ug_emit'], x['ug_fav'], f(x['valor']), x['ptres'], x['pi'], x['nd'], x['rp'], 'Devolução', x.get('evento') or '', x['acao'],
               ('devolução · evento ' + (x.get('evento') or '') + ' · ' + (x['obs'] or ''))[:200]]
        prs = [re.sub(r'\D', '', pr) for pr in re.findall(r'\d{5}\.?\d{6}/?\d{4}-?\d{2}', x['obs'] or '')]
        donos = {('proc', pr) for pr in prs} or envio.get((x['ug_emit'], x['ptres'].strip(), x['pi'].strip(), x['nd'].strip()), set())
        if len(donos) == 1 or (donos and len({d[0] for d in donos}) == 2 and len([d for d in donos if d[0] == 'ted']) == 1):
            tp_, v_ = next((d for d in donos if d[0] == 'ted'), next(iter(donos)))
            (ncT if tp_ == 'ted' else ncProc)[v_].append(lin)
            n_dev[0] += 1
        else:
            n_dev[1] += 1
    print(f'NC devolvidas sem nº de TED: {n_dev[0]} ligadas · {n_dev[1]} sem dono certo (ficam fora)', flush=True)
    # crédito recebido em 2026 pela contabilidade (ted_tesouro_nc_conta.csv): destaque recebido entra como NC do TED;
    # provisão recebida (crédito passado de uma UG da SDR para outra, ex.: 130141 → 130255 no 995343) fica numa lista própria
    provT = collections.defaultdict(list)
    for x in ler(tp, 'ted_tesouro_nc_conta.csv'):
        if not x['ted']:
            continue
        if x['tipo'].startswith('Destaque'):
            ncT[x['ted']].append([x['doc'], x['data'], x['ug_emit'], x['ug_fav'], f(x['valor']), x['ptres'], '', '', '', 'Tesouro', 'destaque recebido',
                                  ac_orc.get(x['ptres'].strip(), ''), x['obs'][:200]])
        elif x['tipo'].startswith('Provisão'):
            provT[x['ted']].append([x['doc'], x['data'], x['ug_emit'], x['ug_fav'], f(x['valor']), x['ptres'], x['obs'][:200]])
    pfT = collections.defaultdict(list)
    vistos_pf = set()
    for x in sorted(ler(tp, 'ted_tesouro_pf.csv'), key=lambda x: not x.get('evento')):   # o mesmo documento: fica o que traz o evento
        if (x['doc'], x['ted'], x['valor']) in vistos_pf:   # o mesmo documento vem no TED_PF e no TED_PF_DEV
            continue
        vistos_pf.add((x['doc'], x['ted'], x['valor']))
        dev = x['ug_fav'] in UGS_SDR and x['ug_emit'] not in UGS_SDR and ted_tesouro.eh_devolucao(x.get('evento'), x.get('evento_nome'), x.get('obs'))
        rot = ('Devolução · ' if dev else 'Tesouro · ') + ((x.get('evento') or '') + ' ' + (x.get('evento_nome') or '')).strip() if x.get('evento') else ('Devolução' if dev else 'Tesouro · ' + (x['tipo'] or ''))
        pfT[x['ted']].append([x['doc'], x['data'], x['ug_emit'], x['ug_fav'], -abs(f(x['valor'])) if dev else f(x['valor']), rot, x['obs'][:160],
                              ((x.get('evento') or '') + ' · ' + (x.get('evento_nome') or '')).strip(' ·')])
    usados = set()
    for o in linhas:
        k = ted_tesouro.chave_ted(o['n'])
        t = tes.get(k) if k else None
        if not tes:
            o['org'] = 'Tesouro não carregado'
        elif t:
            usados.add(k)
            o['org'] = 'Tesouro e API'
        else:
            o['org'] = 'Só na API' if o['n'] else 'Plano sem nº (só API)'
        o['tes'] = t
        nt = ncT.get(k, []) if k else []
        # NC emitida por outro órgão para a SDR: num TED recebido é crédito recebido; num TED enviado é devolução (entra negativa)
        if o['er'] != 'Recebido':
            nt = [x[:4] + [-abs(x[4])] + x[5:9] + ['Devolução'] + x[10:] if str(x[2]) not in UGS_SDR and str(x[3]) in UGS_SDR else x for x in nt]
        o['ncT'] = len(nt)
        o['ncTes'] = nt
        o['provs'] = provT.get(k, []) if k else []
        ag = collections.defaultdict(float)
        for x in nt:
            ag[(x[11] or '', x[5] or '', x[6] or '', x[7] or '', x[8] or '')] += x[4]
        o['nca'] = [list(k) + [round(v, 2)] for k, v in sorted(ag.items(), key=lambda kv: -kv[1])][:20]
        pt_ = pfT.get(k, []) if k else []
        # PF de uma UG da SDR para outra UG da SDR é financeiro que a SDR recebeu, não repasse ao parceiro (varredura de 03/11/2026)
        if o['er'] != 'Recebido':
            pt_ = [x for x in pt_ if str(x[3]) not in UGS_SDR or str(x[5]).startswith('Devolução')]
        o['pfTes'] = pt_
        # RP: vale o da NC do Tesouro (pelo PTRES); emenda só aparece em RP 6, 7 ou 8 e sem os códigos zerados da API
        rpT = sorted({str(x[8]) for x in nt if re.fullmatch(r'RP \d', str(x[8] or ''))})
        if rpT:
            o['rpApi'] = o.get('rp', '')
            o['rp'] = ' | '.join(rpT)
        o['emd'] = ' | '.join(e for e in re.split(r'\s*\|\s*', o.get('emd') or '') if e.strip('0 '))
        if o['emd'] and not re.search(r'[678]', o.get('rp') or ''):
            o['emdApi'] = o['emd']
            o['emd'] = ''
        if pt_ and not o['pfs']:
            o['pfs'] = pt_[:40]
        if nt and not o['ncs']:
            o['ncs'] = nt[:40]
            if not o['nc']:
                o['nc'] = round(sum(x[4] for x in nt), 2)
                o['op'] = max(0, round(o['fir'] - o['nc'], 2))
        if nt and o['acao'] == '(sem ação)':
            ac = sorted({x[11] for x in nt if x[11]})
            if ac:
                o['acao'] = ' | '.join(ac)
        # RP: o do SIAFI (relatório de NC do Tesouro) vale mais que o da API; nota sem RP no Tesouro fica com o RP da API
        if nt:
            rpT = {}
            for x in nt:
                if x[8]:
                    rpT.setdefault(x[0], set()).add(x[8])
            rps = set().union(*rpT.values()) if rpT else set()
            for x in o['ncs']:
                if x[0] not in rpT and x[8]:
                    rps.update(r.strip() for r in str(x[8]).split('|') if r.strip())
            if rps:
                o['rp'] = ' | '.join(sorted(rps))
        if t and not o['obj'] and t.get('obj'):
            o['obj'] = t['obj']
        o['dif'] = []
        if t:
            for rot, a_, b_ in (('Descentralizado (NC)', o['nc'], t['nc']), ('Repassado (PF)', o['pf'], t['rep']), ('Valor firmado', o['fir'], t['fir'])):
                if b_ is not None and abs(a_ - b_) > 1:
                    o['dif'].append([rot, a_, b_])
            if o['dif']:
                o['org'] = 'Tesouro e API · valores diferentes'
    for k, t in tes.items():
        if k in usados:
            continue
        linhas.append(dict(id='T' + k, n=k, ano=t['ano'] or '(sem ano)', cod='', er='Enviado' if t['ugE'] in UGS_SDR else ('Recebido' if t['ugF'] in UGS_SDR else ''),
                           ugd=t['ugE'], und='', ugr=t['ugF'], unr=t['nome'] or '(não informada)', orr='(só no Tesouro)', uge=t['ugF'], prog='', acao='(sem ação)',
                           obj=t['obj'], sp='(só no Tesouro)', st=t['sit'] or '(sem termo)', fase='Só no Tesouro', sei=t['proc'], ass='', ini=t['ini'], fim=t['fim'],
                           dias=(lambda f: (datetime.datetime.strptime(f[:10], '%d/%m/%Y').date() - hoje).days if re.match(r'\d{2}/\d{2}/\d{4}', f or '') else None)(t['fim']),
                           fir=t['fir'] or 0, nc=t['nc'] or 0, op=0, pf=t['rep'] or 0, ar=t['aRep'] or 0, rp='', emd='', ult='', link='', ns='',
                           ncs=ncT.get(k, [])[:40], pfs=pfT.get(k, [])[:40], cro=[], prox=None, par=[], met=[], org='Só no Tesouro', tes=t, dif=[], ncT=len(ncT.get(k, []))))
        o = linhas[-1]
        nt = [x[:4] + [-abs(x[4])] + x[5:9] + ['Devolução'] + x[10:] if str(x[2]) not in UGS_SDR and str(x[3]) in UGS_SDR and o['er'] != 'Recebido' else x for x in ncT.get(k, [])]
        o['ncs'] = nt[:40]
        ag = collections.defaultdict(float)
        for x in nt:
            ag[(x[11] or '', x[5] or '', x[6] or '', x[7] or '', x[8] or '')] += x[4]
        o['nca'] = [list(k) + [round(v, 2)] for k, v in sorted(ag.items(), key=lambda kv: -kv[1])][:20]
        if nt:
            o['nc'] = round(sum(x[4] for x in nt), 2)
            ac = sorted({x[11] for x in nt if x[11]})
            o['acao'] = ' | '.join(ac) or o['acao']
            o['rp'] = ' | '.join(sorted({x[8] for x in nt if x[8]}))
            if not o['obj']:
                o['obj'] = nt[0][12]
    # ---- crédito recebido de outro órgão SEM nº de TED (ex.: Ministério da Pesca, ação 21GE): entra como linha própria.
    # NC sem TED numa ação que a própria SDR também descentraliza é devolução de crédito dela, não recebimento: fica de fora.
    gr = collections.defaultdict(list)
    for x in semTED:
        if x['acao'] and x['acao'] not in acoesSDR:
            gr[(x['ug_emit'], x['ug_fav'], x['acao'])].append(x)
    for i, ((ue, uf, ac), L) in enumerate(sorted(gr.items())):
        v = round(sum(f(x['valor']) for x in L), 2)
        if v < 1000:
            continue
        ncs_ = [[x['nc'], x['data'], x['ug_emit'], x['ug_fav'], f(x['valor']), x['ptres'], x['pi'], x['nd'], x['rp'], 'Tesouro', x.get('evento') or '', x['acao'], x['obs'][:200]] for x in L]
        linhas.append(dict(id='R%d' % i, n='', ano=(L[0]['data'] or '')[-4:] or '(sem ano)', cod=', '.join(sorted({x['nc'] for x in L}))[:80], er='Recebido', ugd=ue, und=L[0].get('nome_emit', '') if isinstance(L[0], dict) else '',
                           ugr=uf, unr=UGN_PY.get(uf, uf), orr='(recebido sem nº de TED)', uge=uf, prog='', acao=ac, obj=(L[0]['obs'] or '')[:400], sp='(recebido sem TED)', st='(sem termo)',
                           fase='Recebido sem nº de TED', sei='', ass='', ini='', fim='', dias=None, fir=v, nc=v, op=0.0, pf=0.0, ar=0.0, rp=' | '.join(sorted({x['rp'] for x in L if x['rp']})),
                           emd='', ult='', link='', ns='', ncs=ncs_, pfs=[], cro=[], prox=None, par=[], met=[], org='Recebido sem nº de TED', tes=None, dif=[], ncT=len(L),
                           nca=[[ac, x['ptres'], x['pi'], x['nd'], x['rp'], f(x['valor'])] for x in L][:20], nes=[], neT=[0.0, 0.0, 0.0, 0.0]))
    # ---- empenhos das unidades que receberam o TED (ted/ted_tesouro_ne.csv): liga pela UG favorecida + PTRES das NCs do TED
    dig = lambda v: re.sub(r'\D', '', v or '')
    idx = collections.defaultdict(set)
    # liga só pelo crédito que ficou: NC estornada (líquido zero naquele PTRES) não liga empenho ao TED
    # (ex.: 991573 e 991592 tiveram NC no PTRES 247476 estornada; os empenhos ficavam nos dois)
    piTED, ncIni = collections.defaultdict(set), {}
    def _dt(s):
        try:
            return datetime.datetime.strptime(str(s)[:10], '%d/%m/%Y').date()
        except ValueError:
            return None
    for o in linhas:
        liq_ = collections.defaultdict(float)
        vis = set()
        for x in (o['ncs'] or []) + ncT.get(ted_tesouro.chave_ted(o['n']) or '', []):
            if (x[0], x[4], x[5]) in vis:
                continue
            vis.add((x[0], x[4], x[5]))
            for pt in str(x[5] or '').split('|'):
                if pt.strip() and x[3]:
                    liq_[(str(x[3]).strip(), pt.strip())] += f(x[4]) if not isinstance(x[4], (int, float)) else x[4]
            if x[6]:
                piTED[o['id']].add(str(x[6]).strip().upper())
            d_ = _dt(x[1])
            if d_ and f(x[4] if not isinstance(x[4], (int, float)) else str(x[4])) > 0 and (o['id'] not in ncIni or d_ < ncIni[o['id']]):
                ncIni[o['id']] = d_
        for x in o.get('provs') or []:   # provisão para outra UG da SDR: os empenhos dela nesse PTRES também são deste TED
            liq_[(str(x[3]).strip(), str(x[5]).strip())] += x[4]
        for k, v_ in liq_.items():
            if v_ > 0.005:
                idx[k].add(o['id'])
    porId = {o['id']: o for o in linhas}
    for o in linhas:
        o['nes'], o['neT'] = [], [0.0, 0.0, 0.0, 0.0]
    # pagamentos (OB, DARF, GPS…) de cada empenho: relatório TED OB do Tesouro (etapa 2 · 03/11/2026)
    obIdx = collections.defaultdict(list)
    for x in ler(tp, 'ted_tesouro_ob.csv'):
        obIdx[(x['ug'], x['ne'])].append([x['ob'] or '—', x['data'], x['tipo'], x['fav_nome'] or x['fav'], f(x['valor']), f(x['pago']), round(f(x['rpp']) + f(x['rpnp']), 2), x['ne']])
    for o in linhas:
        o['obs'], o['obT'], o['_obv'] = [], 0.0, set()
    n_lig = n_fora = 0
    todosN = {(o['n'] or '').upper() for o in linhas if o['n']}
    seiTED = {dig(o['sei']): o['id'] for o in linhas if len(dig(o['sei'])) > 10}
    # TED recebido: o crédito pode ser repassado por provisão a outra UG da SDR (ex.: 995343, MIDR → 130141 → 130255, máquinas do PROMAQ).
    # Liga então os empenhos de QUALQUER UG da SDR nas ações do órgão que mandou (ação que não é da SDR).
    ACOES_EXTRA = {'995343': ['1211']}   # ações do TED que a API não lista (destaque recebido do MIDR na 1211, visto na base EXE)
    porAcaoRec = collections.defaultdict(list)
    for o in linhas:
        if o['er'] == 'Recebido':
            acs = {a.strip().upper() for a in re.split(r'[|,]', o['acao'] or '') if re.fullmatch(r'[0-9A-Za-z]{4}', a.strip())}
            acs |= {str(x[0]).upper() for x in o.get('nca') or [] if x[0]} | set(ACOES_EXTRA.get(o['n'], []))
            for a in acs - acoesSDR:
                porAcaoRec[a].append(o['id'])
    for e in ler(tp, 'ted_tesouro_ne.csv'):
        cand = [porId[i] for i in idx.get((e['ug'], e['ptres']), ())]
        if not cand and e['ug'] in UGS_SDR and e.get('acao', '').upper() in porAcaoRec:
            cand = [porId[i] for i in porAcaoRec[e['acao'].upper()]]
        # empenho que cita o nº do TED (ou o processo SEI) na descrição, da UG que recebeu: vale mesmo sem NC ligada
        # (ex.: o relatório de NC do Tesouro ainda sem a NC do ano, ou a NC ligada a outro TED do mesmo PTRES)
        txt0 = (e['desc'] + ' ' + e['processo']).upper()
        # nº do TED citado: vale de qualquer UG do recebedor (ex.: CODEVASF 195007 → 195006, campus de IF), menos as da SDR; processo SEI: só da UG que recebeu
        porTexto = [o for o in linhas if (o['n'] and e['ug'] not in UGS_SDR and o['er'] == 'Enviado' and re.search(r'\b' + re.escape(o['n'].upper()) + r'\b', txt0))
                    or (o.get('ugr') == e['ug'] and len(dig(o['sei'])) > 10 and dig(o['sei']) in dig(txt0))]
        if not cand:
            cand = porTexto
        if not cand:
            continue
        if len(cand) > 1:  # o mesmo UG+PTRES em mais de um TED: tenta pelo nº do TED ou pelo processo citado no empenho
            txt = (e['desc'] + ' ' + e['processo']).upper()
            m = [o for o in cand if (o['n'] and o['n'].upper() in txt) or (dig(o['sei']) and len(dig(o['sei'])) > 10 and dig(o['sei']) in dig(txt))]
            cand = m or cand
        # a descrição do empenho cita OUTRO TED conhecido (pelo nº ou pelo processo SEI de outro TED da lista): não é deste
        dsc = (e['desc'] or '').upper()
        procs = {dig(p_) for p_ in re.findall(r'\d{5}\.\d{6}/\d{4}-\d{2}', dsc)}
        tedsCit = set(re.findall(r'\b(?:[69]\d{5}|[1-9]AA[A-Z0-9]{3})\b', dsc)) & todosN | set(re.findall(r'(?:TED|SIAFI|TRANSFER\w*)\D{0,14}\b([69]\d{5}|[1-9]AA[A-Z0-9]{3})\b', dsc))   # nº citado junto de TED/SIAFI vale mesmo fora da lista
        def outro(o):
            if tedsCit and o['n'] and o['n'].upper() not in tedsCit:
                return True
            outrosSei = procs & seiTED.keys()
            return bool(outrosSei) and dig(o['sei']) not in procs
        cand = [o for o in cand if not outro(o)] or porTexto
        if len(cand) > 1:   # ainda em mais de um TED: o empenho é do TED que já tinha crédito na data da nota e, se der, do mesmo PI
            dne = _dt(e['data'])
            c2 = [o for o in cand if not (dne and ncIni.get(o['id']) and ncIni[o['id']] > dne)]
            cand = c2 or cand
            c3 = [o for o in cand if (e.get('pi') or '').strip().upper() in piTED.get(o['id'], set())]
            if c3 and len(c3) < len(cand):
                cand = c3
        if not cand:
            n_fora += 1
            continue
        comp = len(cand) > 1
        v = [f(e['emp']), f(e['liq']), f(e['pago']), round(f(e['rpp']) + f(e['rpnp']), 2)]
        n_lig += 1
        for o in cand:
            outros = ' / '.join(sorted({x['n'] or x['cod'] or x['id'] for x in cand if x is not o})) if comp else ''
            o['nes'].append([e['ne'], e['data'], e['fav_nome'] or e['fav'], e['ptres'], e['pi'], e['nd'], v[0], v[1], v[2], v[3], e['desc'][:220], 1 if comp else 0, outros])
            if not comp and (e['ug'], e['ne']) not in o['_obv']:
                o['_obv'].add((e['ug'], e['ne']))
                pg_ = obIdx.get((e['ug'], e['ne']), [])
                o['obs'].extend(pg_)
                o['obT'] = round(o['obT'] + sum(x[4] for x in pg_), 2)
            if not comp:
                o['neT'] = [round(a_ + b_, 2) for a_, b_ in zip(o['neT'], v)]
    # PTRES das NCs de TED em execução que o relatório "EMPENHOS TED" (Tesouro Gerencial) não traz: sem eles o painel não acha os empenhos (12/11/2026)
    cobertos = {e['ptres'].strip() for e in ler(tp, 'ted_tesouro_ne.csv') if e.get('ptres')}
    for o in linhas:
        o['ptF'] = sorted({str(x[5]).strip() for x in o.get('ncs') or [] if str(x[5]).strip()} - cobertos) if cobertos and o.get('fase') == 'Em execução' else []
    for o in linhas:
        o['nes'] = sorted(o['nes'], key=lambda x: (x[1][6:10], x[1][3:5], x[1][:2]), reverse=True)[:60]
        o['obs'] = sorted(o.get('obs') or [], key=lambda x: (x[1][6:10], x[1][3:5], x[1][:2]), reverse=True)[:120]
        o.pop('_obv', None)
    print(f'empenhos ligados a TED: {n_lig} · descartados por citar outro instrumento: {n_fora}', flush=True)
    # ---- ajustes da equipe (aba TED ATUALIZADA): valem sobre a API e o Tesouro (a API guarda só a vigência original)
    pdata = lambda v: datetime.datetime.strptime(v[:10], '%d/%m/%Y').date() if re.match(r'\d{2}/\d{2}/\d{4}', v or '') else None
    aj = {x['ted'].upper(): x for x in ler(tp, 'ted_ajustes.csv')}
    # controle interno direto (abas da equipe, 130010/420013): a data como a equipe digitou. Vale antes do Tesouro e da API,
    # e antes do "Fim trazido do controle interno" da BASE TED (que chegava com 1 dia a menos)
    ctlN, ctlP = {}, {}
    for x in ler(tp, 'ted_controle.csv'):
        if not pdata(x.get('fim')):
            continue
        if x.get('ted'):
            ctlN.setdefault(x['ted'].upper(), x)
        dp = re.sub(r'\D', '', x.get('processo') or '')
        if len(dp) > 10:
            ctlP.setdefault(dp, x)
    for o in linhas:
        so_t = o.get('org') == 'Só no Tesouro'
        o['fimApi'] = '' if so_t else o['fim']
        if so_t and o['dias'] is not None and o['dias'] >= 0:
            o['fase'] = 'Em execução'
        a_ = aj.get((o['n'] or o['cod'] or '').upper())
        if not a_:
            continue
        o['aj'] = [a_['fim'], a_['fase'], a_['obs']]
        o['dep'], o['fiscT'], o['fiscS'], o['uf'] = a_.get('dep', ''), a_.get('fiscT', ''), a_.get('fiscS', ''), a_.get('uf', '')
        fa = pdata(a_['fim'])
        if fa:
            o['fim'], o['dias'] = a_['fim'], (fa - hoje).days
            # vigente pelo ajuste: volta para "em execução" mesmo que o Transferegov já tenha aberto a prestação de contas
            if o['dias'] >= 0 and (o['fase'] in ('Vigência vencida', 'Só no Tesouro') or o['st'].startswith('CUMPRIMENTO_OBJETO_INICIADO')):
                o['fase'] = 'Em execução'
            elif o['dias'] < 0 and o['fase'] == 'Em execução':
                o['fase'] = 'Vigência vencida'
        if a_['fase']:
            o['fase'] = a_['fase']
    # ---- ações usadas em cada TED (pelos eventos das NCs da API; TED só no Tesouro: pelas NCs do Tesouro) + nomes da base de orçamento
    nomeA, nomePO, ptPO = {}, {}, {}
    for x in ler(os.path.join(pasta, 'orcamento'), 'orcamento.csv'):
        nomeA.setdefault(x['acao'], x['acao_nome'])
        nomePO.setdefault((x['acao'], x['po']), x['po_nome'])
        if x['ptres']:
            ptPO.setdefault(x['ptres'], (x['acao'], x['po']))
    nota_pa = {x['id_nota']: x['id_plano_acao'] for x in ler(tp, 'ted_notas_credito.csv')}
    acs = collections.defaultdict(lambda: collections.defaultdict(float))
    for e in ler(tp, 'ted_eventos.csv'):
        pa = nota_pa.get(e['id_nota'])
        pg = (e.get('ptres_programa_trabalho') or '').strip()
        if not pa:
            continue
        ac = pg[9:13] if len(pg) >= 13 else ''
        po = (e.get('ptres_plano_orcamentario') or '').strip()
        try:
            nd = json.loads(e.get('natureza_despesa_evento') or '{}').get('codigo_natureza', '')
        except Exception:
            nd = ''
        acs[pa][(ac, po, e.get('cd_ptres_evento', '').strip(), (e.get('ptres_resultado_primario') or '').strip(), nd)] += f(e.get('vl_evento'))
    for o in linhas:
        if o['id'] in acs:
            L_ = acs[o['id']]
        else:
            L_ = collections.defaultdict(float)
            for x in (o['ncs'] if o.get('org') == 'Só no Tesouro' else []):
                ac, po = ptPO.get(x[5], (x[11], ''))
                L_[(x[11] or ac, po, x[5], x[8], x[7])] += x[4]
        o['acs'] = [[ac, nomeA.get(ac, ''), po, nomePO.get((ac, po), ''), pt, rp, nd, round(v, 2)]
                    for (ac, po, pt, rp, nd), v in sorted(L_.items(), key=lambda kv: -kv[1]) if abs(v) > 0.005][:20]
    # ---- controle interno da equipe (colunas EQUIPE da aba TED ATUALIZADA): completa os TEDs e traz os que só existem no controle
    nm = lambda v: ted_tesouro.num(v) or 0.0
    porN = {(o['n'] or o['cod'] or '').upper(): o for o in linhas}
    n_eq = n_so = 0
    for e in ler(tp, 'ted_equipe.csv'):
        G = lambda k: (e.get(k) or '').strip()
        eq = {'aba': G('Aba do controle'), 'ug': G('UG responsável'), 'dep': G('Departamento'), 'ft': G('Fiscal titular'), 'fs': G('Fiscal suplente'), 'uf': G('UF'),
              'rp': G('RP'), 'acao': G('Ação'), 'situ': G('Situação / tratamento'), 'et': G('Etapas da PC (1=feita)'), 'fim': G('Fim (controle)'),
              'firm': nm(G('Firmado / total')), 'aComp': nm(G('A comprovar')), 'comp': nm(G('Comprovado'))}
        o = porN.get(e['ted'].upper())
        if o is None and e.get('origem') == 'Só no controle interno':
            fc = pdata(eq['fim'])
            dias = (fc - hoje).days if fc else None
            fase = {'Dispensa de TED': 'Dispensa de TED', 'Prestação de contas': 'Prestação de contas', 'Aprovado / concluído': 'Concluído'}.get(eq['aba']) or \
                   ('Em execução' if dias is not None and dias >= 0 else 'Vigência vencida')
            n_ = e['ted'] if not e['ted'].startswith('PROC ') else ''
            o = dict(id='C' + str(n_so), n=n_, ano=(eq['fim'][-4:] if eq['fim'] else '(sem ano)'), cod='' if n_ else e['ted'][5:], er='Enviado', ugd=eq['ug'] or '420013', und='',
                     ugr='', unr=G('Unidade') or '(não informada)', orr='(só no controle interno)', uge='', prog='', acao=eq['acao'] or '(sem ação)', obj=G('Objeto'),
                     sp='(só no controle)', st=eq['situ'] or '(sem termo)', fase=fase, sei=G('Processo'), ass='', ini='', fim=eq['fim'], fimApi='', dias=dias,
                     fir=eq['firm'], nc=0.0, op=0.0, pf=0.0, ar=0.0, rp=eq['rp'], emd='', ult='', link='', ns='', ncs=[], pfs=[], cro=[], prox=None, par=[], met=[],
                     org='Só no controle interno', tes=None, dif=[], ncT=0, nca=[], nes=[], neT=[0.0, 0.0, 0.0, 0.0])
            ncp = ncProc.get(re.sub(r'\D', '', G('Processo')), []) if G('Processo') else []
            if ncp:   # dispensa de TED: as NCs que citam o processo na observação
                o['ncs'], o['ncT'], o['nc'] = ncp[:40], len(ncp), round(sum(x[4] for x in ncp), 2)
                ac = sorted({x[11] for x in ncp if x[11]})
                if ac:
                    o['acao'] = ' | '.join(ac)
            linhas.append(o)
            n_so += 1
        if o is None:
            continue
        o['eq'] = eq
        n_eq += 1
    # ---- PRIORIDADE DOS DADOS: orçamento, financeiro e datas vêm do Tesouro (SIAFI) e da planilha da equipe;
    # a API do Transferegov só completa o que não existe nesses dois (os valores dela ficam em o['api'], para comparar)
    pct_ = lambda v: v if isinstance(v, (int, float)) else None
    for o in linhas:
        if o.get('org') in ('Só no Tesouro', 'Só no controle interno', 'Recebido sem nº de TED'):
            o['api'] = None
            continue
        t, e = o.get('tes') or {}, o.get('eq') or {}
        o['api'] = dict(fir=o['fir'], nc=o['nc'], pf=o['pf'], ar=o['ar'], ini=o['ini'], fim=o.get('fimApi') or o['fim'], ano=o['ano'])
        nt, pt_ = o.get('ncTes') or [], o.get('pfTes') or []
        # valor firmado: Tesouro → planilha → API.
        # No SIAFI a supressão (ou o aditivo) não mexe em "valores firmados": zera/aumenta o "a repassar". O valor atual do TED é então
        # a repassar + repassado (a comprovar, comprovado, a aprovar, aprovado/concluído) + devolvido. Ex.: 991352, firmado 10,2 Mi, 7,2 Mi suprimidos.
        o['firFonte'] = 'Tesouro'
        if pct_(t.get('fir')) and t['fir'] > 0:
            o['fir'] = t['fir']
            if t.get('aRep') is not None and t.get('rep') is not None:
                atual = round(t['aRep'] + t['rep'] + (t.get('dev') or 0), 2)
                if atual > 0 and abs(atual - t['fir']) > 1:
                    o['firOrig'], o['ajValor'], o['fir'] = t['fir'], round(atual - t['fir'], 2), atual
        elif e.get('firm'):
            o['fir'], o['firFonte'] = e['firm'], 'controle da equipe'
        elif str(o.get('ano')) == str(hoje.year) and o['fir']:
            o['firFonte'] = 'API · em formalização'   # TED do ano ainda não lançado no SIAFI: o valor da API é o único registro
        else:
            o['fir'], o['firFonte'] = 0.0, 'sem registro no Tesouro'   # ano anterior e nada no SIAFI nem no controle: o valor da API não vale
        # 04/11/2026: valores, NC, PF, PTRES, ação e RP SÓ do Tesouro (contábil). A API do Transferegov está desatualizada:
        # fica só para o cadastro (unidade, objeto, plano de ação, cronograma, metas, pareceres); os números dela ficam em o['api'] só para consulta.
        # descentralizado: NCs do Tesouro (sem repetição, devoluções negativas) → saldo do Tesouro → zero
        if nt:
            o['nc'] = round(sum(x[4] for x in nt), 2)
            o['ncs'] = nt[:40]
            acT = [x[11] for x in sorted(nt, key=lambda x: -x[4]) if x[11]]
            if acT:
                o['acao'] = ' | '.join(dict.fromkeys(acT))
        else:
            o['ncs'] = [x for x in (o.get('ncs') or []) if len(x) > 9 and x[9] in ('Tesouro', 'Devolução')]
            o['nc'] = t['nc'] if pct_(t.get('nc')) is not None else round(sum(x[4] for x in o['ncs']), 2)
        o['ncT'] = len(o['ncs'])
        # RP: só o das NCs do Tesouro; ação sem NC no Tesouro: a do controle da equipe, senão a do cadastro
        rpT = sorted({str(x[8]) for x in o['ncs'] if re.fullmatch(r'RP \d', str(x[8] or ''))})
        o['rp'] = ' | '.join(rpT) or (e.get('rp') or '')
        if not o['ncs'] and e.get('acao'):
            o['acao'] = e['acao']
        if o['emd'] and not re.search(r'[678]', o['rp'] or ''):
            o['emdApi'], o['emd'] = o['emd'], ''
        # repassado: o que já saiu para a unidade no Tesouro (a comprovar + comprovado + a aprovar + aprovado/concluído) → zero
        # (a soma do relatório de PF ainda não é confiável: valores com dígito a mais e devoluções com sinal trocado; as PFs aparecem só na lista)
        o['pfs'] = pt_[:40]
        # sem o saldo do relatório de TED: soma das PFs do Tesouro → a comprovar + comprovado do controle da equipe → zero
        o['pf'] = t['rep'] if pct_(t.get('rep')) is not None else (round(sum(x[4] for x in pt_), 2) if pt_ else round((e.get('aComp') or 0) + (e.get('comp') or 0), 2))
        o['ar'] = t['aRep'] if pct_(t.get('aRep')) is not None else max(0.0, round(o['fir'] - o['pf'], 2))
        o['op'] = max(0.0, round(o['fir'] - o['nc'], 2))
        o['dif'] = []
        if o.get('org') == 'Tesouro e API · valores diferentes':
            o['org'] = 'Tesouro e API'
        # datas: ajuste da equipe → planilha (controle interno) → Tesouro → API
        if t.get('ini'):
            o['ini'] = t['ini']
        if re.fullmatch(r'\d{4}', str(t.get('ano') or '')):
            o['ano'] = t['ano']
        ajL = o.get('aj') or ['', '', '']
        manual = bool(ajL[0]) and not str(ajL[2] or '').startswith('Fim trazido do controle')
        c_ = ctlN.get((o['n'] or o['cod'] or '').upper()) or ctlP.get(re.sub(r'\D', '', o.get('sei') or '')) if (o['n'] or o['cod'] or len(re.sub(r'\D', '', o.get('sei') or '')) > 10) else None
        if c_:
            o['fimCtl'], o['abaCtl'] = c_['fim'], c_['aba']
            if not manual and o.get('aj') and ajL[0]:
                o['aj'][0] = c_['fim']    # mostra na ficha a data do controle, não a cópia com 1 dia a menos
        fimAj = ajL[0] if manual else ''
        fim = next((v for v in (fimAj, o.get('fimCtl'), ajL[0], e.get('fim'), t.get('fim')) if pdata(v)), None)
        if fim and fim != o['fim']:
            o['fim'] = fim
            o['dias'] = (pdata(fim) - hoje).days
            if not (o.get('aj') or ['', ''])[1]:
                if o['dias'] >= 0 and o['fase'] == 'Vigência vencida':
                    o['fase'] = 'Em execução'
                elif o['dias'] < 0 and o['fase'] == 'Em execução':
                    o['fase'] = 'Vigência vencida'
    # TEDs que não passaram pelo bloco acima (só no Tesouro, só no controle interno, dispensas): fim também pelo controle da equipe
    for o in linhas:
        if o.get('org') not in ('Só no Tesouro', 'Só no controle interno', 'Recebido sem nº de TED'):
            continue
        ajL = o.get('aj') or ['', '', '']
        if ajL[0] and not str(ajL[2] or '').startswith('Fim trazido do controle'):
            continue
        k_, dp_ = (o['n'] or o['cod'] or '').upper(), re.sub(r'\D', '', o.get('sei') or '')
        c_ = (ctlN.get(k_) if k_ else None) or (ctlP.get(dp_) if len(dp_) > 10 else None)
        if not c_ or c_['fim'] == o.get('fim'):
            continue
        o['fimCtl'], o['abaCtl'], o['fim'] = c_['fim'], c_['aba'], c_['fim']
        if o.get('aj') and ajL[0]:
            o['aj'][0] = c_['fim']
        o['dias'] = (pdata(c_['fim']) - hoje).days
        if o['fase'] == 'Vigência vencida' and o['dias'] >= 0:
            o['fase'] = 'Em execução'
        elif o['fase'] == 'Em execução' and o['dias'] < 0:
            o['fase'] = 'Vigência vencida'
    for o in linhas:
        # órgão de quem enviou: o da API; sem ele, MAPA quando quem enviou é UG da SDR
        if not o.get('ord'):
            o['ord'] = 'Ministério da Agricultura e Pecuária' if str(o.get('ugd')) in UGS_SDR else '(não informado)'
        e = o.get('eq') or {}
        o['dep'] = (e.get('dep') or '').upper() or '(sem departamento)'
        o['uf'] = (e.get('uf') or '').upper()
        # ação sempre em maiúsculas, sem repetir (20zv e 20ZV eram contadas como ações diferentes); 20VZ é erro de digitação de 20ZV
        ac = []
        for a_ in re.split(r'[|;,/]', o.get('acao') or ''):
            a_ = a_.strip().upper()
            a_ = {'20VZ': '20ZV'}.get(a_, a_)
            if a_ and a_ != '(SEM AÇÃO)' and a_ not in ac:
                ac.append(a_)
        o['acao'] = ' | '.join(ac) or '(sem ação)'
        # ano: TED antigo (só no SIAFI) vem sem ano no relatório; usa o início da vigência ou a 1ª nota de crédito
        if not re.fullmatch(r'\d{4}', str(o.get('ano') or '')):
            anos = [d[-4:] for d in [o.get('ini') or o.get('ass') or ''] + sorted((x[1] for x in o.get('ncs') or [] if x[1]), key=lambda d: d[-4:] + d[3:5] + d[:2])
                    if re.fullmatch(r'\d{2}/\d{2}/\d{4}', d or '')]
            if anos:
                o['ano'], o['anoInf'] = anos[0], True
    print(f'controle interno: {n_eq} TEDs completados, {n_so} só no controle', flush=True)
    tesInfo = {'carregado': bool(tes), 'gerado_em': tes_meta.get('gerado_em', ''), 'teds': len(tes), 'soTesouro': len(tes) - len(usados),
               'erros': [x.get('erro') for x in tes_meta.get('fontes', []) if not x.get('ok')]}
    data = (meta.get('data_api') or {}).get('data_ultima_atualizacao', '').replace('T', ' ')[:16]
    data = (data[8:10] + '/' + data[5:7] + '/' + data[:4] + data[10:]) if data else meta.get('gerado_em', '')
    # ---- BASE TED ATUALIZADA: uma linha por TED (API + Tesouro + NC + PF) para a aba TED ATUALIZADA (o Apps Script copia)
    tt = lambda o, k: '' if not o.get('tes') or o['tes'].get(k) is None else o['tes'][k]
    ap = lambda fn: (lambda o: '' if o.get('org') == 'Só no Tesouro' else fn(o))
    BASE = [('Nº TED', lambda o: o['n'] or o['cod']), ('Ano', lambda o: o['ano']), ('Plano de ação', ap(lambda o: o['cod'])), ('Origem do dado', lambda o: o.get('org', '')),
            ('Enviado / recebido', lambda o: o['er']), ('UG descentralizadora', lambda o: o['ugd']), ('UG descentralizada', lambda o: o['ugr']),
            ('Unidade descentralizada', lambda o: o['unr']), ('Processo', lambda o: o['sei']), ('Objeto', lambda o: (o['obj'] or '')[:500]),
            ('Ação', lambda o: o['acao']), ('Resultado primário', lambda o: o['rp']), ('Situação do termo (API)', ap(lambda o: o['st'])),
            ('Situação no Tesouro', lambda o: tt(o, 'sit')), ('Início da vigência', lambda o: o['ini']), ('Fim da vigência (API)', lambda o: (o.get('api') or {}).get('fim', '')),
            ('Fim da vigência (Tesouro)', lambda o: tt(o, 'fim')), ('Fim da vigência (painel)', lambda o: o['fim']), ('Dias para o fim', lambda o: '' if o['dias'] is None else o['dias']),
            ('Fase (painel)', lambda o: o['fase']), ('Valor firmado (API)', lambda o: (o.get('api') or {}).get('fir', '')), ('Valor firmado (Tesouro)', lambda o: tt(o, 'fir')),
            ('Descentralizado NC (API)', lambda o: (o.get('api') or {}).get('nc', '')), ('NC no Tesouro', lambda o: round(sum(x[4] for x in o['ncs'] if x[9] in ('Tesouro', 'Devolução')), 2) if o.get('ncT') else ''),
            ('Repassado PF (API)', lambda o: (o.get('api') or {}).get('pf', '')), ('Repassado (Tesouro)', lambda o: tt(o, 'rep')), ('A repassar (Tesouro)', lambda o: tt(o, 'aRep')),
            ('A comprovar (Tesouro)', lambda o: tt(o, 'aComp')), ('Comprovado (Tesouro)', lambda o: tt(o, 'comp')),
            ('Empenhado pela unidade (NE)', lambda o: o['neT'][0] if o.get('nes') else ''), ('Pago pela unidade (NE + RP)', lambda o: round(o['neT'][2] + o['neT'][3], 2) if o.get('nes') else ''),
            ('Notas de crédito', lambda o: ' | '.join(sorted({x[0] for x in o['ncs'] if x[0]}))), ('Programações financeiras', lambda o: ' | '.join(sorted({x[0] for x in o['pfs'] if x[0]}))),
            ('Divergências API x Tesouro', lambda o: ' · '.join(f'{r}: API {a_:,.2f} / Tesouro {b_:,.2f}' for r, a_, b_ in o.get('dif', [])))]
    # PF entre UGs da SDR (financeiro recebido pela própria SDR) não é repasse ao parceiro: sai da lista de PF dos TEDs enviados
    for o in linhas:
        if o.get('er') != 'Recebido' and o.get('pfs'):
            o['pfs'] = [x for x in o['pfs'] if str(x[3] if len(x) > 3 else '') not in UGS_SDR or str(x[5] if len(x) > 5 else '').startswith('Devolução')]
    with open(os.path.join(tp, 'ted_base_atualizada.csv'), 'w', encoding='utf-8', newline='') as fh:
        w = csv.writer(fh)
        w.writerow([h for h, _ in BASE])
        for o in sorted(linhas, key=lambda o: (o['fase'] == 'Plano rejeitado', o['ugd'], o['n'] or o['cod'])):
            w.writerow([fn(o) for _, fn in BASE])
    # NC, PF e empenhos de cada TED (pelo nº), para as abas do controle interno no painel (Vigentes, Dispensa, Prestação de contas, Aprovados)
    fic = {}
    for o in linhas:
        k = ted_tesouro.chave_ted(o.get('n'))
        if not k or k in fic:
            continue
        t = o.get('tes') or {}
        fic[k] = dict(fir=o.get('fir') or 0, nc=o.get('nc') or 0, pf=o.get('pf') or 0, ar=o.get('ar') or 0, neT=o.get('neT') or [0, 0, 0, 0],
                      tes={c: t.get(c) for c in ('fir', 'nc', 'rep', 'aRep', 'aComp', 'comp')} if t else None,
                      ncs=o.get('ncs') or [], provs=o.get('provs') or [], pfs=o.get('pfs') or [], nes=o.get('nes') or [], obs=o.get('obs') or [], obT=o.get('obT') or 0, nca=o.get('nca') or [], acao=o.get('acao', ''), fase=o.get('fase', ''), firOrig=o.get('firOrig'), ajValor=o.get('ajValor'), ugd=o.get('ugd', ''), ptF=o.get('ptF') or [])
    with open(os.path.join(tp, 'ted_ficha.json'), 'w', encoding='utf-8') as fh:
        json.dump(fic, fh, ensure_ascii=False, separators=(',', ':'))
    print(f'ted/ted_ficha.json · {len(fic)} TEDs', flush=True)
    with open(os.path.join(pasta, 'pagina_ted.html'), 'w', encoding='utf-8') as fh:
        fh.write(montar('ted.html', {'linhas': linhas, 'ano': hoje.year, 'tes': tesInfo}, data))
    print(f'pagina_ted.html · {len(linhas)} planos de ação', flush=True)



def orcamento_pag(pasta):
    """Página Orçamento por ação (Tesouro Gerencial · aba ORCAMENTO, lida pelo orcamento.py em PASTA/orcamento)."""
    L = ler(os.path.join(pasta, 'orcamento'), 'orcamento.csv')
    if not L:
        print('página de orçamento: sem orcamento/orcamento.csv', flush=True)
        return
    meta = {}
    try:
        meta = json.load(open(os.path.join(pasta, 'orcamento', 'orcamento.json'), encoding='utf-8'))
    except Exception:
        pass
    M = ['ini', 'sup', 'canc', 'atu', 'indisp', 'provConc', 'provRec', 'destConc', 'disp', 'emp', 'liq', 'pago']
    linhas = [[r['ug'], r['acao'], r['acao_nome'][:70], r['po'], r['po_nome'][:70], r['ptres'], r['gnd'], r['rp']] + [f(r.get(k)) for k in M] for r in L]
    with open(os.path.join(pasta, 'pagina_orcamento.html'), 'w', encoding='utf-8') as fh:
        fh.write(montar('orcamento.html', {'linhas': linhas}, meta.get('gerado_em', '')))
    print(f'pagina_orcamento.html · {len(linhas)} linhas', flush=True)


if __name__ == '__main__':
    main(sys.argv[1] if len(sys.argv) > 1 else 'saida')
