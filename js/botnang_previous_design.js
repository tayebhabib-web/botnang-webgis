/* Previous-style dynamic panel: opens like old design */
(function(){
  function byId(id){ return document.getElementById(id); }

  function getMainState(){
    let scenario='baseline', year='2025';
    if(window.botnangScenarioState){
      if(window.botnangScenarioState.scenario) scenario=window.botnangScenarioState.scenario;
      if(window.botnangScenarioState.year) year=String(window.botnangScenarioState.year);
    }
    const yCurrent=byId('yearCurrent');
    if(yCurrent && yCurrent.textContent) year=yCurrent.textContent.trim();
    const ySelect=byId('yearSelect');
    if(ySelect && ySelect.value) year=String(ySelect.value);
    const active=document.querySelector('#scenarioButtons button.active,.scenario-btn.active');
    if(active && active.dataset.value) scenario=active.dataset.value;
    const sSelect=byId('scenarioSelect');
    if(sSelect && sSelect.value) scenario=sSelect.value;
    return {scenario,year};
  }
  function dashboardUrl(){
    const s=getMainState();
    return 'dashboard.html?scenario='+encodeURIComponent(s.scenario)+'&year='+encodeURIComponent(s.year);
  }
  function syncDashboard(){
    const iframe=document.querySelector('#dashboardPanel iframe');
    if(!iframe) return;
    const s=getMainState();
    try{ iframe.contentWindow.postMessage({type:'botnang-forecast-sync',scenario:s.scenario,year:String(s.year)},'*'); }
    catch(e){ iframe.src=dashboardUrl(); }
  }

  function ensureButtons(){
    let d=byId('dashboardBtn');
    if(!d){ d=document.createElement('button'); d.id='dashboardBtn'; d.type='button'; document.body.appendChild(d); }
    d.classList.add('right-action-btn'); d.innerHTML='📊 Dashboard';
    let b=byId('botnangBotBtn')||byId('aiInsightsBtn');
    if(!b){ b=document.createElement('button'); b.id='botnangBotBtn'; b.type='button'; document.body.appendChild(b); }
    b.id='botnangBotBtn'; b.classList.add('right-action-btn'); b.innerHTML='🤖 BotnangBot';
    return {d,b};
  }
  function buildPanels(){
    let dp=byId('dashboardPanel');
    if(!dp){ dp=document.createElement('div'); dp.id='dashboardPanel'; document.body.appendChild(dp); }
    dp.className='botnang-side-panel';
    dp.innerHTML='<div class="botnang-panel-header"><span>📊 Botnang Dashboard</span><button id="closeDashboard" class="botnang-panel-close" type="button">×</button></div><iframe src="'+dashboardUrl()+'" title="Botnang dashboard"></iframe>';

    let bp=byId('botnangBotPanel')||byId('aiInsightsPanel');
    if(!bp){ bp=document.createElement('div'); bp.id='botnangBotPanel'; document.body.appendChild(bp); }
    bp.id='botnangBotPanel'; bp.className='botnang-side-panel';
    bp.innerHTML='<div class="botnang-panel-header"><span>🤖 BotnangBot</span><button id="closeBotnangBot" class="botnang-panel-close" type="button">×</button></div><div class="botnang-bot-content"><div class="botnang-bot-card"><h3>BotnangBot placeholder</h3><p>This panel is ready for the live AI chatbot.</p><p>No old scripted AI questions are included.</p><p>Next step: connect to <code>server.py</code> and PostgreSQL schema <code>botnang_bot</code>.</p></div></div>';
  }
  function closeDashboard(){ const p=byId('dashboardPanel'); if(p)p.classList.remove('is-open'); document.body.classList.remove('dashboard-open'); if(window.map&&map.invalidateSize)setTimeout(()=>map.invalidateSize(),250); }
  function closeBot(){ const p=byId('botnangBotPanel'); if(p)p.classList.remove('is-open'); document.body.classList.remove('bot-open'); if(window.map&&map.invalidateSize)setTimeout(()=>map.invalidateSize(),250); }
  function openDashboard(){ closeBot(); const p=byId('dashboardPanel'); if(p)p.classList.add('is-open'); document.body.classList.add('dashboard-open'); syncDashboard(); if(window.map&&map.invalidateSize)setTimeout(()=>map.invalidateSize(),250); }
  function openBot(){ closeDashboard(); const p=byId('botnangBotPanel'); if(p)p.classList.add('is-open'); document.body.classList.add('bot-open'); if(window.map&&map.invalidateSize)setTimeout(()=>map.invalidateSize(),250); }

  function init(){
    buildPanels();
    const btns=ensureButtons();
    btns.d.addEventListener('click',function(e){ e.preventDefault(); e.stopImmediatePropagation(); const p=byId('dashboardPanel'); if(p&&p.classList.contains('is-open')) closeDashboard(); else openDashboard(); },true);
    btns.b.addEventListener('click',function(e){ e.preventDefault(); e.stopImmediatePropagation(); const p=byId('botnangBotPanel'); if(p&&p.classList.contains('is-open')) closeBot(); else openBot(); },true);
    const cd=byId('closeDashboard'); if(cd) cd.addEventListener('click',closeDashboard,true);
    const cb=byId('closeBotnangBot'); if(cb) cb.addEventListener('click',closeBot,true);
    document.addEventListener('click',()=>setTimeout(syncDashboard,80),true);
    document.addEventListener('input',()=>setTimeout(syncDashboard,80),true);
    document.addEventListener('change',()=>setTimeout(syncDashboard,80),true);
    setInterval(()=>{ if(document.body.classList.contains('dashboard-open')) syncDashboard(); },800);
  }
  if(document.readyState==='loading') document.addEventListener('DOMContentLoaded',init); else init();
})();
