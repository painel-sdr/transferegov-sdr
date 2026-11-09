/**
 * PAINEL DE EXECUÇÃO FINANCEIRA — base e API · versão 2 (TESTE)
 *
 * ATUALIZAR A PARTIR DA VERSÃO 1 (uma vez):
 *  1. Apps Script da planilha BASE EXECUÇÃO 2027 › apague tudo e cole este arquivo › Salvar.
 *  2. Escolha a função  reiniciarTeste  e clique em Executar (autorize se pedir).
 *     Ela recria as abas no formato novo, mantém USUARIOS e SESSOES e coloca dados de TESTE.
 *  3. Escolha  carregarTesouro  e Executar: lê os CSVs da aba FONTES (EXE e, quando tiver, RAP).
 *  4. Implantar › Gerenciar implantações › lápis (editar) › Versão: "Nova versão" › Implantar.
 *     (Assim o link /exec continua o mesmo.)
 *  5. Opcional: Acionadores › Adicionar › rotinaDiaria › baseado no tempo › diário (6h–7h).
 *
 * ABAS
 *  CONFIG        ano do exercício
 *  FONTES        links dos CSVs publicados do Tesouro (EXE/RAP) — ficam só aqui, não vão para a página
 *  USUARIOS      email · nome · perfil (ADMIN | ORCAMENTO | EXECUTOR) · ativo
 *  INSTRUMENTOS  cadastro (contrato, ata, parceria, TED, suprimento…) com o processo raiz
 *  PREVISAO      previsão de gasto por competência do ano (gerada pela parcela e vigência; editável)
 *  PAGAMENTOS    cada processo de pagamento: demanda → saldo → distribuição → informado → conferido
 *  DDO           autorizações do ano (controle interno, não afeta Tesouro)
 *  TESOURO_NE    uma linha por NE, lida dos CSVs (empenhado, liquidado, pago, saldo)
 *  HISTORICO     quem fez o quê
 */

const ABAS = {
  CONFIG: ['chave', 'valor', 'nota'],
  FONTES: ['nome', 'tipo', 'url', 'ativo'],
  USUARIOS: ['email', 'nome', 'perfil', 'ativo'],
  INSTRUMENTOS: ['id', 'formalizacao', 'orcamento', 'ug', 'sigla', 'atividade', 'natureza', 'numero', 'instrumento', 'proposta',
    'processo_raiz', 'favorecido', 'cnpj', 'modalidade', 'objeto', 'vigencia_ini', 'vigencia_fim', 'prorrogacao_prevista',
    'valor_global', 'valor_parcela', 'executado_anteriores', 'nes', 'regiao', 'uf', 'origem', 'criado_em', 'criado_por', 'alterado_em', 'alterado_por', 'justificativa'],
  PREVISAO: ['instrumento_id', 'competencia', 'valor', 'alterado_por', 'alterado_em'],
  PAGAMENTOS: ['id', 'instrumento_id', 'competencia', 'processo_pagamento', 'area_demandante', 'valor', 'ne', 'recurso', 'fonte',
    'obs_orcamento', 'orcamento_por', 'orcamento_em', 'situacao', 'executor', 'distribuido_por', 'distribuido_em',
    'obs', 'informado_por', 'informado_em', 'conferido_em'],
  DDO: ['id', 'instrumento_id', 'data', 'processo', 'valor', 'situacao', 'ne', 'objeto', 'periodo', 'por', 'em'],
  TESOURO_NE: ['ne', 'tipo', 'ug', 'processo', 'favorecido', 'acao', 'fonte', 'pi', 'nd', 'desc_nd', 'empenhado', 'liquidado', 'em_liquidacao', 'pago', 'saldo', 'base_liquidado', 'carga', 'origem'],
  HISTORICO: ['quando', 'email', 'acao', 'ref', 'detalhe'],
  SESSOES: ['token', 'email', 'exp']
};
const SIT = { REFORCO: 'REFORCO', SALDO_OK: 'SALDO_OK', DISTRIBUIDO: 'DISTRIBUIDO', INFORMADO: 'INFORMADO', CONFIRMADO: 'CONFIRMADO', AJUSTAR: 'AJUSTAR' };
const UGS = ['130010', '420013', '130141', '130255', '135098'];
const NOME_UG = { '130010': 'CEPLAC', '420013': 'SDR', '130141': 'SDR · CGPI', '130255': 'SDR · PROMAQ', '135098': 'SDR · CGPI (repasse)' };

/* =========================== INSTALAÇÃO =========================== */

function instalar() {
  const ss = SpreadsheetApp.getActive();
  Object.keys(ABAS).forEach(n => {
    const sh = ss.getSheetByName(n) || ss.insertSheet(n);
    const cab = ABAS[n];
    sh.getRange(1, 1, 1, cab.length).setValues([cab]).setFontWeight('bold').setBackground('#155a30').setFontColor('#ffffff');
    sh.setFrozenRows(1);
  });
  ['COMPETENCIAS', 'NES', 'TESOURO_OB', 'Página1', 'Sheet1'].forEach(n => { const s = ss.getSheetByName(n); if (s && ss.getSheets().length > 1) ss.deleteSheet(s); });
  if (!lerTudo('CONFIG').length) anexar('CONFIG', { chave: 'ANO', valor: 2027, nota: 'exercício: competências dez/(ANO-1) a dez/ANO' });
  if (!lerTudo('FONTES').length) {
    anexar('FONTES', { nome: 'EXE Padrão', tipo: 'EXE', ativo: 'SIM', url: 'https://docs.google.com/spreadsheets/d/e/2PACX-1vRFcFQpuXUjut17Ftj89ugQvu-eK-ZPI7a90FoPOnhcvXFSL2ymU-WOPiYwBT8qa8tzCeyo05q_YanW/pub?gid=1204904051&single=true&output=csv' });
    anexar('FONTES', { nome: 'EXE MDIR', tipo: 'EXE', ativo: 'SIM', url: 'https://docs.google.com/spreadsheets/d/e/2PACX-1vRFcFQpuXUjut17Ftj89ugQvu-eK-ZPI7a90FoPOnhcvXFSL2ymU-WOPiYwBT8qa8tzCeyo05q_YanW/pub?gid=32904262&single=true&output=csv' });
    anexar('FONTES', { nome: 'RAP', tipo: 'RAP', ativo: 'NÃO', url: '(cole aqui o link CSV publicado do RAP e mude ativo para SIM)' });
  }
  const eu = Session.getEffectiveUser().getEmail();
  if (!lerTudo('USUARIOS').some(u => igual(u.email, eu))) anexar('USUARIOS', { email: eu, nome: 'David (coordenador)', perfil: 'ADMIN', ativo: 'SIM' });
  toast('Abas prontas. ADMIN: ' + eu);
}

/** Apaga os dados de teste (mantém USUARIOS, SESSOES, CONFIG e FONTES) e recria tudo no formato da versão 2. */
function reiniciarTeste() {
  const ss = SpreadsheetApp.getActive();
  ['INSTRUMENTOS', 'PREVISAO', 'PAGAMENTOS', 'DDO', 'TESOURO_NE', 'HISTORICO', 'COMPETENCIAS', 'NES', 'TESOURO_OB'].forEach(n => { const s = ss.getSheetByName(n); if (s) ss.deleteSheet(s); });
  instalar();
  carregarTeste();
  toast('Base de teste recriada. Agora rode carregarTesouro.');
}

function carregarTeste() {
  const A = ano(), agora_ = agora();
  const inst = [
    { id: 'T1', formalizacao: 'Contrato', orcamento: 'CEPLAC', ug: '130010', sigla: 'VIGILÂNCIA', atividade: 'Funcionamento', natureza: '33903703', numero: '00/2025', processo_raiz: '21000.000001/2025-00', favorecido: '[TESTE] EMPRESA DE VIGILÂNCIA', cnpj: '00.000.000/0001-00', modalidade: 'Pregão', objeto: 'Vigilância patrimonial armada e desarmada', vigencia_ini: '2025-05-14', vigencia_fim: A + '-05-13', prorrogacao_prevista: 'SIM', valor_global: 2332674, valor_parcela: 97194.75, executado_anteriores: 1652310.75, nes: (A) + 'NE900010,' + (A - 1) + 'NE900195', regiao: 'Centro-Oeste', uf: 'DF' },
    { id: 'T2', formalizacao: 'Contrato', orcamento: 'CEPLAC', ug: '130010', sigla: 'ENERGIA', atividade: 'Funcionamento', natureza: '33903943', numero: '00/2017', processo_raiz: '21000.000002/2017-00', favorecido: '[TESTE] DISTRIBUIDORA DE ENERGIA', cnpj: '00.000.000/0002-00', modalidade: 'Inexigibilidade', objeto: 'Fornecimento de energia elétrica', vigencia_ini: '2017-01-01', vigencia_fim: '2099-12-31', prorrogacao_prevista: 'NÃO', valor_global: 78000, valor_parcela: 6500, executado_anteriores: 0, nes: A + 'NE900020', regiao: 'Nordeste', uf: 'BA' },
    { id: 'T3', formalizacao: 'Ata', orcamento: 'CEPLAC', ug: '130010', sigla: 'ÁGUA MINERAL', atividade: 'Funcionamento', natureza: '33903007', numero: 'ATA 02/2025', processo_raiz: '21000.000003/2025-00', favorecido: '[TESTE] FORNECEDOR ATA', cnpj: '00.000.000/0003-00', modalidade: 'Pregão SRP', objeto: 'Água mineral em galão de 20 L', vigencia_ini: '2025-03-01', vigencia_fim: A + '-03-01', prorrogacao_prevista: 'NÃO', valor_global: 94752, valor_parcela: 7896, executado_anteriores: 63168, nes: (A - 1) + 'NE900058', regiao: 'Norte', uf: 'PA' },
    { id: 'T4', formalizacao: 'Termo de fomento', orcamento: 'DECAP', ug: '420013', sigla: 'TF ASSOCIAÇÃO', atividade: 'Outras Despesas', natureza: '33504101', numero: '', instrumento: '900001/2026', proposta: '000001/2026', processo_raiz: '21000.000004/2026-00', favorecido: '[TESTE] ASSOCIAÇÃO', cnpj: '00.000.000/0004-00', modalidade: 'Chamamento público', objeto: 'Apoio à agricultura familiar', vigencia_ini: (A - 1) + '-06-01', vigencia_fim: A + '-12-31', prorrogacao_prevista: 'NÃO', valor_global: 570000, valor_parcela: 0, executado_anteriores: 190000, nes: (A - 1) + 'NE900071', regiao: 'Nordeste', uf: 'PE' }
  ];
  inst.forEach(i => { i.origem = 'TESTE'; i.criado_em = agora_; i.criado_por = 'teste'; anexar('INSTRUMENTOS', i); gerarPrevisao(i, 'teste'); });
  // parceria: previsão pelas parcelas do cronograma
  salvarPrevisaoLinha('T4', A + '-03', 190000, 'teste'); salvarPrevisaoLinha('T4', A + '-09', 190000, 'teste');
  [
    { ne: A + 'NE900010', tipo: 'EXE', ug: '130010', processo: '21000.000001/2025-00', favorecido: '[TESTE] EMPRESA DE VIGILÂNCIA', acao: '20ZY', fonte: '1000000000', pi: 'ADMCEPLAC', nd: '33903703', desc_nd: 'VIGILÂNCIA', empenhado: 900000, liquidado: 0, em_liquidacao: 0, pago: 0, saldo: 900000 },
    { ne: (A - 1) + 'NE900195', tipo: 'RAP', ug: '130010', processo: '21000.000001/2025-00', favorecido: '[TESTE] EMPRESA DE VIGILÂNCIA', acao: '20ZY', fonte: '1000000000', pi: 'ADMCEPLAC', nd: '33903703', desc_nd: 'VIGILÂNCIA', empenhado: 194389.5, liquidado: 0, em_liquidacao: 0, pago: 0, saldo: 194389.5 },
    { ne: A + 'NE900020', tipo: 'EXE', ug: '130010', processo: '21000.000002/2017-00', favorecido: '[TESTE] DISTRIBUIDORA DE ENERGIA', acao: '20ZY', fonte: '1000000000', pi: 'ADMCEPLAC', nd: '33903943', desc_nd: 'ENERGIA ELÉTRICA', empenhado: 52000, liquidado: 0, em_liquidacao: 0, pago: 0, saldo: 52000 },
    { ne: (A - 1) + 'NE900058', tipo: 'RAP', ug: '130010', processo: '21000.000003/2025-00', favorecido: '[TESTE] FORNECEDOR ATA', acao: '2000', fonte: '1000000000', pi: 'ADMCEPLAC', nd: '33903007', desc_nd: 'GÊNEROS DE ALIMENTAÇÃO', empenhado: 23688, liquidado: 0, em_liquidacao: 0, pago: 0, saldo: 23688 },
    { ne: (A - 1) + 'NE900071', tipo: 'RAP', ug: '420013', processo: '21000.000004/2026-00', favorecido: '[TESTE] ASSOCIAÇÃO', acao: '215A', fonte: '1000000000', pi: 'SDR', nd: '33504101', desc_nd: 'CONTRIBUIÇÕES', empenhado: 380000, liquidado: 0, em_liquidacao: 0, pago: 0, saldo: 380000 }
  ].forEach(t => { t.base_liquidado = 0; t.carga = agora_; t.origem = 'TESTE'; anexar('TESOURO_NE', t); });
}

/* ====================== PREVISÃO DO ANO ====================== */

function competenciasDoAno() {
  const A = ano(), out = [(A - 1) + '-12'];
  for (let m = 1; m <= 12; m++) out.push(A + '-' + (m < 10 ? '0' : '') + m);
  return out;
}
/** Previsão = valor da parcela em cada competência do ano dentro da vigência (até dezembro se prorrogação prevista). */
function gerarPrevisao(i, por) {
  const parcela = num(i.valor_parcela);
  if (!parcela) return;
  const ini = String(i.vigencia_ini).slice(0, 7);
  const fim = String(i.prorrogacao_prevista).toUpperCase() === 'SIM' ? '9999-12' : String(i.vigencia_fim).slice(0, 7);
  const ja = {}; lerTudo('PREVISAO').filter(p => p.instrumento_id === i.id).forEach(p => ja[p.competencia] = 1);
  competenciasDoAno().forEach(c => { if (c >= ini && c <= fim && !ja[c]) anexar('PREVISAO', { instrumento_id: i.id, competencia: c, valor: parcela, alterado_por: por, alterado_em: agora() }); });
}
function salvarPrevisaoLinha(id, comp, valor, por) {
  const s = sh('PREVISAO'), v = s.getDataRange().getValues();
  for (let r = 1; r < v.length; r++) if (v[r][0] === id && String(v[r][1]) === comp) { s.getRange(r + 1, 3, 1, 3).setValues([[valor, por, agora()]]); return; }
  anexar('PREVISAO', { instrumento_id: id, competencia: comp, valor: valor, alterado_por: por, alterado_em: agora() });
}

/* ====================== TESOURO (CSV publicados) ====================== */

/** Lê os CSVs ativos da aba FONTES e regrava TESOURO_NE (mantém a base_liquidado de cada NE e as linhas de TESTE). */
function carregarTesouro() {
  const fontes = lerTudo('FONTES').filter(f => String(f.ativo).toUpperCase() === 'SIM' && /^https?:/.test(f.url));
  const antes = {}; lerTudo('TESOURO_NE').forEach(t => antes[t.ne + '|' + t.ug] = t);
  const porNe = {}, log = [];
  fontes.forEach(f => {
    try {
      const txt = UrlFetchApp.fetch(f.url, { muteHttpExceptions: true, followRedirects: true }).getContentText('UTF-8');
      const n = lerRelatorioTesouro(txt, String(f.tipo || 'EXE').toUpperCase(), porNe);
      log.push(f.nome + ': ' + n + ' linhas');
    } catch (e) { log.push(f.nome + ': ERRO ' + e.message); }
  });
  const agora_ = agora(), linhas = [];
  Object.keys(porNe).forEach(k => {
    const t = porNe[k];
    if (UGS.indexOf(t.ug) < 0) return;
    const a = antes[k];
    t.base_liquidado = a ? num(a.base_liquidado) : t.liquidado;   // primeira vez que a NE aparece: o que já estava liquidado não entra na conferência
    t.carga = agora_; t.origem = 'TESOURO';
    linhas.push(t);
  });
  Object.keys(antes).forEach(k => { if (antes[k].origem === 'TESTE' && !porNe[k]) linhas.push(antes[k]); });
  const s = sh('TESOURO_NE');
  if (s.getLastRow() > 1) s.getRange(2, 1, s.getLastRow() - 1, s.getLastColumn()).clearContent();
  if (linhas.length) s.getRange(2, 1, linhas.length, ABAS.TESOURO_NE.length).setValues(linhas.map(o => ABAS.TESOURO_NE.map(c => o[c] === undefined ? '' : o[c])));
  setConfig('ULTIMA_CARGA', agora_ + ' · ' + log.join(' · '));
  toast('Tesouro: ' + log.join(' · '));
  return { ok: true, log: log, nes: linhas.length };
}

/** Mesmo leitor do painel-financeiro-mapa: acha o cabeçalho "NE CCor", junta cabeçalho duplo e soma por NE + UG. */
function lerRelatorioTesouro(txt, tipo, porNe) {
  const linhas = Utilities.parseCsv(txt);
  const idxH = linhas.findIndex(l => l.some(c => normalizar(c).indexOf('NE CCOR') >= 0));
  if (idxH < 0) return 0;
  const cab1 = linhas[idxH].map(c => String(c || '').trim()), cab2 = (linhas[idxH + 1] || []).map(c => String(c || '').trim());
  const duplo = cab2.some(c => /EMPENHAD|LIQUIDAD|PAGA|PAGO|INSCRIT/.test(normalizar(c)));
  const cab = cab1.map((c, i) => {
    if (duplo && cab2[i] && !c) return cab2[i];
    if (duplo && cab2[i] && c !== cab2[i] && normalizar(cab2[i]).indexOf('NE') < 0) return c + ' ' + cab2[i];
    return c || 'COL_' + i;
  });
  const vistos = {};
  cab.forEach((c, i) => { vistos[c] = (vistos[c] || 0) + 1; if (vistos[c] > 1) cab[i] = c + ' #' + vistos[c]; });   // colunas repetidas (código / descrição)
  let n = 0;
  for (let i = duplo ? idxH + 2 : idxH + 1; i < linhas.length; i++) {
    const o = {}; cab.forEach((c, j) => o[c] = linhas[i][j]);
    const d = extrairLinha(o, tipo);
    if (!d.ne || /^'?-[89]$/.test(d.ne)) continue;
    const mNe = String(d.ne).toUpperCase().match(/(\d{4}NE\d{6})$/);   // 130010000012026NE000010 → 2026NE000010
    if (mNe) { if (!d.ug) d.ug = String(d.ne).slice(0, 6); d.ne = mNe[1]; }
    const k = d.ne + '|' + d.ug;
    const t = porNe[k] || (porNe[k] = { ne: d.ne, tipo: tipo, ug: d.ug, processo: d.proc, favorecido: d.fav, acao: d.acao, fonte: d.fonte, pi: d.pi, nd: d.nd, desc_nd: d.descNd, empenhado: 0, liquidado: 0, em_liquidacao: 0, pago: 0, saldo: 0 });
    ['empenhado', 'liquidado', 'em_liquidacao', 'pago', 'saldo'].forEach(c => t[c] += d[c]);
    ['processo', 'favorecido', 'acao', 'fonte', 'pi', 'nd', 'desc_nd'].forEach(c => { const m = { processo: 'proc', favorecido: 'fav', desc_nd: 'descNd' }[c] || c; if (!t[c] && d[m]) t[c] = d[m]; });
    n++;
  }
  return n;
}
function extrairLinha(row, tipo) {
  const d = { ne: '', proc: '', ug: '', acao: '', fonte: '', pi: '', nd: '', descNd: '', fav: '', empenhado: 0, liquidado: 0, em_liquidacao: 0, pago: 0, saldo: 0 };
  let aLiquidar = 0;
  Object.keys(row).forEach(k => {
    const kn = normalizar(k), val = row[k];
    if (val === undefined || val === null || String(val).trim() === '' || /^'?-[89]$/.test(String(val).trim())) return;
    const s = String(val).trim();
    if ((kn === 'NE CCOR' || kn === 'NOTA DE EMPENHO' || /NE CCOR$/.test(kn)) && !d.ne) d.ne = s;
    else if (kn.indexOf('PROCESSO') >= 0) d.proc = s;
    else if ((kn.indexOf('UG') >= 0 || kn.indexOf('UNIDADE GESTORA') >= 0) && !d.ug) { const m = s.match(/\d{6}/); d.ug = m ? m[0] : s; }
    else if (kn.indexOf('ACAO GOVERNO') >= 0 || kn === 'ACAO') d.acao = s;
    else if (kn.indexOf('FONTE RECURSOS') >= 0 || kn === 'FONTE') d.fonte = s;
    else if (kn.indexOf('PLANO INTERNO') >= 0 || kn.indexOf('PLANO ORCAMENTARIO') >= 0 || kn === 'PO') d.pi = s;
    else if (kn.indexOf('NATUREZA DESPESA DETALHADA') >= 0 || kn.indexOf('ND DETALHADA') >= 0) { if (!d.nd) d.nd = s; else if (!d.descNd) d.descNd = s; }
    else if (kn === 'NATUREZA DESPESA' && !d.descNd) d.descNd = s;
    else if (kn.indexOf('FAVORECIDO') >= 0) { if (!d.fav || /\d{8,}/.test(d.fav)) d.fav = d.fav ? d.fav + ' ' + s : s; }
    const v = num(val);
    if (!v) return;
    if (kn.indexOf('A LIQUIDAR') >= 0 || kn.indexOf('SALDO EMPENHO') >= 0) aLiquidar += v;
    else if (kn.indexOf('EM LIQUIDACAO') >= 0) d.em_liquidacao += v;
    else if (kn.indexOf('EMPENHADAS') >= 0 || kn.indexOf('EMPENHADO') >= 0 || kn.indexOf('INSCRITOS') >= 0) d.empenhado += v;
    else if (kn.indexOf('LIQUIDAD') >= 0 && (tipo === 'RAP' || kn.indexOf('PAGAR') < 0)) d.liquidado += v;
    else if (kn.indexOf('PAGAS') >= 0 || kn.indexOf('PAGOS') >= 0 || kn.indexOf('PAGO') >= 0) d.pago += v;
    else if (tipo === 'RAP' && kn.indexOf('A PAGAR') >= 0) aLiquidar += v;
  });
  d.saldo = aLiquidar > 0 ? aLiquidar : Math.max(0, d.empenhado - (d.liquidado || d.pago));
  d.fav = mascarar(d.fav);
  return d;
}

/* ====================== CONTRAPROVA (pelo liquidado) ====================== */
/**
 * Para cada NE: movimento = liquidado no Tesouro − base_liquidado (o que já estava liquidado quando a NE entrou na base).
 * Os pagamentos informados naquela NE são confirmados em ordem de data enquanto couberem no movimento.
 * O que não couber fica INFORMADO; depois de 2 dias vira AJUSTAR. Nada é substituído.
 */
function conferir(u) {
  if (u && u.perfil !== 'ADMIN') return { ok: false, msg: 'Só o coordenador roda a conferência.' };
  const tes = {}; lerTudo('TESOURO_NE').forEach(t => { const k = t.ne + '|' + t.ug; tes[k] = (tes[k] || 0) + num(t.liquidado) - num(t.base_liquidado); });
  const ugDe = {}; lerTudo('INSTRUMENTOS').forEach(i => ugDe[i.id] = String(i.ug));
  const pags = lerTudo('PAGAMENTOS').filter(p => [SIT.INFORMADO, SIT.CONFIRMADO, SIT.AJUSTAR].indexOf(p.situacao) >= 0);
  const porNe = {}; pags.forEach(p => { const k = p.ne + '|' + ugDe[p.instrumento_id]; (porNe[k] = porNe[k] || []).push(p); });
  let conf = 0, aj = 0;
  Object.keys(porNe).forEach(ne => {
    let resta = (tes[ne] || 0) + 1;   // tolerância de R$ 1
    porNe[ne].sort((a, b) => String(a.informado_em).localeCompare(String(b.informado_em))).forEach(p => {
      const v = num(p.valor);
      let nova;
      if (v <= resta) { resta -= v; nova = SIT.CONFIRMADO; }
      else nova = (Date.now() - new Date(p.informado_em).getTime()) > 2 * 86400000 ? SIT.AJUSTAR : SIT.INFORMADO;
      if (nova !== p.situacao) { atualizar('PAGAMENTOS', p.id, { situacao: nova, conferido_em: agora() }); hist(u || { email: 'robô' }, nova === SIT.CONFIRMADO ? 'confirmado pelo Tesouro' : (nova === SIT.AJUSTAR ? 'ajustar: liquidado não encontrado' : 'voltou a aguardar'), p.id, ne.split('|')[0]); }
      if (nova === SIT.CONFIRMADO) conf++; if (nova === SIT.AJUSTAR) aj++;
    });
  });
  setConfig('ULTIMA_CONFERENCIA', agora());
  return { ok: true, confirmados: conf, ajustar: aj };
}
function rotinaDiaria() { carregarTesouro(); conferir(null); }

/** Só para TESTE: soma no liquidado das NEs de teste o que foi informado e ainda não confirmado (simula a carga do Tesouro do dia seguinte). */
function simularLiquidacao(u) {
  if (u.perfil !== 'ADMIN') return { ok: false, msg: 'Só o coordenador.' };
  const s = sh('TESOURO_NE'), v = s.getDataRange().getValues(), cab = v[0];
  const iNe = cab.indexOf('ne'), iLiq = cab.indexOf('liquidado'), iSaldo = cab.indexOf('saldo'), iOrig = cab.indexOf('origem');
  const soma = {}; lerTudo('PAGAMENTOS').filter(p => p.situacao === SIT.INFORMADO).forEach(p => soma[p.ne] = (soma[p.ne] || 0) + num(p.valor));
  let n = 0;
  for (let r = 1; r < v.length; r++) {
    if (v[r][iOrig] !== 'TESTE' || !soma[v[r][iNe]]) continue;
    s.getRange(r + 1, iLiq + 1).setValue(num(v[r][iLiq]) + soma[v[r][iNe]]);
    s.getRange(r + 1, iSaldo + 1).setValue(Math.max(0, num(v[r][iSaldo]) - soma[v[r][iNe]])); n++;
  }
  const c = conferir(u); c.msg = 'Simulado em ' + n + ' NE(s) de teste.'; return c;
}

/* =========================== API (painel) =========================== */

function doGet() { return json({ ok: true, servico: 'execucao', versao: 2, hora: new Date().toISOString() }); }

function doPost(e) {
  const lock = LockService.getScriptLock();
  try {
    const p = JSON.parse(e.postData.contents || '{}');
    if (p.acao === 'codigo') return json(pedirCodigo(p));
    if (p.acao === 'entrar') return json(entrar(p));
    const u = usuarioDoToken(p.token);
    if (!u) return json({ ok: false, sessao: false, msg: 'Sessão expirada. Entre de novo.' });
    if (p.acao === 'dados') return json(dados(u));
    lock.waitLock(25000);
    const acoes = { instrumento: salvarInstrumento, previsao: salvarPrevisao, demanda: registrarDemanda, distribuir: distribuir, pago: informarPago, repetir: repetirProcesso, desfazer: desfazer, ddo: salvarDdo, conferir: conferir, simular: simularLiquidacao, tesouro: (uu) => uu.perfil === 'ADMIN' ? Object.assign(carregarTesouro(), conferir(uu)) : { ok: false, msg: 'Só o coordenador.' } };
    const f = acoes[p.acao];
    const r = f ? f(u, p) : { ok: false, msg: 'Ação desconhecida.' };
    SpreadsheetApp.flush();
    return json(r);
  } catch (err) {
    return json({ ok: false, msg: 'Erro: ' + err.message });
  } finally { try { lock.releaseLock(); } catch (x) {} }
}

/* ---- acesso por código no e-mail ---- */
function pedirCodigo(p) {
  const email = String(p.email || '').trim().toLowerCase();
  const u = lerTudo('USUARIOS').find(x => igual(x.email, email) && String(x.ativo).toUpperCase() !== 'NÃO');
  if (!u) return { ok: false, msg: 'Este e-mail não está cadastrado no painel de execução. Peça ao coordenador.' };
  const cod = String(Math.floor(100000 + Math.random() * 900000));
  CacheService.getScriptCache().put('cod_' + email, cod, 600);
  MailApp.sendEmail({ to: email, subject: 'Código de acesso — Painel de Execução: ' + cod, htmlBody: '<p>Seu código para entrar no Painel de Execução Financeira é:</p><p style="font-size:28px;font-weight:bold;letter-spacing:6px">' + cod + '</p><p>Vale por 10 minutos.</p>' });
  return { ok: true };
}
function entrar(p) {
  const email = String(p.email || '').trim().toLowerCase(), c = CacheService.getScriptCache(), cod = c.get('cod_' + email);
  if (!cod) return { ok: false, msg: 'Código vencido. Peça um novo.' };
  if (String(p.codigo) !== cod) return { ok: false, msg: 'Código incorreto.' };
  c.remove('cod_' + email);
  const token = Utilities.getUuid(), exp = Date.now() + (p.lembrar ? 30 : 1) * 86400000;
  anexar('SESSOES', { token: token, email: email, exp: exp });
  return { ok: true, token: token, exp: exp };
}
function usuarioDoToken(token) {
  if (!token) return null;
  const s = lerTudo('SESSOES').find(x => x.token === token && num(x.exp) > Date.now());
  if (!s) return null;
  const u = lerTudo('USUARIOS').find(x => igual(x.email, s.email) && String(x.ativo).toUpperCase() !== 'NÃO');
  return u ? { email: String(u.email).toLowerCase(), nome: u.nome || u.email, perfil: String(u.perfil || 'EXECUTOR').toUpperCase() } : null;
}

/* ---- leitura ---- */
function nesDoInstrumento(i, tes) {
  const lista = String(i.nes || '').split(/[,;\s]+/).filter(Boolean).map(x => x.toUpperCase());
  const raiz = String(i.processo_raiz || '').replace(/\D/g, '');
  return tes.filter(t => (!i.ug || String(t.ug) === String(i.ug)) && (lista.indexOf(String(t.ne).toUpperCase()) >= 0 || (raiz && String(t.processo).replace(/\D/g, '') === raiz))).map(t => t.ne);
}
function dados(u) {
  const tes = lerTudo('TESOURO_NE');
  let inst = lerTudo('INSTRUMENTOS'), pags = lerTudo('PAGAMENTOS');
  inst.forEach(i => { i.nes_vinculadas = nesDoInstrumento(i, tes); i.cnpj = mascarar(i.cnpj); });
  if (u.perfil === 'EXECUTOR') {
    pags = pags.filter(p => igual(p.executor, u.email));
    const ids = {}; pags.forEach(p => ids[p.instrumento_id] = 1);
    inst = inst.filter(i => ids[i.id]);
  }
  const usadas = {}; inst.forEach(i => i.nes_vinculadas.forEach(n => usadas[n] = 1));
  const equipe = lerTudo('USUARIOS').filter(x => String(x.ativo).toUpperCase() !== 'NÃO' && /EXECUTOR|ADMIN/i.test(x.perfil)).map(x => ({ email: String(x.email).toLowerCase(), nome: x.nome || x.email }));
  return {
    ok: true, eu: u, ano: ano(), competencias: competenciasDoAno(), nomeUg: NOME_UG,
    instrumentos: inst, previsao: lerTudo('PREVISAO'), pagamentos: pags, ddo: u.perfil === 'EXECUTOR' ? [] : lerTudo('DDO'),
    tesouro: u.perfil === 'EXECUTOR' ? tes.filter(t => usadas[t.ne]) : tes,
    equipe: equipe, carga: getConfig('ULTIMA_CARGA'), conferencia: getConfig('ULTIMA_CONFERENCIA'), agora: agora()
  };
}

/* ---- ações ---- */
function podeCadastrar(u) { return /ADMIN|ORCAMENTO/.test(u.perfil); }
function salvarInstrumento(u, p) {
  if (!podeCadastrar(u)) return { ok: false, msg: 'Só o Orçamento ou o coordenador cadastram.' };
  const d = p.dados || {};
  if (!d.processo_raiz || !d.ug || !d.formalizacao) return { ok: false, msg: 'Preencha ao menos formalização, UG e processo raiz.' };
  const campos = ABAS.INSTRUMENTOS.filter(c => ['id', 'origem', 'criado_em', 'criado_por', 'alterado_em', 'alterado_por', 'justificativa'].indexOf(c) < 0);
  const o = {}; campos.forEach(c => { if (d[c] !== undefined) o[c] = d[c]; });
  ['valor_global', 'valor_parcela', 'executado_anteriores'].forEach(c => { if (o[c] !== undefined) o[c] = num(o[c]); });
  if (d.id) {
    if (!String(p.justificativa || '').trim()) return { ok: false, msg: 'Informe a justificativa da alteração.' };
    const atual = lerTudo('INSTRUMENTOS').find(i => i.id === d.id);
    if (!atual) return { ok: false, msg: 'Instrumento não encontrado.' };
    if (String(o.cnpj || '').indexOf('*') >= 0) delete o.cnpj;   // veio mascarado da tela: não sobrescreve
    Object.assign(o, { alterado_em: agora(), alterado_por: u.email, justificativa: p.justificativa });
    atualizar('INSTRUMENTOS', d.id, o);
    hist(u, 'instrumento alterado', d.id, p.justificativa);
    if (p.regerar) gerarPrevisao(Object.assign(atual, o), u.email);
    return { ok: true, id: d.id };
  }
  const dup = lerTudo('INSTRUMENTOS').find(i => String(i.processo_raiz).replace(/\D/g, '') === String(o.processo_raiz).replace(/\D/g, '') && String(i.numero || '') === String(o.numero || '') && String(i.ug) === String(o.ug));
  if (dup) return { ok: false, msg: 'Já existe instrumento com este processo raiz e número nesta UG.' };
  o.id = 'I' + Date.now().toString(36).toUpperCase(); o.origem = 'PAINEL'; o.criado_em = agora(); o.criado_por = u.email;
  anexar('INSTRUMENTOS', o);
  gerarPrevisao(o, u.email);
  hist(u, 'instrumento cadastrado', o.id, o.processo_raiz);
  return { ok: true, id: o.id };
}
function salvarPrevisao(u, p) {
  if (!podeCadastrar(u)) return { ok: false, msg: 'Só o Orçamento ou o coordenador ajustam a previsão.' };
  (p.itens || []).forEach(it => salvarPrevisaoLinha(p.instrumento_id, it.competencia, num(it.valor), u.email));
  hist(u, 'previsão ajustada', p.instrumento_id, (p.itens || []).length + ' competência(s)');
  return { ok: true };
}
function registrarDemanda(u, p) {
  if (!podeCadastrar(u)) return { ok: false, msg: 'Só o Orçamento ou o coordenador registram demanda.' };
  const i = lerTudo('INSTRUMENTOS').find(x => x.id === p.instrumento_id);
  if (!i) return { ok: false, msg: 'Instrumento não encontrado.' };
  if (!p.processo) return { ok: false, msg: 'Informe o processo SEI do pagamento.' };
  if (!p.competencia) return { ok: false, msg: 'Informe a competência.' };
  const t = lerTudo('TESOURO_NE').find(x => x.ne === p.ne && String(x.ug) === String(i.ug));
  if (!t) return { ok: false, msg: 'Escolha a NE (da mesma UG do instrumento).' };
  const o = { instrumento_id: i.id, competencia: p.competencia, processo_pagamento: p.processo, area_demandante: p.area || '', valor: num(p.valor), ne: t.ne, recurso: t.tipo === 'RAP' ? 'RAP001' : 'EXE001', fonte: t.fonte, obs_orcamento: p.obs || '', orcamento_por: u.email, orcamento_em: agora(), situacao: p.saldoOk ? SIT.SALDO_OK : SIT.REFORCO };
  if (p.id) { atualizar('PAGAMENTOS', p.id, o); hist(u, p.saldoOk ? 'saldo confirmado' : 'reforço de NE', p.id, p.processo); return { ok: true }; }
  o.id = 'P' + Date.now().toString(36).toUpperCase();
  anexar('PAGAMENTOS', o);
  hist(u, p.saldoOk ? 'demanda · saldo confirmado' : 'demanda · reforço de NE', o.id, p.processo + ' · ' + t.ne);
  return { ok: true };
}
function distribuir(u, p) {
  if (u.perfil !== 'ADMIN') return { ok: false, msg: 'Só o coordenador e o chefe de divisão distribuem.' };
  let n = 0;
  (p.itens || []).forEach(it => {
    const c = lerTudo('PAGAMENTOS').find(x => x.id === it.id);
    if (!c || !it.executor || [SIT.SALDO_OK, SIT.DISTRIBUIDO].indexOf(c.situacao) < 0) return;
    atualizar('PAGAMENTOS', c.id, { executor: it.executor, distribuido_por: u.email, distribuido_em: agora(), situacao: SIT.DISTRIBUIDO });
    hist(u, 'distribuído', c.id, it.executor); n++;
  });
  return { ok: true, n: n };
}
function informarPago(u, p) {
  const c = lerTudo('PAGAMENTOS').find(x => x.id === p.id);
  if (!c) return { ok: false, msg: 'Pagamento não encontrado.' };
  if (u.perfil !== 'ADMIN' && !igual(c.executor, u.email)) return { ok: false, msg: 'Este item não está na sua fila.' };
  if ([SIT.DISTRIBUIDO, SIT.AJUSTAR].indexOf(c.situacao) < 0) return { ok: false, msg: 'Este item não está a pagar.' };
  if (!p.processo) return { ok: false, msg: 'Informe o processo SEI do pagamento.' };
  if (!(num(p.valor) > 0)) return { ok: false, msg: 'Informe o valor liquidado (bruto).' };
  if (!/^(EXE001|RAP001)$/.test(p.recurso || '')) return { ok: false, msg: 'Escolha EXE001 ou RAP001.' };
  atualizar('PAGAMENTOS', c.id, { processo_pagamento: p.processo, valor: num(p.valor), recurso: p.recurso, competencia: p.competencia || c.competencia, obs: p.obs || '', informado_por: u.email, informado_em: agora(), situacao: SIT.INFORMADO });
  hist(u, 'informado pago', c.id, p.processo + ' · ' + num(p.valor) + ' · ' + p.recurso + (p.obs ? ' · ' + p.obs : ''));
  return { ok: true };
}
/** Despesa eventual ou mais de um pagamento no mesmo processo: cria outro lançamento igual, já na fila do mesmo executor. */
function repetirProcesso(u, p) {
  const c = lerTudo('PAGAMENTOS').find(x => x.id === p.id);
  if (!c) return { ok: false, msg: 'Pagamento não encontrado.' };
  if (u.perfil !== 'ADMIN' && !igual(c.executor, u.email)) return { ok: false, msg: 'Este item não está na sua fila.' };
  const o = Object.assign({}, c, { id: 'P' + Date.now().toString(36).toUpperCase(), competencia: p.competencia || c.competencia, valor: 0, obs: '', informado_por: '', informado_em: '', conferido_em: '', situacao: SIT.DISTRIBUIDO, distribuido_por: u.email, distribuido_em: agora() });
  anexar('PAGAMENTOS', o);
  hist(u, 'novo pagamento no mesmo processo', o.id, c.processo_pagamento);
  return { ok: true };
}
function desfazer(u, p) {
  const c = lerTudo('PAGAMENTOS').find(x => x.id === p.id);
  if (!c) return { ok: false, msg: 'Pagamento não encontrado.' };
  if (u.perfil !== 'ADMIN' && !igual(c.informado_por, u.email)) return { ok: false, msg: 'Só quem informou pode desfazer.' };
  if ([SIT.INFORMADO, SIT.AJUSTAR].indexOf(c.situacao) < 0) return { ok: false, msg: 'Só dá para desfazer o que ainda não foi confirmado.' };
  atualizar('PAGAMENTOS', c.id, { informado_por: '', informado_em: '', situacao: SIT.DISTRIBUIDO });
  hist(u, 'desfeito', c.id, '');
  return { ok: true };
}
function salvarDdo(u, p) {
  if (!podeCadastrar(u)) return { ok: false, msg: 'Só o Orçamento ou o coordenador registram DDO.' };
  if (p.excluir) { excluirLinha('DDO', p.excluir); hist(u, 'DDO excluída', p.excluir, ''); return { ok: true }; }
  const d = p.dados || {};
  if (!d.instrumento_id || !d.processo || !(num(d.valor) > 0)) return { ok: false, msg: 'Informe instrumento, processo e valor.' };
  const o = { id: 'D' + Date.now().toString(36).toUpperCase(), instrumento_id: d.instrumento_id, data: d.data || agora().slice(0, 10), processo: d.processo, valor: num(d.valor), situacao: d.situacao || 'A empenhar', ne: d.ne || '', objeto: d.objeto || '', periodo: d.periodo || '', por: u.email, em: agora() };
  anexar('DDO', o); hist(u, 'DDO registrada', o.id, d.processo);
  return { ok: true };
}

/* =========================== utilitários =========================== */
function sh(n) { return SpreadsheetApp.getActive().getSheetByName(n); }
function lerTudo(n) {
  const s = sh(n); if (!s || s.getLastRow() < 2) return [];
  const v = s.getRange(1, 1, s.getLastRow(), s.getLastColumn()).getValues(), cab = v.shift();
  return v.filter(r => r.join('') !== '').map(r => { const o = {}; cab.forEach((c, i) => o[c] = r[i] instanceof Date ? Utilities.formatDate(r[i], 'America/Sao_Paulo', "yyyy-MM-dd'T'HH:mm:ss") : r[i]); return o; });
}
function anexar(n, o) { sh(n).appendRow(ABAS[n].map(c => o[c] === undefined ? '' : o[c])); }
function atualizar(n, id, campos) {
  const s = sh(n), v = s.getDataRange().getValues(), cab = v[0];
  for (let r = 1; r < v.length; r++) {
    if (v[r][0] !== id) continue;
    Object.keys(campos).forEach(k => { const c = cab.indexOf(k); if (c >= 0) s.getRange(r + 1, c + 1).setValue(campos[k]); });
    return true;
  }
  return false;
}
function excluirLinha(n, id) { const s = sh(n), v = s.getDataRange().getValues(); for (let r = 1; r < v.length; r++) if (v[r][0] === id) { s.deleteRow(r + 1); return; } }
function hist(u, acao, ref, det) { anexar('HISTORICO', { quando: agora(), email: u.email, acao: acao, ref: ref, detalhe: det }); }
function getConfig(k) { const c = lerTudo('CONFIG').find(x => x.chave === k); return c ? c.valor : ''; }
function setConfig(k, v) { if (!atualizar('CONFIG', k, { valor: v })) anexar('CONFIG', { chave: k, valor: v }); }
function ano() { return Number(getConfig('ANO')) || 2027; }
function agora() { return Utilities.formatDate(new Date(), 'America/Sao_Paulo', "yyyy-MM-dd'T'HH:mm:ss"); }
function igual(a, b) { return String(a || '').trim().toLowerCase() === String(b || '').trim().toLowerCase(); }
function normalizar(s) { return String(s || '').normalize('NFD').replace(/[̀-ͯ]/g, '').toUpperCase().replace(/\s+/g, ' ').trim(); }
function num(v) {
  if (typeof v === 'number') return v;
  let s = String(v || '').trim().replace(/R\$|\s/g, '');
  if (!s || s === '-') return 0;
  const neg = /^\(.*\)$/.test(s); s = s.replace(/[()]/g, '');
  if (s.indexOf(',') >= 0) s = s.replace(/\./g, '').replace(',', '.');
  const n = parseFloat(s); return isNaN(n) ? 0 : (neg ? -n : n);
}
/** LGPD: CPF aparece ***.452.881-**; CNPJ fica como está. */
function mascarar(s) { return String(s || '').replace(/(^|\D)(\d{3})\.?(\d{3})\.?(\d{3})-?(\d{2})(?!\d)/g, (m, a, b, c, d) => a + '***.' + c + '.' + d + '-**'); }
function json(o) { return ContentService.createTextOutput(JSON.stringify(o)).setMimeType(ContentService.MimeType.JSON); }
function toast(t) { try { SpreadsheetApp.getActive().toast(t, 'Execução', 8); } catch (e) {} }
