
(function(){
  function ensureDashboardPanel(){
    let panel = document.getElementById('dashboardPanel');
    if (!panel) {
      panel = document.createElement('div');
      panel.id = 'dashboardPanel';
      document.body.appendChild(panel);
    }
    panel.setAttribute('aria-hidden','true');
    panel.innerHTML = '<div class="dashboard-header"><span>📊 Botnang Dashboard</span><button id="closeDashboard" type="button">×</button></div><iframe src="dashboard.html" title="Botnang dashboard"></iframe>';
  }

  function ensureBotPanel(){
    let panel = document.getElementById('botnangBotPanel');
    if (!panel) {
      panel = document.createElement('div');
      panel.id = 'botnangBotPanel';
      document.body.appendChild(panel);
    }
    panel.setAttribute('aria-hidden','true');
    panel.innerHTML = '<div class="botnang-panel-header"><span>🤖 BotnangBot</span><button class="botnang-panel-close" id="closeBotnangBot" type="button">×</button></div><div id="botnangBotContent"><div class="bot-card"><h3>BotnangBot placeholder</h3><p>This panel is ready for the live AI chatbot. In the next step it can connect to <code>server.py</code> and PostgreSQL schema <code>botnang_bot</code>.</p><p>No old scripted AI questions are included here.</p></div></div>';
  }

  function closeDashboard(){
    const p=document.getElementById('dashboardPanel');
    if(p){p.classList.remove('is-open');p.setAttribute('aria-hidden','true');}
    document.body.classList.remove('dashboard-open');
    if(window.map && map.invalidateSize) setTimeout(()=>map.invalidateSize(),250);
  }
  function openDashboard(){
    closeBot();
    const p=document.getElementById('dashboardPanel');
    if(p){p.classList.add('is-open');p.setAttribute('aria-hidden','false');}
    document.body.classList.add('dashboard-open');
    if(window.map && map.invalidateSize) setTimeout(()=>map.invalidateSize(),250);
  }
  function toggleDashboard(){
    const p=document.getElementById('dashboardPanel');
    if(p && p.classList.contains('is-open')) closeDashboard(); else openDashboard();
  }

  function closeBot(){
    const p=document.getElementById('botnangBotPanel');
    if(p){p.classList.remove('is-open');p.setAttribute('aria-hidden','true');}
    document.body.classList.remove('bot-open');
    if(window.map && map.invalidateSize) setTimeout(()=>map.invalidateSize(),250);
  }
  function openBot(){
    closeDashboard();
    const p=document.getElementById('botnangBotPanel');
    if(p){p.classList.add('is-open');p.setAttribute('aria-hidden','false');}
    document.body.classList.add('bot-open');
    if(window.map && map.invalidateSize) setTimeout(()=>map.invalidateSize(),250);
  }
  function toggleBot(){
    const p=document.getElementById('botnangBotPanel');
    if(p && p.classList.contains('is-open')) closeBot(); else openBot();
  }

  function init(){
    ensureDashboardPanel();
    ensureBotPanel();

    const dashBtn = document.getElementById('dashboardBtn');
    if(dashBtn){
      dashBtn.onclick = function(e){ e.preventDefault(); e.stopPropagation(); toggleDashboard(); };
    }
    const botBtn = document.getElementById('aiInsightsBtn') || document.getElementById('botnangBotBtn');
    if(botBtn){
      botBtn.onclick = function(e){ e.preventDefault(); e.stopPropagation(); toggleBot(); };
      botBtn.innerHTML = '🤖 BotnangBot';
    }

    const closeD = document.getElementById('closeDashboard');
    if(closeD) closeD.onclick = closeDashboard;
    const closeB = document.getElementById('closeBotnangBot');
    if(closeB) closeB.onclick = closeBot;
  }

  if(document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init);
  else init();
})();
