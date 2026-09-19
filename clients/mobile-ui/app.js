/* SPDX-License-Identifier: MIT */
'use strict';
(() => {
  const $ = id => document.getElementById(id), core = window.ClipNestCore, i18n = window.ClipNestI18n;
  const t = (key,params) => i18n.t(key,params), api = window.ClipNestClient;
  let media=null, selected=null, jobItems=[], polling=false, working=false;
  let analysisSequence=0;
  const states={queued:'Queued',downloading:'Downloading',processing:'Merging / checking',paused:'Paused',ready:'Ready to save',error:'Failed'};
  function node(tag,text,cls){const n=document.createElement(tag);if(text!=null)n.textContent=text;if(cls)n.className=cls;return n;}
  function notify(error){$('notice').textContent=error ? t('Device operation failed') + (error.code ? ' (' + error.code + ')' : '') : '';}
  window.ClipNestSharedText=text=>{
    try{
      const link=core.validateLink(text);
      analysisSequence++;media=null;selected=null;$('result').hidden=true;$('consent').checked=false;
      if($('confirm').open)$('confirm').close();
      $('url').value=link.url;
      // External shares only prefill. Network work requires the user's Analyze action.
      $('url').focus();notify();
    }catch(error){notify(error);}
  };
  function audio(o){return o.has_audio === true ? o.audio_codec || t('With audio') : o.has_audio === false ? t('No audio') : t('Audio unknown');}
  function renderMedia(){
    if(!media)return;
    $('result').hidden=false; $('title').textContent=media.title;
    $('meta').textContent=media.platform+' · '+core.duration(media.duration)+(media.is_demo?' · '+t('Demo · Not a platform download'):'');
    $('qualities').replaceChildren(...media.options.map(o=>{
      const b=node('button',null,'quality');b.type='button';b.setAttribute('role','radio');b.setAttribute('aria-checked',String(o.id===selected));
      b.append(node('strong',o.label),node('small',`${o.width} × ${o.source_height} · ${o.fps?o.fps+' fps':t('Frame rate unknown')}`),node('small',`${o.container.toUpperCase()} · ${o.codec} · ${audio(o)}`),node('small',(o.approximate?'≈ ':'')+core.bytes(o.filesize)));
      b.onclick=()=>{selected=o.id;renderMedia();};return b;
    }));
  }
  function renderJobs(){
    if(!jobItems.length){$('jobs').replaceChildren(node('p',t('Paste a link and choose a quality. Your downloads will appear here.'),'hint'));return;}
    $('jobs').replaceChildren(...jobItems.map(job=>{
      const item=node('article',null,'job'), state=t(states[job.state]||job.state);
      item.append(node('h3',job.title),node('p',`${job.quality} · ${job.container.toUpperCase()} · ${state}`,'hint'));
      if(['downloading','processing','queued'].includes(job.state)){
        const bar=document.createElement('progress');bar.max=100;if(job.progress!=null)bar.value=job.progress;bar.setAttribute('aria-label',state);item.append(bar);
      }
      if(job.state==='downloading')item.append(node('p',core.bytes(job.downloaded)+' / '+core.bytes(job.total)+' · '+(job.eta==null?t('Estimating remaining time…'):t(job.eta_scope==='track'?'Current track: about {time} left':'About {time} left',{time:core.duration(job.eta)})),'hint'));
      if(job.error_code)item.append(node('p',job.error_code));
      const buttons=node('div',null,'actions'), allowed=core.actions(job.state);
      for(const [action,label] of [['pause','Pause'],['resume','Resume'],['save','Save file'],['remove',job.state==='ready'?'Delete task and temporary files':'Cancel download']]){
        if(!allowed[action])continue;
        const b=node('button',t(label),action==='save'?'':'quiet');
        b.onclick=async()=>{b.disabled=true;try{await api.call(action,{id:job.id});await refresh();}catch(e){notify(e);}finally{b.disabled=false;}};buttons.append(b);
      }
      item.append(buttons);return item;
    }));
  }
  async function refresh(){if(polling)return;polling=true;try{jobItems=(await api.call('downloads')).items;renderJobs();}finally{polling=false;}}
  async function analyze(demo){
    if(working)return;working=true;$('analyze').disabled=$('demo').disabled=true;notify();
    const sequence=++analysisSequence;
    try{const result=await api.call(demo?'demo':'analyze',demo?{}:core.validateLink($('url').value));if(sequence!==analysisSequence)return;media=result;selected=media.options[0]?.id;$('consent').checked=false;renderMedia();}
    catch(e){if(sequence===analysisSequence)notify(e);}finally{working=false;$('analyze').disabled=$('demo').disabled=false;}
  }
  $('analyze-form').onsubmit=e=>{e.preventDefault();analyze(false);};$('demo').onclick=()=>analyze(true);
  $('refresh').onclick=()=>refresh().catch(notify);
  $('start').onclick=()=>{
    if(!media||!$('consent').checked){notify({code:'CONSENT_REQUIRED',message:t('I have permission to download or use this video and will follow the source platform\'s terms.')});return;}
    const option=media.options.find(o=>o.id===selected), c=core.confirmation(media,option);
    const rows=[['Video duration',core.duration(c.duration)],['File size',core.bytes(c.bytes)],['Estimated download time',c.secondsMin==null?'—':core.duration(c.secondsMin)+' – '+core.duration(c.secondsMax)+' (1–10 MB/s)']];
    $('summary').replaceChildren(...rows.flatMap(([k,v])=>[node('dt',t(k)),node('dd',v)]));$('confirm').showModal();
  };
  $('no').onclick=()=>$('confirm').close();
  $('yes').onclick=async()=>{
    $('yes').disabled=true;
    try{await api.call('start',{analysis_id:media.id,option_id:selected,rights_confirmed:$('consent').checked,download_confirmed:true});$('confirm').close();await refresh();}
    catch(e){notify(e);$('confirm').close();}finally{$('yes').disabled=false;}
  };
  for(const [code,label] of Object.entries(i18n.languages)){const o=node('option',label);o.value=code;$('language').append(o);}
  $('language').value=i18n.locale;$('language').onchange=()=>i18n.setLocale($('language').value);
  document.addEventListener('clipnest:languagechange',()=>{renderMedia();renderJobs();});
  api.call('capabilities').then(c=>{i18n.text($('engine'),'On-device');$('engine').title='Android · '+(c.engine||'yt-dlp');return refresh();}).catch(notify);
  setInterval(()=>{if(!document.hidden)refresh().catch(()=>{});},1500);
})();
