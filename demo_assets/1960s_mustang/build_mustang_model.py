import json, math, zipfile
from pathlib import Path
OUT = Path(__file__).resolve().parent
OBJ = OUT / 'stylized_1960s_mustang.obj'
MTL = OUT / 'stylized_1960s_mustang.mtl'
README = OUT / 'README.txt'
MANIFEST = OUT / 'asset_manifest.json'
ZIP = OUT / 'stylized_1960s_mustang_asset_pack.zip'
verts=[]; faces=[]
materials={
 'paint_highland_green':(.03,.18,.11,1,.35),'paint_dark_shadow':(.015,.06,.04,1,.2),'chrome':(.78,.76,.70,1,.95),'rubber_black':(.005,.005,.005,1,.05),'glass_blue':(.18,.42,.62,.55,.55),'cream_stripe':(.93,.86,.67,1,.25),'headlight_warm':(1,.92,.72,1,.65),'tail_red':(.85,.02,.01,1,.3),'grille_black':(.01,.012,.012,1,.1)}
def add_v(p):
    verts.append(tuple(round(float(x),5) for x in p)); return len(verts)
def add_face(mat, pts): faces.append((mat,[add_v(p) for p in pts]))
def box(cx,cy,cz,sx,sy,sz,mat):
    x0,x1=cx-sx/2,cx+sx/2; y0,y1=cy-sy/2,cy+sy/2; z0,z1=cz-sz/2,cz+sz/2
    p=[(x0,y0,z0),(x1,y0,z0),(x1,y1,z0),(x0,y1,z0),(x0,y0,z1),(x1,y0,z1),(x1,y1,z1),(x0,y1,z1)]
    for q in ([0,1,2,3],[4,7,6,5],[0,4,5,1],[1,5,6,2],[2,6,7,3],[3,7,4,0]): add_face(mat,[p[i] for i in q])
def trapezoid(cx,cy,cz,length,bottom_w,top_w,height,mat,slope_front=0,slope_back=0):
    x0,x1=cx-length/2,cx+length/2; yb0,yb1=cy-bottom_w/2,cy+bottom_w/2; yt0,yt1=cy-top_w/2,cy+top_w/2; z0,z1=cz-height/2,cz+height/2
    b=[(x0,yb0,z0),(x1,yb0,z0),(x1,yb1,z0),(x0,yb1,z0)]; t=[(x0+slope_front,yt0,z1),(x1-slope_back,yt0,z1),(x1-slope_back,yt1,z1),(x0+slope_front,yt1,z1)]
    add_face(mat,b); add_face(mat,[t[0],t[3],t[2],t[1]])
    for a,c in [(0,1),(1,2),(2,3),(3,0)]: add_face(mat,[b[a],t[a],t[c],b[c]])
def wedge_roof():
    mat='paint_highland_green'
    lower=[(-1.15,-.72,.78),(-.85,-.86,.86),(.35,-.80,.86),(1.30,-.68,.78)]
    upper=[(-1.05,-.48,.92),(-.68,-.52,1.72),(.05,-.49,1.72),(1.00,-.45,.92)]
    ml=[(x,-y,z) for x,y,z in lower]; mu=[(x,-y,z) for x,y,z in upper]
    for i in range(4):
        j=(i+1)%4; add_face(mat,[lower[i],lower[j],upper[j],upper[i]]); add_face(mat,[ml[i],mu[i],mu[j],ml[j]])
    add_face(mat,[upper[1],upper[2],mu[2],mu[1]]); add_face(mat,[upper[2],upper[3],mu[3],mu[2]]); add_face(mat,[upper[0],upper[1],mu[1],mu[0]])
def cylinder(cx,cy,cz,r,depth,mat,segments=40):
    front=[]; back=[]
    for i in range(segments):
        a=2*math.pi*i/segments; front.append((cx+math.cos(a)*r,cy-depth/2,cz+math.sin(a)*r)); back.append((cx+math.cos(a)*r,cy+depth/2,cz+math.sin(a)*r))
    for i in range(segments): add_face(mat,[front[i],front[(i+1)%segments],back[(i+1)%segments],back[i]])
    add_face(mat,list(reversed(front))); add_face(mat,back)
def wheel(x,y):
    cylinder(x,y,0,.46,.34,'rubber_black'); cylinder(x,y*1.002,0,.27,.36,'chrome',32); cylinder(x,y*1.004,0,.13,.38,'paint_dark_shadow',24)
# body
trapezoid(0,0,.42,5.65,1.82,1.64,.78,'paint_highland_green',.12,.08)
trapezoid(-1.35,0,.80,2.15,1.66,1.48,.32,'paint_highland_green',.10,.05)
trapezoid(1.40,0,.74,1.25,1.60,1.45,.25,'paint_highland_green',.03,.08)
wedge_roof()
# glass
box(-.85,0,1.14,.06,1.07,.52,'glass_blue'); box(.52,0,1.21,.08,.96,.50,'glass_blue'); box(-.17,-.835,1.20,1.18,.035,.45,'glass_blue'); box(-.17,.835,1.20,1.18,.035,.45,'glass_blue')
# trim/details
box(-2.88,0,.46,.08,1.16,.36,'grille_black'); box(-2.98,0,.22,.10,1.84,.12,'chrome'); box(2.86,0,.26,.12,1.76,.12,'chrome')
box(-2.94,-.47,.54,.06,.22,.22,'headlight_warm'); box(-2.94,.47,.54,.06,.22,.22,'headlight_warm')
for y in [-.52,-.40,-.28,.28,.40,.52]: box(2.95,y,.55,.05,.08,.28,'tail_red')
box(-1.20,0,1.005,2.05,.18,.035,'cream_stripe'); box(-.05,0,1.75,1.08,.14,.035,'cream_stripe'); box(1.55,0,.895,1.08,.16,.035,'cream_stripe')
box(0,-.94,.23,5.15,.035,.07,'chrome'); box(0,.94,.23,5.15,.035,.07,'chrome'); box(.70,-.94,.55,.54,.06,.22,'grille_black'); box(.70,.94,.55,.54,.06,.22,'grille_black')
for x in (-1.70,1.58): wheel(x,-.97); wheel(x,.97)
box(0,0,-.52,6.3,2.5,.05,'paint_dark_shadow')
with MTL.open('w',encoding='utf-8') as f:
    f.write('# Materials for stylized_1960s_mustang.obj\n')
    for name,(r,g,b,a,shine) in materials.items():
        f.write(f'newmtl {name}\nKa {r*.4:.4f} {g*.4:.4f} {b*.4:.4f}\nKd {r:.4f} {g:.4f} {b:.4f}\nKs {shine:.4f} {shine:.4f} {shine:.4f}\nNs {80+shine*600:.1f}\n')
        if a<1: f.write(f'd {a:.4f}\nTr {1-a:.4f}\n')
        f.write('\n')
with OBJ.open('w',encoding='utf-8') as f:
    f.write('# Stylized clean-room 1960s Mustang-inspired 3D model generated procedurally.\n# No manufacturer logos or copied CAD data are included.\n')
    f.write(f'mtllib {MTL.name}\no stylized_1960s_mustang\n')
    for v in verts: f.write(f'v {v[0]} {v[1]} {v[2]}\n')
    cur=None
    for mat,idx in faces:
        if mat!=cur: f.write(f'usemtl {mat}\n'); cur=mat
        f.write('f '+' '.join(map(str,idx))+'\n')
manifest={'asset':'stylized_1960s_mustang','description':'Procedural clean-room, low-poly 1960s Mustang-inspired coupe/fastback demonstration asset.','geometry':{'vertices':len(verts),'faces':len(faces),'materials':sorted(materials)},'features':['long hood','short rear deck','fastback roofline','chrome bumpers','round headlights','triple tail lamps','side scoops','cream racing stripe','four detailed wheels'],'license_note':'Created from scratch; excludes logos/badges/proprietary CAD.'}
MANIFEST.write_text(json.dumps(manifest,indent=2),encoding='utf-8')
README.write_text('Stylized 1960s Mustang-inspired 3D Model Demo Asset\n\nImport stylized_1960s_mustang.obj into Blender, Unity, Unreal, or any OBJ-compatible viewer. Keep the .mtl file in the same folder.\n\nClean-room procedural model: long hood, short rear deck, fastback cabin, chrome bumpers, round headlights, side scoops, racing stripe, four wheels, and triple rear lamps. No manufacturer logos, badges, or copied CAD/mesh data are included.\n',encoding='utf-8')
if ZIP.exists(): ZIP.unlink()
with zipfile.ZipFile(ZIP,'w',zipfile.ZIP_DEFLATED) as z:
    for p in [OBJ,MTL,MANIFEST,README]: z.write(p,p.name)
print(json.dumps({'output_dir':str(OUT),'obj':str(OBJ),'mtl':str(MTL),'zip':str(ZIP),'vertices':len(verts),'faces':len(faces)},indent=2))
