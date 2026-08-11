package com.inwork.app;

import android.Manifest;
import android.app.Activity;
import android.content.Intent;
import android.content.pm.PackageManager;
import android.net.Uri;
import android.os.Bundle;
import android.util.Log;
import android.webkit.ConsoleMessage;
import android.webkit.GeolocationPermissions;
import android.webkit.JavascriptInterface;
import android.webkit.WebChromeClient;
import android.webkit.WebResourceRequest;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import android.widget.Toast;

import java.io.BufferedReader;
import java.io.InputStream;
import java.io.InputStreamReader;
import java.nio.charset.StandardCharsets;

public class MainActivity extends Activity {
  private static final int LOCATION_REQUEST = 41;
  private WebView web;

  @Override public void onCreate(Bundle b) {
    super.onCreate(b);
    web = new WebView(this);
    configureWebView();
    setContentView(web);
    requestLocationPermissionIfNeeded();
    loadBundledApp();
  }

  private void configureWebView() {
    WebSettings s = web.getSettings();
    s.setJavaScriptEnabled(true);
    s.setDomStorageEnabled(true);
    s.setDatabaseEnabled(true);
    s.setAllowFileAccess(true);
    s.setAllowContentAccess(true);
    s.setGeolocationEnabled(true);
    s.setBuiltInZoomControls(false);
    s.setDisplayZoomControls(false);
    s.setSupportZoom(false);
    s.setMediaPlaybackRequiresUserGesture(false);

    web.setBackgroundColor(0xFFFFFFFF);
    web.setWebViewClient(new WebViewClient() {
      @Override public boolean shouldOverrideUrlLoading(WebView view, WebResourceRequest req) {
        return handleUrl(req.getUrl().toString());
      }
      @Override public boolean shouldOverrideUrlLoading(WebView view, String url) {
        return handleUrl(url);
      }
      @Override public void onReceivedError(WebView view, int errorCode, String description, String failingUrl) {
        Log.e("InWork", "WebView error " + errorCode + ": " + description + " @ " + failingUrl);
      }
    });

    web.setWebChromeClient(new WebChromeClient() {
      @Override public void onGeolocationPermissionsShowPrompt(String origin, GeolocationPermissions.Callback callback) {
        boolean granted = checkSelfPermission(Manifest.permission.ACCESS_FINE_LOCATION) == PackageManager.PERMISSION_GRANTED
            || checkSelfPermission(Manifest.permission.ACCESS_COARSE_LOCATION) == PackageManager.PERMISSION_GRANTED;
        callback.invoke(origin, granted, false);
      }
      @Override public boolean onConsoleMessage(ConsoleMessage message) {
        Log.d("InWorkWeb", message.message() + " @" + message.lineNumber());
        return true;
      }
    });
    web.addJavascriptInterface(new Bridge(), "InWork");
  }

  private boolean handleUrl(String url) {
    if (url == null) return false;
    if (url.startsWith("https://inwork.local/") || url.startsWith("http://inwork.local/")) return false;
    if (url.startsWith("https://") || url.startsWith("http://") || url.startsWith("mailto:") || url.startsWith("tel:")) {
      try { startActivity(new Intent(Intent.ACTION_VIEW, Uri.parse(url))); } catch (Exception ignored) {}
      return true;
    }
    return false;
  }

  private void loadBundledApp() {
    try {
      String html = readAsset("web/index.html");
      if (html.trim().isEmpty()) throw new IllegalStateException("Bundled index.html is empty");
      web.loadDataWithBaseURL("https://inwork.local/", html, "text/html", "UTF-8", null);
    } catch (Exception e) {
      Log.e("InWork", "Unable to load bundled app", e);
      Toast.makeText(this, "تعذر تشغيل واجهة InWork", Toast.LENGTH_LONG).show();
    }
  }

  private String readAsset(String path) throws Exception {
    StringBuilder out = new StringBuilder();
    try (InputStream in = getAssets().open(path);
         BufferedReader reader = new BufferedReader(new InputStreamReader(in, StandardCharsets.UTF_8))) {
      String line;
      while ((line = reader.readLine()) != null) out.append(line).append('\n');
    }
    return out.toString();
  }

  private void requestLocationPermissionIfNeeded() {
    if (android.os.Build.VERSION.SDK_INT >= 23 &&
        checkSelfPermission(Manifest.permission.ACCESS_FINE_LOCATION) != PackageManager.PERMISSION_GRANTED &&
        checkSelfPermission(Manifest.permission.ACCESS_COARSE_LOCATION) != PackageManager.PERMISSION_GRANTED) {
      requestPermissions(new String[]{Manifest.permission.ACCESS_FINE_LOCATION, Manifest.permission.ACCESS_COARSE_LOCATION}, LOCATION_REQUEST);
    }
  }

  private final class Bridge {
    @JavascriptInterface public void requestLocation() {
      runOnUiThread(() -> web.evaluateJavascript(
        "navigator.geolocation.getCurrentPosition(function(p){if(window.receiveLocation)window.receiveLocation(p.coords.latitude,p.coords.longitude)},function(e){console.log('location error',e.code)})", null));
    }
    @JavascriptInterface public void openUrl(String url) {
      try { startActivity(new Intent(Intent.ACTION_VIEW, Uri.parse(url))); } catch(Exception ignored) {}
    }
  }

  @Override public void onBackPressed() {
    if (web != null && web.canGoBack()) web.goBack(); else super.onBackPressed();
  }
}
