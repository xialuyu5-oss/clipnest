// SPDX-License-Identifier: GPL-3.0-only
package org.clipnest.app;

import android.app.*;
import android.content.Intent;
import android.os.*;
import java.util.concurrent.atomic.AtomicInteger;

public final class DownloadService extends Service {
    private final AtomicInteger active=new AtomicInteger();
    private PowerManager.WakeLock wake;
    private final Handler handler=new Handler(Looper.getMainLooper());
    // Renew only while this foreground service owns work. This is a wake-lock
    // lease, not a download duration limit; a stopped service cannot renew it.
    private final Runnable renew=new Runnable(){public void run(){if(wake!=null){wake.acquire(10*60*1000L);handler.postDelayed(this,5*60*1000L);}}};
    private TaskStore store(){return ((ClipNestApplication)getApplication()).store();}
    @Override public void onCreate(){
        super.onCreate();
        NotificationManager manager=getSystemService(NotificationManager.class);
        manager.createNotificationChannel(new NotificationChannel("downloads","Downloads",NotificationManager.IMPORTANCE_LOW));
        PendingIntent open=PendingIntent.getActivity(this,0,new Intent(this,MainActivity.class),PendingIntent.FLAG_IMMUTABLE|PendingIntent.FLAG_UPDATE_CURRENT);
        startForeground(1,new Notification.Builder(this,"downloads").setSmallIcon(R.drawable.ic_clipnest).setContentTitle("ClipNest")
            .setContentText("Downloading on this device · Open to pause or cancel").setContentIntent(open).setOngoing(true).build());
        wake=getSystemService(PowerManager.class).newWakeLock(PowerManager.PARTIAL_WAKE_LOCK,"ClipNest:download");wake.setReferenceCounted(false);renew.run();
    }
    @Override public int onStartCommand(Intent intent,int flags,int startId){
        if(intent==null){stopSelf();return START_NOT_STICKY;}
        active.incrementAndGet();store().enqueue(intent.getStringExtra("id"),()->{
            if(active.decrementAndGet()==0)new Handler(Looper.getMainLooper()).post(()->{if(active.get()==0)stopSelf();});
        });return START_NOT_STICKY;
    }
    @Override public void onTimeout(int startId,int fgsType){store().pauseAll(()->{stopForeground(STOP_FOREGROUND_REMOVE);stopSelf();});}
    @Override public void onDestroy(){handler.removeCallbacks(renew);if(wake!=null&&wake.isHeld())wake.release();wake=null;super.onDestroy();}
    @Override public IBinder onBind(Intent intent){return null;}
}
