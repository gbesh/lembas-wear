package com.middleearth.lembas.wear

import android.app.Activity
import android.app.PendingIntent
import android.app.job.JobInfo
import android.app.job.JobParameters
import android.app.job.JobScheduler
import android.app.job.JobService
import android.content.BroadcastReceiver
import android.content.ComponentName
import android.content.Context
import android.content.Intent
import android.content.pm.PackageInstaller
import android.os.Build
import android.os.Handler
import android.os.Looper
import android.widget.Toast
import org.json.JSONObject
import java.io.File
import java.net.HttpURLConnection
import java.net.URL
import java.util.concurrent.TimeUnit

/**
 * Keeps Lembas on the watch up to date from the public GitHub releases: the watch app itself
 * (lembas-wear.apk) and the watch face (lembas-watchface.apk). It checks once a day, only while
 * the watch is charging, so it never costs battery during the day.
 */
object WearUpdater {
    private const val API = "https://api.github.com/repos/gbesh/lembas-wear/releases/latest"
    const val FACE_PACKAGE = "com.middleearth.launcher.watchface"
    private const val JOB_ID = 0x1e3bb6

    @Volatile var pendingConfirm: Intent? = null

    fun versionName(ctx: Context): String = try {
        ctx.packageManager.getPackageInfo(ctx.packageName, 0).versionName ?: "?"
    } catch (_: Exception) { "?" }

    private fun versionCode(ctx: Context, pkg: String): Long = try {
        val i = ctx.packageManager.getPackageInfo(pkg, 0)
        if (Build.VERSION.SDK_INT >= 28) i.longVersionCode else @Suppress("DEPRECATION") i.versionCode.toLong()
    } catch (_: Exception) { -1 }

    fun schedule(ctx: Context) {
        try {
            val js = ctx.getSystemService(JobScheduler::class.java) ?: return
            if (js.getPendingJob(JOB_ID) != null) return
            js.schedule(JobInfo.Builder(JOB_ID, ComponentName(ctx, UpdateJob::class.java))
                .setRequiredNetworkType(JobInfo.NETWORK_TYPE_ANY)
                .setRequiresCharging(true)
                .setPeriodic(TimeUnit.HOURS.toMillis(24))
                .setPersisted(true)
                .build())
        } catch (_: Throwable) { }
    }

    fun showPending(activity: Activity) {
        val i = pendingConfirm ?: return
        pendingConfirm = null
        try { activity.startActivity(i.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)) } catch (_: Exception) { }
    }

    /** From the app's "Watch face & updates" button: check now and say what happened. */
    fun checkNow(ctx: Context) {
        val app = ctx.applicationContext
        val main = Handler(Looper.getMainLooper())
        Toast.makeText(app, "Checking for Lembas updates…", Toast.LENGTH_SHORT).show()
        Thread {
            val msg = when (run(app)) {
                0 -> if (versionCode(app, FACE_PACKAGE) < 0) "Up to date. The watch face isn't installed yet" else "Lembas is up to date"
                -1 -> "Couldn't reach GitHub; try again on Wi-Fi"
                else -> "Installing…"
            }
            main.post { Toast.makeText(app, msg, Toast.LENGTH_LONG).show() }
        }.start()
    }

    /** Returns how many installs it started, or -1 on a network problem. */
    fun run(ctx: Context): Int = try {
        val rel = JSONObject(get(API).bufferedReader().use { it.readText() })
        val latest = rel.optString("tag_name").removePrefix("v").toLongOrNull() ?: 0L
        val assets = rel.getJSONArray("assets")
        fun url(name: String): String? {
            for (i in 0 until assets.length()) {
                val a = assets.getJSONObject(i)
                if (a.optString("name") == name) return a.optString("browser_download_url")
            }
            return null
        }
        var started = 0
        // The watch face first (a separate package), then the app itself (installing it restarts us)
        if (versionCode(ctx, FACE_PACKAGE) < latest) url("lembas-watchface.apk")?.let { if (install(ctx, it, FACE_PACKAGE)) started++ }
        if (versionCode(ctx, ctx.packageName) < latest) url("lembas-wear.apk")?.let { if (install(ctx, it, ctx.packageName)) started++ }
        started
    } catch (_: Throwable) { -1 }

    private fun get(url: String): java.io.InputStream {
        var u = URL(url)
        repeat(5) {
            val c = u.openConnection() as HttpURLConnection
            c.connectTimeout = 15000
            c.readTimeout = 60000
            c.instanceFollowRedirects = false
            c.setRequestProperty("User-Agent", "Lembas-Wear")
            if (url.contains("api.github.com")) c.setRequestProperty("Accept", "application/vnd.github+json")
            val code = c.responseCode
            if (code in 300..399) { u = URL(u, c.getHeaderField("Location")); c.disconnect() }
            else if (code == 200) return c.inputStream
            else { c.disconnect(); throw java.io.IOException("HTTP $code") }
        }
        throw java.io.IOException("Too many redirects")
    }

    private fun install(ctx: Context, url: String, pkg: String): Boolean {
        val apk = File(ctx.cacheDir, "$pkg.apk")
        get(url).use { input -> apk.outputStream().use { input.copyTo(it) } }
        val pi = ctx.packageManager.packageInstaller
        val params = PackageInstaller.SessionParams(PackageInstaller.SessionParams.MODE_FULL_INSTALL)
        params.setAppPackageName(pkg)
        if (Build.VERSION.SDK_INT >= 31) params.setRequireUserAction(PackageInstaller.SessionParams.USER_ACTION_NOT_REQUIRED)
        val id = pi.createSession(params)
        pi.openSession(id).use { s ->
            s.openWrite("base.apk", 0, apk.length()).use { out ->
                apk.inputStream().use { it.copyTo(out) }
                s.fsync(out)
            }
            val flags = PendingIntent.FLAG_UPDATE_CURRENT or (if (Build.VERSION.SDK_INT >= 31) PendingIntent.FLAG_MUTABLE else 0)
            s.commit(PendingIntent.getBroadcast(ctx, id, Intent(ctx, InstallResult::class.java), flags).intentSender)
        }
        apk.delete()
        return true
    }

    class InstallResult : BroadcastReceiver() {
        override fun onReceive(ctx: Context, intent: Intent) {
            if (intent.getIntExtra(PackageInstaller.EXTRA_STATUS, -999) == PackageInstaller.STATUS_PENDING_USER_ACTION) {
                @Suppress("DEPRECATION")
                val confirm = intent.getParcelableExtra<Intent>(Intent.EXTRA_INTENT) ?: return
                pendingConfirm = confirm
                try { ctx.startActivity(Intent(confirm).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)); pendingConfirm = null } catch (_: Exception) { }
            }
        }
    }

    class UpdateJob : JobService() {
        override fun onStartJob(params: JobParameters): Boolean {
            Thread {
                try { run(applicationContext) } catch (_: Throwable) { }
                jobFinished(params, false)
            }.start()
            return true
        }
        override fun onStopJob(params: JobParameters) = true
    }
}
