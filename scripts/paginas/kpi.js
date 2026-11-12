
// ===================== cartões clicáveis: clicar num cartão mostra a lista do que ele soma =====================
// a página preenche KPI_DEF[chave] = {tit, lista, cols} a cada render e marca o cartão com data-kpi="chave"
var KPI_DEF = window.KPI_DEF || {}; window.KPI_DEF = KPI_DEF;
function kpiDepois(){
  document.querySelectorAll('[data-kpi]').forEach(c => { c.classList.add('kpi-cl'); c.classList.toggle('kpi-on', c.dataset.kpi === window.__kpi); });
  let box = document.getElementById('kpLista');
  if(!box){ const ref = document.querySelector('[data-kpi]'); if(!ref) return; const grade = ref.closest('.kp') || ref.parentElement;
    box = document.createElement('div'); box.id = 'kpLista'; grade.parentNode.insertBefore(box, grade.nextSibling); }
  // a caixa fica logo abaixo da fileira do cartão clicado
  const on = window.__kpi && document.querySelector(`[data-kpi="${window.__kpi}"]`);
  if(on){ const grade = on.closest('.kp') || on.parentElement; if(grade.nextSibling !== box) grade.parentNode.insertBefore(box, grade.nextSibling); }
  const d = window.__kpi && (window.KPI_DEF||{})[window.__kpi];
  if(!d){ box.innerHTML = ''; return; }
  if(KF.__on !== window.__kpi) KF = {__on: window.__kpi};
  const foco = document.activeElement && document.activeElement.dataset ? document.activeElement.dataset.kf : null;
  const LF = kpiFiltrar(d.lista), cols = kpiCols(d), fil = LF.length !== d.lista.length;
  const uniq = a => [...new Set(a)].filter(x => x && x !== '—');
  const mods = uniq(d.lista.map(o => kTipo(o)[0])).sort(), anos = uniq(d.lista.map(o => String(o.ano||''))).sort().reverse();
  const ufs = uniq(d.lista.map(o => String(o.uf||''))).sort(), sits = uniq(d.lista.map(o => String(o.sit||o.fase||''))).sort(), fins = uniq(d.lista.map(kFin)), anosE = uniq(d.lista.flatMap(kAnos).map(String)).sort().reverse();
  const sel = (k, vals, rot) => `<label>${rot}<select data-kf="${k}"><option value="">Todos</option>${vals.map(v => `<option${KF[k]===v?' selected':''}>${esc(v)}</option>`).join('')}</select></label>`;
  const finOps = fins.length ? ['EXE','RAP','EXE e RAP'].concat(fins.filter(v => !/EXE|RAP/.test(v))) : [];
  const met = kpiMetrica(d, cols);
  const nI = x => x.toLocaleString('pt-BR');
  const mc = (rot, cor, v, sub, cls) => `<div class="${cls||''}" style="--c:${cor}"${met ? ` title="${esc(rot)}: ${esc(kBRL(v))}"` : ''}><small>${rot}</small><b>${met ? (Math.abs(v) < 0.005 ? 'R$ 0,00' : 'R$ '+fm(v)) : nI(v)}</b><span>${sub}</span></div>`;
  const vL = l => met ? l.reduce((a,o) => a + met(o), 0) : l.length;
  let mini = mc(fil ? 'Filtrado' : 'Total', fil ? '#e67e22' : '#1f4e79', vL(LF), (fil ? 'de '+(met ? fm(vL(d.lista)) : nI(d.lista.length))+' · ' : '')+(met ? nI(LF.length) : ''), fil ? 'fil' : 'tot');
  if(fins.length) [['EXE','#1f4e79'],['RAP','#8e44ad'],['EXE e RAP','#16756b']].forEach(([k,c]) => { const l = LF.filter(o => kFin(o) === k); mini += mc(k, c, vL(l), met ? nI(l.length) : ''); });
  mini = `<div class="kpi-mc">${mini}</div>`;
  const limpa = Object.keys(KF).some(k => k !== '__on' && KF[k]) ? '<button type="button" class="kpi-bt" data-kflimpa="1">Limpar</button>' : '';
  box.innerHTML = `<section class="card kpi-box"><div class="kpi-cab"><div><h3>📋 ${esc(d.tit)}</h3><p class="d">${fil ? LF.length.toLocaleString('pt-BR')+' de ' : ''}${d.lista.length.toLocaleString('pt-BR')} registro(s) · clique na linha para abrir a ficha</p></div>
    <div><button type="button" class="kpi-bt" data-kpicsv="1">⬇ Extração em Excel</button><button type="button" class="kpi-bt" data-kpifecha="1">✕ Fechar</button></div></div>
    <div class="kpi-fil"><label>Instrumento<input type="search" data-kf="q" data-bm-in="kpi" value="${esc(KF.q||'')}" placeholder="nº, proponente… (vários: ;)" title="Vários termos: separe por ; ou , ou cole uma coluna do Excel · use + para exigir os dois"></label>
    ${sits.length > 1 ? sel('sit', sits, 'Situação') : ''}${mods.length ? sel('mod', mods, 'Modalidade') : ''}${ufs.length > 1 ? sel('uf', ufs, 'UF') : ''}${finOps.length ? sel('fin', finOps, 'Financeiro') : ''}${anos.length ? sel('ano', anos, mods.length ? 'Ano da proposta' : 'Ano') : ''}${anosE.length ? sel('anoNE', anosE, 'Ano do empenho') : ''}${limpa}</div>${mini}
    <div data-bm="kpi"></div>${tabela('k', LF, cols, 10)}</section>`;
  BM.pintar('kpi'); BM.realcar(box.querySelector('table'), 'kpi');
  if(foco){ const x = box.querySelector(`[data-kf="${foco}"]`); if(x){ x.focus(); if(x.type === 'search'){ const n = x.value.length; try{ x.setSelectionRange(n, n); }catch(e){} } } }
}
// ---- filtros, modalidade, financeiro (EXE/RAP) e resumo em valor: mesmo padrão do painel de Parcerias
var KF = {};
const kBRL = v => 'R$ '+Number(v||0).toLocaleString('pt-BR',{minimumFractionDigits:2,maximumFractionDigits:2});
function kTipo(o){ const m = String(o && o.mod || '').normalize('NFD').replace(/[\u0300-\u036f]/g, '').toUpperCase();
  return /FOMENTO/.test(m) ? ['Termo de Fomento','#2e7d32'] : /REPASSE/.test(m) ? ['Contrato de Repasse','#b8650a'] : /COLABORA/.test(m) ? ['Termo de Colaboração','#6a3d9a'] : /CONVENIO/.test(m) ? ['Convênio','#1f4e79'] : m ? [o.mod,'#666'] : ['—','']; }
function kAnos(o){ return [...new Set((o && o.nes || []).map(x => { const t = Array.isArray(x) ? x.find(v => /^\d{4}NE/.test(String(v))) : x; return +((String(t||'').match(/^(\d{4})NE/)||[])[1]||0); }).filter(Boolean))].sort(); }
function kFin(o){
  const anos = kAnos(o);
  if(!anos.length) return '—';
  const a = new Date().getFullYear(), e = anos.includes(a), r = anos.some(x => x < a);
  return e && r ? 'EXE e RAP' : e ? 'EXE' : 'RAP';
}
function kpiFiltrar(L){
  return BM.filtrar('kpi', KF.q, L.filter(o => true
    && (!KF.mod || kTipo(o)[0] === KF.mod)
    && (!KF.fin || (KF.fin === 'EXE' ? /EXE/.test(kFin(o)) : KF.fin === 'RAP' ? /RAP/.test(kFin(o)) : kFin(o) === KF.fin))
    && (!KF.ano || String(o.ano||'') === KF.ano)
    && (!KF.anoNE || kAnos(o).includes(+KF.anoNE))
    && (!KF.sit || String(o.sit||o.fase||'') === KF.sit)
    && (!KF.uf || String(o.uf||'') === KF.uf)), o => [o.n, o.num, o.prop, o.parl, o.munN, o.objr, o.obj, o.ent, o.uf, o.ug].join(' '));
}
const kTag = (t, c) => `<span style="display:inline-block;background:${c};color:#fff;font-size:10.5px;font-weight:700;padding:1px 8px;border-radius:10px;white-space:nowrap">${esc(t)}</span>`;
function kpiCols(d){
  let c = d.cols.slice();
  if(d.lista.some(o => o.mod) && !c.some(x => /modalidade/i.test(x[0]))) c.splice(1, 0, ['Modalidade', o => { const t = kTipo(o); return t[1] ? kTag(t[0], t[1]) : '—'; }]);
  if(d.lista.some(o => kFin(o) !== '—') && !c.some(x => /^financeiro$/i.test(x[0]))) c.splice(c.findIndex(x => /modalidade/i.test(x[0])) + 1 || 1, 0, ['Financeiro', o => { const an = kAnos(o), a = new Date().getFullYear(); if(!an.length) return '<small>—</small>';
    const rap = an.filter(x => x < a); return (rap.length ? kTag('RAP '+rap.join(' · '), '#8e44ad')+' ' : '') + (an.includes(a) ? kTag('EXE '+a, '#1f4e79') : ''); }]);
  if(d.lista.some(o => o.ug) && !c.some(x => /^ug\b/i.test(x[0]))){ const i = c.findIndex(x => /^financeiro$/i.test(x[0])); c.splice(i >= 0 ? i+1 : (c.findIndex(x => /modalidade/i.test(x[0])) + 1 || 1), 0, ['UG', o => o.ug ? `<b>${esc(o.ug)}</b>` : '—']); }
  if(d.lista.some(o => o.uf) && !c.some(x => /^uf$/i.test(x[0]))){ const i = c.findIndex(x => /^(ug|financeiro)$/i.test(x[0])); c.splice(i >= 0 ? i+1 : 1, 0, ['UF', o => o.uf ? `<b>${esc(o.uf)}</b>` : '—']); }
  return c;
}
// valor do resumo: coluna de valor com o mesmo nome do cartão (senão a última coluna de valor); lê o número já formatado (Bi/Mi/Mil)
function kpiNum(t){ t = String(t||'').replace(/<small[\s\S]*$/i, '').replace(/<[^>]+>/g, ' ').trim(); const m = t.match(/^([−-])?\s*(?:R\$\s*)?([\d.]+(?:,\d+)?)\s*(Bi|Mi|Mil)?\b/); if(!m) return null;
  let v = parseFloat(m[2].replace(/\./g, '').replace(',', '.')); v *= m[3]==='Bi' ? 1e9 : m[3]==='Mi' ? 1e6 : m[3]==='Mil' ? 1e3 : 1; return m[1] ? -v : v; }
function kpiMetrica(d, cols){
  const ehValor = c => c[2] === 'n' && d.lista.slice(0, 20).some(o => /\b(Bi|Mi|Mil)\b|R\$/.test(String(c[1](o))));
  const norm = s => String(s||'').replace(/<[^>]+>/g, '').trim().toLowerCase();
  const vs = cols.filter(ehValor); if(!vs.length) return null;
  const c = vs.find(x => norm(x[0]) === norm(d.tit)) || vs.find(x => norm(d.tit).includes(norm(x[0]))) || vs[vs.length - 1];
  return o => kpiNum(c[1](o)) || 0;
}
(function(){
  const css = document.createElement('style');
  css.textContent = `.kpi-cl{cursor:pointer;transition:transform .12s, box-shadow .12s}.kpi-cl:hover{transform:translateY(-2px);box-shadow:0 8px 20px rgba(20,40,60,.16)}
  .kpi-on{outline:3px solid #2fae5c;outline-offset:-3px}.kpi-box{border:2px solid #2fae5c}.kpi-cab{display:flex;justify-content:space-between;gap:10px;align-items:flex-start;flex-wrap:wrap}
  .kpi-bt{border:1px solid #b9c7d3;background:#fff;color:#1f4e79;font:600 12.5px inherit;font-family:inherit;padding:6px 12px;border-radius:8px;cursor:pointer;margin-left:6px}
  .kpi-fil{display:flex;flex-wrap:wrap;gap:8px 12px;align-items:flex-end;margin:6px 0 10px}.kpi-fil label{display:flex;flex-direction:column;font-size:11px;font-weight:600;color:#33475b;gap:3px}
  .kpi-fil input,.kpi-fil select{font:inherit;font-size:12px;font-weight:400;padding:5px 8px;border:1px solid #cfd8e3;border-radius:6px;background:#f7f9fb;width:150px;min-width:0;max-width:150px;box-sizing:border-box;text-overflow:ellipsis}
  .kpi-mc{display:flex;flex-wrap:wrap;gap:8px;margin:0 0 10px}.kpi-mc>div{flex:1;min-width:150px;border:1px solid #dfe6ee;border-left:4px solid var(--c);background:#fafcfd;padding:5px 10px}.kpi-mc>div.fil{background:#fff8ec}.kpi-mc>div.tot{background:#eef3f8}.kpi-mc small{display:block;font-size:10px;font-weight:700;color:#5b6b7b;text-transform:uppercase}.kpi-mc b{font-size:15px;color:#14324f}.kpi-mc span{font-size:10px;color:#7a8794;margin-left:4px}`;
  document.head.appendChild(css);
  const _render = render;
  render = function(){ _render.apply(this, arguments); try{ kpiDepois(); }catch(e){ console.error(e); } };
  document.addEventListener('click', e => {
    const k = e.target.closest('[data-kpi]');
    if(k){ e.stopImmediatePropagation(); window.__kpi = window.__kpi === k.dataset.kpi ? null : k.dataset.kpi; if(typeof PAG === 'object') PAG.k = 0; kpiDepois();
      const b = document.getElementById('kpLista'); if(b && window.__kpi) b.scrollIntoView({block:'nearest', behavior:'smooth'}); return; }
    if(e.target.closest('[data-kpifecha]')){ e.stopImmediatePropagation(); window.__kpi = null; kpiDepois(); return; }
    if(e.target.closest('[data-kflimpa]')){ e.stopImmediatePropagation(); KF = {__on: window.__kpi}; if(typeof PAG === 'object') PAG.k = 0; kpiDepois(); return; }
    if(e.target.closest('[data-kpicsv]')){ e.stopImmediatePropagation(); const d = (window.KPI_DEF||{})[window.__kpi]; if(!d) return;
      const txt = s => String(s ?? '').replace(/<[^>]+>/g, ' ').replace(/&nbsp;/g, ' ').replace(/&amp;/g, '&').replace(/\s+/g, ' ').trim();
      const cs = kpiCols(d), lista = kpiFiltrar(d.lista);
      // Excel no modelo padrão do painel (mesmo das outras telas): valores em número exato, não "50,00 Mi"
      const P = (() => { try{ return window.parent && window.parent !== window && window.parent.baixarXlsx ? window.parent : null; }catch(e){ return null; } })();
      if(P){
        window.__FM_EXATO = true; let L2;
        try{ L2 = lista.map(o => cs.map(c => { const t = txt(c[1](o)), m = t.match(/^§(-?[\d.e+-]+)/); return m ? +m[1] : t.replace(/§(-?[\d.e+-]+)/g, (_, x) => Number(x).toLocaleString('pt-BR', {minimumFractionDigits:2, maximumFractionDigits:2})); })); }
        finally{ window.__FM_EXATO = false; }
        const num = cs.map((c, i) => L2.length && L2.every(l => typeof l[i] === 'number' || l[i] === ''));
        P.baixarXlsx({titulo:(document.title || 'Painel SDR') + ' · ' + txt(d.tit || 'lista'), sub:document.title || '', arquivo:(d.tit || 'lista').replace(/[^\wÀ-ú ]+/g, '').trim().replace(/\s+/g, '_'),
          cab:cs.map((c, i) => num[i] ? {t:txt(c[0]), n:1} : {t:txt(c[0])}), linhas:L2});
        return;
      }
      const linhas = [cs.map(c => txt(c[0]))].concat(lista.map(o => cs.map(c => txt(c[1](o)))));
      const csv = '﻿' + linhas.map(l => l.map(v => '"' + v.replace(/"/g, '""') + '"').join(';')).join('\r\n');
      const a = document.createElement('a'); a.href = URL.createObjectURL(new Blob([csv], {type:'text/csv'})); a.download = (d.tit || 'lista').replace(/[^\wÀ-ú ]+/g, '').trim().replace(/\s+/g, '_') + '.csv';
      document.body.appendChild(a); a.click(); a.remove(); return; }
  }, true);
  let tmK; const mudaK = e => { const x = e.target.closest && e.target.closest('[data-kf]'); if(!x) return; e.stopImmediatePropagation();
    KF[x.dataset.kf] = x.value; if(typeof PAG === 'object') PAG.k = 0; clearTimeout(tmK); tmK = setTimeout(kpiDepois, x.type === 'search' ? 250 : 0); };
  document.addEventListener('input', mudaK, true); document.addEventListener('change', mudaK, true);
})();
