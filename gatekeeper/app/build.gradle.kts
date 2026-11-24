plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.android")
}

val coreUrl: String = (project.findProperty("coreUrl") as String?) ?: "http://127.0.0.1:8000"
val residentUrl: String = (project.findProperty("residentUrl") as String?) ?: "http://127.0.0.1:5174"
// Private DNS hostname of the DNS Shield resolver (DoT); empty in the demo build, where DNS Shield runs on a laptop.
val dnsHost: String = (project.findProperty("dnsHost") as String?) ?: ""

android {
    namespace = "ae.kartoshka.gatekeeper"
    compileSdk = 35

    defaultConfig {
        applicationId = "ae.kartoshka.gatekeeper"
        minSdk = 26
        targetSdk = 35
        versionCode = 1
        versionName = "0.1.0"
        buildConfigField("String", "CORE_URL", "\"$coreUrl\"")
        buildConfigField("String", "RESIDENT_URL", "\"$residentUrl\"")
        buildConfigField("String", "DNS_HOST", "\"$dnsHost\"")
    }

    buildFeatures {
        buildConfig = true
    }

    buildTypes {
        release {
            isMinifyEnabled = false
        }
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }
    kotlinOptions {
        jvmTarget = "17"
    }
    testOptions {
        unitTests.isReturnDefaultValues = true
    }
}

dependencies {
    implementation("androidx.core:core-ktx:1.15.0")
    implementation("androidx.appcompat:appcompat:1.7.0")
    implementation("androidx.work:work-runtime-ktx:2.10.0")
    implementation("androidx.lifecycle:lifecycle-runtime-ktx:2.8.7")
    implementation("org.jetbrains.kotlinx:kotlinx-coroutines-android:1.9.0")
    testImplementation("junit:junit:4.13.2")
    testImplementation("org.json:json:20240303")
}
