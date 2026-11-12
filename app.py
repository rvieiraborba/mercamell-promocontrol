#!/usr/bin/env python3
"""Mercamell PromoControl 3.1 — multi-evento, local/offline, SQLite.
Executa somente em 127.0.0.1. Requer Python 3.9+ sem pacotes externos.
Sorteio aleatório LOCAL: usar para apuração apenas quando previsto no regulamento.
"""
import csv
import base64
import binascii
from contextlib import contextmanager
import io
import json
import re
import secrets
import sqlite3
import sys
import threading
import webbrowser
from datetime import datetime
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse, parse_qs

ROOT = Path(__file__).resolve().parent
DATA_DIR = ROOT / 'dados'
DATA_DIR.mkdir(exist_ok=True)
DEMO = '--demo' in sys.argv
PORT = 8768 if DEMO else 8767
DB_FILE = DATA_DIR / ('mercamell_demo.db' if DEMO else 'mercamell_promocontrol.db')
LOCK = threading.RLock()
DEFAULT_TIERS = [{'amount_cents':2500, 'tickets':1}, {'amount_cents':5000,'tickets':2}, {'amount_cents':8000,'tickets':3}]
DEFAULT_BRANDS = ['Honey Cake','Granuti','New York Slices','Vittai']
DEFAULT_PRIZES = ['Air fryer','Sanduicheira','Abridor elétrico de vinho']
TABLES = {
    'events':['id','name','event_date','description','tiers_json','brands_json','bonus_count','max_tickets','prizes_json','frozen','archived','created_at'],
    'participants':['id','event_id','name','phone','apartment','note','created_at'],
    'purchases':['id','event_id','participant_id','amount_cents','transaction_id','transaction_key','brands_json','created_at','voided_at','event_seq'],
    'tickets':['id','event_id','participant_id','number','status','created_at','changed_at'],
    'winners':['id','event_id','prize_order','prize','ticket_id','participant_id','created_at'],
    'audit':['id','event_id','action','details','created_at'],
    'draw_attempts':['id','event_id','prize_order','prize','ticket_id','participant_id','status','created_at','resolved_at'],
    'prize_images':['event_id','prize_order','data_url','updated_at']
}

def now(): return datetime.now().astimezone().isoformat(timespec='seconds')
def connect():
    c=sqlite3.connect(str(DB_FILE),timeout=20)
    c.row_factory=sqlite3.Row
    c.execute('PRAGMA foreign_keys=ON')
    c.execute('PRAGMA busy_timeout=20000')
    return c

@contextmanager
def db():
    c=connect()
    try:
        with c:
            yield c
    finally:
        c.close()

def init_db():
    with db() as c:
        c.executescript('''
        CREATE TABLE IF NOT EXISTS events (
         id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, event_date TEXT NOT NULL DEFAULT '',
         description TEXT NOT NULL DEFAULT '', tiers_json TEXT NOT NULL, brands_json TEXT NOT NULL,
         bonus_count INTEGER NOT NULL DEFAULT 1, max_tickets INTEGER NOT NULL DEFAULT 4,
         prizes_json TEXT NOT NULL, frozen INTEGER NOT NULL DEFAULT 0, archived INTEGER NOT NULL DEFAULT 0,
         created_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS participants (
         id INTEGER PRIMARY KEY AUTOINCREMENT, event_id INTEGER NOT NULL REFERENCES events(id),
         name TEXT NOT NULL, phone TEXT NOT NULL DEFAULT '', apartment TEXT NOT NULL DEFAULT '', note TEXT NOT NULL DEFAULT '', created_at TEXT NOT NULL);
        CREATE UNIQUE INDEX IF NOT EXISTS uq_phone_event ON participants(event_id,phone) WHERE phone<>'';
        CREATE TABLE IF NOT EXISTS purchases (
         id INTEGER PRIMARY KEY AUTOINCREMENT, event_id INTEGER NOT NULL REFERENCES events(id),
         participant_id INTEGER NOT NULL REFERENCES participants(id), amount_cents INTEGER NOT NULL CHECK(amount_cents>0),
         transaction_id TEXT NOT NULL, transaction_key TEXT NOT NULL, brands_json TEXT NOT NULL DEFAULT '[]',
         created_at TEXT NOT NULL, voided_at TEXT, event_seq INTEGER NOT NULL DEFAULT 0);
        CREATE UNIQUE INDEX IF NOT EXISTS uq_tx_event ON purchases(event_id,transaction_key);
        CREATE INDEX IF NOT EXISTS idx_purchase_person ON purchases(event_id,participant_id);
        CREATE TABLE IF NOT EXISTS tickets (
         id INTEGER PRIMARY KEY AUTOINCREMENT, event_id INTEGER NOT NULL REFERENCES events(id),
         participant_id INTEGER NOT NULL REFERENCES participants(id), number INTEGER NOT NULL,
         status TEXT NOT NULL DEFAULT 'ACTIVE' CHECK(status IN ('ACTIVE','VOID','WINNER','REMOVED')),
         created_at TEXT NOT NULL,changed_at TEXT,UNIQUE(event_id,number));
        CREATE INDEX IF NOT EXISTS idx_tickets_owner ON tickets(event_id,participant_id);
        CREATE TABLE IF NOT EXISTS winners (
         id INTEGER PRIMARY KEY AUTOINCREMENT,event_id INTEGER NOT NULL REFERENCES events(id),
         prize_order INTEGER NOT NULL,prize TEXT NOT NULL,ticket_id INTEGER NOT NULL UNIQUE REFERENCES tickets(id),
         participant_id INTEGER NOT NULL REFERENCES participants(id),created_at TEXT NOT NULL,
         UNIQUE(event_id,prize_order),UNIQUE(event_id,participant_id));
        CREATE TABLE IF NOT EXISTS audit (
         id INTEGER PRIMARY KEY AUTOINCREMENT,event_id INTEGER REFERENCES events(id),
         action TEXT NOT NULL,details TEXT NOT NULL, created_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS draw_attempts (
         id INTEGER PRIMARY KEY AUTOINCREMENT, event_id INTEGER NOT NULL REFERENCES events(id),
         prize_order INTEGER NOT NULL, prize TEXT NOT NULL,
         ticket_id INTEGER NOT NULL REFERENCES tickets(id),participant_id INTEGER NOT NULL REFERENCES participants(id),
         status TEXT NOT NULL CHECK(status IN ('PENDING','DECLINED','ACCEPTED')),
         created_at TEXT NOT NULL,resolved_at TEXT);
        CREATE UNIQUE INDEX IF NOT EXISTS uq_pending_attempt_event ON draw_attempts(event_id) WHERE status='PENDING';
        CREATE INDEX IF NOT EXISTS idx_attempts_event ON draw_attempts(event_id,prize_order,status);
        CREATE TABLE IF NOT EXISTS prize_images (
         event_id INTEGER NOT NULL REFERENCES events(id) ON DELETE CASCADE,
         prize_order INTEGER NOT NULL CHECK(prize_order BETWEEN 1 AND 10),
         data_url TEXT NOT NULL, updated_at TEXT NOT NULL,
         PRIMARY KEY(event_id,prize_order));
        ''')
        # Migração automática de arquivos SQLite criados nas versões anteriores.
        cols={r['name'] for r in c.execute('PRAGMA table_info(participants)')}
        if 'apartment' not in cols:
            c.execute("ALTER TABLE participants ADD COLUMN apartment TEXT NOT NULL DEFAULT ''")
        purchase_cols={r['name'] for r in c.execute('PRAGMA table_info(purchases)')}
        if 'event_seq' not in purchase_cols:
            c.execute('ALTER TABLE purchases ADD COLUMN event_seq INTEGER NOT NULL DEFAULT 0')
        assign_purchase_sequences(c)
        c.execute('CREATE UNIQUE INDEX IF NOT EXISTS uq_purchase_event_seq ON purchases(event_id,event_seq) WHERE event_seq>0')
        if DEMO and c.execute('SELECT COUNT(*) FROM events').fetchone()[0]==0:
            event_id=insert_event(c,'Reinauguração Kiruna — DEMONSTRAÇÃO','2026-11-06','Dados fictícios para testar')
            for i,(name,amount,brands) in enumerate([('Ana Exemplo',2500,[]),('João Exemplo',5000,['Honey Cake']),('Carla Exemplo',8000,['Vittai']),('Pedro Exemplo',6000,[])]):
                c.execute('INSERT INTO participants(event_id,name,phone,note,created_at) VALUES (?, ?,"","Fictício",?)',(event_id,name,now()))
                pid=c.execute('SELECT last_insert_rowid()').fetchone()[0]
                tx='DEMO'+str(i+1)
                c.execute('INSERT INTO purchases(event_id,participant_id,amount_cents,transaction_id,transaction_key,brands_json,created_at,event_seq) VALUES (?,?,?,?,?,?,?,?)',(event_id,pid,amount,tx,tx,json.dumps(brands),now(),i+1))
                reconcile(c,event_id,pid)

def assign_purchase_sequences(c):
    """Preenche sequências de bases antigas pela ordem de inclusão, sem reenumerar as existentes."""
    max_by_event={r['event_id']:r['highest'] for r in c.execute(
        'SELECT event_id,MAX(event_seq) AS highest FROM purchases WHERE event_seq>0 GROUP BY event_id')}
    for row in c.execute('SELECT id,event_id FROM purchases WHERE event_seq<=0 ORDER BY event_id,id').fetchall():
        eid=row['event_id'];seq=max_by_event.get(eid,0)+1
        c.execute('UPDATE purchases SET event_seq=? WHERE id=?',(seq,row['id']))
        max_by_event[eid]=seq

def purchase_code(event_id,sequence):
    return f'{int(event_id):03d}-{int(sequence):06d}'

def validate_prize_image(value):
    if not isinstance(value,str) or len(value)>750_000:
        raise ValueError('Imagem inválida ou muito grande (máximo 500 KB após compactação).')
    found=re.fullmatch(r'data:image/(jpeg|png);base64,([a-zA-Z0-9+/]+={0,2})',value)
    if not found:raise ValueError('Envie uma imagem JPG ou PNG válida.')
    try:raw=base64.b64decode(found.group(2),validate=True)
    except (ValueError,binascii.Error):raise ValueError('Imagem corrompida.')
    if len(raw)>500_000 or not raw:raise ValueError('Imagem muito grande; limite 500 KB por prêmio.')
    if found.group(1)=='jpeg' and not raw.startswith(b'\xff\xd8\xff'):
        raise ValueError('Arquivo JPG inválido.')
    if found.group(1)=='png' and not raw.startswith(b'\x89PNG\r\n\x1a\n'):
        raise ValueError('Arquivo PNG inválido.')
    return value

def audit(c,event_id,action,details):
    c.execute('INSERT INTO audit(event_id,action,details,created_at) VALUES (?,?,?,?)',(event_id,action,json.dumps(details,ensure_ascii=False),now()))

def get_event(c,event_id):
    e=c.execute('SELECT * FROM events WHERE id=?',(event_id,)).fetchone()
    if not e:raise ValueError('Evento não encontrado.')
    return e

def event_info(e):
    return {'id':e['id'],'name':e['name'],'event_date':e['event_date'],'description':e['description'],
       'tiers':json.loads(e['tiers_json']),'brands':json.loads(e['brands_json']),
       'bonus_count':e['bonus_count'],'max_tickets':e['max_tickets'],'prizes':json.loads(e['prizes_json']),
       'frozen':bool(e['frozen']),'archived':bool(e['archived']),'created_at':e['created_at']}

def rules_from(payload):
    tiers=payload.get('tiers',DEFAULT_TIERS)
    if not isinstance(tiers,list) or not 1<=len(tiers)<=8:raise ValueError('Informe de 1 a 8 faixas de participação.')
    cleaned=[]
    for r in tiers:
        if not isinstance(r,dict):raise ValueError('Faixa inválida.')
        a=int(r.get('amount_cents',0));n=int(r.get('tickets',0))
        if not 100<=a<=10_000_000 or not 1<=n<=100:raise ValueError('Valores ou números das faixas inválidos.')
        cleaned.append({'amount_cents':a,'tickets':n})
    cleaned.sort(key=lambda k:k['amount_cents'])
    if any(cleaned[i]['amount_cents']>=cleaned[i+1]['amount_cents'] or cleaned[i]['tickets']>=cleaned[i+1]['tickets'] for i in range(len(cleaned)-1)):
        raise ValueError('As faixas devem ter valores e números estritamente crescentes.')
    brands=payload.get('brands',DEFAULT_BRANDS)
    if not isinstance(brands,list) or len(brands)>30:raise ValueError('Lista de marcas inválida.')
    brands=[str(x).strip() for x in brands]
    if any(not x or len(x)>60 for x in brands) or len(set(x.casefold() for x in brands))!=len(brands):
        raise ValueError('Marcas devem ser únicas, com até 60 caracteres.')
    bonus=int(payload.get('bonus_count',1));maximum=int(payload.get('max_tickets',4))
    if bonus<0 or bonus>20 or maximum<1 or maximum>100 or max(r['tickets'] for r in cleaned)>maximum:
        raise ValueError('Bônus e limite inconsistentes com as faixas.')
    prizes=payload.get('prizes',DEFAULT_PRIZES)
    if not isinstance(prizes,list) or not 1<=len(prizes)<=10:raise ValueError('Informe de 1 a 10 prêmios.')
    prizes=[str(x).strip() for x in prizes]
    if any(not x or len(x)>100 for x in prizes):raise ValueError('Descrição de prêmio inválida.')
    return cleaned,brands,bonus,maximum,prizes

def insert_event(c,name,event_date='',description='',settings=None):
    if not 3<=len(name.strip())<=120:raise ValueError('Nome do evento deve ter entre 3 e 120 caracteres.')
    if event_date and (not re.fullmatch(r'\d{4}-\d{2}-\d{2}',event_date)):
        raise ValueError('Data do evento inválida.')
    if event_date:
        try:datetime.strptime(event_date,'%Y-%m-%d')
        except ValueError:raise ValueError('Data do evento inválida.')
    tiers,brands,bonus,maximum,prizes=rules_from(settings or {})
    c.execute('''INSERT INTO events(name,event_date,description,tiers_json,brands_json,bonus_count,max_tickets,prizes_json,created_at)
       VALUES (?,?,?,?,?,?,?,?,?)''',(name.strip(),event_date,description[:500],json.dumps(tiers),json.dumps(brands,ensure_ascii=False),bonus,maximum,json.dumps(prizes,ensure_ascii=False),now()))
    eid=c.execute('SELECT last_insert_rowid()').fetchone()[0]
    audit(c,eid,'CREATE_EVENT',{'name':name})
    return eid

def parse_cents(value):
    try:
        d=Decimal(str(value).strip().replace(',','.'))
        if not d.is_finite() or d.as_tuple().exponent < -2:raise ValueError()
        d=d.quantize(Decimal('0.01'),rounding=ROUND_HALF_UP)
    except (InvalidOperation,ValueError):raise ValueError('Informe um valor monetário válido, com até duas casas decimais.')
    if d<=0 or d>100000:raise ValueError('Valor deve estar entre R$ 0,01 e R$ 100.000.')
    return int(d*100)

def ensure_open(e):
    if e['frozen']:raise ValueError('Evento fechado: cancele a apuração e reabra antes de alterar cadastros.')
    if e['archived']:raise ValueError('Evento arquivado. Reative antes de registrar compras.')

def count_entitlement(c,event_id,participant_id):
    e=get_event(c,event_id)
    r=c.execute('SELECT amount_cents,brands_json FROM purchases WHERE event_id=? AND participant_id=? AND voided_at IS NULL',(event_id,participant_id)).fetchall()
    spent=sum(x['amount_cents'] for x in r)
    has_brand=any(bool(json.loads(x['brands_json'])) for x in r)
    base=0
    for tier in json.loads(e['tiers_json']):
        if spent>=tier['amount_cents']:base=tier['tickets']
    bonus=e['bonus_count'] if base>0 and has_brand else 0
    return spent,has_brand,min(e['max_tickets'],base+bonus)

def reconcile(c,event_id,participant_id):
    _,_,desired=count_entitlement(c,event_id,participant_id)
    active=c.execute("SELECT id FROM tickets WHERE event_id=? AND participant_id=? AND status='ACTIVE' ORDER BY number DESC",(event_id,participant_id)).fetchall()
    difference=desired-len(active)
    if difference>0:
        maximum=c.execute('SELECT COALESCE(MAX(number),0) FROM tickets WHERE event_id=?',(event_id,)).fetchone()[0]
        for num in range(maximum+1,maximum+difference+1):
            c.execute("INSERT INTO tickets(event_id,participant_id,number,status,created_at) VALUES (?,?,?,'ACTIVE',?)",(event_id,participant_id,num,now()))
    elif difference<0:
        for row in active[:abs(difference)]:
            c.execute("UPDATE tickets SET status='VOID',changed_at=? WHERE id=?",(now(),row['id']))
    return desired

def get_state(c):
    events=[]
    for e in c.execute('SELECT * FROM events ORDER BY archived ASC,id DESC'):
        d=event_info(e)
        d['people_count']=c.execute('SELECT COUNT(*) FROM participants WHERE event_id=?',(e['id'],)).fetchone()[0]
        d['sales_cents']=c.execute('SELECT COALESCE(SUM(amount_cents),0) FROM purchases WHERE event_id=? AND voided_at IS NULL',(e['id'],)).fetchone()[0]
        d['winner_count']=c.execute('SELECT COUNT(*) FROM winners WHERE event_id=?',(e['id'],)).fetchone()[0]
        events.append(d)
    return {'events':events,'demo':DEMO,'version':'3.1'}

def get_event_state(c,event_id):
    e=get_event(c,event_id)
    base=event_info(e)
    participants=[]
    for p in c.execute('SELECT * FROM participants WHERE event_id=? ORDER BY id DESC',(event_id,)):
        spent,brand,entitled=count_entitlement(c,event_id,p['id'])
        tickets=[{'id':t['id'],'number':t['number'],'status':t['status']} for t in c.execute('SELECT id,number,status FROM tickets WHERE event_id=? AND participant_id=? ORDER BY number',(event_id,p['id']))]
        participants.append({'id':p['id'],'name':p['name'],'phone':p['phone'],'apartment':p['apartment'],'note':p['note'],'created_at':p['created_at'],'spent_cents':spent,'qualifying_brand':brand,'entitled':entitled,'numbers':tickets})
    purchases=[]
    for p in c.execute('''SELECT purchases.*,participants.name FROM purchases JOIN participants ON purchases.participant_id=participants.id
        WHERE purchases.event_id=? ORDER BY purchases.id DESC''',(event_id,)):
        purchases.append({'id':p['id'],'participant_id':p['participant_id'],'name':p['name'],'amount_cents':p['amount_cents'],
        'transaction_id':p['transaction_id'],'event_seq':p['event_seq'],
        'purchase_code':purchase_code(event_id,p['event_seq']),
        'brands':json.loads(p['brands_json']),'created_at':p['created_at'],'voided_at':p['voided_at']})
    winners=[]
    for w in c.execute('SELECT winners.*,participants.name,participants.apartment,tickets.number FROM winners JOIN participants ON winners.participant_id=participants.id JOIN tickets ON winners.ticket_id=tickets.id WHERE winners.event_id=? ORDER BY prize_order',(event_id,)):
        winners.append({'prize_order':w['prize_order'],'prize':w['prize'],'ticket_id':w['ticket_id'],'number':w['number'],'participant_id':w['participant_id'],'name':w['name'],'apartment':w['apartment'],'created_at':w['created_at']})
    attempts=[]
    for a in c.execute('''SELECT a.*,p.name,t.number,p.apartment FROM draw_attempts a
        JOIN participants p ON p.id=a.participant_id JOIN tickets t ON t.id=a.ticket_id
        WHERE a.event_id=? ORDER BY a.id''',(event_id,)):
        attempts.append({'id':a['id'],'prize_order':a['prize_order'],'prize':a['prize'],
          'participant_id':a['participant_id'],'name':a['name'],'apartment':a['apartment'],
          'number':a['number'],'status':a['status'],'created_at':a['created_at']})
    pending=next((a for a in attempts if a['status']=='PENDING'),None)
    prize_images={r['prize_order']:r['data_url'] for r in c.execute(
        'SELECT prize_order,data_url FROM prize_images WHERE event_id=?',(event_id,))}
    base.update({'prize_images':prize_images,'participants':participants,'purchases':purchases,'winners':winners,'attempts':attempts,'pending_draw':pending,'metrics':{
      'people':len(participants),'eligible':sum(p['entitled']>0 for p in participants),
      'active_people':sum(any(n['status']=='ACTIVE' for n in p['numbers']) for p in participants),
      'active_tickets':sum(sum(n['status']=='ACTIVE' for n in p['numbers']) for p in participants),
      'total_cents':sum(p['spent_cents'] for p in participants),
      'sales_count':sum(not x['voided_at'] for x in purchases)}})
    return base

def backup_data():
    with LOCK:
        with db() as c:
            result={table:[dict(x) for x in c.execute('SELECT * FROM '+table)] for table in TABLES}
    result.update({'format':'MERCAMELL_PROMOCONTROL_V4','demo':DEMO,'exported_at':now()})
    return json.dumps(result,ensure_ascii=False,indent=2).encode('utf-8')

def restore_data(payload):
    if not isinstance(payload,dict) or payload.get('format') not in ('MERCAMELL_PROMOCONTROL_V2','MERCAMELL_PROMOCONTROL_V3','MERCAMELL_PROMOCONTROL_V4'):
        raise ValueError('Arquivo inválido: exige backup Mercamell PromoControl v2, v3 ou v4.')
    if payload.get('demo') is not DEMO:raise ValueError('Backup de demonstração e base real não podem ser misturados.')
    if len(json.dumps(payload,ensure_ascii=False))>20_000_000:raise ValueError('Backup muito grande.')
    is_v2=payload['format']=='MERCAMELL_PROMOCONTROL_V2'
    is_legacy=payload['format']!='MERCAMELL_PROMOCONTROL_V4'
    for table,cols in TABLES.items():
        rows=payload.get(table,[] if (is_v2 and table=='draw_attempts') or (is_legacy and table=='prize_images') else None)
        if not isinstance(rows,list):raise ValueError('Backup incompleto: '+table)
        expected=set(cols)-({'apartment'} if is_v2 and table=='participants' else set())
        if is_legacy and table=='purchases':expected.discard('event_seq')
        if any(not isinstance(row,dict) or set(row)!=expected for row in rows):raise ValueError('Campos inválidos em '+table)
    with LOCK:
        with db() as c:
            c.execute('BEGIN IMMEDIATE')
            try:
                for table in ['prize_images','draw_attempts','winners','tickets','purchases','participants','audit','events']:
                    c.execute('DELETE FROM '+table)
                for table in ['events','participants','purchases','tickets','winners','audit','draw_attempts','prize_images']:
                    cols=TABLES[table]
                    sql=f"INSERT INTO {table} ({','.join(cols)}) VALUES ({','.join('?' for _ in cols)})"
                    for row in payload.get(table,[]):
                        if table=='participants' and is_v2:row={**row,'apartment':''}
                        if table=='purchases' and is_legacy:row={**row,'event_seq':0}
                        if table=='prize_images':validate_prize_image(row['data_url'])
                        c.execute(sql,[row[col] for col in cols])
                if is_legacy:assign_purchase_sequences(c)
                if c.execute('PRAGMA foreign_key_check').fetchall():raise ValueError('Backup com referências inválidas.')
                c.commit()
            except Exception:
                c.rollback();raise

def import_v1_backup(b, event_name):
    """Importa backup JSON da versão 1 como novo evento, sem sobrescrever dados atuais."""
    required=('participants','purchases','tickets','winners','settings')
    if not isinstance(b,dict) or b.get('format')!='MARKET4U_KIRUNA_V1' or not all(isinstance(b.get(k),list) for k in required):
        raise ValueError('Selecione um backup JSON válido do sistema Kiruna v1.')
    if b.get('demo') is not DEMO:
        raise ValueError('Backup v1 de teste não pode entrar na base real, e vice-versa.')
    if len(json.dumps(b,ensure_ascii=False))>15_000_000:
        raise ValueError('Arquivo v1 grande demais.')
    with LOCK:
        with db() as c:
            c.execute('BEGIN IMMEDIATE')
            eid=insert_event(c,event_name,'','Importado do sistema Kiruna v1')
            people_map={};ticket_map={};tickets_number=set();transactions=set()
            for p in b['participants']:
                old_id=int(p['id']);name=str(p['name']);phone=str(p.get('phone') or '');note=str(p.get('note') or '')
                if old_id in people_map:raise ValueError('Backup v1 contém IDs duplicados de participantes.')
                if phone and c.execute('SELECT 1 FROM participants WHERE event_id=? AND phone=?',(eid,phone)).fetchone():phone=''
                c.execute('INSERT INTO participants(event_id,name,phone,note,created_at) VALUES (?,?,?,?,?)',
                    (eid,name,phone,note,p.get('created_at') or now()))
                people_map[old_id]=c.execute('SELECT last_insert_rowid()').fetchone()[0]
            for sequence,p in enumerate(b['purchases'],1):
                old_id=int(p['id']);pid=people_map.get(int(p['participant_id']))
                if not pid:raise ValueError('Compra v1 sem comprador válido.')
                orig=str(p.get('receipt') or '').strip()
                if orig and re.fullmatch(r'[a-zA-Z0-9._:/-]{1,100}',orig) and orig.casefold() not in transactions:tx=orig
                else:tx='LEGADO-'+str(old_id)
                if tx.casefold() in transactions:raise ValueError('IDs duplicados no backup v1.')
                transactions.add(tx.casefold())
                brands=json.loads(p.get('brands') or '[]')
                if not isinstance(brands,list):raise ValueError('Marcas inválidas no backup v1.')
                c.execute('INSERT INTO purchases(event_id,participant_id,amount_cents,transaction_id,transaction_key,brands_json,created_at,voided_at,event_seq) VALUES (?,?,?,?,?,?,?,?,?)',
                    (eid,pid,int(p['amount_cents']),tx,tx.casefold(),json.dumps(brands,ensure_ascii=False),p.get('created_at') or now(),p.get('voided_at'),sequence))
            for t in b['tickets']:
                old_id=int(t['id']);pid=people_map.get(int(t['participant_id']))
                if not pid or old_id in ticket_map or old_id in tickets_number:raise ValueError('Números duplicados/inválidos no backup v1.')
                tickets_number.add(old_id)
                c.execute('INSERT INTO tickets(event_id,participant_id,number,status,created_at,changed_at) VALUES (?,?,?,?,?,?)',
                  (eid,pid,old_id,t['status'],t.get('created_at') or now(),t.get('changed_at')))
                ticket_map[old_id]=c.execute('SELECT last_insert_rowid()').fetchone()[0]
            for w in b['winners']:
                pid=people_map.get(int(w['participant_id']));ticket=ticket_map.get(int(w['ticket_id']))
                if not pid or not ticket:raise ValueError('Prêmio v1 sem comprador ou número correspondente.')
                c.execute('INSERT INTO winners(event_id,prize_order,prize,ticket_id,participant_id,created_at) VALUES (?,?,?,?,?,?)',
                    (eid,int(w['prize_order']),str(w['prize']),ticket,pid,w.get('created_at') or now()))
            settings={r.get('key'):r.get('value') for r in b.get('settings',[])}
            if settings.get('frozen')=='1' or b['winners']:
                c.execute('UPDATE events SET frozen=1 WHERE id=?',(eid,))
            audit(c,eid,'IMPORT_V1',{'participants':len(people_map),'purchases':len(b['purchases']),
                 'tickets':len(ticket_map),'winners':len(b['winners']),'original_export':b.get('exported_at')})
            if c.execute('PRAGMA foreign_key_check').fetchall():raise ValueError('Backup v1 inconsistente.')
            c.commit()
            return {'message':'Dados v1 importados como evento separado. Compradores, compras, números e resultados preservados.','event_id':eid}


def handle(action,payload):
    if action=='restore':
        restore_data(payload.get('backup'))
        return {'message':'Backup restaurado. Eventos e compras recuperados.'}
    if action=='import_v1':
        return import_v1_backup(payload.get('backup'),str(payload.get('name','Kiruna — importado da versão 1')))
    with LOCK:
        with db() as c:
            c.execute('BEGIN IMMEDIATE')
            if action=='create_event':
                name=str(payload.get('name','')).strip()
                eid=insert_event(c,name,str(payload.get('event_date','')),str(payload.get('description','')),payload)
                result={'message':f'Evento {name} criado.','event_id':eid}
            elif action=='duplicate_event':
                source=get_event(c,int(payload.get('event_id',0)))
                settings=event_info(source)
                newname=str(payload.get('name',source['name']+' — Cópia')).strip()
                eid=insert_event(c,newname,str(payload.get('event_date','')),str(payload.get('description','')),settings)
                for img in c.execute('SELECT prize_order,data_url FROM prize_images WHERE event_id=?',(source['id'],)).fetchall():
                    c.execute('INSERT INTO prize_images(event_id,prize_order,data_url,updated_at) VALUES (?,?,?,?)',
                       (eid,img['prize_order'],img['data_url'],now()))
                audit(c,eid,'DUPLICATE_EVENT',{'source_event_id':source['id']})
                result={'message':'Evento duplicado sem participantes ou compras.','event_id':eid}
            elif action in ('edit_event','archive_event'):
                eid=int(payload.get('event_id',0));e=get_event(c,eid)
                if action=='archive_event':
                    archived=not bool(e['archived'])
                    if e['frozen'] and not archived:pass
                    c.execute('UPDATE events SET archived=? WHERE id=?',(int(archived),eid))
                    audit(c,eid,'ARCHIVE_EVENT' if archived else 'UNARCHIVE_EVENT',{})
                    result={'message':'Evento arquivado.' if archived else 'Evento reativado.'}
                else:
                    if e['frozen']:raise ValueError('Reabra o evento para alterar configurações.')
                    name=str(payload.get('name',e['name'])).strip()
                    date=str(payload.get('event_date',e['event_date']));desc=str(payload.get('description',e['description']))
                    has_purchase=c.execute('SELECT COUNT(*) FROM purchases WHERE event_id=?',(eid,)).fetchone()[0]>0
                    old=event_info(e)
                    rules=rules_from(payload)
                    if has_purchase and (rules[0]!=old['tiers'] or rules[1]!=old['brands'] or rules[2]!=old['bonus_count'] or rules[3]!=old['max_tickets']):
                        raise ValueError('Regras e marcas não podem mudar depois da primeira compra. Duplique o evento para usar outras regras.')
                    if c.execute('SELECT COUNT(*) FROM winners WHERE event_id=?',(eid,)).fetchone()[0] and rules[4]!=old['prizes']:
                        raise ValueError('Cancele a apuração antes de alterar prêmios.')
                    if not 3<=len(name)<=120:raise ValueError('Nome do evento inválido.')
                    if date:
                        try:datetime.strptime(date,'%Y-%m-%d')
                        except ValueError:raise ValueError('Data inválida.')
                    c.execute('''UPDATE events SET name=?,event_date=?,description=?,tiers_json=?,brands_json=?,bonus_count=?,max_tickets=?,prizes_json=? WHERE id=?''',
                        (name,date,desc[:500],json.dumps(rules[0]),json.dumps(rules[1],ensure_ascii=False),rules[2],rules[3],json.dumps(rules[4],ensure_ascii=False),eid))
                    # Uma foto é associada à posição E ao nome do prêmio para evitar trocas acidentais.
                    for image in c.execute('SELECT prize_order FROM prize_images WHERE event_id=?',(eid,)).fetchall():
                        pos=image['prize_order']-1
                        if pos>=len(rules[4]) or pos>=len(old['prizes']) or rules[4][pos]!=old['prizes'][pos]:
                            c.execute('DELETE FROM prize_images WHERE event_id=? AND prize_order=?',(eid,image['prize_order']))
                    audit(c,eid,'EDIT_EVENT',{'name':name})
                    result={'message':'Evento atualizado.'}
            else:
                eid=int(payload.get('event_id',0));e=get_event(c,eid)
                if action=='add_person':
                    ensure_open(e)
                    name=str(payload.get('name','')).strip()
                    phone=''.join(ch for ch in str(payload.get('phone','')) if ch.isdigit())
                    note=str(payload.get('note','')).strip()[:400]
                    apartment=str(payload.get('apartment','')).strip()
                    if len(apartment)>30 or any(ord(ch)<32 for ch in apartment):
                        raise ValueError('Apartamento inválido (máximo 30 caracteres).')
                    if not 3<=len(name)<=100:raise ValueError('Nome deve ter de 3 a 100 caracteres.')
                    if phone and len(phone) not in (10,11):raise ValueError('Telefone deve ter 10 ou 11 dígitos.')
                    if phone and c.execute('SELECT 1 FROM participants WHERE event_id=? AND phone=?',(eid,phone)).fetchone():raise ValueError('Telefone já cadastrado neste evento.')
                    c.execute('INSERT INTO participants(event_id,name,phone,apartment,note,created_at) VALUES (?,?,?,?,?,?)',(eid,name,phone,apartment,note,now()))
                    pid=c.execute('SELECT last_insert_rowid()').fetchone()[0]
                    audit(c,eid,'ADD_PERSON',{'person':pid,'name':name})
                    result={'message':name+' cadastrado(a).','participant_id':pid}
                elif action=='edit_person':
                    ensure_open(e)
                    pid=int(payload.get('participant_id',0))
                    if not c.execute('SELECT 1 FROM participants WHERE id=? AND event_id=?',(pid,eid)).fetchone():raise ValueError('Comprador não encontrado no evento.')
                    name=str(payload.get('name','')).strip()
                    phone=''.join(ch for ch in str(payload.get('phone','')) if ch.isdigit())
                    note=str(payload.get('note','')).strip()[:400]
                    apartment=str(payload.get('apartment','')).strip()
                    if len(apartment)>30 or any(ord(ch)<32 for ch in apartment):
                        raise ValueError('Apartamento inválido (máximo 30 caracteres).')
                    if not 3<=len(name)<=100:raise ValueError('Nome inválido.')
                    if phone and len(phone) not in (10,11):raise ValueError('Telefone inválido.')
                    if phone and c.execute('SELECT 1 FROM participants WHERE event_id=? AND phone=? AND id<>?',(eid,phone,pid)).fetchone():raise ValueError('Telefone já utilizado neste evento.')
                    c.execute('UPDATE participants SET name=?,phone=?,apartment=?,note=? WHERE id=?',(name,phone,apartment,note,pid))
                    audit(c,eid,'EDIT_PERSON',{'person':pid})
                    result={'message':'Comprador atualizado.'}
                elif action=='set_prize_image':
                    if e['archived']:raise ValueError('Reative o evento antes de alterar imagens.')
                    if e['frozen']:raise ValueError('Reabra o evento antes de alterar a imagem do prêmio.')
                    prize_order=int(payload.get('prize_order',0))
                    prizes=json.loads(e['prizes_json'])
                    if not 1<=prize_order<=len(prizes):raise ValueError('Prêmio inválido.')
                    image=payload.get('data_url')
                    if image is None:
                        c.execute('DELETE FROM prize_images WHERE event_id=? AND prize_order=?',(eid,prize_order))
                        result={'message':'Imagem do prêmio removida.'}
                    else:
                        image=validate_prize_image(image)
                        c.execute('INSERT INTO prize_images(event_id,prize_order,data_url,updated_at) VALUES (?,?,?,?) '
                          'ON CONFLICT(event_id,prize_order) DO UPDATE SET data_url=excluded.data_url,updated_at=excluded.updated_at',
                          (eid,prize_order,image,now()))
                        result={'message':'Imagem do prêmio salva e incluída no backup.'}
                    audit(c,eid,'SET_PRIZE_IMAGE',{'prize_order':prize_order,'removed':image is None})
                elif action=='add_purchase':
                    ensure_open(e)
                    pid=int(payload.get('participant_id',0))
                    if not c.execute('SELECT 1 FROM participants WHERE id=? AND event_id=?',(pid,eid)).fetchone():raise ValueError('Comprador inválido para este evento.')
                    amount=parse_cents(payload.get('amount',''))
                    tx=str(payload.get('transaction_id','')).strip()
                    if tx and (len(tx)>100 or not re.fullmatch(r'[a-zA-Z0-9._:/-]+',tx)):
                        raise ValueError('ID externo inválido (máximo 100 caracteres: letras, números, ponto, hífen, /, _ ou :).')
                    sequence=c.execute('SELECT COALESCE(MAX(event_seq),0)+1 FROM purchases WHERE event_id=?',(eid,)).fetchone()[0]
                    key=tx.casefold() if tx else f'~auto/{eid}/{sequence}'
                    if tx and c.execute('SELECT 1 FROM purchases WHERE event_id=? AND transaction_key=?',(eid,key)).fetchone():
                        raise ValueError('Este ID da transação já foi utilizado neste evento, inclusive se a compra foi estornada.')
                    brands=payload.get('brands',[])
                    if not isinstance(brands,list) or any(x not in json.loads(e['brands_json']) for x in brands):raise ValueError('Marca participante inválida.')
                    brands=list(dict.fromkeys(brands))
                    c.execute('''INSERT INTO purchases(event_id,participant_id,amount_cents,transaction_id,transaction_key,brands_json,created_at,event_seq)
                        VALUES (?,?,?,?,?,?,?,?)''',(eid,pid,amount,tx,key,json.dumps(brands,ensure_ascii=False),now(),sequence))
                    purchase=c.execute('SELECT last_insert_rowid()').fetchone()[0]
                    entitled=reconcile(c,eid,pid)
                    code=purchase_code(eid,sequence)
                    audit(c,eid,'ADD_PURCHASE',{'purchase_id':purchase,'purchase_code':code,'participant_id':pid,'transaction_id':tx,'amount_cents':amount,'brands':brands})
                    result={'message':f'Compra {code} registrada. Participante agora tem {entitled} número(s) ativo(s).','purchase_code':code}
                elif action=='void_purchase':
                    ensure_open(e)
                    purchase=int(payload.get('purchase_id',0))
                    p=c.execute('SELECT * FROM purchases WHERE id=? AND event_id=? AND voided_at IS NULL',(purchase,eid)).fetchone()
                    if not p:raise ValueError('Compra não encontrada ou já estornada.')
                    c.execute('UPDATE purchases SET voided_at=? WHERE id=?',(now(),purchase))
                    reconcile(c,eid,p['participant_id'])
                    audit(c,eid,'VOID_PURCHASE',{'purchase_id':purchase,'transaction_id':p['transaction_id']})
                    result={'message':'Compra estornada. Cadastros e demais compras preservados; bilhetes excedentes cancelados.'}
                elif action=='freeze':
                    ensure_open(e)
                    eligible=c.execute("SELECT COUNT(DISTINCT participant_id) FROM tickets WHERE event_id=? AND status='ACTIVE'",(eid,)).fetchone()[0]
                    prizes=json.loads(e['prizes_json'])
                    if eligible<len(prizes):raise ValueError(f'São necessárias pelo menos {len(prizes)} pessoas elegíveis para {len(prizes)} prêmios.')
                    c.execute('UPDATE events SET frozen=1 WHERE id=?',(eid,))
                    audit(c,eid,'FREEZE',{'eligible':eligible})
                    result={'message':'Cadastros encerrados; números congelados para apuração.'}
                elif action=='reopen':
                    if c.execute('SELECT COUNT(*) FROM winners WHERE event_id=?',(eid,)).fetchone()[0] or c.execute('SELECT COUNT(*) FROM draw_attempts WHERE event_id=?',(eid,)).fetchone()[0]:
                        raise ValueError('Há apuração registrada. Use Cancelar sorteio e reabrir para preservar os cadastros.')
                    c.execute('UPDATE events SET frozen=0 WHERE id=?',(eid,))
                    audit(c,eid,'REOPEN',{})
                    result={'message':'Cadastro reaberto; compradores, apartamentos, compras e números mantidos.'}
                elif action=='cancel_draw_reopen':
                    if not e['frozen']:raise ValueError('O evento já está aberto.')
                    winners=[dict(w) for w in c.execute('SELECT * FROM winners WHERE event_id=? ORDER BY prize_order',(eid,))]
                    attempts=[dict(a) for a in c.execute('SELECT * FROM draw_attempts WHERE event_id=? ORDER BY id',(eid,))]
                    c.execute('DELETE FROM draw_attempts WHERE event_id=?',(eid,))
                    c.execute('DELETE FROM winners WHERE event_id=?',(eid,))
                    c.execute("UPDATE tickets SET status='ACTIVE',changed_at=? WHERE event_id=? AND status IN ('WINNER','REMOVED')",(now(),eid))
                    c.execute('UPDATE events SET frozen=0 WHERE id=?',(eid,))
                    audit(c,eid,'CANCEL_DRAW_REOPEN',{'cancelled_winners':winners,'cancelled_attempts':attempts,'preserved':'participants,purchases,tickets'})
                    result={'message':f'Apuração cancelada ({len(winners)} prêmio(s)). Cadastro REABERTO; compradores, apartamentos, compras e números preservados.'}
                elif action in ('draw','redraw','confirm_draw'):
                    if not e['frozen']:raise ValueError('Feche o cadastro antes da apuração.')
                    wins=c.execute('SELECT COUNT(*) FROM winners WHERE event_id=?',(eid,)).fetchone()[0]
                    prizes=json.loads(e['prizes_json'])
                    if wins>=len(prizes):raise ValueError('Todos os prêmios já foram apurados.')
                    prize_order=wins+1
                    pending=c.execute("SELECT * FROM draw_attempts WHERE event_id=? AND status='PENDING'",(eid,)).fetchone()
                    if action=='confirm_draw':
                        if not pending:raise ValueError('Não há resultado pendente para confirmar.')
                        if pending['prize_order']!=prize_order:raise ValueError('Ordem do prêmio inconsistente.')
                        c.execute("UPDATE draw_attempts SET status='ACCEPTED',resolved_at=? WHERE id=?",(now(),pending['id']))
                        c.execute('INSERT INTO winners(event_id,prize_order,prize,ticket_id,participant_id,created_at) VALUES (?,?,?,?,?,?)',
                            (eid,prize_order,pending['prize'],pending['ticket_id'],pending['participant_id'],now()))
                        c.execute("UPDATE tickets SET status='WINNER',changed_at=? WHERE id=?",(now(),pending['ticket_id']))
                        c.execute("UPDATE tickets SET status='REMOVED',changed_at=? WHERE event_id=? AND participant_id=? AND status='ACTIVE'",(now(),eid,pending['participant_id']))
                        name=c.execute('SELECT name FROM participants WHERE id=?',(pending['participant_id'],)).fetchone()['name']
                        audit(c,eid,'CONFIRM_DRAW',{'prize_order':prize_order,'winning_number':c.execute('SELECT number FROM tickets WHERE id=?',(pending['ticket_id'],)).fetchone()[0],'person':pending['participant_id']})
                        result={'message':f'{name} confirmado(a) para {pending["prize"]}.','confirmed':True}
                    else:
                        if action=='draw' and pending:raise ValueError('Há resultado pendente. Confirme ou resorteie antes de continuar.')
                        if action=='redraw' and not pending:raise ValueError('Não há resultado pendente para resortear.')
                        # Inclui ausência em sorteios anteriores: o participante não retorna à seleção nesta apuração.
                        excluded={r[0] for r in c.execute("SELECT DISTINCT participant_id FROM draw_attempts WHERE event_id=? AND status='DECLINED'",(eid,))}
                        if pending and action=='redraw':excluded.add(pending['participant_id'])
                        tickets=[t for t in c.execute("SELECT id,number,participant_id FROM tickets WHERE event_id=? AND status='ACTIVE' ORDER BY number",(eid,)) if t['participant_id'] not in excluded]
                        if not tickets:raise ValueError('Não existem outras pessoas elegíveis disponíveis para este sorteio.')
                        if pending:
                            c.execute("UPDATE draw_attempts SET status='DECLINED',resolved_at=? WHERE id=?",(now(),pending['id']))
                            audit(c,eid,'REDRAW_DECLINED',{'prize_order':prize_order,'ticket_id':pending['ticket_id'],'participant_id':pending['participant_id'],'reason':'Ausente / novo sorteio solicitado'})
                        selected=tickets[secrets.randbelow(len(tickets))]
                        prize=prizes[wins]
                        c.execute("INSERT INTO draw_attempts(event_id,prize_order,prize,ticket_id,participant_id,status,created_at) VALUES (?,?,?,?,?,'PENDING',?)",
                            (eid,prize_order,prize,selected['id'],selected['participant_id'],now()))
                        person=c.execute('SELECT name,apartment FROM participants WHERE id=?',(selected['participant_id'],)).fetchone()
                        audit(c,eid,'DRAW_PENDING',{'prize':prize,'winning_number':selected['number'],'person':selected['participant_id'],'eligible_tickets':len(tickets),'redraw':action=='redraw'})
                        result={'message':'Número selecionado. Confirme ou resorteie o resultado.',
                            'pending':{'number':selected['number'],'name':person['name'],'apartment':person['apartment'],'prize':prize}}
                else:raise ValueError('Operação desconhecida.')
            c.commit()
            return result

def export_csv(event_id):
    with db() as c:
        event=get_event(c,event_id)
        state=get_event_state(c,event_id)
        out=io.StringIO();w=csv.writer(out,delimiter=';')
        w.writerow(['Evento',event['name'],'Emitido em',now()])
        w.writerow(['Código','Comprador','Telefone','Apartamento','Valor acumulado R$','Bônus degustação','Números ativos','Números premiados','Números removidos','Números cancelados'])
        for p in state['participants']:
            def nums(status):return ', '.join(str(n['number']).zfill(3) for n in p['numbers'] if n['status']==status)
            w.writerow([p['id'],p['name'],p['phone'],p['apartment'],f'{p["spent_cents"]/100:.2f}'.replace('.',','),'Sim' if p['qualifying_brand'] else 'Não',nums('ACTIVE'),nums('WINNER'),nums('REMOVED'),nums('VOID')])
        w.writerow([]);w.writerow(['Código da compra','ID externo (opcional)','Comprador','Valor R$','Marcas','Status'])
        for p in state['purchases']:
            w.writerow([p['purchase_code'],p['transaction_id'],p['name'],f'{p["amount_cents"]/100:.2f}'.replace('.',','),', '.join(p['brands']),'Estornada' if p['voided_at'] else 'Válida'])
        w.writerow([]);w.writerow(['Prêmio','Número','Contemplado','Apartamento','Data'])
        for p in state['winners']:w.writerow([p['prize'],p['number'],p['name'],p['apartment'],p['created_at']])
        return ('\ufeff'+out.getvalue()).encode('utf-8')

class Handler(BaseHTTPRequestHandler):
    server_version='Mercamell-PromoControl/3.1'
    def log_message(self,fmt,*args):print('[%s] %s'%(self.log_date_time_string(),fmt%args))
    def reply(self,body,ctype='application/json; charset=utf-8',status=200,filename=None):
        self.send_response(status)
        self.send_header('Content-Type',ctype)
        self.send_header('Cache-Control','no-store')
        self.send_header('X-Content-Type-Options','nosniff')
        self.send_header('Content-Security-Policy',"default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'")
        if filename:self.send_header('Content-Disposition',f'attachment; filename="{filename}"')
        self.send_header('Content-Length',str(len(body)))
        self.end_headers();self.wfile.write(body)
    def do_GET(self):
        url=urlparse(self.path);path=url.path;args=parse_qs(url.query)
        try:
            if path=='/api/state':
                with LOCK:
                    with db() as c:self.reply(json.dumps(get_state(c),ensure_ascii=False).encode())
            elif path=='/api/event':
                event_id=int(args.get('event_id',[0])[0])
                with LOCK:
                    with db() as c:self.reply(json.dumps(get_event_state(c,event_id),ensure_ascii=False).encode())
            elif path=='/api/backup':
                self.reply(backup_data(),'application/json; charset=utf-8',filename='mercamell_backup_'+datetime.now().strftime('%Y%m%d_%H%M')+'.json')
            elif path=='/api/export.csv':
                event_id=int(args.get('event_id',[0])[0])
                self.reply(export_csv(event_id),'text/csv; charset=utf-8',filename=f'mercamell_evento_{event_id}.csv')
            elif path in ('/','/index.html','/static/app.js','/static/style.css','/static/mercamell-logo.png','/static/draw.js'):
                name={'/':'index.html','/index.html':'index.html','/static/app.js':'static/app.js','/static/style.css':'static/style.css','/static/mercamell-logo.png':'static/mercamell-logo.png','/static/draw.js':'static/draw.js'}[path]
                mime={'html':'text/html; charset=utf-8','js':'text/javascript; charset=utf-8','css':'text/css; charset=utf-8','png':'image/png'}[name.rsplit('.',1)[1]]
                self.reply((ROOT/name).read_bytes(),mime)
            else:self.reply(b'Not Found','text/plain; charset=utf-8',404)
        except (ValueError,sqlite3.Error) as ex:self.reply(json.dumps({'error':str(ex)},ensure_ascii=False).encode(),status=400)
    def do_POST(self):
        if urlparse(self.path).path!='/api/action':return self.reply(b'Not Found','text/plain; charset=utf-8',404)
        host=self.headers.get('Host','');origin=self.headers.get('Origin','')
        allowed=(f'127.0.0.1:{PORT}',f'localhost:{PORT}')
        if host not in allowed or (origin and origin not in tuple('http://'+a for a in allowed)):
            return self.reply(b'{"error":"Origem nao autorizada"}',status=403)
        if not self.headers.get('Content-Type','').startswith('application/json'):
            return self.reply(b'{"error":"Formato invalido"}',status=415)
        try:
            length=int(self.headers.get('Content-Length','0'))
            if not 2<=length<=20_000_000:raise ValueError('Tamanho de requisição inválido.')
            payload=json.loads(self.rfile.read(length))
            if not isinstance(payload,dict):raise ValueError('Requisição inválida.')
            result=handle(str(payload.get('action','')),payload)
            return self.reply(json.dumps(result,ensure_ascii=False).encode('utf-8'))
        except (ValueError,TypeError,KeyError,sqlite3.Error,json.JSONDecodeError) as ex:
            return self.reply(json.dumps({'error':str(ex)},ensure_ascii=False).encode('utf-8'),status=400)

def main():
    init_db()
    url=f'http://127.0.0.1:{PORT}/'
    try:server=ThreadingHTTPServer(('127.0.0.1',PORT),Handler)
    except OSError:
        print(f'A porta local {PORT} está ocupada. Feche uma execução anterior.');input('Enter para sair...');return
    print('='*64+'\n MERCAMELL PROMOCONTROL 3.1'+('\n AMBIENTE DE TESTES' if DEMO else '\n AMBIENTE REAL')+'\n Endereço local: '+url+'\n Banco de dados: '+str(DB_FILE)+'\n Mantenha esta janela aberta durante o uso.\n'+'='*64)
    threading.Timer(0.7,lambda:webbrowser.open(url)).start()
    try:server.serve_forever()
    except KeyboardInterrupt:pass
    finally:server.server_close()

if __name__=='__main__':main()