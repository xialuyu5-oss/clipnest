'use strict';
const {DownloadStore} = require('./lib/downloads');
App({
  onLaunch() { this.downloads = new DownloadStore(wx); },
  onHide() { if (this.downloads) this.downloads.pauseAll(); },
});
