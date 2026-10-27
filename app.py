from flask import Flask, render_template, request, redirect, url_for, flash, session, abort
import os, sqlite3, secrets, re, hashlib, urllib.parse, urllib.request
from html.parser import HTMLParser
from datetime import datetime, date
import xml.etree.ElementTree as ET
BASE=os.path.dirname(os.path.abspath(__file__))
try:
 from dotenv import load_dotenv
 load_dotenv(os.path.join(BASE,'.env'), override=False)
except ImportError: pass
DB=os.path.join(BASE,'nyalsama.db')
MODEL=os.environ.get('GEMINI_MODEL','gemini-3.7-flash').strip()
app=Flask(__name__); app.secret_key=os.environ.get('NYALSAMA_SECRET_KEY') or secrets.token_hex(32)
def db():
 c=sqlite3.connect(DB); c.row_factory=sqlite3.Row; return c
def init_db():
 with db() as c:
  c.executescript("""CREATE TABLE IF NOT EXISTS profile(id INTEGER PRIMARY KEY CHECK(id=1),username TEXT NOT NULL DEFAULT '',hobbies TEXT NOT NULL DEFAULT '',preferences TEXT NOT NULL DEFAULT '',thinking_style TEXT NOT NULL DEFAULT '',notes TEXT NOT NULL DEFAULT '',updated_at TEXT NOT NULL DEFAULT '');
  INSERT OR IGNORE INTO profile(id,username) VALUES(1,'');
  CREATE TABLE IF NOT EXISTS messages(id INTEGER PRIMARY KEY AUTOINCREMENT,role TEXT NOT NULL,body TEXT NOT NULL,created_at TEXT NOT NULL);
  CREATE TABLE IF NOT EXISTS predictions(id INTEGER PRIMARY KEY AUTOINCREMENT,prediction TEXT NOT NULL,result TEXT NOT NULL DEFAULT '',created_at TEXT NOT NULL);""")
  # 既存DBを壊さず、新しい列だけを追加する。
  cols={r['name'] for r in c.execute('PRAGMA table_info(profile)').fetchall()}
  if 'zodiac' not in cols: c.execute("ALTER TABLE profile ADD COLUMN zodiac TEXT NOT NULL DEFAULT ''")
  pcols={r['name'] for r in c.execute('PRAGMA table_info(predictions)').fetchall()}
  if 'sources' not in pcols: c.execute("ALTER TABLE predictions ADD COLUMN sources TEXT NOT NULL DEFAULT ''")
# Render/Gunicorn では __main__ が実行されないため、アプリ読込時にDB初期化を行う。
# CREATE TABLE IF NOT EXISTS と INSERT OR IGNORE を使うため、既存データは消さない。
init_db()

def profile():
 with db() as c: return c.execute('SELECT * FROM profile WHERE id=1').fetchone()
def add(role,body):
 with db() as c: c.execute('INSERT INTO messages(role,body,created_at) VALUES(?,?,?)',(role,body,datetime.now().strftime('%Y-%m-%d %H:%M')))
def key(): return (os.environ.get('GOOGLE_API_KEY') or os.environ.get('GEMINI_API_KEY') or '').strip()
def ask(contents,system,tokens=450):
 from google import genai
 from google.genai import types

 api_key = key()
 if not api_key:
  raise RuntimeError('Gemini APIキーが設定されていません。')

 # クライアントを明示的な変数に保持し、通信完了後にだけ閉じる。
 # 生成リクエストの前に閉じたクライアントを参照してしまう状態を避ける。
 client = genai.Client(api_key=api_key, http_options=types.HttpOptions(timeout=12000))
 try:
  response = client.models.generate_content(
   model=MODEL,
   contents=contents,
   config=types.GenerateContentConfig(
    system_instruction=system,
    temperature=0.9,
    max_output_tokens=tokens
   )
  )
  return (response.text or '').strip()
 finally:
  close = getattr(client, 'close', None)
  if callable(close):
   close()
def reply(text):
 if key():
  try:
   p=profile()
   with db() as c: hist=c.execute('SELECT role,body FROM messages ORDER BY id DESC LIMIT 12').fetchall()
   contents=[{'role':'user' if x['role']=='user' else 'model','parts':[{'text':x['body']}]} for x in reversed(hist)]
   prompt=f'あなたは大預言猫ニャル様。偉そうで愛嬌のある猫の預言者として自然な日本語で会話し、時々ニャを使う。落ち込んだ人には優しくする。怖い予言や重要判断への誘導は禁止。保存プロフィール: 呼び名:{p["username"] or "不明"} 趣味:{p["hobbies"] or "不明"} 好み:{p["preferences"] or "不明"} 考え方:{p["thinking_style"] or "不明"} メモ:{p["notes"] or "なし"}'
   out=ask(contents or text,prompt)
   if out:return out[:4000]
  except Exception as e:
   msg=str(e)
   for n in ('GOOGLE_API_KEY','GEMINI_API_KEY'):
    v=os.environ.get(n,'').strip()
    if v:msg=msg.replace(v,'[REDACTED]')
   print(f'Gemini API call failed: {type(e).__name__}: {msg[:1000]}')
   return 'むむっ、Geminiとの通信に失敗したニャ。黒い画面の診断メッセージを確認してほしいニャ。'
 return 'フフフ……余の宇宙ひげが何かを感じ取ったぞ。もう少し詳しく話してみるがよいニャ！ （APIキー未設定のため定型文で返答中）'
ZODIAC_SIGNS=('おひつじ座','おうし座','ふたご座','かに座','しし座','おとめ座','てんびん座','さそり座','いて座','やぎ座','みずがめ座','うお座')

class DDGResults(HTMLParser):
 def __init__(self):
  super().__init__(); self.results=[]; self.current=None; self.capture=None; self.buf=[]; self.target=None
 def handle_starttag(self,tag,attrs):
  a=dict(attrs); cls=a.get('class','')
  if tag=='a' and 'result__a' in cls:
   self.current={'title':'','url':a.get('href',''),'snippet':''}; self.results.append(self.current)
   self.capture='title'; self.target=self.current; self.buf=[]
  elif 'result__snippet' in cls and self.results:
   self.capture='snippet'; self.target=self.results[-1]; self.buf=[]
 def handle_data(self,data):
  if self.capture: self.buf.append(data)
 def handle_endtag(self,tag):
  if self.capture=='title' and tag=='a':
   if self.target is not None: self.target['title']=' '.join(''.join(self.buf).split())
   self.capture=None; self.target=None; self.buf=[]
  elif self.capture=='snippet' and self.target is not None:
   self.target['snippet']=' '.join(''.join(self.buf).split())
   self.capture=None; self.target=None; self.buf=[]


class PlainTextParser(HTMLParser):
 def __init__(self):
  super().__init__(); self.parts=[]; self.skip=0
 def handle_starttag(self,tag,attrs):
  if tag in ('script','style','noscript','svg'): self.skip+=1
 def handle_endtag(self,tag):
  if tag in ('script','style','noscript','svg') and self.skip: self.skip-=1
  elif tag in ('p','div','li','br','h1','h2','h3','tr'): self.parts.append('\n')
 def handle_data(self,data):
  if not self.skip:
   value=' '.join(data.split())
   if value: self.parts.append(value)

def direct_japanese_fallback(sign):
 """Try a known Japanese horoscope page if general search engines fail."""
 # Web-さんいんの星座別週間運勢ページ。番号は黄道12星座の順。
 codes={name:f'{i:02d}' for i,name in enumerate(ZODIAC_SIGNS,1)}
 code=codes.get(sign)
 if not code: return []
 url=f'https://www.web-sanin.co.jp/amuse/astrol/update/daily/{code}.html'
 headers={'User-Agent':'Mozilla/5.0 (compatible; NyalSama/1.0)','Accept-Language':'ja-JP,ja;q=0.9'}
 try:
  req=urllib.request.Request(url,headers=headers)
  with urllib.request.urlopen(req,timeout=5) as response:
   raw=response.read(900_000)
   charset=response.headers.get_content_charset() or 'utf-8'
  html=raw.decode(charset,'replace')
  parser=PlainTextParser(); parser.feed(html)
  text=' '.join(' '.join(parser.parts).split())
  # Require a Japanese horoscope page with the requested sign; do not accept generic pages.
  if not any(x in text for x in (sign, sign.replace('お',''))): return []
  if not any(x in text for x in ('運勢','ラッキーカラー','ラッキーアイテム')): return []
  today=date.today()
  date_forms=(f'{today.month}月{today.day}日', f'{today.month}月{today.day}日（', f'{today.month}月{today.day}日(')
  pos=next((text.find(x) for x in date_forms if text.find(x)>=0),-1)
  if pos>=0:
   snippet=text[max(0,pos-100):pos+1000]
  else:
   snippet=text[:1200]
  snippet=' '.join(snippet.split())
  return [{'title':f'Web-さんいん 星占い {sign}', 'url':url, 'snippet':snippet}]
 except Exception as exc:
  print(f'Direct Japanese horoscope fallback failed: {type(exc).__name__}: {str(exc)[:160]}')
  return []

def search_horoscopes(sign):
 """Search horoscope pages with DuckDuckGo first, then Bing RSS as a fallback."""
 today=date.today().strftime('%Y年%m月%d日')
 query=f'{today} {sign} 今日の運勢 星占い'
 failures=[]
 headers={
  'User-Agent':'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/125.0 Safari/537.36',
  'Accept-Language':'ja-JP,ja;q=0.9,en;q=0.7',
 }
 # 検索先ごとに失敗を切り分け、片方が使えなくてももう片方を試す。
 engines=[
  ('DuckDuckGo','https://html.duckduckgo.com/html/?'+urllib.parse.urlencode({'q':query})),
  ('Bing RSS','https://www.bing.com/search?'+urllib.parse.urlencode({'format':'rss','q':query})),
 ]
 for engine,url in engines:
  try:
   req=urllib.request.Request(url,headers=headers)
   with urllib.request.urlopen(req,timeout=6) as response:
    raw=response.read(1_500_000)
    charset=response.headers.get_content_charset() or 'utf-8'
   body=raw.decode(charset,'replace')
   found=[]
   if engine=='DuckDuckGo':
    parser=DDGResults(); parser.feed(body)
    for item in parser.results:
     link=item.get('url','')
     parsed=urllib.parse.urlparse(link)
     if 'duckduckgo.com' in parsed.netloc:
      target=urllib.parse.parse_qs(parsed.query).get('uddg',[''])[0]
      if target: link=urllib.parse.unquote(target)
     if link.startswith('http') and 'duckduckgo.com' not in urllib.parse.urlparse(link).netloc:
      found.append({'title':item.get('title','').strip() or link,'url':link,'snippet':item.get('snippet','').strip()})
   else:
    root=ET.fromstring(body)
    for item in root.findall('.//item'):
     link=(item.findtext('link') or '').strip()
     title=(item.findtext('title') or '').strip()
     snippet=(item.findtext('description') or '').strip()
     if link.startswith('http') and title:
      # RSS descriptions may contain markup; remove tags and decode entities.
      snippet=re.sub(r'<[^>]+>',' ',snippet)
      from html import unescape
      snippet=' '.join(unescape(snippet).split())
      found.append({'title':title,'url':link,'snippet':snippet})
   # 占いと無関係な英語ページ（礼拝案内・聖書など）を除外する。
   # 日本語を含み、星座・運勢に関する語がある結果だけ採用する。
   relevant_terms=('運勢','星占い','占い','星座','ラッキー','金運','恋愛運','仕事運',
                   'おひつじ座','おうし座','ふたご座','かに座','しし座','おとめ座',
                   'てんびん座','さそり座','いて座','やぎ座','みずがめ座','うお座',
                   '牡羊座','牡牛座','双子座','蟹座','獅子座','乙女座','天秤座',
                   '蠍座','射手座','山羊座','水瓶座','魚座')
   out=[]; seen=set()
   for item in found:
    link=item['url']
    title=' '.join(item.get('title','').split())
    snippet=' '.join(item.get('snippet','').split())
    combined=title+' '+snippet
    has_japanese=bool(re.search(r'[ぁ-んァ-ヶ一-龯]', combined))
    is_horoscope=any(term in combined for term in relevant_terms)
    if not has_japanese or not is_horoscope:
     continue
    if link in seen: continue
    seen.add(link)
    item['title']=title
    item['snippet']=snippet
    out.append(item)
    if len(out)>=6: break
   if out:
    print(f'Horoscope search: {engine} returned {len(out)} relevant Japanese results')
    return out
   failures.append(f'{engine}: no relevant Japanese horoscope results')
   failures.append(f'{engine}: no parseable results (HTTP response received)')
  except Exception as exc:
   failures.append(f'{engine}: {type(exc).__name__}: {str(exc)[:180]}')
 direct=direct_japanese_fallback(sign)
 if direct:
  print('Horoscope search: direct Japanese horoscope source returned 1 result')
  return direct
 failures.append('Direct Japanese horoscope page: no usable content')
 print('Horoscope search failed: ' + ' | '.join(failures)[:700])
 return []

def predict(p):
 sign=(p['zodiac'] or '').strip()
 if sign not in ZODIAC_SIGNS:
  raise ValueError('先に「記憶の管理」で星座を選んで保存してニャ。')
 if not key(): raise RuntimeError('Gemini APIキーが設定されていません。')
 today=date.today().strftime('%Y年%m月%d日')
 results=search_horoscopes(sign)
 if not results: raise RuntimeError('日本語の星占い検索結果を見つけられなかったニャ。少し時間をおいて、もう一度試してニャ。')
 source_text='\n'.join(f"{i+1}. {x['title']}\nURL: {x['url']}\n検索結果の説明: {x.get('snippet','（説明文なし）')}" for i,x in enumerate(results))
 prompt=f'''以下はウェブ検索で見つけた占いサイトの検索結果です。内容に書かれていないことを事実のように作らず、複数の結果に共通する傾向を中心に日本語で要約してください。対象日:{today}、星座:{sign}。全体運・対人運・仕事運/学業運・金運・ラッキーアドバイスを簡潔にまとめてください。検索結果だけでは根拠が足りない項目は「情報なし」としてください。占いは娯楽として楽しむもので、医療・金銭などの重要判断を促さないでください。\n\n検索結果:\n{source_text}'''
 # Gemini呼び出しは既存の ask() をそのまま使用する。
 # 要約API側で例外が起きても、取得済み検索結果から簡易まとめを作成する。
 try:
  summary=ask(prompt,'あなたは大預言猫ニャル様。愛嬌ある猫の占い師として、やさしく読みやすい日本語で、根拠のない断定を避けて要約する。',tokens=650)
  if not summary:
   raise RuntimeError('Gemini returned empty summary')
 except Exception as exc:
  msg=str(exc)
  for n in ('GOOGLE_API_KEY','GEMINI_API_KEY'):
   v=os.environ.get(n,'').strip()
   if v: msg=msg.replace(v,'[REDACTED]')
  print(f'Horoscope summary Gemini failed; using search snippets only: {type(exc).__name__}: {msg[:500]}')
  # Gemini がタイムアウトしても、検索結果の説明文だけで代替表示する。
  # 不完全な検索結果や None が混ざっても、代替処理自体が例外にならないようにする。
  relevant_terms=(
   '運勢','星占い','占い','星座','ラッキー','金運','恋愛運','仕事運',
   'おひつじ座','おうし座','ふたご座','かに座','しし座','おとめ座',
   'てんびん座','さそり座','いて座','やぎ座','みずがめ座','うお座',
   '牡羊座','牡牛座','双子座','蟹座','獅子座','乙女座','天秤座',
   '蠍座','射手座','山羊座','水瓶座','魚座'
  )
  snippets=[]
  for item in results if isinstance(results, (list, tuple)) else []:
   if not isinstance(item, dict):
    continue
   title=str(item.get('title') or '').strip()
   snippet=' '.join(str(item.get('snippet') or '').split())
   combined=title+' '+snippet
   if snippet and re.search(r'[ぁ-んァ-ヶ一-龯]', combined) and any(term in combined for term in relevant_terms):
    snippets.append(snippet)
  if snippets:
   summary='検索結果の説明文をもとにした簡易まとめニャ。\\n' + '\\n'.join(f'・{x[:260]}' for x in snippets[:4]) + '\\n\\nこれは検索結果の説明文に基づく簡易版ニャ。詳しい内容は下の出典サイトで確認してほしいニャ。'
  else:
   summary='検索結果は見つかったものの、説明文を十分に取得できなかったニャ。下の出典サイトを開いて今日の運勢を確認してほしいニャ。'
  source_lines=[]
  for item in results if isinstance(results, (list, tuple)) else []:
   if isinstance(item, dict):
    title=str(item.get('title') or '占いサイト').replace('|','｜').replace('\\n',' ')
    url=str(item.get('url') or '').strip()
    if url.startswith(('https://','http://')):
     source_lines.append(f'{title}|{url}')
  sources='\\n'.join(source_lines)
 return f'【{today}・{sign}の今日の運勢】\n{summary}',sources
@app.before_request
def csrf():
 if 'csrf' not in session:session['csrf']=secrets.token_urlsafe(24)
@app.context_processor
def globals():return {'csrf_token':session.get('csrf','')}
def check():
 if not secrets.compare_digest(request.form.get('csrf_token',''),session.get('csrf','')):abort(400)
@app.route('/about')
def about():
 return render_template('about.html')

@app.route('/')
def index():
 p=profile()
 with db() as c: ms=c.execute('SELECT * FROM messages ORDER BY id DESC LIMIT 30').fetchall(); ps=c.execute('SELECT * FROM predictions ORDER BY id DESC LIMIT 5').fetchall()
 return render_template('index.html',profile=p,messages=list(reversed(ms)),predictions=ps)
@app.post('/chat')
def chat():
 check(); t=request.form.get('message','').strip()
 if not t:flash('ひとこと入力してニャ。','warning')
 elif len(t)>1000:flash('メッセージは1,000文字以内にしてニャ。','warning')
 else:add('user',t);add('cat',reply(t))
 return redirect(url_for('index'))
@app.post('/predict')
def do_predict():
 check()
 try: out,sources=predict(profile())
 except ValueError as e: flash(str(e),'warning');return redirect(url_for('memory'))
 except Exception as e:
  msg=str(e)
  for n in ('GOOGLE_API_KEY','GEMINI_API_KEY'):
   v=os.environ.get(n,'').strip()
   if v: msg=msg.replace(v,'[REDACTED]')
  print(f'Horoscope lookup failed: {type(e).__name__}: {msg[:500]}')
  flash(msg[:250] if isinstance(e,RuntimeError) else '占いの検索または要約に失敗したニャ。ネット接続とGemini APIを確認してニャ。','warning')
  return redirect(url_for('index'))
 with db() as c:c.execute('INSERT INTO predictions(prediction,sources,created_at) VALUES(?,?,?)',(out,sources,datetime.now().strftime('%Y-%m-%d %H:%M')))
 add('cat',out);flash('ネットの占いサイトを調べて、今日の運勢をまとめたニャ！','success');return redirect(url_for('index'))
@app.post('/prediction/<int:pid>/result')
def result(pid):
 check(); r=request.form.get('result',''); reacts={'当たった':'当然である！余の予言が外れるわけがないニャ！','惜しい':'宇宙の誤差範囲では的中である！','外れた':'現実のほうが予言に追いついていないだけニャ！'}
 if r not in reacts:abort(400)
 with db() as c:
  if not c.execute('SELECT id FROM predictions WHERE id=?',(pid,)).fetchone():abort(404)
  c.execute('UPDATE predictions SET result=? WHERE id=?',(r,pid))
 add('cat',reacts[r]);flash('結果を記録したニャ。','success');return redirect(url_for('index'))
@app.route('/memory',methods=['GET','POST'])
def memory():
 if request.method=='POST':
  check(); f={n:request.form.get(n,'').strip() for n in ('username','hobbies','preferences','thinking_style','notes','zodiac')}
  limits={'username':80,'hobbies':1000,'preferences':1000,'thinking_style':1000,'notes':1500,'zodiac':20}
  if f['zodiac'] and f['zodiac'] not in ZODIAC_SIGNS: flash('星座の選択が正しくないニャ。','warning');return redirect(url_for('memory'))
  for n,v in f.items():
   if len(v)>limits[n]:flash(f'{n}が長すぎるニャ。','warning');return redirect(url_for('memory'))
  with db() as c:c.execute('UPDATE profile SET username=?,hobbies=?,preferences=?,thinking_style=?,notes=?,zodiac=?,updated_at=? WHERE id=1',(*f.values(),datetime.now().strftime('%Y-%m-%d %H:%M')))
  flash('記憶を保存したニャ。','success');return redirect(url_for('memory'))
 return render_template('memory.html',profile=profile())
@app.post('/memory/delete')
def delete_memory():
 check()
 with db() as c:c.execute("UPDATE profile SET username='',hobbies='',preferences='',thinking_style='',notes='',zodiac='',updated_at=? WHERE id=1",(datetime.now().strftime('%Y-%m-%d %H:%M'),))
 flash('プロフィールの記憶を消去したニャ。','success');return redirect(url_for('memory'))
@app.post('/history/delete')
def delete_history():
 check()
 with db() as c:c.execute('DELETE FROM messages');c.execute('DELETE FROM predictions')
 flash('会話履歴と予言履歴を消去したニャ。','success');return redirect(url_for('index'))
if __name__=='__main__':
 init_db();print('大預言猫ニャル様: http://127.0.0.1:5000');print('ローカル利用専用です。既存の nyalsama.db をこのフォルダーに置くと履歴を引き継ぎます。');app.run(host='127.0.0.1',port=5000,debug=False)
