#!/usr/bin/env python3
import datetime as dt, email.utils, html, re, sys, urllib.request, urllib.error, xml.etree.ElementTree as ET
from zoneinfo import ZoneInfo

MSK=ZoneInfo('Europe/Moscow')
UTC=dt.timezone.utc
now=dt.datetime.now(MSK)
start=now.replace(hour=8, minute=0, second=0, microsecond=0)
end=now.replace(hour=14, minute=0, second=0, microsecond=0)
if now.hour < 8:
    start=(now-dt.timedelta(days=1)).replace(hour=20, minute=0, second=0, microsecond=0)
    end=now.replace(hour=8, minute=0, second=0, microsecond=0)
elif now.hour < 14:
    start=now.replace(hour=8, minute=0, second=0, microsecond=0)
    end=now.replace(hour=14, minute=0, second=0, microsecond=0)
elif now.hour < 20:
    start=now.replace(hour=14, minute=0, second=0, microsecond=0)
    end=now.replace(hour=20, minute=0, second=0, microsecond=0)
else:
    start=now.replace(hour=20, minute=0, second=0, microsecond=0)
    end=(now+dt.timedelta(days=1)).replace(hour=8, minute=0, second=0, microsecond=0)
# allow current run at boundary to use completed 08-14 window
if now.hour==14 and now.minute<5:
    start=now.replace(hour=8, minute=0, second=0, microsecond=0); end=now.replace(hour=14, minute=0, second=0, microsecond=0)

SOURCES=[
('world','BBC World','https://feeds.bbci.co.uk/news/world/rss.xml'),
('world','Guardian World','https://www.theguardian.com/world/rss'),
('world','Al Jazeera','https://www.aljazeera.com/xml/rss/all.xml'),
('world','CNBC World','https://www.cnbc.com/id/100727362/device/rss/rss.html'),
('ft','CNBC Business','https://www.cnbc.com/id/10001147/device/rss/rss.html'),
('ft','MarketWatch','https://feeds.content.dowjones.io/public/rss/mw_topstories'),
('ft','TechCrunch','https://techcrunch.com/feed/'),
('food','Food Safety News','https://www.foodsafetynews.com/feed/'),
('food','Grocery Dive','https://www.grocerydive.com/feeds/news/'),
('food','Retail Dive','https://www.retaildive.com/feeds/news/'),
('food','Restaurant Business','https://www.restaurantbusinessonline.com/rss.xml'),
]
UA={'User-Agent':'Mozilla/5.0 (ERA_MEDIA editorial freshness scan; contact: public RSS use)'}

def fetch(url, n=0):
    req=urllib.request.Request(url, headers=UA)
    return urllib.request.urlopen(req, timeout=25).read()

def text(x): return html.unescape(re.sub(r'<[^>]+>',' ',x or '')).strip()

def parse_date(s):
    if not s: return None
    try: return email.utils.parsedate_to_datetime(s).astimezone(MSK)
    except Exception:
        try: return dt.datetime.fromisoformat(s.replace('Z','+00:00')).astimezone(MSK)
        except Exception: return None

def link_of(it):
    l=it.findtext('link')
    if l and l.strip(): return l.strip()
    for child in it:
        if child.tag.endswith('link') and child.attrib.get('href'):
            return child.attrib['href']
    return ''

def media_of(it):
    candidates=[]
    for child in it.iter():
        tag=child.tag.lower()
        if 'thumbnail' in tag or 'content' in tag or 'enclosure' in tag:
            u=child.attrib.get('url') or child.attrib.get('href')
            typ=child.attrib.get('type','')
            if u and (u.lower().endswith(('.jpg','.jpeg','.png','.webp')) or typ.startswith('image') or 'image' in tag or 'thumbnail' in tag): candidates.append(u)
    return candidates[0] if candidates else ''

def og_image(url):
    try:
        data=fetch(url)[:300000].decode('utf-8','ignore')
        m=re.search(r'<meta[^>]+property=["\']og:image["\'][^>]+content=["\']([^"\']+)', data, re.I) or re.search(r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+property=["\']og:image["\']', data, re.I)
        if m: return html.unescape(m.group(1))
        m=re.search(r'<meta[^>]+name=["\']twitter:image["\'][^>]+content=["\']([^"\']+)', data, re.I)
        if m: return html.unescape(m.group(1))
    except Exception as e:
        return ''
    return ''

items=[]
print(f'WINDOW {start:%Y-%m-%d %H:%M} - {end:%H:%M} MSK', file=sys.stderr)
for cat,name,url in SOURCES:
    try:
        data=fetch(url)
        root=ET.fromstring(data)
        entries=root.findall('.//item') or root.findall('.//{http://www.w3.org/2005/Atom}entry')
        for it in entries[:30]:
            title=text(it.findtext('title') or it.findtext('{http://www.w3.org/2005/Atom}title'))
            desc=text(it.findtext('description') or it.findtext('summary') or it.findtext('{http://www.w3.org/2005/Atom}summary'))
            pub=parse_date(it.findtext('pubDate') or it.findtext('published') or it.findtext('updated') or it.findtext('{http://www.w3.org/2005/Atom}published') or it.findtext('{http://www.w3.org/2005/Atom}updated'))
            if not pub or not (start <= pub <= end): continue
            link=link_of(it)
            media=media_of(it) or og_image(link)
            items.append((cat,pub,name,title,link,desc[:240],media))
    except Exception as e:
        print('ERR', name, url, repr(e), file=sys.stderr)
for x in sorted(items, key=lambda t:t[1], reverse=True):
    print('\t'.join(str(v).replace('\n',' ') for v in x))
