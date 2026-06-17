# Keep WebView JavaScript interfaces (none currently, but safe for future bridges).
-keepclassmembers class * {
    @android.webkit.JavascriptInterface <methods>;
}
