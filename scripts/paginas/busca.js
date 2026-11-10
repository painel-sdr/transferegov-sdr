// ===================== busca inteligente: vários termos (; , quebra de linha ou colar do Excel), + para exigir os dois =====================
var BM = window.BM || (function(){
  const norm = s => String(s ?? '').normalize('NFD').replace(/[̀-ͯ]/g, '').toUpperCase();
  const comp = s => norm(s).replace(/[^A-Z0-9]/g, '');
  const ult = {}, modo = {};
  const escB = s => String(s ?? '').replace(/[&<>"]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
  function termos(txt){
    return String(txt || '').split(/[;,\n\r\t]+/).map(t => t.trim()).filter(Boolean)
      .map(t => ({txt: t, partes: t.split('+').map(p => p.trim()).filter(Boolean).map(p => ({n: norm(p), c: comp(p)}))}))
      .filter(t => t.partes.length);
  }
  const semZero = s => s.replace(/(^|[^0-9])0+(?=[0-9])/g, '$1');   // 000724/2026 = 724/2026
  const bateParte = (p, N, C) => N.includes(p.n) || (p.c.length >= 4 && C.includes(p.c)) || (/[0-9]/.test(p.n) && semZero(N).includes(semZero(p.n)));
  function quais(T, texto){ const N = norm(texto), C = N.replace(/[^A-Z0-9]/g, ''); const r = []; T.forEach((t, i) => { if(t.partes.every(p => bateParte(p, N, C))) r.push(i); }); return r; }
  // filtra a lista pelo texto da busca; textoFn(o) devolve o texto pesquisável da linha
  function filtrar(id, txt, L, textoFn){
    const T = termos(txt), R = {T, cont: T.map(() => 0), tags: new Map(), total: L.length, achou: L.length};
    ult[id] = R;
    if(!T.length) return L;
    const todos = modo[id] === 'e';
    const out = L.filter(o => { const q = quais(T, textoFn(o)); q.forEach(i => R.cont[i]++); if(!q.length || (todos && q.length < T.length)) return false; R.tags.set(o, q); return true; });
    R.achou = out.length;
    return out;
  }
  // um valor bate com algum dos termos? (filtros de coluna)
  function algum(txt, valor){ const T = termos(txt); return !T.length || quais(T, valor).length > 0; }
  const ativo = id => !!(ult[id] && ult[id].T.length);
  const multi = id => !!(ult[id] && ult[id].T.length > 1);
  // etiqueta com o(s) termo(s) que trouxe(ram) a linha (só quando há mais de um termo)
  function tag(id, o){ const R = ult[id]; if(!R || R.T.length < 2) return ''; const q = R.tags.get(o); return q ? q.map(i => `<span class="bm-tag">${escB(R.T[i].txt)}</span>`).join('') : ''; }
  function pintar(id){
    const R = ult[id];
    document.querySelectorAll(`[data-bm="${id}"]`).forEach(el => {
      if(!R || !R.T.length){ el.innerHTML = ''; return; }
      const nao = R.cont.filter(c => !c).length;
      el.innerHTML = '<div class="bm-chips">' + R.T.map((t, i) => `<span class="bm-chip ${R.cont[i] ? '' : 'nao'} ${t.partes.length > 1 ? 'e' : ''}" title="${R.cont[i] ? R.cont[i]+' linha(s) com este termo' : 'nenhuma linha com este termo'}">${escB(t.txt)} <i>${R.cont[i].toLocaleString('pt-BR')}</i>${R.cont[i] ? '' : ' não encontrado'} <b data-bmx="${id}|${i}" title="Tirar este termo">✕</b></span>`).join('')
        + `<a class="bm-limpa" data-bmlimpa="${id}">limpar busca</a></div>`
        + (R.T.length > 1 ? `<div class="bm-modo">Mostrar linhas com: <span data-bmmodo="${id}|ou" class="${modo[id] === 'e' ? '' : 'on'}">qualquer termo (OU)</span><span data-bmmodo="${id}|e" class="${modo[id] === 'e' ? 'on' : ''}">todos os termos (E)</span><em>${R.achou.toLocaleString('pt-BR')} de ${R.total.toLocaleString('pt-BR')} linha(s) · ${R.T.length} termos${nao ? ' · ' + nao + ' não encontrado(s)' : ''}</em></div>` : '');
    });
  }
  // marca em amarelo o trecho encontrado nas células da tabela
  function realcar(raiz, id){
    const R = ult[id]; if(!raiz || !R || !R.T.length) return;
    const ps = [...new Set(R.T.flatMap(t => t.partes.map(p => p.n.trim())).filter(x => x.length >= 2))].sort((a, b) => b.length - a.length);
    if(!ps.length) return;
    const alvo = raiz.querySelector('tbody') || raiz, w = document.createTreeWalker(alvo, NodeFilter.SHOW_TEXT), nodes = [];
    while(w.nextNode()) nodes.push(w.currentNode);
    nodes.forEach(nd => {
      const pai = nd.parentNode; if(!pai || pai.closest('.bm-tag,mark,select,option,script,style')) return;
      const s = nd.nodeValue; if(!s || !s.trim()) return;
      let N = ''; for(const ch of s){ const x = norm(ch); N += (x + ' '.repeat(ch.length)).slice(0, ch.length); }
      const rs = [];
      ps.forEach(p => { let i = N.indexOf(p); while(i >= 0){ if(!rs.some(([a, b]) => i < b && i + p.length > a)) rs.push([i, i + p.length]); i = N.indexOf(p, i + 1); } });
      if(!rs.length) return;
      rs.sort((a, b) => a[0] - b[0]);
      const f = document.createDocumentFragment(); let k = 0;
      rs.forEach(([a, b]) => { if(a > k) f.appendChild(document.createTextNode(s.slice(k, a))); const m = document.createElement('mark'); m.className = 'bm-mark'; m.textContent = s.slice(a, b); f.appendChild(m); k = b; });
      if(k < s.length) f.appendChild(document.createTextNode(s.slice(k)));
      pai.replaceChild(f, nd);
    });
  }
  // texto que vai para o PDF/Excel ("Busca: ...")
  function rotulo(id, txt){ const T = termos(txt); return !T.length ? '' : T.length === 1 ? `Busca: "${T[0].txt}"` : `Busca (${modo[id] === 'e' ? 'todos' : 'qualquer'} de ${T.length} termos): ${T.map(t => t.txt).join('; ')}`; }
  function disparar(inp){ inp.dispatchEvent(new Event('input', {bubbles: true})); }
  const entrada = id => document.querySelector(`[data-bm-in="${id}"]`);
  document.addEventListener('click', e => {
    const x = e.target.closest('[data-bmx]'), l = e.target.closest('[data-bmlimpa]'), m = e.target.closest('[data-bmmodo]');
    if(!x && !l && !m) return;
    e.preventDefault(); e.stopImmediatePropagation();
    if(m){ const [id, v] = m.dataset.bmmodo.split('|'); modo[id] = v; const inp = entrada(id); if(inp) disparar(inp); return; }
    const id = (x ? x.dataset.bmx.split('|')[0] : l.dataset.bmlimpa), inp = entrada(id); if(!inp) return;
    if(l) inp.value = '';
    else { const i = +x.dataset.bmx.split('|')[1]; inp.value = termos(inp.value).filter((t, j) => j !== i).map(t => t.txt).join('; '); }
    disparar(inp);
  }, true);
  // colar uma coluna do Excel: cada linha vira um termo
  document.addEventListener('paste', e => {
    const inp = e.target.closest && e.target.closest('input[data-bm-in],input[data-bm-col]'); if(!inp) return;
    const t = (e.clipboardData || window.clipboardData).getData('text'); if(!/[\n\r\t]/.test(t)) return;
    e.preventDefault();
    const novos = t.split(/[\n\r\t]+/).map(s => s.trim()).filter(Boolean);
    const ini = inp.value.slice(0, inp.selectionStart).replace(/[;,\s]+$/, ''), fim = inp.value.slice(inp.selectionEnd).replace(/^[;,\s]+/, '');
    inp.value = [ini, novos.join('; '), fim].filter(Boolean).join('; ');
    disparar(inp);
  }, true);
  if(!document.getElementById('bm-css')){
    const st = document.createElement('style'); st.id = 'bm-css';
    st.textContent = `.bm-chips{display:flex;flex-wrap:wrap;gap:6px;align-items:center;margin:8px 0 2px}
.bm-chip{display:inline-flex;align-items:center;gap:5px;border-radius:14px;padding:2px 9px;font-size:12px;font-weight:600;background:#e3f1e7;color:#1f6e43;border:1px solid #9cd0ae;line-height:1.6}
.bm-chip i{font-style:normal;background:#1f6e43;color:#fff;border-radius:9px;padding:0 6px;font-size:10.5px}
.bm-chip b{color:#7b8790;cursor:pointer;font-weight:700;padding:0 2px}.bm-chip b:hover{color:#b03a2e}
.bm-chip.nao{background:#fde4e1;color:#b03a2e;border-color:#f0a69c}.bm-chip.nao i{background:#b03a2e}
.bm-chip.e{background:#e3edf7;color:#1f4e79;border-color:#9fbfdf}.bm-chip.e i{background:#1f4e79}
.bm-limpa{font-size:12px;color:#1f4e79;font-weight:600;cursor:pointer;margin-left:4px;text-decoration:underline}
.bm-modo{font-size:12px;margin:6px 0 4px;display:flex;flex-wrap:wrap;gap:8px;align-items:center;color:#3a4a55}
.bm-modo span{border:1px solid #c9d3db;border-radius:12px;padding:1px 10px;cursor:pointer;background:#fff}.bm-modo span.on{background:#1f6e43;color:#fff;border-color:#1f6e43}
.bm-modo em{font-style:normal;color:#66727c;margin-left:6px}
.bm-tag{display:inline-block;font-size:10.5px;font-weight:600;color:#1f6e43;background:#e3f1e7;border-radius:8px;padding:0 6px;margin:0 0 0 4px;vertical-align:1px;white-space:nowrap}
mark.bm-mark{background:#fff2a8;color:inherit;padding:0 1px;border-radius:2px}`;
    document.head.appendChild(st);
  }
  return {norm, termos, filtrar, algum, ativo, multi, tag, pintar, realcar, rotulo, ult, modo};
})();
window.BM = BM;
