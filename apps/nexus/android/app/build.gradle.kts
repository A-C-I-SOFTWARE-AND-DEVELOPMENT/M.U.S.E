plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.android")
}

// A thin, native WebView shell that turns the NEXUS PWA into a true installable
// app: its own launcher icon, full-screen (no browser chrome), and real device
// access (camera / mic / location / file upload+download / notifications) granted
// through the WebView permission bridges. It loads the hosted NEXUS by default;
// override the URL at build time with NEXUS_URL (e.g. a local Termux gateway).
android {
    namespace = "dev.aci.nexus"
    compileSdk = 34

    defaultConfig {
        applicationId = "dev.aci.nexus"
        minSdk = 26
        targetSdk = 34
        // CI injects a unique run number + a date.commits version so a fresh
        // download supersedes the prior install; falls back for local builds.
        versionCode = System.getenv("ANDROID_VERSION_CODE")?.toIntOrNull() ?: 1
        versionName = System.getenv("ANDROID_VERSION_NAME")?.takeIf { it.isNotBlank() } ?: "0.1.0"

        // The URL the shell loads. Defaults to the GitHub Pages deploy; override
        // with NEXUS_URL to ship a build that points at a local gateway
        // (e.g. http://127.0.0.1:8765/nexus/).
        val nexusUrl = System.getenv("NEXUS_URL")?.takeIf { it.isNotBlank() }
            ?: "https://a-c-i-software-and-development.github.io/M.U.S.E/"
        resValue("string", "nexus_url", nexusUrl)
    }

    buildTypes {
        release {
            isMinifyEnabled = false
            proguardFiles(getDefaultProguardFile("proguard-android-optimize.txt"), "proguard-rules.pro")
        }
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }
    kotlinOptions {
        jvmTarget = "17"
    }
    buildFeatures {
        buildConfig = true
    }
}

dependencies {
    implementation("androidx.core:core-ktx:1.13.1")
    implementation("androidx.appcompat:appcompat:1.7.0")
    implementation("androidx.activity:activity-ktx:1.9.0")
}
