"""Exercise real builds, revision protection, loopback API and isolated Git publishing."""
import copy
import base64
from datetime import datetime
from zoneinfo import ZoneInfo
from http.client import HTTPConnection
from http.server import ThreadingHTTPServer
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from editor.content import bundle, read_content, validate
from scripts.editor_server import Editor, EditorError, make_handler
from editor.design import validate_design


class EditorTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name) / 'site'
        shutil.copytree(ROOT, self.root, ignore=shutil.ignore_patterns('.git', '.openai', '__pycache__', '.editor-state'))
        self.editor = Editor(self.root)

    def tearDown(self):
        if self.editor.preview: self.editor.preview.cleanup()
        self.temp.cleanup()

    def draft(self):
        data = bundle(self.root)
        data['content']['news'].insert(0, dict(date='2026-10', kind='Update', text='Editor integration test announcement.', url=''))
        return data

    def test_gallery_upload_preview_and_validation(self):
        draft = bundle(self.root)
        raw = b'\xff\xd8\xffexample\xff\xd9'
        payload = dict(base_revision=draft['base_revision'], photo_id='photo-test', data=base64.b64encode(raw).decode())
        result = self.editor.upload_photo(payload)
        draft['content']['gallery'] = [dict(id='photo-test', caption='Team & research', date='2026-10', event='Lab life', members='Example members', alt='Example group photo', image=result['path'])]
        self.assertFalse(validate(draft['content'], read_content(self.root)))
        self.editor.preview_content(draft)
        html = (Path(self.editor.preview.name) / 'dist/gallery.html').read_text()
        self.assertIn('Team &amp; research', html)
        self.assertIn('gallery-viewer', html)
        self.assertEqual((Path(self.editor.preview.name) / 'dist' / result['path']).read_bytes(), raw)
        self.assertEqual(read_content(self.root)['gallery'], [])
        self.editor.upload_photo(payload)
        self.assertTrue(list((self.root / '.editor-state/backups').glob('*/photo-test.jpg')))
        for invalid in (dict(payload, photo_id='../bad'), dict(payload, data='YmFk'), dict(payload, base_revision='stale')):
            with self.assertRaises(EditorError): self.editor.upload_photo(invalid)
        draft['content']['gallery'][0]['image'] = '../secret.jpg'
        self.assertTrue(validate(draft['content'], read_content(self.root)))

    def test_paper_upload_preview_backup_and_invalid_paths(self):
        draft = bundle(self.root)
        paper = draft['content']['publications'][0]
        raw = b'%PDF-1.4\nexample\n%%EOF'
        payload = dict(base_revision=draft['base_revision'], paper_id=paper['id'], data=base64.b64encode(raw).decode())
        result = self.editor.upload_paper(payload)
        paper['links'] = [dict(label='Paper', url=result['path'])]
        self.assertFalse(validate(draft['content'], read_content(self.root)))
        self.editor.preview_content(draft)
        self.assertEqual((Path(self.editor.preview.name) / 'dist' / result['path']).read_bytes(), raw)
        self.assertIn(result['path'], (Path(self.editor.preview.name) / 'dist/index.html').read_text())
        self.editor.upload_paper(payload)
        self.assertTrue(list((self.root / '.editor-state/backups').glob('*/' + paper['id'] + '.pdf')))
        for invalid in (dict(payload, paper_id='../escape'), dict(payload, data=base64.b64encode(b'not pdf').decode()), dict(payload, base_revision='stale')):
            with self.assertRaises(EditorError): self.editor.upload_paper(invalid)
        paper['links'][0]['url'] = 'assets/papers/../../secret.pdf'
        self.assertTrue(validate(draft['content'], read_content(self.root)))

    def test_preview_does_not_save_and_save_rebuilds_with_backup(self):
        before = read_content(self.root)
        draft = self.draft()
        result = self.editor.preview_content(draft)
        self.assertEqual(result['preview_url'], '/preview/index.html')
        preview = Path(self.editor.preview.name) / 'dist/index.html'
        self.assertIn('Editor integration test announcement.', preview.read_text())
        self.assertEqual(read_content(self.root), before)
        saved = self.editor.save(draft)
        self.assertEqual(saved['changed'], ['news'])
        self.assertIn('Editor integration test announcement.', (self.root / 'dist/index.html').read_text())
        backups = list((self.root / '.editor-state/backups').glob('*/news.json'))
        self.assertEqual(json.loads(backups[0].read_text()), before['news'])
        with self.assertRaises(EditorError) as error: self.editor.save(draft)
        self.assertEqual(error.exception.status, 409)

    def test_preview_uses_current_template_and_new_renderer_module(self):
        (self.root / 'future_renderer.py').write_text("MARKER = 'Future template marker'\n")
        build = self.root / 'build.py'
        with build.open('a') as output:
            output.write("\nfrom future_renderer import MARKER\np = OUT / 'index.html'\np.write_text(p.read_text().replace('</main>', '<p>' + MARKER + '</p></main>'))\n")
        self.editor.preview_content(self.draft())
        page = Path(self.editor.preview.name) / 'dist/index.html'
        self.assertIn('Future template marker', page.read_text())

    def test_content_editor_rejects_design_changes(self):
        draft = self.draft()
        draft['content']['design']['typography']['body_size'] = 18
        with self.assertRaisesRegex(EditorError, 'cannot change design'):
            self.editor.preview_content(draft)

    def test_bad_input_and_build_failure_leave_content_unchanged(self):
        before = read_content(self.root)
        draft = self.draft()
        draft['content']['news'][0]['url'] = 'javascript:alert(1)'
        with self.assertRaises(EditorError): self.editor.save(draft)
        draft = self.draft()
        with patch.object(self.editor, 'build_preview', side_effect=EditorError('failed build')):
            with self.assertRaises(EditorError): self.editor.save(draft)
        self.assertEqual(read_content(self.root), before)
        bad = copy.deepcopy(before)
        bad['publications'][1]['id'] = bad['publications'][0]['id']
        bad['profile']['name'] = ' '
        self.assertGreaterEqual(len(validate(bad, before)), 2)

    def test_design_save_rebuilds_all_layouts_and_keeps_content(self):
        before = read_content(self.root)
        draft = bundle(self.root)
        design = draft['content']['design']
        design['typography']['body_size'] = 18
        design['layout'].update(page_width=1200, news_height=440, portrait_position='right')
        self.assertEqual(validate_design(design), [])
        saved = Editor(self.root, allow_design=True).save(json.loads(json.dumps(draft)))
        self.assertEqual(saved['changed'], ['design'])
        self.assertEqual(read_content(self.root)['news'], before['news'])
        css = (self.root / 'dist/assets/design-tokens.css').read_text()
        self.assertIn('--d-body-size:18px;', css)
        self.assertIn('--d-page-width:1200px;', css)
        self.assertIn('--d-news-height:440px;', css)
        for layout in ('',):
            for page in ('index.html', 'lab.html'):
                html = (self.root / 'dist' / layout / page).read_text()
                self.assertIn('data-portrait="right"', html)
                self.assertIn('design-tokens.css', html)
                self.assertIn('design.css', html)
        bad = bundle(self.root)
        bad['content']['design']['dark']['ink'] = '#1B1B1B'
        with self.assertRaises(EditorError): self.editor.save(bad)
        self.assertEqual(read_content(self.root)['design'], design)

    def test_loopback_http_blocks_cross_origin_and_traversal(self):
        server = ThreadingHTTPServer(('127.0.0.1', 0), make_handler(self.editor))
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        origin = f'http://127.0.0.1:{server.server_port}'
        def request(method, path, headers=None, body=None):
            conn = HTTPConnection('127.0.0.1', server.server_port)
            conn.request(method, path, body=body, headers=headers or {})
            response = conn.getresponse()
            status, raw = response.status, response.read()
            conn.close()
            return status, raw
        try:
            status, raw = request('GET', '/api/status')
            self.assertEqual(status, 200)
            token = json.loads(raw)['token']
            self.assertEqual(request('GET', '/api/status', {'Host': 'malicious.example'})[0], 403)
            self.assertEqual(request('GET', '/%2e%2e/content/profile.json')[0], 404)
            self.assertEqual(request('GET', '/.git/config')[0], 404)
            body = json.dumps(self.draft())
            headers = {'Content-Type': 'application/json', 'Origin': 'https://malicious.example', 'X-Editor-Token': token}
            self.assertEqual(request('POST', '/api/save', headers, body)[0], 403)
            headers['Origin'] = origin
            headers['X-Editor-Token'] = 'wrong'
            self.assertEqual(request('POST', '/api/save', headers, body)[0], 403)
            headers['X-Editor-Token'] = token
            self.assertEqual(request('POST', '/api/preview', headers, body)[0], 200)
            self.assertEqual(request('POST', '/api/push-status', headers, '{}')[0], 200)
            self.assertEqual(request('GET', '/preview/index.html')[0], 200)
            large = dict(headers, **{'Content-Length': '1000001'})
            self.assertEqual(request('POST', '/api/save', large, b'{}')[0], 413)
            self.assertNotIn('Editor integration test announcement.', (self.root / 'content/news.json').read_text())
        finally:
            server.shutdown(); server.server_close(); thread.join()

    def test_pdf_upload_validates_and_builds_local_viewer_link(self):
        raw = b'%PDF-1.4\n1 0 obj<</Type/Catalog>>endobj\n%%EOF'
        current = bundle(self.root)
        with self.assertRaises(EditorError):
            self.editor.upload_cv(dict(base_revision=current['base_revision'], data=base64.b64encode(b'not PDF').decode()))
        uploaded = self.editor.upload_cv(dict(base_revision=current['base_revision'], data=base64.b64encode(raw).decode()))
        self.assertEqual((self.root / uploaded['path']).read_bytes(), raw)
        current['content']['profile']['cv'] = uploaded['path']
        self.editor.save(current)
        self.assertEqual((self.root / 'dist' / uploaded['path']).read_bytes(), raw)
        self.assertIn('href="assets/cv/jinzhen-wang.pdf"', (self.root / 'dist/index.html').read_text())
        with self.assertRaises(EditorError):
            self.editor.upload_cv(dict(base_revision='stale', data=base64.b64encode(raw).decode()))

    def test_publish_retry_pushes_existing_commit_and_excludes_code_edits(self):
        # Local bare fixture only: no real GitHub repository is written.
        remote = Path(self.temp.name) / 'remote.git'
        subprocess.run(['git', 'init', '--bare', str(remote)], check=True, capture_output=True)
        def git(*args):
            return subprocess.run(['git', '-C', str(self.root), *args], check=True, capture_output=True, text=True).stdout.strip()
        git('init', '-b', 'local-design'); git('config', 'user.name', 'Editor Test'); git('config', 'user.email', 'test@example.org')
        git('add', '.'); git('commit', '-m', 'Initial test source'); git('remote', 'add', 'origin', str(remote)); git('push', '-u', 'origin', 'local-design')
        with patch.object(self.editor, 'github_remote', return_value=True):
            (self.root / 'assets/style.css').write_text('changed layout')
            with self.assertRaises(EditorError): self.editor.publish(self.draft())
            git('restore', 'assets/style.css')
            raw = b'%PDF-1.4\n%%EOF'
            cv = self.root / 'assets/cv/jinzhen-wang.pdf'; cv.parent.mkdir(parents=True, exist_ok=True); cv.write_bytes(raw)
            draft = self.draft(); draft['content']['profile']['cv'] = 'assets/cv/jinzhen-wang.pdf'
            original_git = self.editor.git
            def fail_push(*args, **kwargs):
                if args[0] == 'push': raise EditorError('Simulated network failure', 409)
                return original_git(*args, **kwargs)
            with patch.object(self.editor, 'git', side_effect=fail_push):
                with self.assertRaises(EditorError) as error: self.editor.publish(draft)
            self.assertTrue(error.exception.extra['committed'])
            commit = git('rev-parse', 'HEAD')
            retry = self.editor.publish(bundle(self.root))
            self.assertEqual(retry['commit'], commit)
            self.assertEqual(git('rev-parse', 'origin/local-design'), commit)
            self.assertFalse(self.editor.pending_path.exists())
            self.assertEqual(git('show', 'HEAD:assets/cv/jinzhen-wang.pdf'), raw.decode().strip())
            self.assertEqual(read_content(self.root)['profile']['updated'], datetime.now(ZoneInfo('America/New_York')).strftime('%B %-d, %Y'))
            message = git('log', '-1', '--format=%B')
            self.assertIn('news: add Editor integration test announcement.', message)
            self.assertNotIn('main', retry['message'].split('.')[0])
            unchanged = self.editor.publish(bundle(self.root))
            self.assertEqual(unchanged['message'], 'No content changes to publish.')
            self.assertEqual(git('rev-parse', 'HEAD'), commit)
            self.assertTrue(retry['push_status']['confirmed'])
            self.assertEqual(self.editor.push_status()['state'], 'synced')
            # A zero exit code alone is insufficient: simulate no remote receipt.
            unreceived = self.draft()
            unreceived['content']['news'][0]['text'] = 'Unreceived publication test'
            def fake_success(*args, **kwargs):
                if args[0] == 'push': return ''
                return original_git(*args, **kwargs)
            with patch.object(self.editor, 'git', side_effect=fake_success):
                with self.assertRaises(EditorError) as error:
                    self.editor.publish(unreceived)
            self.assertIn('not confirmed', str(error.exception))
            self.assertTrue(self.editor.pending_path.exists())
            self.assertEqual(self.editor.push_status()['state'], 'unpushed')
            # Confirmation also works after the user pushes manually.
            git('push', 'origin', 'HEAD:local-design')
            self.assertTrue(self.editor.push_status()['confirmed'])
            self.assertFalse(self.editor.pending_path.exists())
            git('switch', '--detach')
            (self.root / 'bot-marker.txt').write_text('remote bot update')
            git('add', 'bot-marker.txt'); git('commit', '-m', 'Bot update'); git('push', 'origin', 'HEAD:local-design')
            git('switch', 'local-design')
            checked = self.editor.push_status()
            self.assertTrue(checked['confirmed']); self.assertEqual(checked['state'], 'behind')
            git('merge', '--ff-only', 'origin/local-design')
            saved = self.draft(); self.editor.save(saved)
            self.assertEqual(self.editor.push_status()['state'], 'saved')
            def offline(*args, **kwargs):
                if args[0] == 'fetch': raise EditorError('offline')
                return original_git(*args, **kwargs)
            with patch.object(self.editor, 'git', side_effect=offline):
                self.assertEqual(self.editor.push_status()['state'], 'unconfirmed')


if __name__ == '__main__': unittest.main()
