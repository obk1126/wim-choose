"""Input preparation and authored-fixture checks, not model evaluations."""
import argparse
import copy
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from openpyxl import Workbook

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from prepare import convert, prepare, make_units
from validate import load_json, validate_config, validate_input, validate_output


def args_for(file,config,**kwargs):
    args=argparse.Namespace(file=Path(file),config=Path(config),format='csv',source_id='s1',scope='specified test range',complete='yes',rows='1:1',lines=None,sheet=None,cell_range=None,whole_file=False,pointer='',items=None,query_id=None,delimiter=',',encoding='utf-8-sig')
    for k,v in kwargs.items():setattr(args,k,v)
    return args


class PreparationTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.dir=Path(self.tmp.name)
        self.config=load_json(ROOT/'examples/configs/support.json')
        self.cfg=self.dir/'config.json';self.save_config()

    def save_config(self):
        self.cfg.write_text(json.dumps(self.config),encoding='utf-8')

    def file(self,name,data):
        p=self.dir/name;p.write_text(data,encoding='utf-8');return p

    def test_csv_only_selected_records_no_read_ahead(self):
        p=self.file('x.csv','ticket_id,message\na,first\nb,second\nc,"broken unterminated quote')
        out=prepare(args_for(p,self.cfg,rows='2:2'))
        self.assertEqual(out['state'],[{'ticket_id':'b','message':'second'}])
        self.assertIn('data record 2',out['sources'][0]['locations']['/0/message'])
        self.assertEqual(out['sources'][0]['metadata']['column_mapping'],self.config['columns'])

    def test_csv_newlines_do_not_fake_physical_row_numbers(self):
        p=self.file('x.csv','ticket_id,message\na,"first\nsecond"\n')
        out=prepare(args_for(p,self.cfg))
        self.assertEqual(out['state'][0]['message'],'first\nsecond')
        self.assertIn('data record 1',out['sources'][0]['locations']['/0/message'])

    def test_missing_range_rejected(self):
        p=self.file('x.csv','ticket_id,message\na,hi\n')
        with self.assertRaises(ValueError):prepare(args_for(p,self.cfg,rows=None))

    def test_truncated_range_is_not_silent_success(self):
        p=self.file('x.csv','ticket_id,message\na,hi\n')
        with self.assertRaises(ValueError):prepare(args_for(p,self.cfg,rows='1:2'))

    def test_duplicate_headers_ragged_records_and_missing_columns(self):
        for data in ['ticket_id,ticket_id\na,hi\n','ticket_id,message\na,hi,extra\n','ticket_id,unknown\na,hi\n']:
            with self.subTest(data=data),self.assertRaises(ValueError):
                prepare(args_for(self.file('x.csv',data),self.cfg))

    def test_blank_null_zero_false_and_literal_null_preserved(self):
        col={'source':'n','field':'n','type':'integer','empty':'preserve'}
        self.assertEqual(convert('',col),'');self.assertIsNone(convert(None,col));self.assertEqual(convert('0',col),0)
        with self.assertRaises(ValueError):convert(False,col)
        st={**col,'type':'string'}
        self.assertEqual(convert('null',st),'null')
        bo={**col,'type':'boolean','true_values':['yes'],'false_values':['no']}
        self.assertIs(convert('no',bo),False)
        self.assertIs(convert(False,bo),False)
        self.assertEqual(convert('',bo),'')
        self.assertIsNone(convert('',{**col,'empty':'null'}))

    def test_numbers_are_not_guessed(self):
        col={'source':'n','field':'n','type':'number','empty':'preserve'}
        for value in ['1,000',' 2','1e999','NaN','01','10cm']:
            with self.subTest(value=value),self.assertRaises(ValueError):convert(value,col)
        self.assertEqual(convert('0',col),0)

    def test_dates_require_format_and_datetime_timezone(self):
        col={'source':'d','field':'d','type':'date','empty':'preserve'}
        with self.assertRaises(ValueError):convert('03/04',col)
        self.assertEqual(convert('2026-03-04',{**col,'date_format':'%Y-%m-%d'}),'2026-03-04')
        with self.assertRaises(ValueError):convert('2026-03-04 12:00',{**col,'type':'datetime','date_format':'%Y-%m-%d %H:%M'})
        self.assertEqual(convert('2026-03-04T12:00+0900',{**col,'type':'datetime','date_format':'%Y-%m-%dT%H:%M%z'}),'2026-03-04T12:00:00+09:00')

    def test_json_requires_explicit_whole_file_permission(self):
        self.config.pop('columns');self.save_config()
        p=self.file('x.json','[{"ticket_id":"a"}]')
        with self.assertRaises(ValueError):prepare(args_for(p,self.cfg,format='json'))
        out=prepare(args_for(p,self.cfg,format='json',whole_file=True))
        self.assertEqual(out['state'],[{'ticket_id':'a'}])

    def test_json_selection_and_bad_duplicate_keys(self):
        self.config.pop('columns');self.save_config()
        p=self.file('x.json','{"data":[{"ticket_id":"a"},{"ticket_id":"b"}]}')
        out=prepare(args_for(p,self.cfg,format='json',whole_file=True,pointer='/data',items='1:1'))
        self.assertEqual(out['state'],[{'ticket_id':'b'}])
        self.assertEqual(out['sources'][0]['locations']['/0'],'JSON pointer /data/1')
        p=self.file('x.json','{"x":1,"x":2}')
        with self.assertRaises(ValueError):prepare(args_for(p,self.cfg,format='json',whole_file=True))

    def test_group_ids_preserve_key_type_and_member_provenance(self):
        self.config['unit']={'mode':'group','group_by':['message']};self.save_config()
        p=self.file('x.csv','ticket_id,message\na,A\nb,B\nc,A\n')
        out=prepare(args_for(p,self.cfg,rows='1:3'))
        self.assertEqual([x['ticket_id'] for x in out['state'][0]['rows']],['a','c'])
        self.assertIn('data record 3',out['sources'][0]['locations']['/0/rows/1/ticket_id'])
        self.assertFalse(validate_input(out))
        state,subjects=make_units([{'g':False},{'g':0}],{'unit':{'mode':'group','group_by':['g']}},'s1',True)
        self.assertEqual(len(subjects),2)

    def test_duplicate_missing_and_null_row_ids_rejected(self):
        self.config.pop('columns');self.save_config()
        for rows in [[{'ticket_id':'a'},{'ticket_id':'a'}],[{}],[{'ticket_id':None}]]:
            with self.subTest(rows=rows),self.assertRaises(ValueError):
                prepare(args_for(self.file('x.json',json.dumps(rows)),self.cfg,format='json',whole_file=True))

    def test_xlsx_zero_false_blank_and_empty_text(self):
        cfg=ROOT/'examples/configs/inspection.json'
        out=prepare(args_for(ROOT/'examples/data/inspection.xlsx',cfg,format='xlsx',sheet='Inspection',cell_range='A1:C4'))
        self.assertIsNone(out['state'][0]['defects']);self.assertEqual(out['state'][1]['defects'],0)
        self.assertIs(out['state'][1]['flag'],False)
        self.assertEqual(out['sources'][0]['locations']['/1/defects'],'Inspection!B3')
        wb=Workbook();ws=wb.active;ws.title='Data';ws.append(['ticket_id','message']);ws.append(['a','']);ws.append(['b',None]);p=self.dir/'x.xlsx';wb.save(p)
        out=prepare(args_for(p,self.cfg,format='xlsx',sheet='Data',cell_range='A1:B3'))
        self.assertEqual(out['state'][0]['message'],'');self.assertIsNone(out['state'][1]['message'])

    def test_xlsx_formula_error_sheet_and_bounds_rejected(self):
        for bad in ['=1+1','#DIV/0!']:
            wb=Workbook();ws=wb.active;ws.title='Data';ws.append(['ticket_id','message']);ws.append(['a',bad]);p=self.dir/'x.xlsx';wb.save(p)
            with self.subTest(bad=bad),self.assertRaises(ValueError):prepare(args_for(p,self.cfg,format='xlsx',sheet='Data',cell_range='A1:B2'))
        for sheet,rng in [('Missing','A1:B2'),('Data','A1:B20'),('Data',None)]:
            with self.subTest(sheet=sheet,rng=rng),self.assertRaises(ValueError):prepare(args_for(p,self.cfg,format='xlsx',sheet=sheet,cell_range=rng))

    def test_text_and_unknown_completeness(self):
        self.config.pop('columns');self.config['unit']={'mode':'single'};self.save_config()
        p=self.file('x.txt','first\nsecond\nthird\n')
        out=prepare(args_for(p,self.cfg,format='text',lines='2:2',complete='unknown'))
        self.assertEqual(out['state'],'second\n');self.assertIsNone(out['unit']['complete'])
        self.assertIsNone(out['sources'][0]['complete'])

    def test_preparation_cli_failure_is_not_decision_json(self):
        p=self.file('x.csv','ticket_id,message\na,hi\n')
        proc=subprocess.run([sys.executable,str(ROOT/'scripts/prepare.py'),'--format','csv','--file',str(p),'--config',str(self.cfg),'--source-id','s1','--scope','one row','--complete','yes'],capture_output=True,text=True)
        self.assertEqual(proc.returncode,2);self.assertEqual(proc.stdout,'');self.assertFalse(json.loads(proc.stderr)['ok'])

    def test_corrupt_xlsx_cli_fails_cleanly(self):
        p=self.file('x.xlsx','not a zip')
        proc=subprocess.run([sys.executable,str(ROOT/'scripts/prepare.py'),'--format','xlsx','--file',str(p),'--config',str(self.cfg),'--source-id','s1','--scope','one row','--complete','yes','--sheet','x','--range','A1:B2'],capture_output=True,text=True)
        self.assertEqual(proc.returncode,2);self.assertFalse(json.loads(proc.stderr)['ok'])


class ExampleContractTests(unittest.TestCase):
    def test_all_authored_examples(self):
        paths=sorted((ROOT/'examples').glob('*.case.json'));self.assertEqual(len(paths),26)
        for path in paths:
            with self.subTest(case=path.name):
                case=load_json(path)
                self.assertEqual(not validate_input(case['input']),case['input_valid'])
                self.assertEqual(validate_output(case['expected'],case['input']),[])

    def test_all_configs(self):
        for path in (ROOT/'examples/configs').glob('*.json'):
            with self.subTest(config=path.name):self.assertEqual(validate_config(load_json(path)),[])

    def test_six_source_fixture_cli_conversions(self):
        n=0
        for path in (ROOT/'examples').glob('*.case.json'):
            case=load_json(path)
            if 'preparation' not in case:continue
            n+=1;p=case['preparation']
            cmd=[sys.executable,str(ROOT/'scripts/prepare.py'),'--format',p['format'],'--file',str(ROOT/'examples'/p['file']),'--config',str(ROOT/'examples'/p['config']),'--source-id','s1','--scope',p['scope'],'--complete','yes']+p['args']
            with self.subTest(case=path.name):
                proc=subprocess.run(cmd,capture_output=True,text=True)
                self.assertEqual(proc.returncode,0,proc.stderr)
                actual=json.loads(proc.stdout)
                self.assertEqual(actual['state'],case['input']['state'])
                self.assertEqual(validate_input(actual),[])
                self.assertEqual(validate_output(case['expected'],actual),[])
        self.assertEqual(n,6)


if __name__=='__main__':unittest.main()
