#!/usr/bin/env python3
"""Regression checks for required KB packet provenance and acceptance mapping."""
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import android_knowledge as gate
import android_pilot as ledger

class KnowledgeGateTests(unittest.TestCase):
    def verified_packet(self, task, base):
        gate.verify('packet/manifest.json', expected_task=task)
        return 'packet/manifest.json'

    def test_model_input_uses_verified_documents_not_packet_body(self):
        (self.root/'packet/context.md').write_text('UNSELECTED_FULL_HISTORY')
        self.manifest['context_sha256']=self.sha('packet/context.md')
        self.save('packet/manifest.json',self.manifest)
        with patch.object(gate,'ensure',side_effect=self.verified_packet):
            text, meta=gate.model_input('search','packet')
        self.assertIn('Kotlin required rule',text)
        self.assertIn('Cancellation rule',text)
        self.assertNotIn('UNSELECTED_FULL_HISTORY',text)
        self.assertEqual(meta['documents'],self.manifest['documents'])
        self.assertEqual(meta['input_sha256'],hashlib.sha256(text.encode()).hexdigest())

    def test_model_input_rejects_unknown_profile(self):
        with self.assertRaises(ValueError):gate.model_input('unknown','packet')

    def test_model_input_rejects_changed_source_before_reading(self):
        (self.root/'source.kt').write_text('changed')
        with patch.object(gate,'ensure',side_effect=self.verified_packet):
            with self.assertRaises(ValueError):gate.model_input('search','packet')

    def test_model_input_rejects_not_ready_selection(self):
        self.ready_patch.stop()
        with patch.object(gate.knowledge,'context',return_value=2),patch.object(gate,'ensure',side_effect=self.verified_packet):
            with self.assertRaises(ValueError):gate.model_input('search','packet')

    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name).resolve();self.patch=patch.object(gate,'ROOT',self.root);self.patch.start();self.addCleanup(self.patch.stop)
        self.ready_patch=patch.object(gate.knowledge,'context',return_value=0);self.ready_patch.start();self.addCleanup(self.ready_patch.stop)
        (self.root/'knowledge').mkdir();(self.root/'packet').mkdir();(self.root/'agents').mkdir()
        header='---\ntitle: fixture\nconfirmed_on: 2026-10-28\nreview_status: static-reviewed\nruntime_status: not-run\nsource_ids: ["S1"]\n---\n'
        self.docs={'knowledge/a.md':header+'Kotlin required rule','knowledge/b.md':header+'Cancellation rule'}
        for name,text in self.docs.items():(self.root/name).write_text(text)
        (self.root/'source.kt').write_text('original source')
        source=dict(id='S1',kind='local',path='source.kt',sha256=self.sha('source.kt'),review_status='read')
        (self.root/'knowledge/sources.json').write_text(json.dumps({'sources':[source]}))
        (self.root/'packet/context.md').write_text('required input')
        self.save('agents/android-native.json',{'knowledge':{'feature':'stock-search-price','platform':'android','documents':{'search':['a.md','b.md']}}})
        self.manifest=dict(task='search',feature='stock-search-price',platform='android',documents={n:self.sha(n) for n in self.docs},context='packet/context.md',context_sha256=self.sha('packet/context.md'),source_records={'S1':source})
        self.save('packet/manifest.json',self.manifest)
        self.usage=dict(context_sha256=self.manifest['context_sha256'],applied_rules=[dict(document=n,rule='explicit rule',implementation='Client.symbol') for n in self.docs])
        self.save('packet/usage.json',self.usage)
    def sha(self,name):return hashlib.sha256((self.root/name).read_bytes()).hexdigest()
    def save(self,name,value):(self.root/name).write_text(json.dumps(value))
    def verify(self):return gate.verify('packet/manifest.json','packet/usage.json',expected_task='search')
    def test_current_packet_and_complete_application_map_pass(self):self.verify()
    def test_missing_or_modified_document_blocks(self):
        (self.root/'knowledge/a.md').write_text('changed')
        with self.assertRaisesRegex(ValueError,'input changed'):self.verify()
        (self.root/'knowledge/a.md').unlink()
        with self.assertRaisesRegex(ValueError,'input changed'):self.verify()
    def test_modified_packet_blocks(self):
        (self.root/'packet/context.md').write_text('replaced')
        with self.assertRaisesRegex(ValueError,'input changed'):self.verify()
    def test_changed_original_source_blocks_even_when_wiki_is_unchanged(self):
        (self.root/'source.kt').write_text('changed')
        with self.assertRaisesRegex(ValueError,'input changed'):self.verify()
    def test_wrong_packet_receipt_blocks(self):
        self.usage['context_sha256']='wrong';self.save('packet/usage.json',self.usage)
        with self.assertRaisesRegex(ValueError,'different context'):self.verify()
    def test_omitting_a_required_document_blocks(self):
        self.usage['applied_rules'].pop();self.save('packet/usage.json',self.usage)
        with self.assertRaisesRegex(ValueError,'missing from application'):self.verify()
    def test_empty_or_unmapped_rule_blocks(self):
        self.usage['applied_rules'][0]['implementation']='';self.save('packet/usage.json',self.usage)
        with self.assertRaisesRegex(ValueError,'incomplete'):self.verify()
    def test_unprepared_knowledge_prevents_packet_creation(self):
        self.save('agents/android-native.json',{'knowledge':{'feature':'stock-search-price','platform':'android','documents':{'search':[]}}})
        with patch.object(gate.knowledge,'context',return_value=2):
            with self.assertRaisesRegex(ValueError,'preparation check failed'):gate.prepare('search','new-packets')
        self.assertFalse((self.root/'new-packets').exists())
    def test_outside_repository_path_blocks(self):
        with self.assertRaisesRegex(ValueError,'outside repository'):gate.inside('../outside')
    def test_removing_required_document_from_both_manifest_and_usage_blocks(self):
        self.manifest['documents'].pop('knowledge/b.md');self.save('packet/manifest.json',self.manifest)
        self.usage['applied_rules'].pop();self.save('packet/usage.json',self.usage)
        with self.assertRaisesRegex(ValueError,'document set mismatch'):self.verify()
    def test_wrong_task_and_missing_required_source_block(self):
        self.manifest['task']='price';self.save('packet/manifest.json',self.manifest)
        with self.assertRaisesRegex(ValueError,'identity mismatch'):self.verify()
        self.manifest['task']='search';self.manifest['source_records']={};self.save('packet/manifest.json',self.manifest)
        with self.assertRaisesRegex(ValueError,'source set mismatch'):self.verify()

    def test_ensure_reuses_valid_packet_without_rewriting_and_checks_readiness_once(self):
        # Match the existing task-based directory layout without regenerating its receipt.
        (self.root/'packet').rename(self.root/'search')
        self.manifest['context']='search/context.md';self.save('search/manifest.json',self.manifest)
        before=(self.root/'search/manifest.json').read_bytes()
        self.assertEqual(gate.ensure('search','.'),'search/manifest.json')
        self.assertEqual((self.root/'search/manifest.json').read_bytes(),before)
        gate.knowledge.context.assert_called_once()
        self.assertFalse(gate.knowledge.context.call_args.kwargs['emit_documents'])

    def test_ensure_does_not_replace_stale_packet(self):
        (self.root/'packet').rename(self.root/'search')
        self.manifest['context']='search/context.md';self.save('search/manifest.json',self.manifest)
        before=(self.root/'search/manifest.json').read_bytes()
        (self.root/'knowledge/a.md').write_text('changed')
        with self.assertRaisesRegex(ValueError,'input changed'):gate.ensure('search','.')
        self.assertEqual((self.root/'search/manifest.json').read_bytes(),before)

    def test_prepare_and_ledger_start_perform_one_readiness_check(self):
        self.save('ledger.json',{'tasks':{'implement.search':{'status':'queued','kind':'agent','deps':[]}},'events':[],'frozen':{}})
        with patch.object(gate.knowledge,'knowledge_document',side_effect=lambda p:self.root/'knowledge'/p), \
             patch.object(ledger,'ROOT',self.root), \
             patch('sys.argv',['android_pilot.py','--state','ledger.json','start','implement.search']):
            self.assertEqual(ledger.main(),0)
        gate.knowledge.context.assert_called_once()
        packet=json.loads((self.root/'knowledge-v1/search/manifest.json').read_text())
        self.assertEqual(set(packet['documents']),set(self.docs))

    def test_reused_packet_still_requires_prepared_platform(self):
        gate.knowledge.context.return_value=2
        with self.assertRaisesRegex(ValueError,'preparation check failed'):self.verify()

    def test_changed_check_selection_requires_new_packet(self):
        config=json.loads((self.root/'agents/android-native.json').read_text())
        config['knowledge']['task_checks']={'search':['new required check']}
        self.save('agents/android-native.json',config)
        with self.assertRaisesRegex(ValueError,'check selection mismatch'):self.verify()

if __name__=='__main__':unittest.main()
