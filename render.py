"""Render the daily Yesterday's Professional Sport Report short.
Input : data/latest.json  (written by Zapier)
Output: out/video.mp4  (720x1280, ~44s: 4s highlights card, swipe up, scrolling full results, music + voice)
"""
import json, os, subprocess, sys, urllib.request, asyncio, html as H
import markdown, numpy as np, wave
from PIL import Image
from playwright.async_api import async_playwright

OUT = "out"; os.makedirs(OUT, exist_ok=True)
d = json.load(open("data/latest.json"))
DATE = d.get("date_label", "")
W, HGT = 720, 1280
SCROLL_SECS = 40
INTRO = 4

CSS = """
body{margin:0;background:#0b1f3a}
#w{width:1080px;background:#0b1f3a;color:#fff;font-family:Poppins,Arial,sans-serif;box-sizing:border-box}
.hdr{text-align:center;border-bottom:6px solid #f5b301;padding-bottom:30px;margin-bottom:30px}
.k{color:#f5b301;letter-spacing:6px;font-size:28px;font-weight:700}
.t{font-size:64px;font-weight:800;line-height:1.1}.s{font-size:30px;color:#c9d6ea;margin-top:10px}
h1{display:none}h2{background:#f5b301;color:#0b1f3a;font-size:44px;padding:14px 24px;margin:44px 0 18px;border-radius:8px}
p{font-size:34px;line-height:1.35;margin:10px 0}strong{color:#f5b301}ul{margin:6px 0 18px;padding-left:44px}
li{font-size:38px;line-height:1.35;margin:4px 0}hr{display:none}
.cta{text-align:center;margin-top:60px;font-size:40px;color:#f5b301;font-weight:700}
"""
HDR = f"""<div class=hdr><div class=k>YESTERDAY'S</div><div class=t>PROFESSIONAL SPORT REPORT</div>
<div class=s>{H.escape(DATE)}</div></div>"""

def fix(l):
    if l.startswith('**') and ' | ' in l and ':**' in l:
        head, rest = l.split(':**', 1)
        return head + ':**\n\n' + '\n'.join('- ' + i.strip() for i in rest.split(' | '))
    return l

md = d["results_md"]
md = '\n'.join(l for l in md.split('\n') if not l.startswith(('Compiled ', 'Rows marked')))
cut = md.find('## NOTHING FOUND')
if cut > 0: md = md[:cut]
md = '\n'.join(fix(l) for l in md.split('\n'))
body = markdown.markdown(md, extensions=['extra'])

scroll_html = f"<html><body><style>{CSS}</style><div id=w style='padding:60px 56px 200px'>{HDR}{body}<div class=cta>FOLLOW FOR TOMORROW'S SCORES</div></div></body></html>"

hook = H.escape(d.get("hook", ""))
_ost = d.get("on_screen_text", [])
if isinstance(_ost, str): _ost = [x.strip(" -•\t") for x in _ost.splitlines() if x.strip()]
bullets = ''.join(f"<li style='font-size:46px;margin:18px 0'>{H.escape(x)}</li>" for x in _ost[:6])
intro_html = f"""<html><body><style>{CSS}</style><div id=w style='height:1920px;padding:120px 70px;display:flex;flex-direction:column;justify-content:center'>
{HDR}<div style='font-size:60px;font-weight:800;line-height:1.2;margin:50px 0'>{hook}</div>
<ul style='padding-left:50px;font-size:48px'>{bullets}</ul>
<div class=cta>FULL RESULTS BELOW ↓</div></div></body></html>"""

async def shots():
    async with async_playwright() as p:
        b = await p.chromium.launch()
        pg = await b.new_page(viewport={'width': 1080, 'height': 1920})
        for name, h in (("intro", intro_html), ("tall", scroll_html)):
            await pg.set_content(h); await pg.wait_for_timeout(500)
            await (await pg.query_selector('#w')).screenshot(path=f"{OUT}/{name}_full.png")
        await b.close()
asyncio.run(shots())
for n in ("intro", "tall"):
    im = Image.open(f"{OUT}/{n}_full.png"); r = W / im.width
    im.resize((W, int(im.height * r)), Image.LANCZOS).save(f"{OUT}/{n}.png")

# --- voice ---
voice = None
if d.get("audio_url"):
    try:
        urllib.request.urlretrieve(d["audio_url"], f"{OUT}/voice.mp3"); voice = f"{OUT}/voice.mp3"
    except Exception as e:
        print("voice download failed:", e, file=sys.stderr)
if d.get("audio_local"): voice = d["audio_local"]
def dur(f):
    return float(subprocess.check_output(["ffprobe","-v","error","-show_entries","format=duration","-of","csv=p=0",f]).strip())
VOICE_LEN = dur(voice) if voice else 0
SCROLL_SECS = max(SCROLL_SECS, int(VOICE_LEN + 3 - INTRO))
TOTAL = INTRO + SCROLL_SECS

# --- original synthesized music loop (no copyright) ---
sr = 44100; bpm = 104; beat = 60 / bpm
chords = [(220.0, 261.63, 329.63), (174.61, 220.0, 261.63), (196.0, 246.94, 293.66), (164.81, 196.0, 246.94)]
bars = []
for ch in chords:
    n = int(sr * beat * 4); t = np.arange(n) / sr
    pad = sum(np.sin(2*np.pi*f*t) + 0.4*np.sin(2*np.pi*2*f*t) for f in ch) / 6
    pad *= np.minimum(1, t/0.05) * np.exp(-0.15*t)
    bass = np.sin(2*np.pi*ch[0]/2*t) * 0.5 * (np.floor(t/beat) % 2 == 0)
    hat = np.zeros(n)
    for i in range(8):
        s = int(i*beat/2*sr); m = int(0.05*sr)
        hat[s:s+m] += np.random.default_rng(i).standard_normal(len(hat[s:s+m])) * np.exp(-np.arange(len(hat[s:s+m]))/(0.012*sr)) * 0.12
    kick = np.zeros(n)
    for i in range(4):
        s = int(i*beat*sr); m = int(0.15*sr); tt = np.arange(m)/sr
        kick[s:s+m] += np.sin(2*np.pi*(50+80*np.exp(-tt*30))*tt) * np.exp(-tt*20) * 0.7
    bars.append(pad + bass + hat + kick)
loop = np.concatenate(bars); loop /= np.abs(loop).max()
reps = int(TOTAL / (len(loop)/sr)) + 2
music = np.tile(loop, reps)[: int(TOTAL * sr)]
with wave.open(f"{OUT}/music.wav", "w") as w:
    w.setnchannels(1); w.setsampwidth(2); w.setframerate(sr); w.writeframes((music*32000).astype(np.int16).tobytes())

# --- video ---
FPS = 24
XF = 1.0
vf = (f"[0:v]scale={W}:{HGT},setsar=1[a];"
      f"[1:v]crop={W}:{HGT}:0:'(ih-{HGT})*t/{SCROLL_SECS}',setsar=1[b];[a][b]xfade=transition=slideup:duration={XF}:offset={INTRO-XF}[v]")
mus_vol = f"volume='if(lt(t,{VOICE_LEN+1}),0.18,0.5)':eval=frame"
cmd = ["ffmpeg", "-y",
       "-loop", "1", "-framerate", str(FPS), "-t", str(INTRO), "-i", f"{OUT}/intro.png",
       "-loop", "1", "-framerate", str(FPS), "-t", str(SCROLL_SECS), "-i", f"{OUT}/tall.png",
       "-i", f"{OUT}/music.wav"]
if voice: cmd += ["-i", voice]
af = f"[2:a]{mus_vol}[m]"
if voice: af += f";[3:a]volume=1.6[vo];[m][vo]amix=inputs=2:duration=first:normalize=0[aud]"
else: af += ";[m]anull[aud]"
cmd += ["-filter_complex", vf + ";" + af, "-map", "[v]", "-map", "[aud]", "-t", str(TOTAL - XF),
        "-c:v", "libx264", "-preset", "veryfast", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "160k",
        "-movflags", "+faststart", f"{OUT}/video.mp4"]
subprocess.check_call(cmd)
print("done", TOTAL)
