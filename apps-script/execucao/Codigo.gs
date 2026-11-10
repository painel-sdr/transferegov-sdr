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
 *  5. Opcional: Acionadores › Adicionar › rotinaDiaria › baseado no tempo › diário (8h–9h, depois do robô do GitHub).
 *
 * CADASTRO AUTOMÁTICO (importarCadastro): o robô do GitHub gera todo dia, na branch "dados",
 *  execucao_instrumentos.csv (contratos vigentes da API Contratos, parcerias com parcela prevista no ano, TED enviados
 *  em execução) e execucao_previsao.csv. A importação atualiza só os campos que vêm das bases; o que foi ajustado no
 *  painel (orçamento, sigla, atividade, natureza, previsão, anos anteriores, NEs acrescentadas) fica. Quem sai da
 *  lista vira ENCERRADO (não é apagado: pode ter pagamentos). Contrato vencido só entra se a NE tiver saldo no Tesouro.
 *
 * ABAS
 *  CONFIG        ano do exercício
 *  FONTES        links dos CSVs publicados do Tesouro (EXE/RAP) — ficam só aqui, não vão para a página
 *  USUARIOS      email · nome · perfil (ADMIN | CHEFE_ORCAMENTO | ORCAMENTO | EXECUTOR) · ativo
 *                ADMIN = coordenador e chefe de divisão financeiro (distribuem o pagamento); CHEFE_ORCAMENTO = responsável
 *                do orçamento (registra a chegada do processo e distribui ao analista); ORCAMENTO = analista do orçamento
 *                (NE e saldo); EXECUTOR = equipe financeira (paga e informa).
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
    'valor_global', 'valor_parcela', 'executado_anteriores', 'nes', 'regiao', 'uf', 'origem', 'criado_em', 'criado_por', 'alterado_em', 'alterado_por', 'justificativa',
    'chave', 'situacao_cadastro', 'sincronizado_em', 'acao', 'base_previsao', 'a_desembolsar'],
  PREVISAO: ['instrumento_id', 'competencia', 'valor', 'alterado_por', 'alterado_em'],
  PAGAMENTOS: ['id', 'instrumento_id', 'competencia', 'processo_pagamento', 'area_demandante', 'valor', 'ne', 'recurso', 'fonte',
    'obs_orcamento', 'orcamento_por', 'orcamento_em', 'situacao', 'executor', 'distribuido_por', 'distribuido_em',
    'obs', 'informado_por', 'informado_em', 'conferido_em',
    'analista', 'recebido_por', 'recebido_em', 'dist_orc_por', 'dist_orc_em', 'devolvido_por', 'devolvido_em', 'motivo_devolucao'],
  DDO: ['id', 'instrumento_id', 'data', 'processo', 'valor', 'situacao', 'ne', 'objeto', 'periodo', 'por', 'em'],
  TESOURO_NE: ['ne', 'tipo', 'ug', 'processo', 'favorecido', 'acao', 'fonte', 'pi', 'nd', 'desc_nd', 'empenhado', 'liquidado', 'em_liquidacao', 'pago', 'saldo', 'base_liquidado', 'carga', 'origem'],
  HISTORICO: ['quando', 'email', 'acao', 'ref', 'detalhe'],
  SESSOES: ['token', 'email', 'exp']
};
const SIT = { RECEBIDO: 'RECEBIDO', NO_ORCAMENTO: 'NO_ORCAMENTO', DEVOLVIDO: 'DEVOLVIDO', REFORCO: 'REFORCO', SALDO_OK: 'SALDO_OK', DISTRIBUIDO: 'DISTRIBUIDO', INFORMADO: 'INFORMADO', CONFIRMADO: 'CONFIRMADO', AJUSTAR: 'AJUSTAR' };
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
  garantirCabecalhos();
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
  limparCacheTesouro();
}

/* ====================== PREVISÃO DO ANO ====================== */

function competenciasDoAno() {
  const A = ano(), out = [(A - 1) + '-12'];
  for (let m = 1; m <= 12; m++) out.push(A + '-' + (m < 10 ? '0' : '') + m);
  return out;
}
/** Previsão = valor da parcela em cada competência do ano dentro da vigência (até dezembro se prorrogação prevista). */
/** Ata, compra sem parcela, contrato de repasse, convênio e termos: o valor do ano fica todo em julho (se pagar antes, o executor ajusta).
 *  Parcerias: o a desembolsar (inclusive parcela atrasada), limitado ao saldo das NEs. Ata e compra: o saldo das NEs. */
const MES_UNICO_RE = /^(ata|contrato de repasse|conv[eê]nio|termo de fomento|termo de colabora)/i;
function previsaoMesUnico(i) { return MES_UNICO_RE.test(String(i.formalizacao || '')) || /^compra/i.test(String(i.base_previsao || '')); }
function mesUnico() { return ano() + '-07'; }
const PARCERIA_RE = /^(contrato de repasse|conv[eê]nio|termo de fomento|termo de colabora)/i;
function saldoDasNes(nes, ug) { const sd = {}; tesouroEmCache().forEach(t => { const k = t.ne + '|' + t.ug; sd[k] = (sd[k] || 0) + num(t.saldo); }); return String(nes || '').split(/[,;\s]+/).filter(Boolean).reduce((a, ne) => a + (sd[ne + '|' + ug] || 0), 0); }
function gerarPrevisao(i, por) {
  const ja = {}; lerTudo('PREVISAO').filter(p => p.instrumento_id === i.id).forEach(p => ja[p.competencia] = 1);
  if (previsaoMesUnico(i)) {
    if (Object.keys(ja).length) return;   // já tem previsão: não mexe
    const sd = saldoDasNes(i.nes, i.ug), v = num(i.valor_parcela) || (PARCERIA_RE.test(String(i.formalizacao || '')) ? Math.min(num(i.a_desembolsar) || num(i.valor_global), sd || num(i.valor_global)) : sd) || num(i.valor_global);
    if (v) anexarVarios('PREVISAO', [{ instrumento_id: i.id, competencia: mesUnico(), valor: v, alterado_por: por, alterado_em: agora() }]);
    return;
  }
  const parcela = num(i.valor_parcela);
  if (!parcela) return;
  const ini = String(i.vigencia_ini || '').slice(0, 7);   // sem início: o ano todo
  const fimTxt = String(i.vigencia_fim || '').slice(0, 7);
  const fim = String(i.prorrogacao_prevista).toUpperCase() === 'SIM' || !fimTxt ? '9999-12' : fimTxt;   // sem fim (ex.: diárias e passagens): até dezembro
  const quando = agora(), novas = competenciasDoAno().filter(c => c >= ini && c <= fim && !ja[c]).map(c => ({ instrumento_id: i.id, competencia: c, valor: parcela, alterado_por: por, alterado_em: quando }));
  anexarVarios('PREVISAO', novas);
}
function salvarPrevisaoLinha(id, comp, valor, por) {
  const s = sh('PREVISAO'), v = s.getDataRange().getValues();
  for (let r = 1; r < v.length; r++) if (v[r][0] === id && compStr(v[r][1]) === comp) { s.getRange(r + 1, 3, 1, 3).setValues([[valor, por, agora()]]); return; }
  anexar('PREVISAO', { instrumento_id: id, competencia: comp, valor: valor, alterado_por: por, alterado_em: agora() });
}

/* ====================== TESOURO (CSV publicados) ====================== */

/** Lê os CSVs ativos da aba FONTES e regrava TESOURO_NE (mantém a base_liquidado de cada NE e as linhas de TESTE). */
/** Mesmas abas de RAP do Painel SDR (planilha "BASE GERENCIAL RAP 2026", compartilhada por link). OUTRAS AÇÕES por último. */
const RAP_PLANILHA = '1cPRChDP0KU0rfjgGij4hC2hz76auQ4a_rxL-XXFqrWQ';
const RAP_ABAS = [['1255285299', 'RAP - 20ZV'], ['1626303078', 'RAP - 20ZY'], ['1251866406', 'RAP - 2000'], ['2071147261', 'RAP 215A'], ['296590604', 'RAP - 8593'],
  ['557514819', 'RAP - 214Z'], ['1888642019', 'RAP - 00PN'], ['1039014086', 'RAP - 8622'], ['238112304', 'RAP - 21B6'], ['1419215442', 'RAP - 8606'], ['240279963', 'RAP - 2161'], ['132081842', 'RAP - OUTRAS AÇÕES']];
/** Se a aba FONTES ainda não tem RAP ativo, troca a linha-modelo pelas abas do Painel SDR. */
function configurarRap() {
  const f = lerTudo('FONTES');
  if (f.some(x => String(x.tipo).toUpperCase() === 'RAP' && String(x.ativo).toUpperCase() === 'SIM' && /^https?:/.test(x.url))) return false;
  const s = sh('FONTES'), v = s.getDataRange().getValues(), cab = v[0], iT = cab.indexOf('tipo'), iU = cab.indexOf('url');
  const fica = v.slice(1).filter(r => r.join('') !== '' && !(String(r[iT]).toUpperCase() === 'RAP' && !/^https?:/.test(String(r[iU]))));
  if (v.length > 1) s.getRange(2, 1, v.length - 1, cab.length).clearContent();
  if (fica.length) s.getRange(2, 1, fica.length, cab.length).setValues(fica);
  anexarVarios('FONTES', RAP_ABAS.map(a => ({ nome: a[1], tipo: 'RAP', ativo: 'SIM', url: 'https://docs.google.com/spreadsheets/d/' + RAP_PLANILHA + '/export?format=csv&gid=' + a[0] })));
  return true;
}
function carregarTesouro() {
  try { configurarRap(); } catch (e) { }
  const fontes = lerTudo('FONTES').filter(f => String(f.ativo).toUpperCase() === 'SIM' && /^https?:/.test(f.url));
  const antes = {}; lerTudo('TESOURO_NE').forEach(t => antes[t.ne + '|' + t.ug] = t);
  const porNe = {}, log = [];
  fontes.forEach(f => {
    try {
      let r = UrlFetchApp.fetch(f.url, { muteHttpExceptions: true, followRedirects: true });   // planilha compartilhada por link: baixa sem login
      if (r.getResponseCode() !== 200 || /<html/i.test(r.getContentText().slice(0, 300))) r = UrlFetchApp.fetch(f.url, { muteHttpExceptions: true, followRedirects: true, headers: { Authorization: 'Bearer ' + ScriptApp.getOAuthToken() } });
      if (r.getResponseCode() !== 200) throw new Error('HTTP ' + r.getResponseCode());
      const txt = r.getContentText('UTF-8'), tipo = String(f.tipo || 'EXE').toUpperCase();
      const n = tipo === 'RAP' ? lerRapMensal(txt, porNe) : lerRelatorioTesouro(txt, tipo, porNe);
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
  limparCacheTesouro();
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
/**
 * RAP do Tesouro Gerencial por mês de lançamento (como a base do Painel SDR): cada NE tem uma linha por mês, com a posição acumulada.
 * Fica só o último mês de cada NE + UG. Liquidado (para a contraprova) = não processados liquidados + processados pagos no ano:
 * o processado já veio liquidado do ano anterior, então o que mexe nele em 2027 é o pagamento.
 * Uma NE que já veio de uma aba anterior não é somada de novo (a aba OUTRAS AÇÕES só completa).
 */
function lerRapMensal(txt, porNe) {
  const L = Utilities.parseCsv(txt);
  const hi = L.findIndex(l => l.some(c => normalizar(c) === 'NE CCOR' || /(^| )NE CCOR$/.test(normalizar(c))));
  if (hi < 0) return 0;
  let H = L[hi].map(c => normalizar(c));
  const prox = (L[hi + 1] || []).map(c => normalizar(c)), duplo = prox.some(c => /INSCRIT|PAGO|LIQUIDAD|A PAGAR/.test(c));
  if (duplo) H = H.map((c, i) => prox[i] && c !== prox[i] ? (c ? c + ' ' + prox[i] : prox[i]) : c);
  const ach = (f) => H.findIndex(f), tem = t => h => h.indexOf(t) >= 0;
  const np = t => ach(h => h.indexOf('NAO PROCESSADOS ' + t) >= 0);
  const pr = t => ach(h => h.indexOf('PROCESSADOS ' + t) >= 0 && h.indexOf('NAO PROCESSADOS') < 0);
  const ix = { ano: ach(tem('ANO LANCAMENTO')), mes: ach(tem('MES LANCAMENTO')), ug: ach(tem('UG EXECUTORA')), acao: ach(tem('ACAO GOVERNO')), pi: ach(h => h === 'PI' || h.indexOf('PLANO INTERNO') >= 0),
    fonte: ach(tem('FONTE RECURSOS')), nd: ach(h => h.indexOf('ND DETALHADA') >= 0 || h.indexOf('NATUREZA DESPESA DETALHADA') >= 0), fav: (function () { const f = H.indexOf('FORNECEDOR'); if (f >= 0) return f; const i = H.findIndex(h => h.indexOf('FAVORECIDO') >= 0); return i >= 0 && H[i + 1] === '' ? i + 1 : i; })(),
    ne: ach(h => h === 'NE CCOR' || /(^| )NE CCOR$/.test(h)), proc: ach(tem('PROCESSO')),
    pI: pr('INSCRITOS'), pR: pr('REINSCRITOS'), pC: pr('CANCELADOS'), pP: pr('PAGOS'), pAP: pr('A PAGAR'),
    nI: np('INSCRITOS'), nR: np('REINSCRITOS'), nC: np('CANCELADOS'), nL: np('LIQUIDADOS'), nP: np('PAGOS'), nAP: np('A PAGAR') };
  const g = (r, i) => i < 0 ? '' : String(r[i] || '').trim(), n = (r, i) => i < 0 ? 0 : num(r[i]);
  const ult = {}, linhas = [];
  for (let i = hi + (duplo ? 2 : 1); i < L.length; i++) {
    const r = L[i], m = g(r, ix.ne).toUpperCase().match(/(\d{4}NE\d{6})/); if (!m) continue;
    const ugM = g(r, ix.ug).match(/\d{6}/), ug = ugM ? ugM[0] : (g(r, ix.ne).match(/^\d{6}/) || [''])[0];
    const mesTxt = normalizar(g(r, ix.mes)), MES = ['JAN', 'FEV', 'MAR', 'ABR', 'MAI', 'JUN', 'JUL', 'AGO', 'SET', 'OUT', 'NOV', 'DEZ'];
    const mes = parseInt(mesTxt, 10) || (MES.indexOf(mesTxt.slice(0, 3)) + 1), rank = (parseInt(g(r, ix.ano), 10) || 0) * 100 + (mes > 0 ? mes : 0);
    const k = m[1] + '|' + ug;
    linhas.push({ k: k, ne: m[1], ug: ug, rank: rank, r: r });
    if (!(k in ult) || rank > ult[k]) ult[k] = rank;
  }
  const novos = {}; let cont = 0;
  linhas.forEach(x => {
    if (x.rank !== ult[x.k]) return;
    if (porNe[x.k] && !novos[x.k]) return;   // já veio de outra aba
    const r = x.r, insc = n(r, ix.pI) + n(r, ix.pR) + n(r, ix.nI) + n(r, ix.nR), canc = n(r, ix.pC) + n(r, ix.nC), pago = n(r, ix.pP) + n(r, ix.nP);
    const saldo = (ix.pAP >= 0 || ix.nAP >= 0) ? n(r, ix.pAP) + n(r, ix.nAP) : insc - canc - pago;
    const t = porNe[x.k] || (porNe[x.k] = novos[x.k] = { ne: x.ne, tipo: 'RAP', ug: x.ug, processo: g(r, ix.proc), favorecido: mascarar(g(r, ix.fav)), acao: g(r, ix.acao), fonte: g(r, ix.fonte), pi: g(r, ix.pi),
      nd: g(r, ix.nd), desc_nd: ix.nd >= 0 ? g(r, ix.nd + 1) : '', empenhado: 0, liquidado: 0, em_liquidacao: 0, pago: 0, saldo: 0 });
    t.empenhado += insc - canc; t.liquidado += n(r, ix.nL) + n(r, ix.pP); t.pago += pago; t.saldo += Math.max(0, saldo);
    ['processo', 'acao', 'fonte', 'pi', 'nd'].forEach(c => { if (!t[c]) t[c] = g(r, ix[{ processo: 'proc' }[c] || c]); });
    if (!t.favorecido) t.favorecido = mascarar(g(r, ix.fav));
    cont++;
  });
  return cont;
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
  const tes = {}; tesouroEmCache().forEach(t => { const k = t.ne + '|' + t.ug; tes[k] = (tes[k] || 0) + num(t.liquidado) - num(t.base_liquidado); });
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
function rotinaDiaria() { carregarTesouro(); try { importarCadastro(null); } catch (e) { setConfig('ULTIMA_IMPORTACAO', agora() + ' · ERRO ' + e.message); } conferir(null); }

/* ====================== CADASTRO AUTOMÁTICO (robô do GitHub) ====================== */
const BASE_DADOS = 'https://raw.githubusercontent.com/painel-sdr/transferegov-sdr/dados/';
function baixarCsv(nome) {
  const r = UrlFetchApp.fetch(BASE_DADOS + nome + '?t=' + Date.now(), { muteHttpExceptions: true });
  if (r.getResponseCode() !== 200) throw new Error(nome + ': HTTP ' + r.getResponseCode());
  const l = Utilities.parseCsv(r.getContentText('UTF-8')), cab = l.shift();
  return l.filter(x => x.join('') !== '').map(x => { const o = {}; cab.forEach((c, i) => o[c] = x[i]); return o; });
}
/** Acrescenta no fim do cabeçalho as colunas novas (versões novas do código), sem mexer nas que já existem. */
function garantirCabecalhos(so) {
  (so || Object.keys(ABAS)).forEach(n => {
    const s = sh(n); if (!s) return;
    const atual = s.getRange(1, 1, 1, Math.max(1, s.getLastColumn())).getValues()[0].filter(String);
    const falta = ABAS[n].filter(c => atual.indexOf(c) < 0);
    if (falta.length) s.getRange(1, atual.length + 1, 1, falta.length).setValues([falta]).setFontWeight('bold').setBackground('#155a30').setFontColor('#ffffff');
  });
}
function importarCadastro(u) {
  if (u && u.perfil !== 'ADMIN') return { ok: false, msg: 'Só o coordenador importa.' };
  garantirCabecalhos();
  const novos = baixarCsv('execucao_instrumentos.csv'), prevs = baixarCsv('execucao_previsao.csv');
  const saldoNe = {}; tesouroEmCache().forEach(t => saldoNe[t.ne + '|' + t.ug] = (saldoNe[t.ne + '|' + t.ug] || 0) + num(t.saldo));
  const s = sh('INSTRUMENTOS'), v = s.getDataRange().getValues(), cab = v[0], ix = {};
  cab.forEach((c, i) => ix[c] = i);
  const linhas = v.slice(1).filter(r => r.join('') !== '').map(r => { while (r.length < cab.length) r.push(''); return r; });
  const g = (r, c) => r[ix[c]], put = (r, c, x) => { if (ix[c] !== undefined) r[ix[c]] = x; };
  const dig = x => String(x || '').replace(/\D/g, '');
  const porChave = {}, porProc = {};
  linhas.forEach(r => { if (g(r, 'chave')) porChave[g(r, 'chave')] = r; porProc[dig(g(r, 'processo_raiz')) + '|' + g(r, 'ug') + '|' + String(g(r, 'numero') || g(r, 'instrumento'))] = r; });
  const AUTO = ['formalizacao', 'ug', 'numero', 'instrumento', 'proposta', 'processo_raiz', 'favorecido', 'cnpj', 'modalidade', 'objeto', 'vigencia_ini', 'vigencia_fim', 'valor_global', 'valor_parcela', 'base_previsao', 'uf', 'regiao', 'acao', 'a_desembolsar'];
  const agora_ = agora(), vistos = {}, tocados = [];
  let criados = 0, atualizados = 0, encerrados = 0, semSaldo = 0;
  novos.forEach(n => {
    const nes = String(n.nes || '').split(',').filter(Boolean);
    if (n.condicao === 'VENCIDO_COM_NE' && !nes.some(ne => (saldoNe[ne + '|' + n.ug] || 0) > 0.01)) { semSaldo++; return; }
    ['valor_global', 'valor_parcela'].forEach(c => n[c] = num(n[c]));
    let r = porChave[n.chave] || porProc[dig(n.processo_raiz) + '|' + n.ug + '|' + String(n.numero || n.instrumento)];
    if (r) {
      AUTO.forEach(c => { if (n[c] !== '' && n[c] !== undefined) put(r, c, n[c]); });
      if (!g(r, 'orcamento') && n.orcamento) put(r, 'orcamento', n.orcamento);
      const juntas = String(g(r, 'nes') || '').split(/[,;\s]+/).filter(Boolean); nes.forEach(x => { if (juntas.indexOf(x) < 0) juntas.push(x); });
      put(r, 'nes', juntas.join(',')); put(r, 'chave', n.chave); put(r, 'situacao_cadastro', n.condicao); put(r, 'sincronizado_em', agora_);
      atualizados++;
    } else {
      r = cab.map(() => '');
      AUTO.concat(['orcamento']).forEach(c => put(r, c, n[c] === undefined ? '' : n[c]));
      put(r, 'id', n.chave); put(r, 'nes', nes.join(',')); put(r, 'chave', n.chave); put(r, 'situacao_cadastro', n.condicao); put(r, 'sincronizado_em', agora_);
      put(r, 'prorrogacao_prevista', 'NÃO'); put(r, 'origem', 'ROBÔ'); put(r, 'criado_em', agora_); put(r, 'criado_por', 'robô');
      linhas.push(r); porChave[n.chave] = r; criados++;
    }
    vistos[n.chave] = 1; tocados.push(r);
  });
  linhas.forEach(r => { const k = g(r, 'chave'); if (k && !vistos[k] && g(r, 'situacao_cadastro') !== 'ENCERRADO') { put(r, 'situacao_cadastro', 'ENCERRADO'); put(r, 'sincronizado_em', agora_); encerrados++; } });
  if (linhas.length) s.getRange(2, 1, linhas.length, cab.length).setValues(linhas);
  // previsão: parcerias/TED pelo cronograma; contratos pela parcela e vigência. Só preenche competência que ainda não existe.
  const ps = sh('PREVISAO'), idPorChave = {}; linhas.forEach(r => { if (g(r, 'chave')) idPorChave[g(r, 'chave')] = g(r, 'id'); });
  // mês único (ata, compra, repasse, convênio, termos): soma do ano em junho; refeito a cada importação, salvo se alguém editou à mão
  const unico = {}; linhas.forEach(r => { if (g(r, 'chave') && previsaoMesUnico({ formalizacao: g(r, 'formalizacao'), base_previsao: g(r, 'base_previsao') })) unico[g(r, 'id')] = r; });
  const somaU = {}, crono = {};
  prevs.forEach(p => { const id = idPorChave[p.chave]; if (id && unico[id]) crono[id] = (crono[id] || 0) + num(p.valor); });
  Object.keys(unico).forEach(id => {
    const r = unico[id], sd = String(g(r, 'nes') || '').split(/[,;\s]+/).filter(Boolean).reduce((a, ne) => a + Math.max(0, saldoNe[ne + '|' + g(r, 'ug')] || 0), 0);
    const parceria = PARCERIA_RE.test(String(g(r, 'formalizacao') || '')), falta = num(g(r, 'a_desembolsar')) || crono[id] || 0;
    const v = parceria ? Math.min(falta, sd) : sd;   // só o que tem empenho para pagar
    if (v > 0.01) somaU[id] = v;
  });
  competenciaComoTexto();
  const pvBruto = ps.getLastRow() > 1 ? ps.getRange(2, 1, ps.getLastRow() - 1, 5).getValues().filter(x => x.join('') !== '') : [];
  const unicoPv = {}; pvBruto.forEach(x => { x[1] = compStr(x[1]); const k = x[0] + '|' + x[1], old = unicoPv[k]; if (!old || String(old[3]) === 'robô' || String(old[3]) === 'teste') unicoPv[k] = x; });   // uma linha por instrumento e mês; a editada à mão vence
  const pv = Object.keys(unicoPv).map(k => unicoPv[k]);
  const manual = {}; pv.forEach(x => { if (unico[x[0]] && ['robô', 'teste', ''].indexOf(String(x[3])) < 0) manual[x[0]] = 1; });
  const fica = pv.filter(x => !(unico[x[0]] && !manual[x[0]]));
  Object.keys(somaU).forEach(id => { if (!manual[id]) fica.push([id, mesUnico(), Math.round(somaU[id] * 100) / 100, 'robô', agora_]); });
  if (pvBruto.length) ps.getRange(2, 1, pvBruto.length, 5).clearContent();
  if (fica.length) ps.getRange(2, 1, fica.length, 5).setValues(fica);
  const ja = {}; fica.forEach(x => ja[x[0] + '|' + x[1]] = 1);
  const novasPrev = [], add = (id, c, val) => { if (!ja[id + '|' + c] && val) { ja[id + '|' + c] = 1; novasPrev.push([id, c, val, 'robô', agora_]); } };
  prevs.forEach(p => { const id = idPorChave[p.chave]; if (id && !unico[id]) add(id, p.competencia, num(p.valor)); });
  tocados.forEach(r => {
    if (unico[g(r, 'id')]) return;
    const parcela = num(g(r, 'valor_parcela')); if (!parcela) return;
    const ini = String(g(r, 'vigencia_ini')).slice(0, 7), fim = String(g(r, 'prorrogacao_prevista')).toUpperCase() === 'SIM' ? '9999-12' : String(g(r, 'vigencia_fim')).slice(0, 7);
    competenciasDoAno().forEach(c => { if (c >= ini && c <= fim) add(g(r, 'id'), c, parcela); });
  });
  if (novasPrev.length) ps.getRange(ps.getLastRow() + 1, 1, novasPrev.length, 5).setValues(novasPrev);
  const msg = criados + ' novo(s), ' + atualizados + ' atualizado(s), ' + encerrados + ' encerrado(s), ' + semSaldo + ' contrato(s) vencido(s) sem saldo de NE ficaram de fora · ' + novasPrev.length + ' competência(s) de previsão';
  setConfig('ULTIMA_IMPORTACAO', agora_ + ' · ' + msg);
  if (u) hist(u, 'cadastro importado', '', msg);
  toast('Cadastro: ' + msg);
  return { ok: true, msg: msg };
}

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
  limparCacheTesouro();
  const c = conferir(u); c.msg = 'Simulado em ' + n + ' NE(s) de teste.'; return c;
}

/* =========================== API (painel) =========================== */

const VERSAO = '2026-11-10 · RAP + produção';
function doGet() { return json({ ok: true, servico: 'execucao', versao: VERSAO, hora: new Date().toISOString() }); }

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
    const acoes = { importar: importarCadastro, buscaTesouro: buscaTesouro, instrumento: salvarInstrumento, previsao: salvarPrevisao, demanda: registrarDemanda, receber: receberProcesso, distribuirOrc: distribuirOrcamento, distribuir: distribuir, devolver: devolverAoOrcamento, limparTeste: limparTeste, pago: informarPago, repetir: repetirProcesso, desfazer: desfazer, ddo: salvarDdo, conferir: conferir, simular: simularLiquidacao, tesouro: (uu) => uu.perfil === 'ADMIN' ? Object.assign(carregarTesouro(), conferir(uu)) : { ok: false, msg: 'Só o coordenador.' } };
    const f = acoes[p.acao];
    const r = f ? f(u, p) : { ok: false, msg: 'Ação desconhecida.' };
    SpreadsheetApp.flush();
    if (r.ok && p.devolver) r.dados = dados(u);   // já devolve a base atualizada: uma ida ao servidor em vez de duas
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
  limparSessoes();
  anexar('SESSOES', { token: token, email: email, exp: exp });
  return { ok: true, token: token, exp: exp };
}
function usuarioDoToken(token) {
  if (!token) return null;
  const cache = CacheService.getScriptCache(), emCache = cache.get('tk_' + token);
  if (emCache) return JSON.parse(emCache);
  const s = lerTudo('SESSOES').find(x => x.token === token && num(x.exp) > Date.now());
  if (!s) return null;
  const u = lerTudo('USUARIOS').find(x => igual(x.email, s.email) && String(x.ativo).toUpperCase() !== 'NÃO');
  const r = u ? { email: String(u.email).toLowerCase(), nome: u.nome || u.email, perfil: String(u.perfil || 'EXECUTOR').toUpperCase() } : null;
  if (r) cache.put('tk_' + token, JSON.stringify(r), 21600);
  return r;
}

/* ---- leitura ---- */
function nesDoInstrumento(i, tes) {
  const lista = String(i.nes || '').split(/[,;\s]+/).filter(Boolean).map(x => x.toUpperCase());
  const raiz = String(i.processo_raiz || '').replace(/\D/g, '');
  return tes.filter(t => (!i.ug || String(t.ug) === String(i.ug)) && (lista.indexOf(String(t.ne).toUpperCase()) >= 0 || (raiz && String(t.processo).replace(/\D/g, '') === raiz))).map(t => t.ne);
}
function dados(u) {
  const tes = tesouroEmCache();
  let inst = lerTudo('INSTRUMENTOS'), pags = lerTudo('PAGAMENTOS');
  inst.forEach(i => { i.nes_vinculadas = nesDoInstrumento(i, tes); i.cnpj = mascarar(i.cnpj); });
  if (u.perfil === 'EXECUTOR') {
    pags = pags.filter(p => igual(p.executor, u.email));
    const ids = {}; pags.forEach(p => ids[p.instrumento_id] = 1);
    inst = inst.filter(i => ids[i.id]);
  }
  const usadas = {}; inst.forEach(i => i.nes_vinculadas.forEach(n => usadas[n] = 1));
  const equipe = lerTudo('USUARIOS').filter(x => String(x.ativo).toUpperCase() !== 'NÃO' && /EXECUTOR|ADMIN/i.test(x.perfil)).map(x => ({ email: String(x.email).toLowerCase(), nome: x.nome || x.email }));
  const ativos = lerTudo('USUARIOS').filter(x => String(x.ativo).toUpperCase() !== 'NÃO');
  const equipeOrc = ativos.filter(x => /^(ORCAMENTO|CHEFE_ORCAMENTO)$/i.test(x.perfil) || (u.perfil === 'ADMIN' && igual(x.email, u.email)))
    .map(x => ({ email: String(x.email).toLowerCase(), nome: x.nome || x.email }));
  return {
    ok: true, eu: u, ano: ano(), equipeOrc: equipeOrc, competencias: competenciasDoAno(), nomeUg: NOME_UG,
    instrumentos: inst, previsao: lerTudo('PREVISAO'), pagamentos: pags, ddo: u.perfil === 'EXECUTOR' ? [] : lerTudo('DDO'),
    tesouro: tes.filter(t => usadas[t.ne]), totalTesouro: tes.length,
    equipe: equipe, importacao: getConfig('ULTIMA_IMPORTACAO'), carga: getConfig('ULTIMA_CARGA'), conferencia: getConfig('ULTIMA_CONFERENCIA'), agora: agora()
  };
}

/** Busca no Tesouro (cadastro de instrumento): NE, processo, CNPJ ou favorecido. Até 60 resultados. */
function buscaTesouro(u, p) {
  if (!podeCadastrar(u)) return { ok: false, msg: 'Sem permissão.' };
  const q = String(p.q || '').trim(), dg = q.replace(/\D/g, ''), nq = normalizar(q);
  if (q.length < 3) return { ok: true, itens: [] };
  const itens = tesouroEmCache().filter(t => { const txt = [t.ne, t.processo, t.favorecido].join(' '); return (dg.length >= 4 && txt.replace(/\D/g, '').indexOf(dg) >= 0) || normalizar(txt).indexOf(nq) >= 0; }).slice(0, 60);
  return { ok: true, itens: itens };
}

/* ---- ações ---- */
function podeCadastrar(u) { return /ADMIN|ORCAMENTO/.test(u.perfil); }   // ADMIN, CHEFE_ORCAMENTO e ORCAMENTO
function chefeOrc(u) { return u.perfil === 'ADMIN' || u.perfil === 'CHEFE_ORCAMENTO'; }

/** Responsável do orçamento: o processo SEI chegou. Cria a demanda (sem NE ainda) e, se já escolher, entrega ao analista. */
function receberProcesso(u, p) {
  if (!chefeOrc(u)) return { ok: false, msg: 'Só o responsável do orçamento registra a chegada do processo.' };
  garantirCabecalhos(['PAGAMENTOS']); competenciaComoTexto();
  const i = lerTudo('INSTRUMENTOS').find(x => x.id === p.instrumento_id);
  if (!i) return { ok: false, msg: 'Instrumento não encontrado.' };
  if (!String(p.processo || '').trim()) return { ok: false, msg: 'Informe o processo SEI.' };
  if (!p.competencia) return { ok: false, msg: 'Informe a competência.' };
  const quando = agora();
  const o = { id: 'P' + Date.now().toString(36).toUpperCase(), instrumento_id: i.id, competencia: p.competencia, processo_pagamento: String(p.processo).trim(),
    area_demandante: p.area || '', valor: num(p.valor), recebido_por: u.email, recebido_em: quando, situacao: SIT.RECEBIDO };
  if (p.analista) Object.assign(o, { analista: String(p.analista).toLowerCase(), dist_orc_por: u.email, dist_orc_em: quando, situacao: SIT.NO_ORCAMENTO });
  anexar('PAGAMENTOS', o);
  hist(u, 'processo recebido', o.id, o.processo_pagamento + (p.analista ? ' · analista ' + p.analista : ''));
  return { ok: true, id: o.id };
}
/** Responsável do orçamento: entrega (ou troca) o analista que vai tratar a NE e o saldo. */
function distribuirOrcamento(u, p) {
  if (!chefeOrc(u)) return { ok: false, msg: 'Só o responsável do orçamento distribui no orçamento.' };
  garantirCabecalhos(['PAGAMENTOS']);
  const todos = lerTudo('PAGAMENTOS'), quando = agora(); let n = 0;
  (p.itens || []).forEach(it => {
    const c = todos.find(x => x.id === it.id);
    if (!c || !it.analista || [SIT.RECEBIDO, SIT.NO_ORCAMENTO, SIT.DEVOLVIDO, SIT.REFORCO].indexOf(c.situacao) < 0) return;
    atualizar('PAGAMENTOS', c.id, { analista: String(it.analista).toLowerCase(), dist_orc_por: u.email, dist_orc_em: quando, situacao: [SIT.REFORCO, SIT.DEVOLVIDO].indexOf(c.situacao) >= 0 ? c.situacao : SIT.NO_ORCAMENTO });
    hist(u, 'distribuído no orçamento', c.id, it.analista); n++;
  });
  return { ok: true, n: n };
}
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
  competenciaComoTexto();
  const ps = sh('PREVISAO'), v = ps.getDataRange().getValues(), quando = agora(), onde = {}, novas = [];
  for (let r = 1; r < v.length; r++) if (v[r][0] === p.instrumento_id) onde[compStr(v[r][1])] = r;
  let mudou = false;
  (p.itens || []).forEach(it => {
    const r = onde[it.competencia], val = Math.abs(num(it.valor));   // previsão é sempre despesa: guarda positivo
    if (r !== undefined) { v[r][2] = val; v[r][3] = u.email; v[r][4] = quando; mudou = true; }
    else novas.push({ instrumento_id: p.instrumento_id, competencia: it.competencia, valor: val, alterado_por: u.email, alterado_em: quando });
  });
  if (mudou && v.length > 1) ps.getRange(2, 3, v.length - 1, 3).setValues(v.slice(1).map(x => [x[2], x[3], x[4]]));
  anexarVarios('PREVISAO', novas);
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
  garantirCabecalhos(['PAGAMENTOS']);
  if (p.id) {
    const c = lerTudo('PAGAMENTOS').find(x => x.id === p.id);
    if (!c) return { ok: false, msg: 'Demanda não encontrada.' };
    if ([SIT.RECEBIDO, SIT.NO_ORCAMENTO, SIT.DEVOLVIDO, SIT.REFORCO, SIT.SALDO_OK].indexOf(c.situacao) < 0) return { ok: false, msg: 'Esta demanda já foi distribuída no financeiro.' };
    if (!chefeOrc(u) && !igual(c.analista, u.email)) return { ok: false, msg: 'Esta demanda está com outro analista.' };
    if (!c.analista) o.analista = u.email;
    atualizar('PAGAMENTOS', p.id, o); hist(u, p.saldoOk ? 'saldo confirmado' : 'reforço de NE', p.id, p.processo); return { ok: true };
  }
  o.id = 'P' + Date.now().toString(36).toUpperCase(); o.analista = u.email;
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
/** Financeiro (coordenação ou o próprio executor) devolve ao orçamento por irregularidade. Motivo obrigatório; volta ao mesmo analista. */
function devolverAoOrcamento(u, p) {
  garantirCabecalhos(['PAGAMENTOS']);
  const c = lerTudo('PAGAMENTOS').find(x => x.id === p.id);
  if (!c) return { ok: false, msg: 'Pagamento não encontrado.' };
  const motivo = String(p.motivo || '').trim();
  if (motivo.length < 5) return { ok: false, msg: 'Escreva o motivo da devolução.' };
  if (u.perfil !== 'ADMIN') {
    if (u.perfil !== 'EXECUTOR' || !igual(c.executor, u.email)) return { ok: false, msg: 'Só o executor do item ou a coordenação financeira devolvem.' };
    if (c.situacao !== SIT.DISTRIBUIDO) return { ok: false, msg: 'Só dá para devolver o que ainda não foi informado como pago.' };
  } else if ([SIT.SALDO_OK, SIT.DISTRIBUIDO].indexOf(c.situacao) < 0) return { ok: false, msg: 'Só dá para devolver o que ainda não foi informado como pago.' };
  atualizar('PAGAMENTOS', c.id, { situacao: c.analista ? SIT.DEVOLVIDO : SIT.RECEBIDO, executor: '', devolvido_por: u.email, devolvido_em: agora(), motivo_devolucao: motivo });
  hist(u, 'devolvido ao orçamento', c.id, motivo + (c.executor ? ' · estava com ' + c.executor : ''));
  return { ok: true };
}
/** Apaga os dados de TESTE (instrumentos T1–T4, NEs 900xxx e tudo ligado a eles). O histórico fica. */
function limparTeste(u) {
  if (u && u.perfil !== 'ADMIN') return { ok: false, msg: 'Só o coordenador apaga os dados de teste.' };
  const ids = {}; lerTudo('INSTRUMENTOS').forEach(i => { if (i.origem === 'TESTE') ids[i.id] = 1; });
  const nesTeste = {}; lerTudo('TESOURO_NE').forEach(t => { if (t.origem === 'TESTE') nesTeste[t.ne] = 1; });
  const tira = (aba, fora) => {
    const s = sh(aba); if (!s || s.getLastRow() < 2) return 0;
    const v = s.getDataRange().getValues(), cab = v[0], fica = v.slice(1).filter(r => r.join('') !== '' && !fora(r, cab));
    const n = v.length - 1 - fica.length;
    s.getRange(2, 1, v.length - 1, cab.length).clearContent();
    if (fica.length) s.getRange(2, 1, fica.length, cab.length).setValues(fica);
    return n;
  };
  const col = (cab, c) => cab.indexOf(c);
  const n = {
    instrumentos: tira('INSTRUMENTOS', (r, c) => r[col(c, 'origem')] === 'TESTE'),
    pagamentos: tira('PAGAMENTOS', (r, c) => ids[r[col(c, 'instrumento_id')]] || nesTeste[r[col(c, 'ne')]]),
    previsao: tira('PREVISAO', (r, c) => ids[r[col(c, 'instrumento_id')]]),
    ddo: tira('DDO', (r, c) => ids[r[col(c, 'instrumento_id')]]),
    nes: tira('TESOURO_NE', (r, c) => r[col(c, 'origem')] === 'TESTE')
  };
  limparCacheTesouro();
  hist(u || { email: 'apps-script' }, 'dados de teste apagados', '', JSON.stringify(n));
  return { ok: true, msg: 'Dados de teste apagados: ' + n.instrumentos + ' instrumento(s), ' + n.pagamentos + ' pagamento(s), ' + n.previsao + ' linha(s) de previsão, ' + n.ddo + ' DDO, ' + n.nes + ' NE(s) de teste.' };
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

/* ---- cache (deixa a abertura do painel rápida) ---- */
function tesouroEmCache() {
  const c = CacheService.getScriptCache(), n = Number(c.get('tes_n') || 0);
  if (n) { const partes = c.getAll(Array.from({ length: n }, (_, i) => 'tes_' + i)); if (Object.keys(partes).length === n) { try { return JSON.parse(Array.from({ length: n }, (_, i) => partes['tes_' + i]).join('')); } catch (e) {} } }
  const tes = lerTudo('TESOURO_NE'), txt = JSON.stringify(tes), o = {}, TAM = 45000;
  const qt = Math.ceil(txt.length / TAM);   // 45 mil caracteres: fica abaixo de 100 KB mesmo com acentos
  if (qt <= 150) { for (let i = 0; i < qt; i++) o['tes_' + i] = txt.slice(i * TAM, (i + 1) * TAM); o.tes_n = String(qt); try { c.putAll(o, 21600); } catch (e) {} }
  return tes;
}
function limparCacheTesouro() { CacheService.getScriptCache().remove('tes_n'); }
function limparSessoes() {
  const s = sh('SESSOES'), v = s.getDataRange().getValues(), agora_ = Date.now();
  for (let r = v.length - 1; r >= 1; r--) if (Number(v[r][2]) < agora_) s.deleteRow(r + 1);
}

/* =========================== utilitários =========================== */
function sh(n) { return SpreadsheetApp.getActive().getSheetByName(n); }
function lerTudo(n) {
  const s = sh(n); if (!s || s.getLastRow() < 2) return [];
  const v = s.getRange(1, 1, s.getLastRow(), s.getLastColumn()).getValues(), cab = v.shift();
  return v.filter(r => r.join('') !== '').map(r => { const o = {}; cab.forEach((c, i) => o[c] = c === 'competencia' ? compStr(r[i]) : (r[i] instanceof Date ? Utilities.formatDate(r[i], 'America/Sao_Paulo', "yyyy-MM-dd'T'HH:mm:ss") : r[i])); return o; });
}
/** O Google Sheets transforma "2027-03" em data: aqui volta sempre para o texto "2027-03". */
function compStr(x) { return x instanceof Date ? Utilities.formatDate(x, 'America/Sao_Paulo', 'yyyy-MM') : String(x || '').slice(0, 7); }
/** Deixa a coluna competência como texto, para o Sheets não converter mais (uma vez por aba). */
function competenciaComoTexto() {
  ['PREVISAO', 'PAGAMENTOS'].forEach(n => { const s = sh(n); if (!s) return; const c = s.getRange(1, 1, 1, s.getLastColumn()).getValues()[0].indexOf('competencia'); if (c >= 0) s.getRange(1, c + 1, s.getMaxRows(), 1).setNumberFormat('@'); });
}
function anexar(n, o) { sh(n).appendRow(ABAS[n].map(c => o[c] === undefined ? '' : o[c])); }
/** Várias linhas de uma vez (uma gravação só). */
function anexarVarios(n, lista) {
  if (!lista.length) return;
  const s = sh(n), cab = s.getRange(1, 1, 1, s.getLastColumn()).getValues()[0];
  s.getRange(s.getLastRow() + 1, 1, lista.length, cab.length).setValues(lista.map(o => cab.map(c => o[c] === undefined ? '' : o[c])));
}
function atualizar(n, id, campos) {
  const s = sh(n), v = s.getDataRange().getValues(), cab = v[0];
  for (let r = 1; r < v.length; r++) {
    if (v[r][0] !== id) continue;
    // uma gravação só: do primeiro ao último campo alterado da linha
    const cols = Object.keys(campos).map(k => cab.indexOf(k)).filter(c => c >= 0);
    if (!cols.length) return true;
    const a = Math.min.apply(null, cols), b = Math.max.apply(null, cols), linha = v[r].slice(a, b + 1);
    Object.keys(campos).forEach(k => { const c = cab.indexOf(k); if (c >= 0) linha[c - a] = campos[k]; });
    s.getRange(r + 1, a + 1, 1, linha.length).setValues([linha]);
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
