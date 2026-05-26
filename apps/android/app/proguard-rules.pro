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
