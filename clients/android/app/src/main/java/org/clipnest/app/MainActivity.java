// SPDX-License-Identifier: GPL-3.0-only
package org.clipnest.app;

import android.app.Activity;
import android.content.Intent;
import android.content.pm.PackageManager;
import android.net.Uri;
import android.os.*;
import android.webkit.*;
import androidx.webkit.*;
import org.json.JSONObject;
import java.io.*;
import java.util.Set;

public final class MainActivity extends Activity {
    private static final String ORIGIN="https://appassets.androidplatform.net";
    private WebView view;
    private File exportFile;
    private String exportJob,exportRequest;
    private JavaScriptReplyProxy exportReply;
    private boolean copyingExport;
    private String pendingSharedText;
    private boolean pageReady;
    private TaskStore store(){return ((ClipNestApplication)getApplication()).store();}
    @Override public void onCreate(Bundle saved){
        super.onCreate(saved);
        pendingSharedText=saved==null?sharedText(getIntent()):saved.getString("pendingSharedText");
        getWindow().getDecorView().setSystemUiVisibility(android.view.View.SYSTEM_UI_FLAG_LIGHT_STATUS_BAR|android.view.View.SYSTEM_UI_FLAG_LIGHT_NAVIGATION_BAR);
        if(saved!=null&&saved.containsKey("exportJob"))try{
            exportJob=saved.getString("exportJob");exportFile=store().beginExport(exportJob);
        }catch(Exception ignored){exportFile=null;}
        android.widget.FrameLayout host=new android.widget.FrameLayout(this);
        view=new WebView(this);view.setTag("clipnest-view");host.addView(view,new android.widget.FrameLayout.LayoutParams(-1,-1));setContentView(host);
        host.setOnApplyWindowInsetsListener((v,insets)->{v.setPadding(insets.getSystemWindowInsetLeft(),insets.getSystemWindowInsetTop(),insets.getSystemWindowInsetRight(),insets.getSystemWindowInsetBottom());return insets;});
        host.requestApplyInsets();
        view.getSettings().setJavaScriptEnabled(true);view.getSettings().setDomStorageEnabled(true);
        view.getSettings().setAllowFileAccess(false);view.getSettings().setAllowContentAccess(false);
        view.getSettings().setMixedContentMode(WebSettings.MIXED_CONTENT_NEVER_ALLOW);
        WebViewAssetLoader assets=new WebViewAssetLoader.Builder().addPathHandler("/assets/",new WebViewAssetLoader.AssetsPathHandler(this)).build();
        view.setWebViewClient(new WebViewClient(){
            @Override public void onPageFinished(WebView v,String url){
                if((ORIGIN+"/assets/ui/index.html").equals(url)){pageReady=true;deliverSharedText();}
            }
            @Override public WebResourceResponse shouldInterceptRequest(WebView v,WebResourceRequest r){
                if(ORIGIN.equals(r.getUrl().getScheme()+"://"+r.getUrl().getHost()))return assets.shouldInterceptRequest(r.getUrl());
                return new WebResourceResponse("text/plain","utf-8",403,"Blocked",null,new ByteArrayInputStream(new byte[0]));
            }
            @Override public boolean shouldOverrideUrlLoading(WebView v,WebResourceRequest r){return true;}
        });
        if(WebViewFeature.isFeatureSupported(WebViewFeature.WEB_MESSAGE_LISTENER)){
        WebViewCompat.addWebMessageListener(view,"ClipNestNative",java.util.Collections.singleton(ORIGIN),(v,message,origin,isMainFrame,reply)->{
            if(!isMainFrame||!ORIGIN.equals(origin.toString()))return;
            try {
                String raw=message.getData();if(raw==null||raw.length()>16384)return;
                JSONObject request=new JSONObject(raw);String id=request.getString("id"), method=request.getString("method");
                if(id.length()>80)return;JSONObject params=request.optJSONObject("params");if(params==null)params=new JSONObject();
                if(method.equals("save")){beginExport(id,params,reply);return;}
                if(method.equals("start")&&Build.VERSION.SDK_INT>=33&&checkSelfPermission("android.permission.POST_NOTIFICATIONS")!=PackageManager.PERMISSION_GRANTED)requestPermissions(new String[]{"android.permission.POST_NOTIFICATIONS"},10);
                store().call(method,params,(result,error)->runOnUiThread(()->respond(reply,id,result,error)));
            }catch(Exception ignored) { /* Ignore malformed messages from the bundled interface. */ }
        });
        }else{view.loadData("<p>Please update Android System WebView to use ClipNest.</p>","text/html","UTF-8");return;}
        view.loadUrl(ORIGIN+"/assets/ui/index.html");
    }
    static String sharedText(Intent intent){
        if(intent==null||!Intent.ACTION_SEND.equals(intent.getAction())||!"text/plain".equals(intent.getType()))return null;
        try{
            CharSequence text=intent.getCharSequenceExtra(Intent.EXTRA_TEXT);
            if(text==null||text.length()==0||text.length()>4096)return null;
            return text.toString();
        }catch(RuntimeException invalid){return null;}
    }
    @Override protected void onNewIntent(Intent intent){
        super.onNewIntent(intent);setIntent(intent);
        String text=sharedText(intent);
        if(text!=null){pendingSharedText=text;deliverSharedText();}
    }
    private void deliverSharedText(){
        if(!pageReady||view==null||pendingSharedText==null)return;
        // JSON quoting keeps shared content as data, never executable JavaScript.
        String text=pendingSharedText;pendingSharedText=null;
        view.evaluateJavascript("window.ClipNestSharedText("+JSONObject.quote(text)+")",null);
    }
    private void respond(JavaScriptReplyProxy reply,String id,Object result,Exception error){
        if(reply==null||isDestroyed())return;
        String code=error instanceof TaskStore.Problem?((TaskStore.Problem)error).code:"ENGINE_ERROR";
        if(WebViewFeature.isFeatureSupported(WebViewFeature.WEB_MESSAGE_LISTENER)){
        reply.postMessage(error==null?TaskStore.json("id",id,"result",result).toString():TaskStore.json("id",id,"error",TaskStore.json("code",code,"message",code)).toString());
        }
    }
    private void beginExport(String id,JSONObject params,JavaScriptReplyProxy reply){
        if(exportFile!=null){respond(reply,id,null,new TaskStore.Problem("FILE_IN_USE"));return;}
        boolean leased=false;
        try {
            exportJob=params.getString("id");exportFile=store().beginExport(exportJob);leased=true;exportReply=reply;exportRequest=id;
            String extension=exportFile.getName().substring(exportFile.getName().lastIndexOf('.')+1);
            Intent intent=new Intent(Intent.ACTION_CREATE_DOCUMENT).addCategory(Intent.CATEGORY_OPENABLE).setType(extension.equals("mp4")?"video/mp4":"application/octet-stream").putExtra(Intent.EXTRA_TITLE,"ClipNest-"+exportJob.substring(0,8)+"."+extension);
            startActivityForResult(intent,20);
        }catch(Exception e){if(leased)store().endExport(exportJob);exportFile=null;respond(reply,id,null,e);}
    }
    @Override protected void onActivityResult(int request,int result,Intent data){
        super.onActivityResult(request,result,data);if(request!=20||exportFile==null)return;
        File file=exportFile;String job=exportJob,id=exportRequest;JavaScriptReplyProxy reply=exportReply;
        if(result!=RESULT_OK||data==null){store().endExport(job);exportFile=null;respond(reply,id,TaskStore.json("saved",false),null);return;}
        Uri uri=data.getData();
        copyingExport=true;
        new Thread(()->{Exception failure=null;
            try(InputStream in=new FileInputStream(file);OutputStream out=getContentResolver().openOutputStream(uri,"w")){
                if(out==null)throw new IOException("Cannot open destination");TaskStore.copy(in,out);
            }catch(Exception e){failure=e;}
            store().endExport(job);Exception error=failure;runOnUiThread(()->{copyingExport=false;exportFile=null;respond(reply,id,TaskStore.json("saved",error==null),error);});
        },"clipnest-export").start();
    }
    @Override protected void onSaveInstanceState(Bundle saved){
        if(pendingSharedText!=null)saved.putString("pendingSharedText",pendingSharedText);
        if(exportFile!=null&&!copyingExport)saved.putString("exportJob",exportJob);
        super.onSaveInstanceState(saved);
    }
    @Override protected void onDestroy(){
        if(exportFile!=null&&!copyingExport)store().endExport(exportJob);
        if(view!=null){view.destroy();view=null;}super.onDestroy();
    }
}
