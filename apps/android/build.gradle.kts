plugins {
    kotlin("jvm") version "2.0.21"
}

repositories {
    mavenCentral()
}

dependencies {
    testImplementation("org.jetbrains.kotlin:kotlin-test")
    testImplementation("org.junit.jupiter:junit-jupiter:5.10.2")
    testRuntimeOnly("org.junit.platform:junit-platform-launcher")
}

kotlin {
    jvmToolchain(21)
}

tasks.test {
    useJUnitPlatform()
    testLogging {
        events("passed", "failed", "skipped")
    }
}

// The production module ships as an Android library; in this environment we
// build the platform-agnostic core as a JVM module. `assembleDebug` is aliased
// to the JVM `assemble` task so the documented build command works end-to-end.
tasks.register("assembleDebug") {
    group = "build"
    description = "Builds the Jarvis Prime notifications core (alias of :assemble)."
    dependsOn("assemble", "test")
}
