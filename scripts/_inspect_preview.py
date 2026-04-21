import urllib.request as u

r = u.urlopen("http://127.0.0.1:5000/preview/", timeout=5)
html = r.read().decode("utf-8", "ignore")
print("status", r.status)
print("length", len(html))
print("--- first 600 chars ---")
print(html[:600])
print("--- flags ---")
print("home-hero:", "home-hero" in html)
print("sidebar:", '<aside class="sidebar"' in html)
print("preview.css:", "/static/css/v2/preview.css" in html)
