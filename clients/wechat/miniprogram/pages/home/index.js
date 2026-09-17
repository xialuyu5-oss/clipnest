'use strict';
const core=require('../../lib/core');
const direct=require('../../lib/direct');
const catalogs=require('../../lib/catalogs');
const languages={en:'English','zh-CN':'简体中文','zh-TW':'繁體中文',ja:'日本語',ko:'한국어',es:'Español',fr:'Français',de:'Deutsch',pt:'Português',ru:'Русский',ar:'العربية',hi:'हिन्दी'};
const labels={onDevice:'On-device',hero:'Keep the videos',heroAccent:'you love.',start:'Start with a video link',analyze:'Analyze video',downloads:'Downloads',duration:'Video duration',size:'File size',estimate:'Estimated download time',confirm:'Confirm download',cancel:'Cancel',pause:'Pause',resume:'Resume',save:'Save file',remove:'Cancel download',rights:'I have permission to download or use this video and will follow the source platform\'s terms.',preview:'Direct MP4 preview',resumeSource:'Source advertises resume',restartSource:'Continuing after pause restarts the download',storage:'Mini Program storage note',estimateNote:'Direct link estimate note'};
const states={queued:'Queued',downloading:'Downloading',paused:'Paused',ready:'Ready to save',error:'Failed'};
Page({
  data:{url:'',busy:false,media:null,rights:false,jobs:[],error:'',locale:'en',languageIndex:0,languageNames:Object.values(languages),text:{},confirmation:false},
  onLoad(){
    this.store=getApp().downloads;
    const stored=wx.getStorageSync('clipnest_language');this.setLanguage(languages[stored]?stored:'en');
    this.unsubscribe=this.store.on(()=>this.renderJobs());this.renderJobs();
  },
  onShow(){if(this.store)this.renderJobs();},
  onUnload(){if(this.unsubscribe)this.unsubscribe();},
  t(key){return (catalogs[this.data.locale]||catalogs.en)[key]||catalogs.en[key]||key;},
  setLanguage(locale){const text={};Object.keys(labels).forEach(k=>text[k]=this.tFor(locale,labels[k]));this.setData({locale,text,languageIndex:Object.keys(languages).indexOf(locale)});wx.setStorageSync('clipnest_language',locale);this.renderJobs();},
  tFor(locale,key){return (catalogs[locale]||catalogs.en)[key]||catalogs.en[key]||key;},
  language(e){this.setLanguage(Object.keys(languages)[Number(e.detail.value)]);},
  input(e){this.setData({url:e.detail.value});},
  rights(e){this.setData({rights:e.detail.value.length>0});},
  fail(error){const code=error.code||'DOWNLOAD_FAILED';this.setData({error:this.t(['DIRECT_MP4_REQUIRED','HTTPS_REQUIRED'].includes(code)?'Direct MP4 preview':'Device operation failed')+' ('+code+')'});},
  async analyze(){
    if(this.data.busy)return;this.setData({busy:true,error:'',media:null,rights:false});
    try{const media=await direct.analyze(wx,this.data.url),option=media.options[0];this.setData({media,mediaSize:core.bytes(option.filesize),mediaDuration:core.duration(media.duration),mediaDetails:[option.width&&option.source_height?option.width+' × '+option.source_height:'',option.fps?option.fps+' fps':this.t('Frame rate unknown'),option.codec||'unknown',option.audio_codec||this.t(option.has_audio===false?'No audio':'Audio unknown')].filter(Boolean).join(' · ')});}
    catch(e){this.fail(e);}finally{this.setData({busy:false});}
  },
  review(){
    if(!this.data.rights){this.fail({code:'CONSENT_REQUIRED'});return;}
    const media=this.data.media,c=core.confirmation(media,media.options[0]);
    this.setData({confirmation:true,summary:{duration:core.duration(c.duration),size:core.bytes(c.bytes),time:c.secondsMin===null?'—':core.duration(c.secondsMin)+' – '+core.duration(c.secondsMax)+' (1–10 MB/s)'}});
  },
  close(){this.setData({confirmation:false});},
  start(){try{this.store.start(this.data.media,this.data.media.options[0],{rights_confirmed:this.data.rights,download_confirmed:true});this.close();this.renderJobs();}catch(e){this.fail(e);}},
  renderJobs(){
    if(!this.store)return;
    const jobs=this.store.list().map(j=>({...j,stateLabel:this.t(states[j.state]||j.state),actions:core.actions(j.state),
      size:core.bytes(j.ranges||j.state==='ready'?j.downloaded:j.transferred)+' / '+core.bytes(j.total),remaining:j.eta==null?this.t('Estimating remaining time…'):this.t('About {time} left').replace('{time}',core.duration(j.eta))}));this.setData({jobs});
  },
  async action(e){
    const {action,id}=e.currentTarget.dataset;
    try{if(!['pause','resume','remove','save'].includes(action))return;
      if(action==='save'){await this.store.save(id);wx.showToast({title:this.t('Saved'),icon:'success'});
      }else await this.store[action](id);
    }catch(error){this.fail(error);}
  },
});
