plugins {
    alias(libs.plugins.android.application)
    alias(libs.plugins.kotlin.android)
    alias(libs.plugins.kotlin.compose)
    alias(libs.plugins.kotlin.serialization)
}

// Gateway URL is resolved at build time from (in order):
//   1. -PhermesGatewayUrl=...        (gradle property — gradle.properties or CLI)
//   2. $HERMES_GATEWAY_URL           (env var — primary name)
//   3. $ANDROID_API_BASE_URL         (env var — alias)
// If none are set, debug falls back to the Android-emulator loopback
// (http://10.0.2.2:8080) so the emulator-on-host workflow still works
// out of the box; release falls back to an empty string so the user is
// forced through the on-device setup screen.
//
// NEVER hardcode a token here. Tokens stay server-side in ~/.hermes/.env
// or in the gateway's environment.
val hermesGatewayUrlOverride: String =
    (project.findProperty("hermesGatewayUrl") as String?)?.takeIf { it.isNotBlank() }
        ?: System.getenv("HERMES_GATEWAY_URL")?.takeIf { it.isNotBlank() }
        ?: System.getenv("ANDROID_API_BASE_URL")?.takeIf { it.isNotBlank() }
        ?: ""

val emulatorFallbackGatewayUrl = "http://10.0.2.2:8080"

android {
    namespace = "com.aci.hermes"
    compileSdk = 35

    defaultConfig {
        applicationId = "com.aci.hermes"
        minSdk = 26
        targetSdk = 35
        versionCode = 1
        versionName = "0.1.0"

        testInstrumentationRunner = "androidx.test.runner.AndroidJUnitRunner"
        vectorDrawables { useSupportLibrary = true }
    }

    buildTypes {
        getByName("debug") {
            applicationIdSuffix = ".debug"
            versionNameSuffix = "-debug"
            isMinifyEnabled = false
            val debugDefault = hermesGatewayUrlOverride.ifBlank { emulatorFallbackGatewayUrl }
            buildConfigField("String", "DEFAULT_GATEWAY_URL", "\"$debugDefault\"")
            buildConfigField(
                "boolean",
                "DEFAULT_GATEWAY_URL_IS_EMULATOR_FALLBACK",
                "${hermesGatewayUrlOverride.isBlank()}"
            )
            buildConfigField("boolean", "ENABLE_MOCK_DEFAULT", "true")
        }
        getByName("release") {
            isMinifyEnabled = true
            isShrinkResources = true
            proguardFiles(
                getDefaultProguardFile("proguard-android-optimize.txt"),
                "proguard-rules.pro"
            )
            buildConfigField("String", "DEFAULT_GATEWAY_URL", "\"$hermesGatewayUrlOverride\"")
            buildConfigField(
                "boolean",
                "DEFAULT_GATEWAY_URL_IS_EMULATOR_FALLBACK",
                "false"
            )
            buildConfigField("boolean", "ENABLE_MOCK_DEFAULT", "false")
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
        compose = true
        buildConfig = true
    }

    packaging {
        resources {
            excludes += setOf(
                "/META-INF/{AL2.0,LGPL2.1}",
                "/META-INF/DEPENDENCIES",
                "/META-INF/LICENSE",
                "/META-INF/LICENSE.txt",
                "/META-INF/NOTICE",
                "/META-INF/NOTICE.txt"
            )
        }
    }
}

dependencies {
    implementation(libs.androidx.core.ktx)
    implementation(libs.androidx.lifecycle.runtime.ktx)
    implementation(libs.androidx.lifecycle.viewmodel.ktx)
    implementation(libs.androidx.lifecycle.viewmodel.compose)
    implementation(libs.androidx.activity.compose)

    implementation(platform(libs.androidx.compose.bom))
    implementation(libs.androidx.compose.ui)
    implementation(libs.androidx.compose.ui.graphics)
    implementation(libs.androidx.compose.ui.tooling.preview)
    implementation(libs.androidx.compose.material3)
    implementation(libs.androidx.compose.material.icons.extended)
    implementation(libs.androidx.navigation.compose)

    implementation(libs.androidx.datastore.preferences)
    implementation(libs.androidx.security.crypto)

    implementation(libs.okhttp)
    implementation(libs.okhttp.sse)
    implementation(libs.kotlinx.serialization.json)
    implementation(libs.kotlinx.coroutines.core)
    implementation(libs.kotlinx.coroutines.android)

    debugImplementation(libs.androidx.compose.ui.tooling)

    testImplementation(libs.junit)
    androidTestImplementation(libs.androidx.test.junit)
    androidTestImplementation(libs.androidx.test.espresso.core)
    androidTestImplementation(platform(libs.androidx.compose.bom))
}
