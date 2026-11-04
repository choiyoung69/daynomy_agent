plugins { kotlin("jvm") }
kotlin { jvmToolchain(21) }
dependencies {
    implementation("org.jetbrains.kotlinx:kotlinx-coroutines-core:1.10.2")
    implementation("org.jetbrains.kotlinx:kotlinx-serialization-json:1.8.1")
    implementation("com.squareup.okhttp3:okhttp:4.12.0")
    testImplementation("junit:junit:4.13.2")
    testImplementation("org.jetbrains.kotlinx:kotlinx-coroutines-test:1.10.2")
    testImplementation("com.squareup.okhttp3:mockwebserver:4.12.0")
}
tasks.test { testLogging { events("passed", "failed", "skipped"); exceptionFormat = org.gradle.api.tasks.testing.logging.TestExceptionFormat.FULL } }

val backendTest by sourceSets.creating
configurations[backendTest.implementationConfigurationName].extendsFrom(configurations.testImplementation.get())
configurations[backendTest.runtimeOnlyConfigurationName].extendsFrom(configurations.testRuntimeOnly.get())
backendTest.compileClasspath += sourceSets.main.get().output
backendTest.runtimeClasspath += sourceSets.main.get().output
tasks.register<Test>("backendTest") {
    description = "Actual existing Rust HTTP / disposable DB acceptance; explicit base URL required"
    testClassesDirs = backendTest.output.classesDirs
    classpath = backendTest.runtimeClasspath
    testLogging { events("passed", "failed", "skipped") }
}
