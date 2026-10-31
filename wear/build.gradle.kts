plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.android")
    id("org.jetbrains.kotlin.plugin.compose")
}

// Lembas for the watch: a themed app launcher (Compose for Wear OS, Material 3) and a tile.
android {
    namespace = "com.middleearth.lembas.wear"
    compileSdk = 36

    defaultConfig {
        applicationId = "com.middleearth.launcher"   // same as the phone app, so they're one app to Wear OS
        minSdk = 30
        targetSdk = 36
        val build = (System.getenv("LEMBAS_BUILD") ?: "1").toInt()
        versionCode = build
        versionName = "1.$build"
    }

    val keystore = System.getenv("LEMBAS_KEYSTORE")?.let { file(it) }
    signingConfigs {
        if (keystore != null && keystore.exists()) create("lembas") {
            storeFile = keystore
            storePassword = System.getenv("LEMBAS_KEYSTORE_PASSWORD")
            keyAlias = System.getenv("LEMBAS_KEY_ALIAS") ?: "lembas"
            keyPassword = System.getenv("LEMBAS_KEY_PASSWORD")
        }
    }

    buildTypes {
        release {
            isMinifyEnabled = true
            isShrinkResources = true
            proguardFiles(getDefaultProguardFile("proguard-android-optimize.txt"))
            signingConfig = signingConfigs.findByName("lembas") ?: signingConfigs.getByName("debug")
        }
    }
    buildFeatures { compose = true }
    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }
    lint {
        abortOnError = false
        checkReleaseBuilds = false
    }
}

kotlin {
    compilerOptions {
        jvmTarget.set(org.jetbrains.kotlin.gradle.dsl.JvmTarget.JVM_17)
    }
}

dependencies {
    implementation("androidx.activity:activity-compose:1.12.4")
    implementation("androidx.wear.compose:compose-material3:1.5.6")
    implementation("androidx.wear.compose:compose-foundation:1.5.6")
    implementation("androidx.wear.tiles:tiles:1.6.2")
    implementation("androidx.wear.protolayout:protolayout:1.4.2")
    implementation("androidx.concurrent:concurrent-futures:1.2.0")
    implementation("androidx.wear.watchface:watchface-complications-data-source:1.2.1")
    implementation("com.google.android.gms:play-services-wearable:19.0.0")   // the look, in step with the phone
}
