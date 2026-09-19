// SPDX-License-Identifier: GPL-3.0-only
package org.clipnest.app;

import android.content.Context;
import android.content.Intent;
import android.test.InstrumentationTestCase;
import org.json.JSONObject;
import java.io.*;
import java.lang.reflect.Method;
import java.nio.charset.StandardCharsets;
import java.util.concurrent.*;

public class DeviceSmokeTest extends InstrumentationTestCase {
    private TaskStore store;
    private Context context;
    private MainActivity activity;
    @Override protected void setUp() throws Exception {
        super.setUp();context=getInstrumentation().getTargetContext();
        activity=(MainActivity)getInstrumentation().startActivitySync(new Intent(context,MainActivity.class).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK|Intent.FLAG_ACTIVITY_CLEAR_TASK));
        store=((ClipNestApplication)context.getApplicationContext()).store();
        call("capabilities",new JSONObject());
    }
    @Override protected void tearDown() throws Exception {
        if(activity!=null)getInstrumentation().runOnMainSync(activity::finish);
        super.tearDown();
    }
    private String javascript(String script) throws Exception {
        CompletableFuture<String> result=new CompletableFuture<>();
        getInstrumentation().runOnMainSync(()->{
            android.view.ViewGroup content=activity.findViewById(android.R.id.content);
            ((android.webkit.WebView)content.findViewWithTag("clipnest-view")).evaluateJavascript(script,result::complete);
        });return result.get(10,TimeUnit.SECONDS);
    }
    public void testBundledInterfaceAndLanguageSwitch() throws Exception {
        for(int i=0;i<100&&!"true".equals(javascript("!!window.ClipNestClient && !!window.ClipNestI18n"));i++)Thread.sleep(100);
        assertEquals("true",javascript("!!window.ClipNestNative"));
        assertEquals("true",javascript("document.documentElement.scrollWidth <= innerWidth"));
        javascript("document.getElementById('demo').click()");
        for(int i=0;i<100&&"true".equals(javascript("document.getElementById('result').hidden"));i++)Thread.sleep(100);
        assertEquals("false",javascript("document.getElementById('result').hidden"));
        for(String locale:new String[]{"de","ar","zh-CN"}){
            javascript("ClipNestI18n.setLocale('"+locale+"')");
            assertEquals("true",javascript("document.documentElement.scrollWidth <= innerWidth"));
        }
        javascript("ClipNestI18n.setLocale('en')");
    }
    private JSONObject call(String method,JSONObject args) throws Exception {
        CompletableFuture<JSONObject> future=new CompletableFuture<>();
        store.call(method,args,(result,error)->{if(error!=null)future.completeExceptionally(error);else future.complete((JSONObject)result);});
        return future.get(150,TimeUnit.SECONDS);
    }
    public void testShareRequiresUserAction() throws Exception {
        for(int i=0;i<100&&!"true".equals(javascript("!!window.ClipNestSharedText"));i++)Thread.sleep(100);
        int before=call("downloads",new JSONObject()).getJSONArray("items").length();
        Intent share=new Intent(Intent.ACTION_SEND).setType("text/plain")
            .putExtra(Intent.EXTRA_TEXT,"Watch this https://www.youtube.com/watch?v=abc");
        getInstrumentation().runOnMainSync(()->activity.onNewIntent(share));
        getInstrumentation().waitForIdleSync();
        assertEquals("\"https://www.youtube.com/watch?v=abc\"",javascript("document.getElementById('url').value"));
        assertEquals("true",javascript("document.getElementById('result').hidden"));
        assertEquals(before,call("downloads",new JSONObject()).getJSONArray("items").length());
        javascript("document.getElementById('demo').click()");
        for(int i=0;i<100&&"true".equals(javascript("document.getElementById('result').hidden"));i++)Thread.sleep(100);
        assertEquals("false",javascript("document.getElementById('result').hidden"));
        javascript("document.getElementById('consent').checked=true;document.getElementById('start').click()");
        assertEquals("true",javascript("document.getElementById('confirm').open"));
        getInstrumentation().runOnMainSync(()->activity.onNewIntent(share));
        assertEquals("false",javascript("document.getElementById('confirm').open"));
        assertEquals("true",javascript("document.getElementById('result').hidden"));
        assertEquals("false",javascript("document.getElementById('consent').checked"));
        Intent injection=new Intent(Intent.ACTION_SEND).setType("text/plain")
            .putExtra(Intent.EXTRA_TEXT,"\");window.shareInjected=true;//");
        getInstrumentation().runOnMainSync(()->activity.onNewIntent(injection));
        assertEquals("false",javascript("!!window.shareInjected"));
        assertNull(MainActivity.sharedText(new Intent(Intent.ACTION_SEND).setType("image/png").putExtra(Intent.EXTRA_TEXT,"https://vimeo.com/1")));
        assertNull(MainActivity.sharedText(new Intent(Intent.ACTION_SEND).setType("text/plain").putExtra(Intent.EXTRA_TEXT,new String(new char[4097]))));
    }
    public void testNativeEngineAndLocalMedia() throws Exception {
        JSONObject capabilities=call("capabilities",new JSONObject());assertTrue(capabilities.getBoolean("onDevice"));
        try {call("analyze",TaskStore.json("url","https://example.com/not-a-platform"));fail("Unsupported source accepted");}
        catch(ExecutionException e){assertTrue(e.getCause() instanceof TaskStore.Problem);assertEquals("UNSUPPORTED_SITE",((TaskStore.Problem)e.getCause()).code);}
        JSONObject media=call("demo",new JSONObject());
        try {call("start",TaskStore.json("analysis_id",media.getString("id"),"option_id","demo-480"));fail("Consent skipped");}
        catch(ExecutionException e){assertEquals("CONSENT_REQUIRED",((TaskStore.Problem)e.getCause()).code);}
        JSONObject job=call("start",TaskStore.json("analysis_id",media.getString("id"),"option_id","demo-480","rights_confirmed",true,"download_confirmed",true));
        JSONObject current=null;
        for(int i=0;i<100;i++){
            current=call("downloads",new JSONObject()).getJSONArray("items").getJSONObject(0);
            if(current.getString("state").equals("ready")||current.getString("state").equals("error"))break;
            Thread.sleep(100);
        }
        assertEquals(current.toString(),"ready",current.getString("state"));
        File saved=store.beginExport(job.getString("id"));assertTrue(saved.length()>1000);store.endExport(job.getString("id"));
        call("remove",TaskStore.json("id",job.getString("id")));assertFalse(saved.exists());
        assertEquals(0,call("downloads",new JSONObject()).getJSONArray("items").length());
    }
    public void testPackagedPythonDownloaderAndFFmpeg() throws Exception {
        File scripts=new File(context.getFilesDir(),"engine"), base=new File(context.getNoBackupFilesDir(),"youtubedl-android");
        File nativeDir=new File(context.getApplicationInfo().nativeLibraryDir), testDir=new File(context.getCacheDir(),"engine-test");testDir.mkdirs();
        File script=new File(testDir,"test.py");
        String source="import sys, os, threading, http.server, functools, hashlib, subprocess\n"+
            "sys.path.insert(0,sys.argv[1])\nimport yt_dlp\n"+
            "sample, target, ffmpeg = sys.argv[2:]\n"+
            "handler=functools.partial(http.server.SimpleHTTPRequestHandler,directory=os.path.dirname(sample))\n"+
            "server=http.server.ThreadingHTTPServer(('127.0.0.1',0),handler)\n"+
            "threading.Thread(target=server.serve_forever,daemon=True).start()\n"+
            "output=os.path.join(target,'download.mp4')\n"+
            "with yt_dlp.YoutubeDL({'quiet':True,'outtmpl':output}) as y: y.download(['http://127.0.0.1:%s/%s'%(server.server_port,os.path.basename(sample))])\n"+
            "assert hashlib.sha256(open(output,'rb').read()).digest()==hashlib.sha256(open(sample,'rb').read()).digest()\n"+
            "v=os.path.join(target,'v.mp4'); a=os.path.join(target,'a.m4a'); merged=os.path.join(target,'merged.mp4')\n"+
            "for command in [[ffmpeg,'-y','-i',output,'-map','0:v:0','-c','copy',v],[ffmpeg,'-y','-i',output,'-map','0:a:0','-c','copy',a],[ffmpeg,'-y','-i',v,'-i',a,'-map','0:v:0','-map','1:a:0','-c','copy',merged]]: subprocess.run(command,check=True,stdout=subprocess.DEVNULL,stderr=subprocess.PIPE)\n"+
            "assert os.path.getsize(merged)>1000\nserver.shutdown()\nprint('ENGINE_FIXTURE_OK')\n";
        try(FileOutputStream out=new FileOutputStream(script)){out.write(source.getBytes(StandardCharsets.UTF_8));}
        ProcessBuilder builder=new ProcessBuilder(new File(nativeDir,"libpython.so").getAbsolutePath(),script.getAbsolutePath(),new File(base,"yt-dlp/yt-dlp").getAbsolutePath(),new File(scripts,"demo-480.mp4").getAbsolutePath(),testDir.getAbsolutePath(),new File(nativeDir,"libffmpeg.so").getAbsolutePath());
        builder.environment().put("PYTHONHOME",new File(base,"packages/python/usr").getAbsolutePath());
        builder.environment().put("LD_LIBRARY_PATH",new File(base,"packages/python/usr/lib").getAbsolutePath()+":"+new File(base,"packages/ffmpeg/usr/lib").getAbsolutePath());
        builder.environment().put("SSL_CERT_FILE",new File(base,"packages/python/usr/etc/tls/cert.pem").getAbsolutePath());
        Process process=builder.redirectErrorStream(true).start();
        ByteArrayOutputStream capture=new ByteArrayOutputStream();
        Thread reader=new Thread(()->{try{process.getInputStream().transferTo(capture);}catch(Exception ignored){}});reader.start();
        assertTrue("Engine fixture timed out",process.waitFor(60,TimeUnit.SECONDS));reader.join(3000);
        String output=capture.toString("UTF-8");assertEquals(output,0,process.exitValue());assertTrue(output,output.contains("ENGINE_FIXTURE_OK"));
        try(android.media.MediaMetadataRetriever probe=new android.media.MediaMetadataRetriever()){
            probe.setDataSource(new File(testDir,"merged.mp4").getAbsolutePath());
            assertEquals("yes",probe.extractMetadata(android.media.MediaMetadataRetriever.METADATA_KEY_HAS_AUDIO));
            assertEquals("yes",probe.extractMetadata(android.media.MediaMetadataRetriever.METADATA_KEY_HAS_VIDEO));
        }
    }
}
