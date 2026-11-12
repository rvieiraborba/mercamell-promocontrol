"""Testes automáticos usando apenas a biblioteca padrão: python test_app.py"""
import json
import tempfile
import unittest
from pathlib import Path
import app

class AppTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        app.DB_FILE=Path(self.tmp.name)/'test.db'
        app.DEMO=False
        app.init_db()
    def tearDown(self):self.tmp.cleanup()
    def do(self,action,**kwargs):return app.handle(action,kwargs)
    def create(self,name,tiers=None):
        return self.do('create_event',name=name,tiers=tiers or app.DEFAULT_TIERS,brands=app.DEFAULT_BRANDS,
            bonus_count=1,max_tickets=4,prizes=app.DEFAULT_PRIZES)['event_id']
    def person(self,eid,name):return self.do('add_person',event_id=eid,name=name)['participant_id']
    def sale(self,eid,pid,amount,tx,brands=None):
        return self.do('add_purchase',event_id=eid,participant_id=pid,amount=amount,transaction_id=tx,brands=brands or [])
    def draw_confirm(self,eid):
        self.do('draw',event_id=eid)
        return self.do('confirm_draw',event_id=eid)
    def state(self,eid):
        with app.db() as c:return app.get_event_state(c,eid)
    def test_multi_events_and_rules(self):
        a=self.create('Kiruna')
        b=self.create('Superia',tiers=[{'amount_cents':1000,'tickets':1},{'amount_cents':3000,'tickets':2}])
        pa=self.person(a,'Ana do Kiruna');pb=self.person(b,'Ana do Superia')
        self.sale(a,pa,'20','00000001');self.sale(b,pb,'20','00000001')
        self.assertEqual(self.state(a)['participants'][0]['entitled'],0)
        self.assertEqual(self.state(b)['participants'][0]['entitled'],1)
        self.assertEqual(self.state(b)['participants'][0]['numbers'][0]['number'],1)
        self.assertEqual(self.state(a)['purchases'][0]['transaction_id'],'00000001')
    def test_accumulation_bonus_duplicates(self):
        e=self.create('Kiruna');p=self.person(e,'Ana Oliveira')
        self.sale(e,p,'24.99','00000001')
        self.assertEqual(self.state(e)['participants'][0]['entitled'],0)
        self.sale(e,p,'25.01','T-002',brands=['Honey Cake'])
        self.assertEqual(self.state(e)['participants'][0]['entitled'],3)
        with self.assertRaises(ValueError):self.sale(e,p,'100','t-002')
        self.sale(e,p,'40','A'*50)
        self.assertEqual(self.state(e)['participants'][0]['entitled'],4)
        self.assertEqual([t['number'] for t in self.state(e)['participants'][0]['numbers']],[1,2,3,4])
    def test_cancel_draw_keeps_purchases_and_people(self):
        e=self.create('Kiruna')
        ps=[self.person(e,name) for name in ('Maria','João','Carlos','Ana')]
        for i,p in enumerate(ps):self.sale(e,p,'80',f'TX-{i+1}',brands=['Vittai'])
        before=self.state(e)
        self.do('freeze',event_id=e)
        self.draw_confirm(e)
        self.draw_confirm(e)
        between=self.state(e)
        self.assertEqual(len(between['winners']),2)
        self.do('cancel_draw_reopen',event_id=e)
        after=self.state(e)
        self.assertFalse(after['frozen']);self.assertEqual(after['winners'],[])
        self.assertEqual(after['metrics']['total_cents'],before['metrics']['total_cents'])
        self.assertEqual(len(after['purchases']),len(before['purchases']))
        self.assertEqual([p['id'] for p in after['participants']],[p['id'] for p in before['participants']])
        self.assertTrue(all(t['status']=='ACTIVE' for p in after['participants'] for t in p['numbers']))
        self.assertEqual(after['metrics']['active_tickets'],before['metrics']['active_tickets'])
        self.sale(e,ps[0],'1.00','TX-EXTRA')
        with app.db() as c:
            audit=c.execute("SELECT * FROM audit WHERE event_id=? AND action='CANCEL_DRAW_REOPEN'",(e,)).fetchone()
            self.assertTrue(audit)
            self.assertEqual(len(json.loads(audit['details'])['cancelled_winners']),2)
    def test_one_prize_per_person_and_scope(self):
        e=self.create('Kiruna');pids=[self.person(e,x) for x in ('Ana','Bea','Carlos','Davi')]
        for i,p in enumerate(pids):self.sale(e,p,'80',f'V{i}')
        self.do('freeze',event_id=e)
        for _ in range(3):self.draw_confirm(e)
        names=[w['name'] for w in self.state(e)['winners']]
        self.assertEqual(len(set(names)),3)
        self.assertEqual(len(self.state(e)['winners']),3)
        self.assertEqual(self.state(e)['metrics']['active_people'],1)
    def test_void_purchase_and_no_reuse(self):
        e=self.create('Kiruna');p=self.person(e,'Ana')
        self.sale(e,p,'80','S1');numbers=[n['number'] for n in self.state(e)['participants'][0]['numbers']]
        self.do('void_purchase',event_id=e,purchase_id=self.state(e)['purchases'][0]['id'])
        self.assertEqual(self.state(e)['metrics']['active_tickets'],0)
        self.sale(e,p,'80','S2')
        nums=self.state(e)['participants'][0]['numbers']
        self.assertEqual(len(nums),6)
        self.assertTrue(all(t['status']=='VOID' for t in nums[:3]))
        self.assertTrue(all(t['status']=='ACTIVE' for t in nums[3:]))
        self.assertEqual([x['number'] for x in nums[:3]],numbers)
    def test_protection_edit_rules_and_transact(self):
        e=self.create('Kiruna');p=self.person(e,'Ana')
        self.sale(e,p,'25','tx-01')
        s=self.state(e)
        with self.assertRaises(ValueError):self.do('edit_event',event_id=e,name='Kiruna',tiers=[{'amount_cents':2000,'tickets':1}],brands=s['brands'],bonus_count=1,max_tickets=4,prizes=s['prizes'])
        self.assertEqual(self.state(e)['tiers'],app.DEFAULT_TIERS)
    def test_backup_restore(self):
        e=self.create('Kiruna');p=self.person(e,'Ana');self.sale(e,p,'50','ABC123')
        b=json.loads(app.backup_data())
        self.do('create_event',name='Extra')
        app.restore_data(b)
        self.assertEqual(len(json.loads(app.backup_data())['events']),1)
        self.assertEqual(self.state(e)['purchases'][0]['transaction_id'],'ABC123')
    def test_transaction_id_never_reused_even_if_voided(self):
        e=self.create('Kiruna');pid=self.person(e,'Ana')
        self.sale(e,pid,'25','000000000001')
        purchase_id=self.state(e)['purchases'][0]['id']
        self.do('void_purchase',event_id=e,purchase_id=purchase_id)
        with self.assertRaisesRegex(ValueError,'já foi utilizado'):
            self.sale(e,pid,'25','000000000001')
    def test_cancel_after_all_draws_and_new_draws(self):
        e=self.create('Kiruna');pids=[self.person(e,x) for x in ('Ana','Bea','Carla','Davi','Erica')]
        for i,p in enumerate(pids):self.sale(e,p,'80',f'K-{i}')
        before=self.state(e)
        self.do('freeze',event_id=e)
        for _ in range(3):self.draw_confirm(e)
        self.do('cancel_draw_reopen',event_id=e)
        self.assertEqual(self.state(e)['metrics']['active_tickets'],before['metrics']['active_tickets'])
        self.do('freeze',event_id=e)
        for _ in range(3):self.draw_confirm(e)
        self.assertEqual(len({w['participant_id'] for w in self.state(e)['winners']}),3)
        self.assertEqual(self.state(e)['metrics']['total_cents'],before['metrics']['total_cents'])
    def test_import_v1_data(self):
        old={'format':'MARKET4U_KIRUNA_V1','demo':False,'participants':[{'id':1,'name':'Ana','phone':'','note':'','created_at':app.now()}],
            'purchases':[{'id':4,'participant_id':1,'amount_cents':2500,'receipt':'00000123','brands':'[]','created_at':app.now(),'voided_at':None}],
            'tickets':[{'id':5,'participant_id':1,'status':'ACTIVE','created_at':app.now(),'changed_at':None}],
            'winners':[],'settings':[{'key':'frozen','value':'0'}]}
        existing=self.create('Superia')
        e=self.do('import_v1',backup=old,name='Kiruna importado')['event_id']
        self.assertNotEqual(e,existing)
        s=self.state(e)
        self.assertEqual(s['purchases'][0]['transaction_id'],'00000123')
        self.assertEqual(s['participants'][0]['numbers'][0]['number'],5)
        self.assertEqual(len(self.state(existing)['participants']),0)

    def test_apartment_and_pending_and_redraw(self):
        e=self.create('Kiruna')
        pids=[self.person(e,x) for x in ('Ana','Bea','Caique','Davi','Erica')]
        self.do('edit_person',event_id=e,participant_id=pids[0],name='Ana',apartment='1002',note='Contato de teste')
        for i,pid in enumerate(pids):self.sale(e,pid,'80',f'AB-{i}')
        self.do('freeze',event_id=e)
        s=self.state(e)
        self.assertEqual(next(p['apartment'] for p in s['participants'] if p['id']==pids[0]),'1002')
        self.do('draw',event_id=e)
        s=self.state(e)
        self.assertEqual(s['winners'],[])
        self.assertIsNotNone(s['pending_draw'])
        with self.assertRaisesRegex(ValueError,'resultado pendente'):
            self.do('draw',event_id=e)
        first=s['pending_draw']['participant_id']
        self.do('redraw',event_id=e)
        s=self.state(e)
        self.assertEqual(len([a for a in s['attempts'] if a['status']=='DECLINED']),1)
        self.assertNotEqual(first,s['pending_draw']['participant_id'])
        self.do('confirm_draw',event_id=e)
        self.assertEqual(len(self.state(e)['winners']),1)
        self.assertIsNone(self.state(e)['pending_draw'])
        # Pessoas recusadas não voltam a concorrer nesta apuração.
        for _ in range(2):
            self.do('draw',event_id=e)
            self.assertNotEqual(self.state(e)['pending_draw']['participant_id'],first)
            self.do('confirm_draw',event_id=e)
        self.assertEqual(len(self.state(e)['winners']),3)
        self.assertEqual(len({w['participant_id'] for w in self.state(e)['winners']}),3)
        self.do('cancel_draw_reopen',event_id=e)
        after=self.state(e)
        self.assertFalse(after['frozen'])
        self.assertEqual(len(after['purchases']),5)
        self.assertEqual(after['winners'],[])
        self.assertEqual(after['attempts'],[])
        self.assertEqual(after['metrics']['active_tickets'],15)
    def test_pending_survives_backup_v3_and_v2_restore(self):
        e=self.create('Kiruna');pids=[self.person(e,x) for x in ('Ana','Bea','Carlos')]
        for i,p in enumerate(pids):self.sale(e,p,'80',str(i+11))
        self.do('freeze',event_id=e)
        self.do('draw',event_id=e)
        backup=json.loads(app.backup_data())
        self.assertEqual(backup['format'],'MERCAMELL_PROMOCONTROL_V4')
        self.assertEqual(len(backup['draw_attempts']),1)
        self.do('cancel_draw_reopen',event_id=e)
        app.restore_data(backup)
        self.assertIsNotNone(self.state(e)['pending_draw'])
        self.do('confirm_draw',event_id=e)
        # V2 ainda pode ser restaurado preservando cadastros.
        old=json.loads(app.backup_data())
        old['format']='MERCAMELL_PROMOCONTROL_V2'
        old.pop('draw_attempts')
        old.pop('prize_images')
        for person in old['participants']:person.pop('apartment')
        for purchase in old['purchases']:purchase.pop('event_seq')
        app.restore_data(old)
        self.assertEqual(self.state(e)['participants'][0]['apartment'],'')
        self.assertEqual(len(self.state(e)['winners']),1)


    def test_purchase_number_per_event_without_external_id(self):
        a=self.create('Kiruna');b=self.create('Superia')
        x=self.person(a,'Ana');y=self.person(b,'Bruna')
        self.assertEqual(self.do('add_purchase',event_id=a,participant_id=x,amount='25')['purchase_code'],f'{a:03d}-000001')
        self.assertEqual(self.do('add_purchase',event_id=b,participant_id=y,amount='25')['purchase_code'],f'{b:03d}-000001')
        self.assertEqual(self.do('add_purchase',event_id=a,participant_id=x,amount='60')['purchase_code'],f'{a:03d}-000002')
        self.assertEqual([p['purchase_code'] for p in self.state(a)['purchases']],[f'{a:03d}-000002',f'{a:03d}-000001'])
        self.assertEqual(self.state(a)['purchases'][0]['transaction_id'],'')

    def test_void_purchase_does_not_reuse_automatic_number(self):
        e=self.create('Kiruna');p=self.person(e,'Ana')
        first=self.do('add_purchase',event_id=e,participant_id=p,amount='25')['purchase_code']
        pid=self.state(e)['purchases'][0]['id']
        self.do('void_purchase',event_id=e,purchase_id=pid)
        second=self.do('add_purchase',event_id=e,participant_id=p,amount='30')['purchase_code']
        self.assertEqual((first,second),(f'{e:03d}-000001',f'{e:03d}-000002'))

    def test_prize_image_backup_restore_and_winner_apartment(self):
        import base64
        photo='data:image/png;base64,'+base64.b64encode(b'\x89PNG\r\n\x1a\n'+b'teste').decode()
        e=self.create('Kiruna');self.do('set_prize_image',event_id=e,prize_order=1,data_url=photo)
        self.assertEqual(self.state(e)['prize_images']['1'] if '1' in self.state(e)['prize_images'] else self.state(e)['prize_images'][1],photo)
        ids=[]
        for i,name in enumerate(('Ana','Bea','Carla')):
            pid=self.person(e,name);ids.append(pid)
            self.do('edit_person',event_id=e,participant_id=pid,name=name,apartment=f'{i+1}01')
            self.do('add_purchase',event_id=e,participant_id=pid,amount='80')
        self.do('freeze',event_id=e);self.draw_confirm(e)
        winner=self.state(e)['winners'][0]
        self.assertEqual(winner['apartment'],next(p['apartment'] for p in self.state(e)['participants'] if p['id']==winner['participant_id']))
        backup=json.loads(app.backup_data())
        self.assertEqual(backup['format'],'MERCAMELL_PROMOCONTROL_V4')
        self.do('cancel_draw_reopen',event_id=e)
        app.restore_data(backup)
        self.assertEqual(self.state(e)['prize_images'][1],photo)
        with self.assertRaisesRegex(ValueError,'Reabra o evento'):
            self.do('set_prize_image',event_id=e,prize_order=1,data_url=None)
        self.do('cancel_draw_reopen',event_id=e)
        self.do('set_prize_image',event_id=e,prize_order=1,data_url=None)
        self.assertFalse(self.state(e)['prize_images'])

    def test_migration_from_v3_backup_and_existing_db(self):
        e=self.create('Kiruna');p=self.person(e,'Ana')
        self.sale(e,p,'25','EXTERNO-001')
        self.sale(e,p,'26','EXTERNO-002')
        legacy=json.loads(app.backup_data());legacy['format']='MERCAMELL_PROMOCONTROL_V3'
        legacy.pop('prize_images')
        for buy in legacy['purchases']:buy.pop('event_seq')
        app.restore_data(legacy)
        self.assertEqual([p['purchase_code'] for p in self.state(e)['purchases']],[f'{e:03d}-000002',f'{e:03d}-000001'])
        with app.db() as c:
            c.execute('UPDATE purchases SET event_seq=0 WHERE event_id=?',(e,))
            app.assign_purchase_sequences(c)
        self.assertEqual(len({p['purchase_code'] for p in self.state(e)['purchases']}),2)

    def test_image_rejected_and_prize_renaming_drops_old_photo(self):
        import base64
        e=self.create('Kiruna')
        with self.assertRaisesRegex(ValueError,'JPG ou PNG'):
            self.do('set_prize_image',event_id=e,prize_order=1,data_url='data:image/svg+xml;base64,AAAA')
        photo='data:image/png;base64,'+base64.b64encode(b'\x89PNG\r\n\x1a\n'+b'safe').decode()
        self.do('set_prize_image',event_id=e,prize_order=1,data_url=photo)
        state=self.state(e)
        self.do('edit_event',event_id=e,name='Kiruna',tiers=state['tiers'],brands=state['brands'],
            bonus_count=state['bonus_count'],max_tickets=state['max_tickets'],prizes=['Prêmio novo',*state['prizes'][1:]])
        self.assertFalse(self.state(e)['prize_images'])

    def test_migrate_on_disk_v3_schema_with_existing_purchases(self):
        e=self.create('Kiruna');p=self.person(e,'Ana')
        self.sale(e,p,'25','ORIG-A')
        self.sale(e,p,'30','ORIG-B')
        # Simula uma instalação antiga que não possui a coluna adicionada na 3.1.
        with app.db() as c:
            c.execute('DROP INDEX uq_purchase_event_seq')
            c.execute('ALTER TABLE purchases DROP COLUMN event_seq')
        app.init_db()
        state=self.state(e)
        self.assertEqual([x['purchase_code'] for x in state['purchases']],
            [f'{e:03d}-000002',f'{e:03d}-000001'])
        self.assertEqual(self.do('add_purchase',event_id=e,participant_id=p,amount='40')['purchase_code'],f'{e:03d}-000003')
        self.assertEqual({x['transaction_id'] for x in state['purchases']},{'ORIG-A','ORIG-B'})

if __name__=='__main__':unittest.main(verbosity=2)