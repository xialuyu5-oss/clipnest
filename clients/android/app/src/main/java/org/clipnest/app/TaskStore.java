// SPDX-License-Identifier: GPL-3.0-only
package org.clipnest.app;

import android.content.Context;
import android.content.Intent;
import android.media.MediaMetadataRetriever;
import android.os.Handler;
import android.os.Looper;
import android.system.Os;
import android.system.OsConstants;
import android.util.AtomicFile;
import com.yausername.youtubedl_android.YoutubeDL;
import com.yausername.ffmpeg.FFmpeg;
import org.json.JSONArray;
import org.json.JSONObject;
import java.io.*;
import java.nio.charset.StandardCharsets;
import java.util.*;
import java.util.concurrent.*;

final class TaskStore {
    interface Reply { void done(Object value, Exception error); }
    static void copy(InputStream input,OutputStream output) throws IOException {
        byte[] buffer=new byte[65536];int length;
        while((length=input.read(buffer))!=-1)output.write(buffer,0,length);
    }
    static JSONObject json(Object... pairs) {
        JSONObject o = new JSONObject();
        try { for (int i=0;i<pairs.length;i+=2) o.put((String)pairs[i], pairs[i+1] == null ? JSONObject.NULL : pairs[i+1]); }
        catch (Exception e) { throw new IllegalArgumentException(e); }
        return o;
    }
    static final class Problem extends Exception {
        final String code;
        Problem(String code) { super(code); this.code=code; }
    }
    static final class Job {
        final Object controls = new Object();
        JSONObject data;
        volatile Process process;
        volatile int group;
        volatile String stopping = "";
        volatile boolean exporting;
        volatile Future<?> future;
        volatile CountDownLatch ended = new CountDownLatch(0);
        volatile boolean started;
        volatile Runnable finished;
        final java.util.concurrent.atomic.AtomicBoolean completed=new java.util.concurrent.atomic.AtomicBoolean();
        Job(JSONObject data) { this.data=data; }
        String id() { return data.optString("id"); }
        String state() { return data.optString("state"); }
    }
    private final Context context;
    private final File root, engine;
    private final Map<String,Job> jobs = new ConcurrentHashMap<>();
    private final Map<String,JSONObject> analyses = new ConcurrentHashMap<>();
    private final ExecutorService commands = Executors.newFixedThreadPool(3);
    private final ExecutorService queue = Executors.newSingleThreadExecutor();
    private final CompletableFuture<Void> initialized = new CompletableFuture<>();
    private final Handler main = new Handler(Looper.getMainLooper());
    TaskStore(Context context) {
        this.context=context; root=new File(context.getNoBackupFilesDir(),"tasks"); root.mkdirs();
        engine=new File(context.getFilesDir(),"engine");
        load();
        commands.execute(() -> { try {
            copyAssets("engine",engine);
            YoutubeDL.getInstance().init(context);
            FFmpeg.getInstance().init(context);
            initialized.complete(null);
        } catch(Exception e) { initialized.completeExceptionally(e); } });
    }
    private void copyAssets(String name, File out) throws IOException {
        String[] children=context.getAssets().list(name);
        if (children != null && children.length>0) {
            if (!out.isDirectory() && !out.mkdirs()) throw new IOException("Create engine directory failed");
            for(String child:children) copyAssets(name+"/"+child,new File(out,child));
        } else try(InputStream in=context.getAssets().open(name); OutputStream target=new FileOutputStream(out)) { TaskStore.copy(in,target); }
    }
    private void load() {
        File[] dirs=root.listFiles(); if(dirs==null)return;
        for(File dir:dirs) try {
            if(!dir.getName().matches("[a-f0-9]{32}"))continue;
            AtomicFile file=new AtomicFile(new File(dir,"job.json"));
            JSONObject data=new JSONObject(new String(file.readFully(),StandardCharsets.UTF_8));
            if(!dir.getName().equals(data.optString("id")))continue;
            Job job=new Job(data);
            if(Arrays.asList("queued","downloading","processing").contains(job.state())) data.put("state","paused");
            if("ready".equals(job.state()) && !mediaFile(job).isFile()) data.put("state","error").put("error_code","FILE_NOT_READY");
            jobs.put(job.id(),job); persist(job);
        } catch(Exception ignored) { /* A damaged record is never turned into an arbitrary path. */ }
    }
    private File directory(Job job) throws IOException {
        File dir=new File(root,job.id()).getCanonicalFile();
        if(!job.id().matches("[a-f0-9]{32}") || !dir.getParentFile().equals(root.getCanonicalFile())) throw new IOException("Invalid task path");
        return dir;
    }
    private void persist(Job job) throws IOException {
        File dir=directory(job); if(!dir.isDirectory() && !dir.mkdirs())throw new IOException("Create task directory failed");
        AtomicFile file=new AtomicFile(new File(dir,"job.json"));
        FileOutputStream stream=null;
        try { stream=file.startWrite(); stream.write(job.data.toString().getBytes(StandardCharsets.UTF_8)); file.finishWrite(stream); }
        catch(IOException e) { if(stream!=null)file.failWrite(stream); throw e; }
    }
    private void set(Job job,Object... values) throws Exception {
        synchronized(job) { for(int i=0;i<values.length;i+=2)job.data.put((String)values[i],values[i+1]==null?JSONObject.NULL:values[i+1]); persist(job); }
    }
    private JSONObject publicJob(Job job) throws Exception {
        synchronized(job) {
            JSONObject data=new JSONObject(job.data.toString()); data.remove("media"); data.remove("option"); data.remove("path");
            return data;
        }
    }
    void call(String method, JSONObject params, Reply reply) {
        commands.execute(() -> { try { reply.done(dispatch(method,params),null); } catch(Exception e) { reply.done(null,e); } });
    }
    private Object dispatch(String method,JSONObject p) throws Exception {
        if(method.equals("capabilities")) {
            initialized.get(120,TimeUnit.SECONDS);
            return json("schemaVersion",1,"onDevice",true,"platform","android","engine",YoutubeDL.getInstance().version(context),"pause",true,"merge",true);
        }
        if(method.equals("downloads")) {
            JSONArray items=new JSONArray(); List<Job> sorted=new ArrayList<>(jobs.values());
            sorted.sort((a,b)->Double.compare(b.data.optDouble("created_at"),a.data.optDouble("created_at")));
            for(Job job:sorted) items.put(publicJob(job)); return json("items",items);
        }
        if(method.equals("analyze")) {
            initialized.get(120,TimeUnit.SECONDS);
            String url=p.optString("url"); if(url.length()>4096)throw new Problem("INVALID_REQUEST");
            JSONObject media=runEngine(json("mode","analyze","url",url),null);
            String id=UUID.randomUUID().toString(); media.put("id",id);
            if(analyses.size()>20)analyses.clear(); analyses.put(id,media); return media;
        }
        if(method.equals("demo")) {
            initialized.get(120,TimeUnit.SECONDS);
            String id=UUID.randomUUID().toString();
            JSONObject option=json("id","demo-480","label","480p","height",480,"width",854,"source_height",480,"fps",24,"codec","h264","audio_codec","aac","has_audio",true,"container","mp4","needs_merge",false,"filesize",new File(engine,"demo-480.mp4").length(),"approximate",false);
            JSONObject media=json("id",id,"title","A little motion","platform","ClipNest demo","duration",6,"is_demo",true,"options",new JSONArray().put(option));
            analyses.put(id,media); return media;
        }
        if(method.equals("start")) {
            if(!p.optBoolean("rights_confirmed"))throw new Problem("CONSENT_REQUIRED");
            if(!p.optBoolean("download_confirmed"))throw new Problem("DOWNLOAD_CONFIRMATION_REQUIRED");
            JSONObject media=analyses.get(p.optString("analysis_id")); if(media==null)throw new Problem("ANALYSIS_EXPIRED");
            JSONObject option=null; JSONArray options=media.getJSONArray("options");
            for(int i=0;i<options.length();i++)if(options.getJSONObject(i).getString("id").equals(p.optString("option_id")))option=options.getJSONObject(i);
            if(option==null)throw new Problem("INVALID_FORMAT");
            String id=UUID.randomUUID().toString().replace("-","");
            Job job=new Job(json("id",id,"title",media.optString("title"),"platform",media.optString("platform"),"is_demo",media.optBoolean("is_demo"),"quality",option.getString("label"),"container",option.getString("container"),"state","queued","progress",0,"created_at",System.currentTimeMillis()/1000.0,"media",media,"option",option,"downloaded",0,"total",option.opt("filesize"),"eta",null,"eta_scope","track"));
            persist(job); jobs.put(id,job); launch(job); return publicJob(job);
        }
        Job job=jobs.get(p.optString("id")); if(job==null)throw new Problem("NOT_FOUND");
        synchronized(job.controls) {
        if(jobs.get(job.id())!=job)throw new Problem("NOT_FOUND");
        synchronized(job) {
            if(method.equals("resume")) {
                if(!Arrays.asList("paused","error").contains(job.state()) || job.ended.getCount()>0)throw new Problem("JOB_NOT_RESUMABLE");
                job.stopping=""; set(job,"state","queued","error_code",null,"eta",null); launch(job); return publicJob(job);
            }
        }
        if(method.equals("pause")) {
            if(!Arrays.asList("queued","downloading","paused").contains(job.state()))throw new Problem("JOB_NOT_PAUSABLE");
            stop(job,"paused"); return publicJob(job);
        }
        if(method.equals("remove")) {
            synchronized(job){if(job.exporting)throw new Problem("FILE_IN_USE");job.stopping="remove";}
            stop(job,"remove"); delete(directory(job)); jobs.remove(job.id()); return json("ok",true);
        }
        throw new Problem("INVALID_REQUEST");
        }
    }
    private void launch(Job job) {
        main.post(() -> {
            try { context.startForegroundService(new Intent(context,DownloadService.class).putExtra("id",job.id())); }
            catch(Exception e) { try { set(job,"state","error","error_code","BACKGROUND_START_FAILED"); } catch(Exception ignored){} }
        });
    }
    void enqueue(String id,Runnable finished) {
        Job job=jobs.get(id);
        if(job==null || !job.state().equals("queued") || job.ended.getCount()>0) { finished.run();return; }
        synchronized(job) {
            job.started=false;job.completed.set(false);job.finished=finished;
            job.ended=new CountDownLatch(1);
            job.future=queue.submit(() -> { try {
                synchronized(job){if(!job.stopping.isEmpty())return;job.started=true;}
                initialized.get(120,TimeUnit.SECONDS);
                set(job,"state","downloading");
                JSONObject media=job.data.getJSONObject("media"), option=job.data.getJSONObject("option");
                File file;
                if(media.optBoolean("is_demo")) {
                    file=new File(directory(job),"media.mp4");
                    try(InputStream in=new FileInputStream(new File(engine,"demo-480.mp4"));OutputStream out=new FileOutputStream(file)){TaskStore.copy(in,out);}
                } else {
                    JSONObject result=runEngine(json("mode","download","url",media.getString("url"),"selector",option.getString("_selector"),"container",option.getString("container"),"directory",directory(job).getAbsolutePath()),job);
                    file=new File(result.getString("path")).getCanonicalFile();
                    if(!file.getParentFile().equals(directory(job)))throw new IOException("Invalid output path");
                }
                if(!job.stopping.isEmpty())return;
                if(!file.isFile() || file.length()==0)throw new Problem("FILE_NOT_READY");
                MediaMetadataRetriever probe=new MediaMetadataRetriever();
                try {
                    probe.setDataSource(file.getAbsolutePath());
                    String duration=probe.extractMetadata(MediaMetadataRetriever.METADATA_KEY_DURATION);
                    if(duration==null || Long.parseLong(duration)<=0)throw new Problem("MERGE_FAILED");
                } finally {probe.release();}
                set(job,"state","ready","path",file.getName(),"container",file.getName().substring(file.getName().lastIndexOf('.')+1),"progress",100,"downloaded",file.length(),"total",file.length(),"eta",null);
            } catch(Exception e) {
                if(job.stopping.isEmpty())try {set(job,"state","error","error_code",e instanceof Problem?((Problem)e).code:"DOWNLOAD_FAILED","eta",null);}catch(Exception ignored){}
            } finally { job.process=null;job.group=0;complete(job); } });
        }
    }
    private void complete(Job job){if(job.completed.compareAndSet(false,true)){job.ended.countDown();if(job.finished!=null)job.finished.run();}}
    private JSONObject runEngine(JSONObject payload,Job job) throws Exception {
        File base=new File(context.getNoBackupFilesDir(),"youtubedl-android"), libs=new File(context.getApplicationInfo().nativeLibraryDir);
        payload.put("engine_zip",new File(base,"yt-dlp/yt-dlp").getAbsolutePath()).put("ffmpeg",new File(libs,"libffmpeg.so").getAbsolutePath()).put("quickjs",new File(libs,"libqjs.so").getAbsolutePath());
        ProcessBuilder builder=new ProcessBuilder(new File(libs,"libpython.so").getAbsolutePath(),new File(engine,"worker.py").getAbsolutePath(),payload.toString());
        Map<String,String> env=builder.environment();
        env.put("PYTHONHOME",new File(base,"packages/python/usr").getAbsolutePath());
        env.put("LD_LIBRARY_PATH",new File(base,"packages/python/usr/lib").getAbsolutePath()+":"+new File(base,"packages/ffmpeg/usr/lib").getAbsolutePath());
        env.put("SSL_CERT_FILE",new File(base,"packages/python/usr/etc/tls/cert.pem").getAbsolutePath());
        env.put("TMPDIR",context.getCacheDir().getAbsolutePath());
        env.put("PATH",env.getOrDefault("PATH","")+":"+libs.getAbsolutePath());
        Process process=builder.redirectErrorStream(true).start();
        if(job!=null)job.process=process;
        JSONObject result=null; String error="EXTRACTION_FAILED";
        ScheduledExecutorService watchdog=Executors.newSingleThreadScheduledExecutor();
        ScheduledFuture<?> timeout=job==null?watchdog.schedule(process::destroy,120,TimeUnit.SECONDS):null;
        try(BufferedReader reader=new BufferedReader(new InputStreamReader(process.getInputStream(),StandardCharsets.UTF_8))) {
            String line;
            while((line=reader.readLine())!=null) {
                if(!line.startsWith("{"))continue;
                JSONObject event;try{event=new JSONObject(line);}catch(Exception ignored){continue;}
                switch(event.optString("event")) {
                    case "process": if(job!=null){job.group=event.getInt("pid");if(!job.stopping.isEmpty())signal(job);}break;
                    case "result": result=event.getJSONObject("result");break;
                    case "error": error=event.optString("code",error);break;
                    case "processing": if(job!=null && job.stopping.isEmpty())set(job,"state","processing","eta",null);break;
                    case "progress": if(job!=null && job.stopping.isEmpty())set(job,"state","downloading","downloaded",event.opt("downloaded"),"total",event.opt("total"),"progress",event.opt("progress"),"speed",event.opt("speed"),"eta",event.opt("eta"));break;
                }
            }
            if(process.waitFor()!=0 || result==null)throw new Problem(error);
            return result;
        } finally {
            if(timeout!=null)timeout.cancel(false);watchdog.shutdownNow();
            if(job!=null&&!job.stopping.isEmpty()&&job.group>0)try{Os.kill(-job.group,OsConstants.SIGKILL);}catch(Exception ignored){}
            if(process.isAlive())process.destroyForcibly();
        }
    }
    private void signal(Job job) {
        if(job.group>0)try{Os.kill(-job.group,OsConstants.SIGTERM);}catch(Exception ignored){}
        if(job.process!=null)job.process.destroy();
    }
    private void stop(Job job,String reason) throws Exception {
        synchronized(job){job.stopping=reason;signal(job);if(!job.started&&job.future!=null&&job.future.cancel(false))complete(job);}
        int group=job.group;
        if(!job.ended.await(6,TimeUnit.SECONDS)) {
            if(job.group>0)try{Os.kill(-job.group,OsConstants.SIGKILL);}catch(Exception ignored){}
            if(job.process!=null)job.process.destroyForcibly();
            if(!job.ended.await(4,TimeUnit.SECONDS))throw new Problem("CLEANUP_FAILED");
        }
        // A terminated parent can leave a media-tool descendant alive. The
        // dedicated group belongs to this task; end it before deleting cache.
        if(group>0)try{Os.kill(-group,OsConstants.SIGKILL);}catch(Exception ignored){}
        set(job,"state","paused","eta",null,"speed",null);
    }
    void pauseAll(Runnable finished) {
        commands.execute(()->{for(Job job:jobs.values())synchronized(job.controls){if(jobs.get(job.id())==job&&Arrays.asList("queued","downloading","processing").contains(job.state()))try{stop(job,"paused");}catch(Exception ignored){}}finished.run();});
    }
    private void delete(File target) throws IOException {
        File actual=target.getCanonicalFile(), boundary=root.getCanonicalFile();
        if(!actual.toPath().startsWith(boundary.toPath()) || actual.equals(boundary))throw new IOException("Invalid cleanup scope");
        File[] children=actual.listFiles();if(children!=null)for(File child:children)delete(child);
        if(actual.exists()&&!actual.delete())throw new IOException("Cache cleanup failed");
    }
    private File mediaFile(Job job) throws IOException {
        File path=new File(directory(job),job.data.optString("path","missing")).getCanonicalFile();
        if(!path.getParentFile().equals(directory(job)))throw new IOException("Invalid file path");return path;
    }
    File beginExport(String id) throws Exception {
        Job job=jobs.get(id);if(job==null||!job.state().equals("ready"))throw new Problem("FILE_NOT_READY");
        synchronized(job){if(job.exporting||!job.stopping.isEmpty())throw new Problem("FILE_IN_USE");File path=mediaFile(job);job.exporting=true;return path;}
    }
    void endExport(String id){Job job=jobs.get(id);if(job!=null)job.exporting=false;}
}
