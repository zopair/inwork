package com.inwork.app;

import android.app.Activity;
import android.content.Intent;
import android.net.Uri;
import android.os.Bundle;
import android.view.Gravity;
import android.webkit.GeolocationPermissions;
import android.webkit.JavascriptInterface;
import android.webkit.WebChromeClient;
import android.webkit.WebResourceRequest;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import android.widget.TextView;

public class MainActivity extends Activity {
  private static final String APP_URL = "https://raw.githubusercontent.com/zopair/inwork/main/index.html";
  private WebView web;

  @Override public void onCreate(Bundle b) {
    super.onCreate(b);
    web = new WebView(this);
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

    web.setWebViewClient(new WebViewClient() {
      @Override public boolean shouldOverrideUrlLoading(WebView view, WebResourceRequest req) {
        String u = req.getUrl().toString();
        // Keep InWork resources/navigation inside the app. Open unrelated external links normally.
        if (u.startsWith("https://raw.githubusercontent.com/zopair/inwork/") ||
            u.startsWith("https://zopair.github.io/inwork/") ||
            u.startsWith("file:")) return false;
        if (u.startsWith("https://") || u.startsWith("http://")) {
          try { startActivity(new Intent(Intent.ACTION_VIEW, Uri.parse(u))); } catch(Exception ignored) {}
          return true;
        }
        return false;
      }

      @Override public void onReceivedError(WebView view, int errorCode, String description, String failingUrl) {
        showError();
      }
    });

    web.setWebChromeClient(new WebChromeClient() {
      @Override public void onGeolocationPermissionsShowPrompt(String origin, GeolocationPermissions.Callback callback) {
        callback.invoke(origin, true, false);
      }
    });
    web.addJavascriptInterface(new Bridge(), "InWork");
    setContentView(web);
    loadApp();
  }

  private void loadApp() {
    web.loadUrl(APP_URL);
  }

  private void showError() {
    TextView error = new TextView(this);
    error.setText("تعذر تحميل InWork\n\nتحقق من اتصال الإنترنت ثم اضغط رجوع لإعادة المحاولة.");
    error.setTextSize(18);
    error.setGravity(Gravity.CENTER);
    error.setPadding(40, 40, 40, 40);
    error.setOnClickListener(v -> loadApp());
    setContentView(error);
  }

  private final class Bridge {
    @JavascriptInterface public void requestLocation() {
      runOnUiThread(() -> web.evaluateJavascript(
        "navigator.geolocation.getCurrentPosition(function(p){if(window.receiveLocation)receiveLocation(p.coords.latitude,p.coords.longitude)},function(){})", null));
    }
    @JavascriptInterface public void openUrl(String url) {
      try { startActivity(new Intent(Intent.ACTION_VIEW, Uri.parse(url))); } catch(Exception ignored) {}
    }
  }

  @Override public void onBackPressed() {
    if (web != null && web.canGoBack()) web.goBack(); else super.onBackPressed();
  }
}
