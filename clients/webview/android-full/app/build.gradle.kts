plugins { id("com.android.application"); kotlin("android") }
val debugOrigin = providers.gradleProperty("debugWebOrigin").orElse("http://10.0.2.2:18082")
val releaseOrigin = providers.gradleProperty("webOrigin").orElse("")
android {
    namespace = "com.daynomy.webview"
    compileSdk = 35
    buildToolsVersion = "35.0.0"
    defaultConfig {
        applicationId = "com.daynomy.webview.full"
        minSdk = 26
        targetSdk = 35
        versionCode = 1
        versionName = "0.1.0"
    }
    buildFeatures { buildConfig = true }
    buildTypes {
        debug {
            require(debugOrigin.get().matches(Regex("http://(127\\.0\\.0\\.1|10\\.0\\.2\\.2|localhost):[0-9]{1,5}"))) { "debugWebOrigin must be a local HTTP origin" }
            buildConfigField("String", "WEB_ORIGIN", "\"${debugOrigin.get()}\"")
        }
        release {
            require(!releaseOrigin.get().contains('"') && !releaseOrigin.get().contains('\\')) { "webOrigin must be a plain HTTPS origin" }
            buildConfigField("String", "WEB_ORIGIN", "\"${releaseOrigin.get()}\"")
        }
    }
    compileOptions { sourceCompatibility = JavaVersion.VERSION_21; targetCompatibility = JavaVersion.VERSION_21 }
    kotlinOptions { jvmTarget = "21" }
}
