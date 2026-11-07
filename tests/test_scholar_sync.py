"""Scholar profile parsing, Crossref verification and entry generation (offline)."""
import json
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts import scholar_sync as S  # noqa: E402
from design import token_css, validate_design  # noqa: E402

ROW = ('<tr class="gsc_a_tr"><td class="gsc_a_t"><a href="/citations?view_op=view_citation" class="gsc_a_at">{title}</a>'
       '<div class="gs_gray">J Wang, X Liang, ...</div><div class="gs_gray">{venue}<span class="gs_oph">, {year}</span></div></td>'
       '<td class="gsc_a_c"><a class="gsc_a_ac gs_ibl">12</a></td><td class="gsc_a_y"><span class="gsc_a_h gsc_a_hc gs_ibl">{year}</span></td></tr>')
PAGE = '<html><table id="gsc_a_t"><tbody id="gsc_a_b">{rows}</tbody></table></html>'


def crossref_item(title, doi='10.1109/new.2026.1', container='2026 IEEE 42nd International Conference on Data Engineering (ICDE)',
                  kind='proceedings-article', owner=True, year=2026):
    authors = [dict(given='Ada', family='Lovelace')] + ([dict(given='Jinzhen', family='Wang')] if owner else [])
    return {'type': kind, 'title': [title], 'author': authors, 'container-title': [container], 'DOI': doi,
            'published-print': {'date-parts': [[year]]}, 'page': '1-10', 'publisher': 'IEEE'}


class ScholarSyncTests(unittest.TestCase):
    def setUp(self):
        self.publications = json.loads((ROOT / 'content/publications.json').read_text())

    def test_profile_rows_and_blocked_pages(self):
        html = PAGE.format(rows=ROW.format(title='Paper &amp; One', venue='IEEE TPDS 30 (2)', year='2026') + ROW.format(title='Two', venue='', year=''))
        rows = S.parse_profile(html)
        self.assertEqual(rows[0], dict(title='Paper & One', authors='J Wang, X Liang, ...', venue='IEEE TPDS 30 (2)', year='2026'))
        self.assertEqual(rows[1]['year'], '')
        with self.assertRaises(S.ScholarBlocked):
            S.parse_profile('<html><div id="gs_captcha_ccl">Please show you are not a robot</div></html>')
        self.assertEqual(S.parse_profile(PAGE.format(rows='')), [])  # empty profile, not a block

    def test_existing_papers_are_skipped_and_new_ones_verified(self):
        existing = self.publications[4]
        rows = [dict(title=existing['title'].upper() + '.', authors='', venue='', year=str(existing['year'])),
                dict(title='Fast Lossy Compression for Exascale Data', authors='', venue='ICDE', year='2026'),
                dict(title='A Workshop Poster', authors='', venue='', year='2026'),
                dict(title='Same DOI, Different Title', authors='', venue='', year='2023')]

        def lookup(row):
            if row['title'].startswith('Fast'): return crossref_item('Fast Lossy Compression for Exascale Data'), ''
            if row['title'].startswith('Same'): return crossref_item('x', doi=existing['doi'].upper()), ''
            return None, 'no confident Crossref title match'

        added, manual = S.run(rows, self.publications, lookup)
        self.assertEqual([r['title'] for r, _ in manual], ['A Workshop Poster'])
        self.assertEqual(len(added), 1)
        entry, known_venue = added[0]
        self.assertTrue(known_venue)
        self.assertEqual((entry['id'], entry['venue'], entry['short']), ('fast2026', 'IEEE International Conference on Data Engineering', 'ICDE'))
        self.assertEqual(entry['authors'], 'Ada Lovelace, Jinzhen Wang')
        self.assertEqual(entry['links'], [dict(label='DOI', url='https://doi.org/10.1109/new.2026.1')])
        self.assertEqual(entry['citation']['pages'], '1--10')
        self.assertTrue(set(['id', 'title', 'authors', 'year', 'venue', 'short', 'links']) <= set(entry))
        ordered = S.insert(list(self.publications), [entry])
        self.assertEqual([p['year'] for p in ordered], sorted((p['year'] for p in ordered), reverse=True))

    def test_crossref_requires_title_match_owner_and_paper_type(self):
        row = dict(title='Fast Lossy Compression for Exascale Data', authors='', venue='', year='2026')
        cases = [([crossref_item(row['title'])], True),
                 ([crossref_item(row['title'], owner=False)], 'does not list Jinzhen Wang'),
                 ([crossref_item(row['title'], kind='posted-content')], 'no confident'),
                 ([crossref_item('Something Else Entirely')], 'no confident'),
                 ([crossref_item(row['title'], year=2019)], 'is from 2019')]
        for items, expected in cases:
            with self.subTest(expected=expected), patch.object(S, 'get', return_value=json.dumps({'message': {'items': items}})):
                item, reason = S.crossref_match(row)
                if expected is True: self.assertIsNotNone(item)
                else: self.assertIsNone(item); self.assertIn(expected, reason)

    def test_venue_cleanup_and_unique_ids(self):
        self.assertEqual(S.clean_venue('Proceedings of the 39th ACM International Conference on Supercomputing'), ('ACM International Conference on Supercomputing', ''))
        self.assertEqual(S.clean_venue('2023 IEEE 39th International Conference on Data Engineering (ICDE)'), ('IEEE International Conference on Data Engineering', 'ICDE'))
        taken = {'fast2026'}
        self.assertEqual(S.make_id('Towards Fast I/O', 2026, taken), 'fast2026b')
        self.assertEqual(S.scholar_user({'scholar': 'https://scholar.google.com/citations?user=otnPh2IAAAAJ&hl=en'}), 'otnPh2IAAAAJ')


    def test_dblp_fallback_picks_profile_overlapping_site_dois(self):
        doi_a, doi_b = self.publications[4]['doi'], self.publications[5]['doi']
        def person(*pubs):
            body = ''.join(f'<r><{kind} key="k{i}"{extra}><author pid="1">Jinzhen Wang</author><title>{title}.</title><year>2026</year>'
                           f'<booktitle>ICDE</booktitle><ee>https://doi.org/{doi}</ee></{kind}></r>' for i, (kind, extra, title, doi) in enumerate(pubs))
            return f'<dblpperson name="Jinzhen Wang">{body}</dblpperson>'
        mine = person(('inproceedings', '', 'Old A', doi_a), ('article', '', 'Old B', doi_b),
                      ('inproceedings', '', 'Brand New <i>Paper</i>', '10.1/new'), ('article', ' publtype="informal"', 'arXiv copy', '10.48550/x'))
        other = person(('article', '', 'Unrelated', '10.9/zzz'))
        pages = {'search': json.dumps({'result': {'hits': {'hit': [{'info': {'url': 'https://dblp.org/pid/00/other'}}, {'info': {'url': 'https://dblp.org/pid/11/mine'}}]}}}),
                 'other': other, 'mine': mine}
        fake = lambda url, accept='': pages['search' if 'search' in url else 'mine' if 'mine' in url else 'other']
        with patch.object(S, 'get', side_effect=fake), patch.object(S.time, 'sleep'):
            url, rows = S.dblp_author('Jinzhen Wang', self.publications)
        self.assertEqual(url, 'https://dblp.org/pid/11/mine')
        self.assertEqual([r['title'] for r in rows], ['Old A', 'Old B', 'Brand New Paper'])
        new, _ = S.find_new(rows, self.publications, [])
        self.assertEqual([r['doi'] for r in new], ['10.1/new'])
        with patch.object(S, 'get', side_effect=lambda url, accept='': pages['search'] if 'search' in url else other), patch.object(S.time, 'sleep'):
            with self.assertRaises(S.ScholarBlocked): S.dblp_author('Jinzhen Wang', self.publications)

    def test_crossref_lookup_by_doi(self):
        row = dict(title='Brand New Paper', authors='', venue='', year='2026', doi='10.1/new')
        message = lambda **kw: json.dumps({'message': crossref_item('Brand New Paper:', doi='10.1/new', **kw)})
        with patch.object(S, 'get', return_value=message()) as get:
            item, _ = S.crossref_match(row)
        self.assertEqual(item['DOI'], '10.1/new'); self.assertIn('/works/10.1%2Fnew', get.call_args[0][0])
        with patch.object(S, 'get', return_value=message(kind='posted-content')):
            self.assertIn('not a paper', S.crossref_match(row)[1])

class DesignTokenTests(unittest.TestCase):
    def test_current_design_is_valid_and_uses_google_sans_headings(self):
        design = json.loads((ROOT / 'content/design.json').read_text())
        self.assertEqual(validate_design(design), [])
        css = token_css(design)
        self.assertIn('--d-heading-font:\'Google Sans\'', css)
        self.assertIn('--d-body-font:-apple-system', css)


if __name__ == '__main__':
    unittest.main()
