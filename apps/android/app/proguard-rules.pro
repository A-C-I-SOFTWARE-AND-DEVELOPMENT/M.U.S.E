# Keep kotlinx.serialization metadata.
-keepattributes *Annotation*, InnerClasses
-dontnote kotlinx.serialization.AnnotationsKt

-keep,includedescriptorclasses class com.aci.hermes.**$$serializer { *; }
-keepclassmembers class com.aci.hermes.** {
    *** Companion;
}
-keepclasseswithmembers class com.aci.hermes.** {
    kotlinx.serialization.KSerializer serializer(...);
}

# OkHttp / Okio internals
-dontwarn okhttp3.internal.platform.**
-dontwarn org.conscrypt.**
-dontwarn org.bouncycastle.**
-dontwarn org.openjsse.**

# Rive runtime ships native (JNI) + reflection-heavy classes. CI compiles the
# release build but never renders a .riv, so keep Rive intact to avoid an
# R8-stripped ClassNotFound/NoSuchMethod crash when the avatar first animates.
-keep class app.rive.runtime.** { *; }
-keep interface app.rive.runtime.** { *; }
-dontwarn app.rive.runtime.**
