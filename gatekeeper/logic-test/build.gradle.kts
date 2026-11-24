plugins { kotlin("jvm") version "2.1.0" }

repositories { mavenCentral() }

dependencies {
    implementation("org.json:json:20240303")
    testImplementation("junit:junit:4.13.2")
}

kotlin { jvmToolchain(17) }

sourceSets {
    main { kotlin.srcDir("../app/src/main/java/ae/kartoshka/gatekeeper/logic") }
    test { kotlin.srcDir("../app/src/test/java/ae/kartoshka/gatekeeper/logic") }
}

tasks.test {
    workingDir = file("../app")   // the tests read src/main/assets/brands.json, as the Android unit tests do
    testLogging { events("failed"); exceptionFormat = org.gradle.api.tasks.testing.logging.TestExceptionFormat.FULL }
}
