#!/usr/bin/env python3
"""Run the optional loopback-only editor: python3 scripts/editor_server.py."""
import argparse
import base64
import binascii
from zoneinfo import ZoneInfo
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import mimetypes
from pathlib import Path
import re
import secrets
import shutil
import subprocess
import sys
import tempfile
import threading
from urllib.parse import unquote, urlparse

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from editor.content import bundle, read_content, revision, validate
from editor.schema import CONTENT_NAMES
from editor.change_summary import summarize_changes
from bibliography import lookup as lookup_citation
from editor.design_assistant import DesignAssistant, CSS_PATH

PUBLISH_BRANCH = "local-design"
CV_PATH = "assets/cv/jinzhen-wang.pdf"


class EditorError(Exception):
    def __init__(self, message, status=400, **extra):
        super().__init__(message)
        self.status, self.extra = status, extra


class Editor:
    def __init__(self, root, allow_design=False):
        self.root = root.resolve()
        self.allow_design = allow_design
        self.assistant = DesignAssistant(self.root)
        self.preview = None
        self.lock = threading.Lock()
        self.token = secrets.token_urlsafe(32)
        self.state = self.root / '.editor-state'
        self.pending_path = self.state / 'pending-publish.json'

    def git(self, *args, timeout=30):
        result = subprocess.run(['git', '-C', str(self.root), *args], capture_output=True, text=True, timeout=timeout)
        if result.returncode:
            raise EditorError('Git could not complete this step. Check the local repository, GitHub authentication, and network, then try again.', 409)
        return result.stdout.strip()

    @staticmethod
    def github_remote(url):
        return bool(re.fullmatch(r'(?:https://github\.com/|git@github\.com:)[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+(?:\.git)?', url))

    def publishing_status(self):
        try:
            if Path(self.git('rev-parse', '--show-toplevel')).resolve() != self.root:
                return dict(ready=False, reason='Open the editor from the website repository root.')
            remote = self.git('remote', 'get-url', '--push', 'origin')
            if not self.github_remote(remote):
                return dict(ready=False, reason='Publishing needs a GitHub origin remote. Preview and saving are available.')
            branch = self.git('branch', '--show-current')
            if branch != PUBLISH_BRANCH:
                return dict(ready=False, reason='Start with python3 edit.py to synchronize and publish local-design.')
            return dict(ready=True, repository=remote, branch=branch)
        except (EditorError, subprocess.TimeoutExpired, FileNotFoundError):
            return dict(ready=False, reason='Publishing needs Git and a local checkout of the GitHub website repository.')

    def push_status(self, payload=None):
        status = self.publishing_status()
        if not status['ready']:
            return dict(state='unavailable', message=status['reason'], confirmed=False)
        try:
            self.git('fetch', 'origin', timeout=20)
            remote_line = self.git('ls-remote', 'origin', 'refs/heads/' + PUBLISH_BRANCH, timeout=20)
            if not remote_line:
                return dict(state='unpushed', confirmed=False, message='local-design is not on GitHub yet. Click Publish to push it.')
            remote = remote_line.split()[0]
            fetched = self.git('rev-parse', 'refs/remotes/origin/' + PUBLISH_BRANCH)
            if remote != fetched:
                return dict(state='unconfirmed', confirmed=False, message='GitHub changed during the check. Check again to confirm your push.')
            local = self.git('rev-parse', 'HEAD')
            ahead, behind = map(int, self.git('rev-list', '--left-right', '--count', 'HEAD...' + fetched).split())
            pending = json.loads(self.pending_path.read_text()) if self.pending_path.exists() else None
            wanted = pending['commit'] if pending else local
            received = subprocess.run(['git', '-C', str(self.root), 'merge-base', '--is-ancestor', wanted, fetched], capture_output=True).returncode == 0
            checked = datetime.now(timezone.utc).isoformat()
            if pending and received:
                self.pending_path.unlink(missing_ok=True)
            dirty = bool(self.git('status', '--porcelain'))
            state = 'synced'
            message = 'GitHub confirmed commit ' + wanted[:7] + ' on local-design.'
            if ahead and behind:
                state, message = 'diverged', 'Local and GitHub commits have diverged. Reconcile local-design before publishing.'
            elif ahead:
                state, message = 'unpushed', f'{ahead} local commit(s) have not reached GitHub. Click Publish to push them.'
            elif dirty:
                state, message = 'saved', 'Saved local changes have not been pushed. Click Publish when ready.'
            elif behind:
                state, message = 'behind', 'Your commit is confirmed on GitHub; newer remote changes are available. Reopen with a clean checkout to pull them.'
            if pending and not received:
                state, message = 'unpushed', 'Your previous push is not confirmed. Click Publish to retry the saved commit.'
            return dict(state=state, message=message, confirmed=received, local_commit=local,
                        remote_commit=remote, checked_at=checked, ahead=ahead, behind=behind)
        except (EditorError, subprocess.TimeoutExpired, ValueError, OSError):
            return dict(state='unconfirmed', confirmed=False,
                        message='GitHub push status could not be verified. Check authentication/network, then Check GitHub or retry Publish. Local files are preserved.')

    def candidate(self, payload, publishing=False):
        if not isinstance(payload, dict) or payload.get('schema_version') != 1:
            raise EditorError('Import an editor content package, version 1.')
        baseline = read_content(self.root)
        if payload.get('base_revision') != revision(baseline):
            raise EditorError('The source content changed since this draft was loaded. Download your draft, then load the current content before applying it.', 409)
        if not self.allow_design and isinstance(payload.get('content'), dict) and payload['content'].get('design') != baseline['design']:
            raise EditorError('The content editor cannot change design. Import design XML separately.')
        if not publishing and isinstance(payload.get('content'), dict) and isinstance(payload['content'].get('profile'), dict):
            payload['content']['profile']['updated'] = baseline['profile']['updated']
        errors = validate(payload.get('content'), baseline)
        if errors:
            raise EditorError('Please fix the highlighted content fields.', errors=errors)
        return payload['content']

    def build_preview(self, data, asset_overrides=None):
        temporary = tempfile.TemporaryDirectory(prefix='hpdi-editor-')
        folder = Path(temporary.name)
        try:
            # Use the same source tree as deployment, including future renderers.
            # Exclude generated output, repository state and local-only data.
            ignored = shutil.ignore_patterns('.git', '.openai', 'dist', '.editor-state',
                                            '__pycache__', '.DS_Store', '._*',
                                            '.venv', 'venv', 'node_modules', '.env', '.env.*')
            shutil.copytree(self.root, folder, dirs_exist_ok=True, ignore=ignored)
            for name in CONTENT_NAMES:
                (folder / 'content' / f'{name}.json').write_text(json.dumps(data[name], ensure_ascii=False, indent=2) + '\n')
            for name, source in (asset_overrides or {}).items():
                (folder / name).parent.mkdir(parents=True, exist_ok=True)
                (folder / name).write_text(source)
            for script in ('build.py', 'scripts/check_site.py'):
                result = subprocess.run([sys.executable, script], cwd=folder, capture_output=True, text=True, timeout=45)
                if result.returncode:
                    raise EditorError('The generated site did not pass its checks. ' + (result.stdout + result.stderr)[-2000:])
            return temporary
        except Exception:
            temporary.cleanup()
            raise

    def preview_content(self, payload):
        temporary = self.build_preview(self.candidate(payload))
        previous = self.preview
        self.preview = temporary
        if previous: previous.cleanup()
        return dict(ok=True, preview_url='/preview/index.html')

    def save(self, payload, publishing=False):
        data = self.candidate(payload, publishing=publishing)
        temporary = self.build_preview(data)
        current = read_content(self.root)
        # Recheck after the build in case an assistant or another editor changed files.
        if payload['base_revision'] != revision(current):
            temporary.cleanup()
            raise EditorError('The content changed during validation. Download your draft and reload current content.', 409)
        changed = [name for name in CONTENT_NAMES if data[name] != current[name]]
        if changed:
            backup = self.state / 'backups' / datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
            backup.mkdir(parents=True)
            for name in changed: shutil.copy2(self.root / 'content' / f'{name}.json', backup / f'{name}.json')
            try:
                for name in changed:
                    target = self.root / 'content' / f'{name}.json'
                    stage = target.with_suffix('.json.editor-tmp')
                    stage.write_text(json.dumps(data[name], ensure_ascii=False, indent=2) + '\n')
                    stage.replace(target)
                shutil.copytree(Path(temporary.name) / 'dist', self.root / 'dist', dirs_exist_ok=True)
            except Exception:
                for name in changed: shutil.copy2(backup / f'{name}.json', self.root / 'content' / f'{name}.json')
                raise
        if not changed:
            # A replacement PDF can keep the same profile link; refresh assets anyway.
            shutil.copytree(Path(temporary.name) / 'dist', self.root / 'dist', dirs_exist_ok=True)
        temporary.cleanup()
        return dict(ok=True, bundle=bundle(self.root), changed=changed)

    def design_configure(self, payload):
        return self.assistant.configure(payload)

    def design_chat(self, payload):
        return self.assistant.request(payload)

    def design_preview(self, payload):
        proposal = self.assistant.get_proposal(payload)
        data = read_content(self.root); data['design'] = proposal['design']
        temporary = self.build_preview(data, {CSS_PATH: proposal['css']})
        previous = self.preview; self.preview = temporary
        if previous: previous.cleanup()
        return dict(ok=True, preview_url='/preview/index.html')

    def design_apply(self, payload):
        proposal = self.assistant.get_proposal(payload)
        data = read_content(self.root); data['design'] = proposal['design']
        temporary = self.build_preview(data, {CSS_PATH: proposal['css']})
        try:
            self.assistant.get_proposal(payload)  # Check again after validation/build.
            backup = self.state / 'backups' / datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
            backup.mkdir(parents=True)
            targets = {'content/design.json': json.dumps(proposal['design'], ensure_ascii=False, indent=2)+'\n', CSS_PATH:proposal['css']}
            old = {name:(self.root / name).read_bytes() if (self.root / name).exists() else None for name in targets}
            for name, raw in old.items():
                if raw is not None: (backup / Path(name).name).write_bytes(raw)
            try:
                for name, source in targets.items():
                    target = self.root / name; stage = target.with_suffix(target.suffix+'.editor-tmp')
                    stage.write_text(source); stage.replace(target)
                shutil.copytree(Path(temporary.name) / 'dist', self.root / 'dist', dirs_exist_ok=True)
            except Exception:
                for name, raw in old.items():
                    target = self.root / name
                    if raw is None: target.unlink(missing_ok=True)
                    else: target.write_bytes(raw)
                raise
            self.assistant.proposal = None
            return dict(ok=True, bundle=bundle(self.root), message='Design applied locally. Publish design when ready.')
        finally: temporary.cleanup()

    def design_publish(self, payload):
        return self.publish(bundle(self.root), design_publish=True)

    def lookup_bibtex(self, payload):
        try: return lookup_citation(payload['paper'])
        except Exception as error:
            raise EditorError('Citation lookup failed. Check the DOI or paste the publisher BibTeX export. ' + str(error))

    def upload_cv(self, payload):
        if payload.get('base_revision') != revision(read_content(self.root)):
            raise EditorError('Content changed; reload the editor before uploading.', 409)
        try: raw = base64.b64decode(payload.get('data', ''), validate=True)
        except (ValueError, binascii.Error): raise EditorError('Choose a valid PDF file.')
        if not 0 < len(raw) <= 10 * 1024 * 1024 or not raw.startswith(b'%PDF-') or b'%%EOF' not in raw[-2048:]:
            raise EditorError('Choose a PDF file of at most 10 MB.')
        target = self.root / CV_PATH
        if target.exists():
            backup = self.state / 'backups' / datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
            backup.mkdir(parents=True); shutil.copy2(target, backup / 'cv.pdf')
        target.parent.mkdir(parents=True, exist_ok=True)
        stage = target.with_suffix('.pdf.editor-tmp'); stage.write_bytes(raw); stage.replace(target)
        return dict(ok=True, path=CV_PATH)

    def upload_photo(self, payload):
        if payload.get('base_revision') != revision(read_content(self.root)):
            raise EditorError('Content changed; reload before uploading.', 409)
        key = payload.get('photo_id', '')
        if not isinstance(key, str) or not re.fullmatch(r'[a-zA-Z0-9][a-zA-Z0-9_-]{0,99}', key):
            raise EditorError('Choose a valid gallery record.')
        try: raw = base64.b64decode(payload.get('data', ''), validate=True)
        except (ValueError, binascii.Error): raise EditorError('Choose a valid photo.')
        if not 0 < len(raw) <= 10 * 1024 * 1024 or not raw.startswith(b'\xff\xd8\xff') or not raw.endswith(b'\xff\xd9'):
            raise EditorError('Choose a JPEG photo of at most 10 MB.')
        path = f'assets/gallery/{key}.jpg'
        target = self.root / path
        if target.exists():
            backup = self.state / 'backups' / datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
            backup.mkdir(parents=True); shutil.copy2(target, backup / target.name)
        target.parent.mkdir(parents=True, exist_ok=True)
        stage = target.with_suffix('.jpg.editor-tmp'); stage.write_bytes(raw); stage.replace(target)
        return dict(ok=True, path=path)

    def upload_paper(self, payload):
        if payload.get('base_revision') != revision(read_content(self.root)):
            raise EditorError('Content changed; reload the editor before uploading.', 409)
        paper_id = payload.get('paper_id', '')
        if not isinstance(paper_id, str) or not re.fullmatch(r'[a-zA-Z0-9][a-zA-Z0-9_-]{0,99}', paper_id):
            raise EditorError('Choose a paper with a valid record ID.')
        try: raw = base64.b64decode(payload.get('data', ''), validate=True)
        except (ValueError, binascii.Error): raise EditorError('Choose a valid PDF file.')
        if not 0 < len(raw) <= 10 * 1024 * 1024 or not raw.startswith(b'%PDF-') or b'%%EOF' not in raw[-2048:]:
            raise EditorError('Choose a PDF file of at most 10 MB.')
        path = f'assets/papers/{paper_id}.pdf'
        target = self.root / path
        if target.exists():
            backup = self.state / 'backups' / datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
            backup.mkdir(parents=True); shutil.copy2(target, backup / target.name)
        target.parent.mkdir(parents=True, exist_ok=True)
        stage = target.with_suffix('.pdf.editor-tmp'); stage.write_bytes(raw); stage.replace(target)
        return dict(ok=True, path=path)

    def publish(self, payload, design_publish=False):
        status = self.publishing_status()
        if not status['ready']: raise EditorError(status['reason'], 409)
        outside = self.git('diff', '--name-only', 'HEAD').splitlines() + self.git('ls-files', '--others', '--exclude-standard').splitlines()
        allowed = {f'content/{name}.json' for name in CONTENT_NAMES if name != 'design'} | {CV_PATH}
        allowed.update(path for path in outside if re.fullmatch(r'assets/papers/[a-zA-Z0-9][a-zA-Z0-9_-]{0,99}\.pdf', path))
        allowed.update(path for path in outside if re.fullmatch(r'assets/gallery/[a-zA-Z0-9][a-zA-Z0-9_-]{0,99}\.jpg', path))
        if design_publish: allowed = {'content/design.json', CSS_PATH}
        if any(path not in allowed and not path.startswith('dist/') for path in outside):
            raise EditorError('There are code or layout changes outside the editor. Commit or discard them separately before publishing content.', 409)
        if self.pending_path.exists():
            pending = json.loads(self.pending_path.read_text())
            if pending.get('branch', PUBLISH_BRANCH) != PUBLISH_BRANCH:
                raise EditorError('The pending commit targets another branch. Push it manually before continuing.', 409)
            if self.git('rev-parse', 'HEAD') != pending['commit'] or outside:
                raise EditorError('A previous publish needs attention. Finish pushing its commit before making another content publish.', 409)
            if revision(self.candidate(payload)) != revision(read_content(self.root)):
                raise EditorError('Push the previous saved commit before publishing this new draft.', 409)
        else:
            self.git('fetch', 'origin', timeout=45)
            remote_ref = 'refs/remotes/origin/' + PUBLISH_BRANCH
            exists = subprocess.run(['git', '-C', str(self.root), 'show-ref', '--verify', '--quiet', remote_ref]).returncode == 0
            if exists and subprocess.run(['git', '-C', str(self.root), 'merge-base', '--is-ancestor', remote_ref, 'HEAD']).returncode != 0:
                raise EditorError('Local and GitHub history differ. Reconcile local-design with origin/local-design before publishing.', 409)
            committed_content = {name: json.loads(self.git('show', f'HEAD:content/{name}.json')) for name in CONTENT_NAMES}
            payload = json.loads(json.dumps(payload))
            payload['content']['profile']['updated'] = datetime.now(ZoneInfo('America/New_York')).strftime('%B %-d, %Y')
            saved = self.save(payload, publishing=True)
            paths = (['content/design.json', 'content/profile.json'] + ([CSS_PATH] if (self.root / CSS_PATH).exists() else [])) if design_publish else [f'content/{name}.json' for name in CONTENT_NAMES if name != 'design'] + ['dist']
            if 'dist' in paths and not self.git('ls-files', '--', 'dist'):
                paths.remove('dist')  # GitHub Actions rebuilds ignored output from source.
            if not design_publish and (self.root / CV_PATH).exists(): paths.append(CV_PATH)
            if not design_publish and (self.root / 'assets/papers').exists(): paths.append('assets/papers')
            if not design_publish and (self.root / 'assets/gallery').exists(): paths.append('assets/gallery')
            self.git('add', '--', *paths)
            if not self.git('diff', '--cached', '--name-only'):
                checked = self.push_status()
                if checked.get('confirmed'):
                    return dict(ok=True, message='No content changes to publish.', bundle=saved['bundle'], push_status=checked)
                if checked.get('state') != 'unpushed':
                    raise EditorError(checked['message'], 409, push_status=checked)
                pending = dict(commit=self.git('rev-parse', 'HEAD'), branch=PUBLISH_BRANCH)
                self.state.mkdir(exist_ok=True)
                self.pending_path.write_text(json.dumps(pending))
                return self.publish(saved['bundle'], design_publish=design_publish)
            try:
                self.git('commit', '-m', ('Update website design\n\n- Apply reviewed design settings and CSS overrides' if design_publish else summarize_changes(committed_content, read_content(self.root))) + ('\n- CV: upload PDF' if CV_PATH in self.git('diff', '--cached', '--name-only').splitlines() else ''))
            except EditorError:
                raise EditorError('Content is saved locally, but Git could not create the commit. Check your Git name/email configuration.', 409, saved=True)
            pending = dict(commit=self.git('rev-parse', 'HEAD'), branch=PUBLISH_BRANCH)
            self.state.mkdir(exist_ok=True)
            self.pending_path.write_text(json.dumps(pending))
        try:
            self.git('push', 'origin', 'HEAD:' + PUBLISH_BRANCH, timeout=45)
        except (EditorError, subprocess.TimeoutExpired):
            raise EditorError('The content commit is saved locally, but GitHub did not confirm the push. Check authentication/network and click Publish again to retry this commit.', 409, saved=True, committed=True, commit=pending['commit'], bundle=bundle(self.root))
        checked = self.push_status()
        if not checked.get('confirmed'):
            raise EditorError('Git returned from push, but GitHub receipt is not confirmed. Check GitHub or click Publish again to retry.', 409, saved=True, committed=True, commit=pending['commit'], bundle=bundle(self.root), push_status=checked)
        self.pending_path.unlink(missing_ok=True)
        return dict(ok=True, push_status=checked, commit=pending['commit'], bundle=bundle(self.root), message='GitHub confirmed your push to local-design (' + pending['commit'][:7] + '). Merge into main when ready to deploy.')


def make_handler(editor):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args): pass

        def trusted_host(self):
            return self.headers.get('Host') == f'127.0.0.1:{self.server.server_port}'

        def reply(self, value, status=200):
            raw = json.dumps(value, ensure_ascii=False).encode()
            self.send_response(status)
            self.send_header('Content-Type', 'application/json; charset=utf-8')
            self.send_header('Cache-Control', 'no-store')
            self.send_header('X-Content-Type-Options', 'nosniff')
            self.end_headers()
            self.wfile.write(raw)

        def do_GET(self):
            if not self.trusted_host(): return self.reply(dict(error='Invalid host.'), 403)
            path = unquote(urlparse(self.path).path)
            if path == '/api/status':
                return self.reply(dict(mode='local', token=editor.token, bundle=bundle(editor.root), publishing=editor.publishing_status(), assistant=editor.assistant.status()))
            if path.startswith('/api/'): return self.reply(dict(error='Unknown endpoint.'), 404)
            root = editor.root / 'dist'
            if path.startswith('/preview/'):
                if not editor.preview: return self.reply(dict(error='Generate a preview first.'), 404)
                root = Path(editor.preview.name) / 'dist'
                path = path[len('/preview'):]
            target = (root / path.lstrip('/')).resolve()
            if target.is_dir(): target /= 'index.html'
            if not target.is_relative_to(root.resolve()) or not target.is_file() or any(p.startswith('.') for p in target.relative_to(root.resolve()).parts):
                return self.reply(dict(error='File not found.'), 404)
            raw = target.read_bytes()
            self.send_response(200)
            self.send_header('Content-Type', mimetypes.guess_type(target)[0] or 'application/octet-stream')
            self.send_header('Cache-Control', 'no-store')
            self.send_header('X-Content-Type-Options', 'nosniff')
            self.end_headers()
            self.wfile.write(raw)

        def do_POST(self):
            origin = f'http://127.0.0.1:{self.server.server_port}'
            if not self.trusted_host() or self.headers.get('Origin') != origin or not secrets.compare_digest(self.headers.get('X-Editor-Token', ''), editor.token):
                return self.reply(dict(error='Open the editor on this computer to make changes.'), 403)
            if self.headers.get('Content-Type', '').split(';')[0] != 'application/json':
                return self.reply(dict(error='JSON content is required.'), 415)
            try: length = int(self.headers.get('Content-Length', '0'))
            except ValueError: return self.reply(dict(error='Invalid request size.'), 400)
            if not 0 < length <= (14000000 if urlparse(self.path).path in ('/api/upload-cv', '/api/upload-paper', '/api/upload-photo') else 1000000): return self.reply(dict(error='Content package is too large or empty.'), 413)
            if not editor.lock.acquire(blocking=False): return self.reply(dict(error='Another editor operation is running. Try again when it finishes.'), 409)
            try:
                payload = json.loads(self.rfile.read(length))
                action = {'/api/preview': editor.preview_content, '/api/save': editor.save, '/api/publish': editor.publish, '/api/upload-cv': editor.upload_cv, '/api/upload-paper': editor.upload_paper, '/api/upload-photo': editor.upload_photo, '/api/bibtex': editor.lookup_bibtex, '/api/push-status': editor.push_status, '/api/design-configure': editor.design_configure, '/api/design-chat': editor.design_chat, '/api/design-preview': editor.design_preview, '/api/design-apply': editor.design_apply, '/api/design-publish': editor.design_publish}.get(urlparse(self.path).path)
                if not action: raise EditorError('Unknown editor action.', 404)
                self.reply(action(payload))
            except EditorError as error: self.reply(dict(error=str(error), **error.extra), error.status)
            except (ValueError, TypeError) as error: self.reply(dict(error=str(error) or 'The content package could not be read.'), 400)
            except subprocess.TimeoutExpired: self.reply(dict(error='The operation timed out. Check the repository state before retrying.'), 504)
            except Exception: self.reply(dict(error='The operation failed. Your draft remains in the browser; download it before restarting.'), 500)
            finally: editor.lock.release()
    return Handler


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', type=int, default=8765)
    parser.add_argument('--open', action='store_true', help='Open the local editor in your browser')
    args = parser.parse_args()
    # Always refresh the editor and pages from the current checkout.
    subprocess.run([sys.executable, str(ROOT / 'build.py')], check=True)
    subprocess.run([sys.executable, str(ROOT / 'scripts/check_site.py')], check=True)
    editor = Editor(ROOT)
    server = ThreadingHTTPServer(('127.0.0.1', args.port), make_handler(editor))
    print(f'Open http://127.0.0.1:{server.server_port}/admin/ in your browser. Ctrl+C stops the editor.', flush=True)
    if args.open:
        import webbrowser
        webbrowser.open(f'http://127.0.0.1:{server.server_port}/admin/')
    try: server.serve_forever()
    except KeyboardInterrupt: pass
    finally:
        server.server_close()
        if editor.preview: editor.preview.cleanup()


if __name__ == '__main__': main()
