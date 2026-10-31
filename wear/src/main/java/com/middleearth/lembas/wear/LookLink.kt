package com.middleearth.lembas.wear

import android.content.Context
import com.google.android.gms.wearable.DataEvent
import com.google.android.gms.wearable.DataEventBuffer
import com.google.android.gms.wearable.DataMapItem
import com.google.android.gms.wearable.PutDataMapRequest
import com.google.android.gms.wearable.Wearable
import com.google.android.gms.wearable.WearableListenerService

/**
 * The look, kept in step with the phone over the watch link (and through the phone, with Lembas
 * for Windows). The watch app, its tiles, the Lembas complications and the watch face all follow
 * (the face through the hidden LookComplication).
 */
object LookLink {
    const val PATH = "/lembas/look"

    fun tellPhone(ctx: Context, look: String) {
        try {
            val req = PutDataMapRequest.create(PATH).apply {
                dataMap.putString("look", if (look == WearLook.AUTO) "adaptive" else look)
                dataMap.putLong("keepUntil", 0)
                dataMap.putString("by", "watch")
                dataMap.putLong("t", System.currentTimeMillis())
            }.asPutDataRequest().setUrgent()
            Wearable.getDataClient(ctx).putDataItem(req)
        } catch (_: Throwable) { }
    }
}

/** A look chosen on the phone (or the PC, through the phone). */
class PhoneLookListener : WearableListenerService() {
    override fun onDataChanged(events: DataEventBuffer) {
        for (e in events) {
            if (e.type != DataEvent.TYPE_CHANGED || e.dataItem.uri.path != LookLink.PATH) continue
            val m = DataMapItem.fromDataItem(e.dataItem).dataMap
            if (m.getString("by") != "phone") continue
            val look = m.getString("look") ?: continue
            getSharedPreferences("lembas", MODE_PRIVATE).edit()
                .putString(WearLooks.PREF_LOOK, if (look == "adaptive") WearLook.AUTO else look)
                .putLong(WearLooks.PREF_KEEP_UNTIL, m.getLong("keepUntil", 0)).apply()
            LembasTile.refresh(this)
            LookComplication.refresh(this)
        }
    }
}
