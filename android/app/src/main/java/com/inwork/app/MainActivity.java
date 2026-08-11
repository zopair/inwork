package com.inwork.app;

import android.app.Activity;
import android.content.Intent;
import android.net.Uri;
import android.os.Bundle;
import android.webkit.GeolocationPermissions;
import android.webkit.JavascriptInterface;
import android.webkit.WebChromeClient;
import android.webkit.WebResourceRequest;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;

public class MainActivity extends Activity {
  private WebView web;

  @Override public void onCreate(Bundle b) {
    super.onCreate(b);
    web = new WebView(this);
    WebSettings s = web.getSettings();
    s.setJavaScriptEnabled(true);
    s.setDomStorageEnabled(true);
    s.setAllowFileAccess(true);
    s.setAllowContentAccess(true);
    s.setGeolocationEnabled(true);
    web.setWebViewClient(new WebViewClient(){
      @Override public boolean shouldOverrideUrlLoading(WebView view, WebResourceRequest req) {
        String u = req.getUrl().toString();
        if (u.startsWith("https://") || u.startsWith("http://")) {
          try { startActivity(new Intent(Intent.ACTION_VIEW, Uri.parse(u))); } catch(Exception ignored) {}
          return true;
        }
        return false;
      }
    });
    web.setWebChromeClient(new WebChromeClient(){
      @Override public void onGeolocationPermissionsShowPrompt(String origin, GeolocationPermissions.Callback callback) {
        callback.invoke(origin, true, false);
      }
    });
    web.addJavascriptInterface(new Bridge(), "InWork");
    web.loadUrl("file:///android_asset/web/index.html");
    setContentView(web);
  }

  private final class Bridge {
    @JavascriptInterface public void requestLocation() {
      runOnUiThread(() -> web.evaluateJavascript("navigator.geolocation.getCurrentPosition(function(p){receiveLocation(p.coords.latitude,p.coords.longitude)},function(){})", null));
    }
    @JavascriptInterface public void openUrl(String url) {
      try { startActivity(new Intent(Intent.ACTION_VIEW, Uri.parse(url))); } catch(Exception ignored) {}
    }
  }

  @Override public void onBackPressed() {
    if (web != null && web.canGoBack()) web.goBack(); else super.onBackPressed();
  }
}
