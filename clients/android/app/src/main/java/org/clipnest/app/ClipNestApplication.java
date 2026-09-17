// SPDX-License-Identifier: GPL-3.0-only
package org.clipnest.app;

import android.app.Application;

public final class ClipNestApplication extends Application {
    private TaskStore store;
    @Override public void onCreate() { super.onCreate(); store = new TaskStore(this); }
    public TaskStore store() { return store; }
}
