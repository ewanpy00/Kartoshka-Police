# Android build environment for Gatekeeper: JDK 17, Gradle 8.11.1 and the Android SDK (platform 35,
# build-tools 34). Runs as linux/amd64 because the Android build tools (aapt2) ship only for x86_64 on
# Linux; on Apple Silicon Docker emulates it. Used by scripts/apk.sh (make apk).
FROM --platform=linux/amd64 gradle:8.11.1-jdk17

ENV ANDROID_HOME=/opt/android-sdk \
    ANDROID_SDK_ROOT=/opt/android-sdk
ENV PATH=$PATH:$ANDROID_HOME/cmdline-tools/latest/bin:$ANDROID_HOME/platform-tools

RUN apt-get update && apt-get install -y --no-install-recommends unzip && rm -rf /var/lib/apt/lists/* \
 && mkdir -p $ANDROID_HOME/cmdline-tools \
 && curl -fsSL -o /tmp/tools.zip https://dl.google.com/android/repository/commandlinetools-linux-11076708_latest.zip \
 && unzip -q /tmp/tools.zip -d $ANDROID_HOME/cmdline-tools && mv $ANDROID_HOME/cmdline-tools/cmdline-tools $ANDROID_HOME/cmdline-tools/latest \
 && rm /tmp/tools.zip \
 && yes | sdkmanager --licenses >/dev/null \
 && sdkmanager --install "platforms;android-35" "build-tools;34.0.0" >/dev/null \
 && chmod -R a+rwX $ANDROID_HOME
# The Android Gradle plugin wants platform-tools too; installing it here saves a download on every build.
RUN yes | sdkmanager --install "platform-tools" >/dev/null && chmod -R a+rwX $ANDROID_HOME
