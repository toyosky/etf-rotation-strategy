"""Offline deterministic V3 build and V2 collision audit from frozen evidence."""
from __future__ import annotations
import argparse
from collections import Counter, defaultdict
from datetime import date, timedelta
import hashlib
import json
from pathlib import Path
from bs4 import BeautifulSoup
import pandas as pd
from .model import economic_labels, name_key, normalize_name, valid_index_name, validate_intervals, supplemental_labels_v31
from .evidence import verify_documents


def dump(path: Path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False)+"\n")


def official_inputs(root: Path):
    sse = json.loads((root/"sse.json").read_text())
    sh = {r['FUND_CODE']: (r, sse) for r in sse['payload']['result'] if r['CATEGORY'].startswith(('F1', 'F2'))}
    sz = {}
    counts = Counter()
    totals = {}
    for p in sorted(root.glob('szse-*.json')):
        obj = json.loads(p.read_text())
        meta = obj['payload'][0]['metadata']
        counts[meta['catalogid']] += len(obj['payload'][0]['data'])
        totals[meta['catalogid']] = int(meta['recordcount'])
        for r in obj['payload'][0]['data']:
            code = BeautifulSoup(r['sys_key'], 'html.parser').get_text().strip()
            if code in sz:
                raise ValueError(f"duplicate official symbol {code}")
            rr = dict(r, product_type='LOF' if obj['payload'][0]['metadata']['catalogid']=='1945_LOF' else 'ETF')
            sz[code] = (rr, obj)
    if set(totals) != {'1945', '1945_LOF'} or dict(counts) != totals:
        raise ValueError('incomplete official ETF/LOF pagination; resume collection')
    return sh, sz


def registry_inputs(root: Path, snapshot_date: str | None = None):
    """Use ONLY official full-name/code links; never silently learn from returns."""
    by_code, by_name = {}, defaultdict(set)
    for p in sorted(root.glob('cnindex-*.json')):
        if p.stem == 'cnindex-indices':
            continue
        obj = json.loads(p.read_text())
        r = obj['payload'].get('data')
        if not r or not r.get('indexcode') or not r.get('indexfullcname'):
            continue
        code = r['indexcode']
        rec = dict(key=f"OFFICIAL_INDEX_CODE:{code}", index_code=code, index_name=r['indexfullcname'],
                   index_provider=None, source_url=obj['source_url'])
        by_code[code] = rec
        by_name[normalize_name(r['indexfullcname'])].add(code)
        # Short names are separately retained for auditing; never automatically
        # equate an arbitrary short name with a legal full index name.
    p = root/'sse-indices.json'
    if p.exists():
        obj = json.loads(p.read_text())
        for r in obj['payload']['result']:
            code = r['indexCode']
            rec = dict(key=f"OFFICIAL_INDEX_CODE:{code}", index_code=code,
                       index_name=r['indexFullName'], index_provider=None, source_url=obj['source_url'])
            if code in by_code and by_code[code]['index_name'] != rec['index_name']:
                raise ValueError(f"official registry code conflict: {code}")
            by_code[code] = rec
            by_name[normalize_name(r['indexFullName'])].add(code)
    # V3.1: CSI publishes an official index-code/full-name catalog.  This
    # exact bridge is evidence from the compiler, never a fund-name guess.
    # Never replace a contradictory registry mapping silently.
    csi = root/'csindex-catalog.json'
    if csi.exists():
        source = json.loads(csi.read_text())
        if source.get('provider') != 'CSI' or len(source['payload'].get('indices',[])) < 500:
            raise ValueError('Invalid/incomplete official CSI catalog')
        observed = source.get('observed_at')
        if not observed or not source.get('raw_sha256'):
            raise ValueError('CSI provenance fields missing')
        seen_codes = {}
        for idx in source['payload']['indices']:
            code, name = str(idx['index_code']), str(idx['index_name'])
            if not code or not name:
                raise ValueError('Blank official CSI index entry')
            if code in seen_codes and seen_codes[code] != name:
                raise ValueError(f'Conflicting CSI code mapping: {code}')
            seen_codes[code] = name
            prior = by_code.get(code)
            if prior and normalize_name(prior['index_name']) != normalize_name(name):
                # A bare code can collide across index vendors; preserve the
                # registry already known to this V3 snapshot, quarantine
                # this potential bridge instead of overwriting it.
                continue
            if not prior:
                by_code[code] = dict(key=f'CSI:{code}', index_code=code,
                    index_name=name, index_provider='CSI',
                    source_url=source['source_url'])
            by_name[normalize_name(name)].add(code)
    aliases = json.loads(Path(__file__).with_name('index_aliases.json').read_text())
    for a in aliases:
        verify_documents(a.get('evidence_documents', []), snapshot_date)
        rec = dict(key=a['canonical_key'], index_code=a['index_code'], index_name=a['index_name'],
                   index_provider=a['index_provider'], source_url=a['source_url'],
                   code_namespace=a.get('code_namespace'), return_variant=a.get('index_return_variant'))
        for code in a['code_aliases']:
            prior = by_code.get(code)
            if prior and normalize_name(prior['index_name']) not in {normalize_name(n) for n in a['name_aliases']}:
                raise ValueError(f'curated code conflicts with a different official index: {code}')
            by_code[code] = rec
        # Some legally verified synonyms have no evidenced canonical code.
        # Internal lookup IDs must never be exposed as official index_code.
        lookup = a['index_code'] or '@ALIAS:' + a['canonical_key']
        by_code[lookup] = rec
        for name in a['name_aliases']:
            by_name[normalize_name(name)] = {lookup}
    return by_code, by_name


def build(metadata: list[dict], profiles: dict, official: Path, archive: pd.DataFrame,
          snapshot_date: str):
    sh, sz = official_inputs(official)
    by_code, by_name = registry_inputs(official, snapshot_date)
    listings = {}
    for p in sorted(official.glob('listings-*.json')):
        src = json.loads(p.read_text())
        for r in src['payload'][0]['data']:
            symbol = BeautifulSoup(r['sys_key'], 'html.parser').get_text().strip()
            if symbol in listings:
                raise ValueError('duplicate official listing record')
            listings[symbol] = (r, src)
    # Input includes every metadata interval; keep full export as the backup.
    current = {}
    for r in sorted(metadata, key=lambda r: (r['symbol'], r['valid_from'], r['id'])):
        if not r['valid_to']:
            current[r['symbol']] = r
    archive = archive.copy()
    archive['symbol'] = archive.symbol.astype(str).str.zfill(6)
    archive['date'] = archive.date.astype(str).str[:10]
    coverage = archive.groupby('symbol').agg(first_bar=('date','min'),last_bar=('date','max'),bar_count=('date','size')).to_dict('index')
    symbols = sorted(set(current) | set(profiles) | set(sh) | set(sz) | set(coverage))
    next_day = (date.fromisoformat(snapshot_date)+timedelta(days=1)).isoformat()
    for obj in list(profiles.values()) + [json.loads(p.read_text()) for p in official.glob('*.json')]:
        if obj.get('observed_at', '')[:10] != snapshot_date:
            raise ValueError('frozen evidence date differs from snapshot date; use a new dated cache')
    # For a code-only SZSE identity, keep the official code. Link to an official
    # full name only via registry, otherwise the auxiliary profile is explicit.
    # A bridge supported solely by an auxiliary page is a candidate, not a
    # verified code/name merge. Unresolved bridges go to identity_review.json.
    # Fund-specific mandates: strictly curated from published issuer documents;
    # no benchmark-as-tracking-index substitution and no historical backdating.
    mandates = json.loads(Path(__file__).with_name('fund_contract_evidence_v31.json').read_text())
    mandate_by_symbol = {r["symbol"]:r for r in mandates}
    if len(mandate_by_symbol) != len(mandates):
        raise ValueError("Duplicate manual mandate symbol")
    records, reviews, identity_review = [], [], []
    for symbol in symbols:
        legacy = current.get(symbol, {})
        prof = profiles.get(symbol, {})
        facts = prof.get('facts', {}) if prof.get('status') == 'ok' else {}
        legal = facts.get('基金全称')
        aux_index = facts.get('跟踪标的', '')
        if not valid_index_name(aux_index):
            aux_index = None
        rec = dict(symbol=symbol, name=legacy.get('name'), legal_fund_name=legal,
            product_type=legacy.get('product_type', 'UNKNOWN'), tracking_mode='UNKNOWN',
            index_name=None, index_code=None, index_provider=None, exact_index_key=None,
            exact_index_verified=False, exposure_id=None, exposure_name=None, exposure_parent=None,
            sector_level1=None, sector_level2=None, sector_level3=None, region_primary=None,
            exposure_type=None, risk_bucket=None, index_style=None,
            classification_source=[], source_url=[], source_date=None, observed_on=snapshot_date,
            valid_from=snapshot_date, valid_to=None, known_from=next_day,
            listing_date=None, delisting_date=None, listing_known_from=None,
            confidence='UNVERIFIED', needs_review=True, classification_reason=[],
            classification_version='V3.2.0', historical_scope='CURRENT_SNAPSHOT_ONLY',
            legacy_underlying_key=legacy.get('underlying_key'), legacy_risk_bucket=legacy.get('risk_bucket'),
            legacy_style_sector=legacy.get('style_sector'),
            auxiliary_index_name=aux_index, auxiliary_source_url=prof.get('source_url'),
            auxiliary_status=prof.get('status', 'missing'),
            current_exchange_listed_verified=symbol in sh or symbol in sz,
            legacy_listed_flag=legacy.get('current_exchange_listed'),
            quote_currency=None, settlement_mechanism=None, replication_method=None,
            premium_sensitive=True, execution_attributes_verified=False,
            legal_mandate_verified=False, mandate_document_url=None, mandate_published_date=None,
            **coverage.get(symbol, dict(first_bar=None, last_bar=None, bar_count=0)))
        reasons = []
        registry = None
        if symbol in sh:
            r, src = sh[symbol]
            rec.update(name=r['FUND_EXPANSION_ABBR'],
                       product_type='ETF' if r['CATEGORY'].startswith('F1') else 'LOF',
                       listing_date=r['LISTING_DATE'], listing_known_from=next_day)
            rec['classification_source'].append('SSE_OFFICIAL_TRACKED_INDEX_LIST')
            rec['source_url'].append(src['source_url'])
            if valid_index_name(r['INDEX_NAME']):
                rec.update(index_name=r['INDEX_NAME'], exact_index_verified=True,
                           confidence='HIGH_OFFICIAL_TRACKED_NAME', tracking_mode='PASSIVE_INDEX')
                codes = by_name.get(normalize_name(r['INDEX_NAME']), set())
                if len(codes) == 1:
                    registry = by_code[next(iter(codes))]
            else:
                reasons.append('OFFICIAL_LIST_HAS_NO_TRACKED_INDEX')
        elif symbol in sz:
            r, src = sz[symbol]
            code = r['nhzs'].strip().split()[0] if r['nhzs'].strip() else ''
            rec.update(name=BeautifulSoup(r['kzjcurl'], 'html.parser').get_text(' ',strip=True), product_type=r['product_type'])
            rec['classification_source'].append('SZSE_OFFICIAL_FITTED_INDEX_CODE')
            rec['source_url'].append(src['source_url'])
            if code and code not in {'-', '--'}:
                rec.update(index_code=code, exact_index_key='SZSE_FITTED_CODE:'+code,
                           exact_index_verified=True, tracking_mode='PASSIVE_INDEX',
                           confidence='MEDIUM_OFFICIAL_CODE_AUXILIARY_NAME')
                registry = by_code.get(code)
                if registry:
                    rec['index_name'] = registry['index_name']
                else:
                    rec['index_name'] = aux_index
                    reasons.append('OFFICIAL_CODE_NAME_LINK_NOT_VERIFIED')
                    identity_review.append(dict(symbol=symbol, official_code=code,
                        candidate_name=aux_index, reason='DO_NOT_MERGE_BY_AUXILIARY_NAME_ALONE'))
            else:
                reasons.append('OFFICIAL_FITTED_CODE_MISSING')
            if symbol in listings:
                listing, ls = listings[symbol]
                rec.update(listing_date=listing['ssrq'], listing_known_from=next_day)
                rec['source_url'].append(ls['source_url'])
                rec['classification_source'].append('SZSE_OFFICIAL_LISTING_DATE')
            else:
                reasons.append('OFFICIAL_LISTING_DATE_MISSING')
        else:
            reasons.append('NOT_IN_CAPTURED_OFFICIAL_LISTS')
            if aux_index:
                reasons.append('AUXILIARY_TRACKING_IDENTITY_ONLY')
        if registry:
            rec.update(exact_index_key=registry['key'], index_code=registry['index_code'],
                       index_provider=registry['index_provider'], confidence='HIGH_OFFICIAL_INDEX_LINK')
            rec['index_code_namespace'] = registry.get('code_namespace')
            rec['index_return_variant'] = registry.get('return_variant')
            rec['classification_source'].append('OFFICIAL_INDEX_REGISTRY_FULL_NAME_CODE')
            rec['source_url'].append(registry['source_url'])
        rec['official_fitted_index_code'] = (sz[symbol][0]['nhzs'].strip() if symbol in sz else None)
        if rec['product_type'] == 'LOF' and rec['exact_index_verified']:
            # A LOF may publish a benchmark/fitted index without a legal passive
            # mandate. Only a reviewed contract/prospectus may promote it.
            rec.update(reference_index_name=rec['index_name'], reference_index_code=rec['index_code'],
                       index_name=None, index_code=None, index_provider=None,
                       exact_index_key=None, exact_index_verified=False,
                       tracking_mode='UNVERIFIED_LOF_MANDATE', confidence='UNVERIFIED')
            reasons.append('LOF_LEGAL_TRACKING_MANDATE_NOT_VERIFIED')
        if rec['index_name'] and not rec['exact_index_key']:
            rec['exact_index_key'] = name_key(rec['index_name'])
        if rec['index_name'] and rec['exact_index_verified']:
            rec.update(supplemental_labels_v31(rec['index_name'], economic_labels(rec['index_name'])))
            if rec['exposure_type'] and rec['region_primary']:
                # Conservative minimum fine exposure: one distinct index/strategy.
                # Cross-index equivalence is NEVER inferred from a sector label.
                rec['exposure_id'] = 'EXPOSURE:'+rec['exact_index_key']
                rec['exposure_name'] = rec['index_name']
                rec['exposure_parent'] = rec['sector_level1']
            else:
                reasons.append('INDEX_ECONOMIC_REGION_OR_ASSET_NOT_VERIFIED')
            if not rec['sector_level1']:
                reasons.append('INDEX_SECTOR_CLASSIFICATION_NOT_VERIFIED')
        if legal and '增强' in legal:
            rec['tracking_mode'] = 'ENHANCED_INDEX'
            if rec['exposure_id']:
                rec['exposure_id'] += '|ENHANCED'
            reasons.append('ENHANCED_STRATEGY_REQUIRES_MANDATE_REVIEW')
        if not rec['exact_index_verified'] and rec['tracking_mode'] != 'UNVERIFIED_LOF_MANDATE':
            # A benchmark is NOT a legally tracked index. Never use it as one.
            rec['tracking_mode'] = 'UNVERIFIED_NON_INDEX_STRATEGY' if not aux_index else 'UNVERIFIED_INDEX_STRATEGY'
            rec['classification_reason'].append('Benchmark deliberately not substituted for a tracked index')
        if rec['index_name'] and rec['region_primary'] == 'CN' and rec['exposure_type'] == 'EQUITY':
            # Research proxy only: domestic-equity classification does not certify
            # any T+0/settlement/currency flags; those remain NULL/unverified.
            rec['premium_sensitive'] = False
        if symbol in mandate_by_symbol:
            d = mandate_by_symbol[symbol]
            verify_documents(d.get('evidence_documents', []), snapshot_date)
            # A documented fund-specific identity is stronger than a
            # third-party name bridge. The evidence is current and must
            # never be extrapolated before the current captured snapshot.
            if d["source_date"] > snapshot_date:
                raise ValueError(f"Future-dated legal evidence: {symbol}")
            if not rec["current_exchange_listed_verified"]:
                raise ValueError(f"Mandate without official current listing: {symbol}")
            rec["legal_mandate_verified"] = True
            rec["mandate_document_url"] = d["source_url"]
            rec["mandate_published_date"] = d["source_date"]
            rec["source_date"] = d["source_date"]
            rec["source_url"].append(d["source_url"])
            rec["classification_source"].append(d["kind"])
            rec["confidence"] = "HIGH_OFFICIAL_FUND_MANDATE"
            rec["region_primary"] = d["region_primary"]
            rec["exposure_type"] = d["exposure_type"]
            rec["sector_level1"] = d["sector_level1"]
            rec["sector_level2"] = d["sector_level2"]
            rec["tracking_mode"] = d["tracking_mode"]
            rec["risk_bucket"] = "|".join((d["region_primary"],
                                        d["exposure_type"],d["sector_level1"]))
            if d.get("replication_method"):
                rec["replication_method"] = d["replication_method"]
            rec['share_class'] = d.get('share_class')
            rec['reported_contract_effective_date'] = d.get('reported_contract_effective_date')
            rec['history_review_note'] = d.get('history_review_note')
            if d["kind"] in {"OFFICIAL_PASSIVE_INDEX_MANDATE",
                              "OFFICIAL_PASSIVE_INDEX_FOF_MANDATE"}:
                if not d.get("index_name"):
                    raise ValueError(f"Passive mandate has no tracked legal index: {symbol}")
                # Do not assert that an exchange 'fitted code' is the
                # index compiler's canonical ID: legal-name key is safer.
                rec["index_name"] = d["index_name"]
                matches = by_name.get(normalize_name(d['index_name']), set())
                canonical = by_code[next(iter(matches))] if len(matches) == 1 else None
                rec["index_code"] = canonical['index_code'] if canonical else None
                rec["index_provider"] = canonical['index_provider'] if canonical else None
                rec["exact_index_key"] = canonical['key'] if canonical else name_key(d["index_name"])
                rec['canonical_index_name'] = canonical['index_name'] if canonical else d['index_name']
                if canonical:
                    rec['source_url'].append(canonical['source_url'])
                    rec['classification_source'].append('OFFICIAL_DOCUMENTED_INDEX_SYNONYM')
                rec["exact_index_verified"] = True
                rec["exposure_id"] = "EXPOSURE:"+rec["exact_index_key"]
                rec["exposure_name"] = d["index_name"]
                rec["exposure_parent"] = d["sector_level1"]
                reasons = [x for x in reasons if x not in {
                    "OFFICIAL_CODE_NAME_LINK_NOT_VERIFIED",
                    "INDEX_ECONOMIC_REGION_OR_ASSET_NOT_VERIFIED",
                    "INDEX_SECTOR_CLASSIFICATION_NOT_VERIFIED",
                    "OFFICIAL_LIST_HAS_NO_TRACKED_INDEX",
                    "OFFICIAL_FITTED_CODE_MISSING",
                    "LOF_LEGAL_TRACKING_MANDATE_NOT_VERIFIED",
                    "AUXILIARY_TRACKING_IDENTITY_ONLY"}]
                identity_review = [x for x in identity_review if x['symbol'] != symbol]
            else:
                if d.get("index_name") is not None:
                    raise ValueError(f"Non-index mandate cannot create tracked index: {symbol}")
                rec["index_name"] = None
                rec["index_code"] = None
                rec["index_provider"] = None
                rec["exact_index_key"] = None
                rec["exact_index_verified"] = False
                rec["exposure_id"] = d.get("legal_exposure_id","NON_PASSIVE:GLOBAL_CRUDE_OIL_FOF")
                rec["exposure_name"] = d.get("legal_exposure_name","全球原油基金中基金（非被动指数）")
                rec["exposure_parent"] = d["sector_level1"]
                rec["performance_benchmark"] = d.get("performance_benchmark")
                # The economic asset is legally identified, but there is no
                # official tracked *index* to inject into the passive
                # exact-index pool. Quarantine the benchmark alias.
                reasons = [x for x in reasons if x not in {
                    "OFFICIAL_LIST_HAS_NO_TRACKED_INDEX",
                    "OFFICIAL_CODE_NAME_LINK_NOT_VERIFIED",
                    "INDEX_ECONOMIC_REGION_OR_ASSET_NOT_VERIFIED",
                    "INDEX_SECTOR_CLASSIFICATION_NOT_VERIFIED",
                    "LOF_LEGAL_TRACKING_MANDATE_NOT_VERIFIED",
                    "OFFICIAL_FITTED_CODE_MISSING",
                    "AUXILIARY_TRACKING_IDENTITY_ONLY"}]
                identity_review = [x for x in identity_review if x["symbol"] != symbol]
                reason = ("OFFICIALLY_VERIFIED_NON_PASSIVE_STRATEGY_EXCLUDED"
                          if d["tracking_mode"]=="ACTIVE_QDII_FOF"
                          else "OFFICIALLY_VERIFIED_NON_INDEX_REFERENCE_EXCLUDED")
                reasons.append(reason)
            # Missing settlement/premium/quote attributes are NOT invented.
            rec["classification_reason"].append(
                "Official fund mandate recorded with document date; not automatically historical-PIT qualified")
        known_exclusions = {'OFFICIALLY_VERIFIED_NON_PASSIVE_STRATEGY_EXCLUDED',
                            'OFFICIALLY_VERIFIED_NON_INDEX_REFERENCE_EXCLUDED'}
        unresolved_reasons = [x for x in reasons if x not in known_exclusions]
        rec['economic_classification_verified'] = not unresolved_reasons and bool(rec['exposure_id'])
        rec['classification_status'] = ('VERIFIED_CURRENT_INDEX' if not reasons else
            'VERIFIED_EXCLUDED_STRATEGY' if rec['economic_classification_verified'] else 'NEEDS_REVIEW')
        rec['current_index_pool_approved'] = not reasons
        rec['unresolved_reasons'] = unresolved_reasons
        rec['needs_review'] = bool(reasons)  # legacy pool-approval flag; see classification_status
        rec['classification_reason'] += reasons + [
            'Distinct indices retained as distinct fine exposures; cross-index equivalence unapproved',
            'Current observation is unavailable before known_from; first quote is not a listing certificate']
        records.append(rec)
        if reasons:
            reviews.append(dict(symbol=symbol, name=rec['name'], reasons=reasons,
                                auxiliary_index_name=aux_index, exact_index_key=rec['exact_index_key'],
                                classification_status=rec['classification_status'],
                                unresolved_reasons=unresolved_reasons,
                                confidence=rec['confidence'], source_url=rec['source_url'],
                                auxiliary_source_url=rec['auxiliary_source_url'], observed_on=snapshot_date))
    validate_intervals(records)
    return records, reviews, identity_review, coverage


def quality_audit(records, legacy_rows):
    verified = [r for r in records if r['exact_index_verified']]
    groups = defaultdict(list)
    exacts = defaultdict(list)
    for r in verified:
        if r['legacy_underlying_key']:
            groups[r['legacy_underlying_key']].append(r)
        exacts[r['exact_index_key']].append(r)
    merges = []
    for key, rr in sorted(groups.items()):
        if len({r['exact_index_key'] for r in rr}) > 1:
            proven = {r['exact_index_key'] for r in rr if r['confidence'] != 'MEDIUM_OFFICIAL_CODE_AUXILIARY_NAME'}
            merges.append(dict(legacy_underlying_key=key, exact_indices=len({r['exact_index_key'] for r in rr}),
                proven_official_index_groups=len(proven),
                funds=[dict(symbol=r['symbol'], name=r['name'], index_name=r['index_name'],
                            index_code=r['index_code'], exact_index_key=r['exact_index_key']) for r in rr]))
    splits = []
    for key, rr in sorted(exacts.items()):
        old = {r['legacy_underlying_key'] for r in rr if r['legacy_underlying_key']}
        if len(old) > 1:
            modes = {r['tracking_mode'] for r in rr}
            splits.append(dict(exact_index_key=key, legacy_keys=sorted(old),
                assessment='RETAIN_STRATEGY_DIFFERENCES' if len(modes)>1 else 'SAME_INDEX_SPLIT_REPAIR', funds=[
                dict(symbol=r['symbol'], name=r['name'], legacy_underlying_key=r['legacy_underlying_key']) for r in rr]))
    # Validate name/code bridges not yet safely unified, instead of claiming
    # false precision from a current profile.
    candidates = defaultdict(list)
    for r in verified:
        if r['index_name']:
            candidates[normalize_name(r['index_name'])].append(r)
    potential_splits = [dict(index_name=n, keys=sorted({r['exact_index_key'] for r in rr}),
                            symbols=[r['symbol'] for r in rr]) for n, rr in sorted(candidates.items())
                        if len({r['exact_index_key'] for r in rr}) > 1]
    conflicts = []
    for key, rr in sorted(exacts.items()):
        attrs = {(r['region_primary'], r['exposure_type']) for r in rr}
        if len(attrs) > 1:
            conflicts.append(dict(key=key, attrs=sorted(attrs, key=str)))
    if conflicts:
        raise ValueError(f"cross-region/asset exact identity conflict: {conflicts}")
    return dict(legacy_false_merges=merges, legacy_false_splits=splits,
                unresolved_code_name_bridges=potential_splits,
                exact_identity_asset_conflicts=conflicts)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--metadata', type=Path, required=True)
    ap.add_argument('--profiles', type=Path, required=True)
    ap.add_argument('--official', type=Path, required=True)
    ap.add_argument('--bars', type=Path, required=True)
    ap.add_argument('--snapshot-date', required=True)
    ap.add_argument('--output', type=Path, required=True)
    args = ap.parse_args()
    metadata = json.loads(args.metadata.read_text())
    profiles = {p.stem: json.loads(p.read_text()) for p in sorted(args.profiles.glob('*.json'))}
    bars = pd.read_parquet(args.bars)
    records, reviews, identities, coverage = build(metadata, profiles, args.official, bars, args.snapshot_date)
    out = args.output
    dump(out/'classifications.json', records)
    dump(out/'review_queue.json', reviews)
    dump(out/'identity_review.json', identities)
    dump(out/'quality_audit.json', quality_audit(records, metadata))
    prelisting = [dict(symbol=r['symbol'],name=r['name'],first_bar=r['first_bar'],listing_date=r['listing_date'],
                       reason='Possible conversion/share-class/source history; first bar cannot establish current mandate')
                  for r in records if r['first_bar'] and r['listing_date'] and r['first_bar']<r['listing_date']]
    dump(out/'prelisting_history_review.json', prelisting)
    history_events = [dict(symbol=r['symbol'],name=r['name'],
        reported_contract_effective_date=r['reported_contract_effective_date'],
        first_bar=r['first_bar'], current_replication_method=r['replication_method'],
        source_url=r['mandate_document_url'], source_date=r['source_date'],
        status='HISTORICAL_ANNOUNCEMENT_REQUIRED',
        warning='Current report states a contract effective date; not proof of the earlier mandate or of its publication-time availability')
        for r in records if r.get('reported_contract_effective_date') and r.get('first_bar')
        and r['first_bar'] < r['reported_contract_effective_date']]
    dump(out/'strategy_history_review.json',history_events)
    index_events = json.loads(Path(__file__).with_name('index_history_events_v32.json').read_text())
    for event in index_events:
        verify_documents(event['evidence_documents'], args.snapshot_date)
    dump(out/'index_history_review.json',index_events)
    dump(out/'profiles.json', [profiles[k] for k in sorted(profiles)])
    dump(out/'calendar_observed.json', sorted(bars.date.astype(str).str[:10].unique()))
    for name, rr in [('classifications', records), ('review_queue', reviews)]:
        pd.DataFrame(rr).to_csv(out/f'{name}.csv', index=False)
    pd.DataFrame(records).to_parquet(out/'classifications.parquet', index=False)
    verified = [r for r in records if r['exact_index_verified']]
    complete = [r for r in verified if not r['needs_review']]
    current = {}
    for r in sorted(metadata, key=lambda r: (r['symbol'], r['valid_from'], r['id'])):
        if not r['valid_to']:
            current[r['symbol']] = r
    summary = dict(snapshot_date=args.snapshot_date, total_funds=len(records),
        archive_rows=len(bars), archive_symbols=len(coverage), archive_min_date=str(bars.date.min())[:10],
        archive_max_date=str(bars.date.max())[:10], archive_sha256=hashlib.sha256(args.bars.read_bytes()).hexdigest(),
        archive_duplicate_symbol_dates=int(bars.duplicated(['symbol','date']).sum()),
        prelisting_history_count=len(prelisting),
        reported_contract_history_review_count=len(history_events),
        archive_symbols_missing_legacy_metadata=len(set(coverage)-set(current)),
        official_current_listed=sum(r['current_exchange_listed_verified'] for r in records),
        officially_verified_index_identity=len(verified),
        officially_verified_index_identity_pct=round(100*len(verified)/len(records),2),
        official_full_name_count=sum(r['exact_index_verified'] and r['confidence'] != 'MEDIUM_OFFICIAL_CODE_AUXILIARY_NAME' for r in records),
        index_code_count=sum(bool(r['index_code']) for r in records),
        official_identity_candidate_groups=len({r['exact_index_key'] for r in verified}),
        provisional_fine_exposure_groups=len({r['exposure_id'] for r in verified if r['exposure_id']}),
        exact_index_groups=len({r['exact_index_key'] for r in complete}),
        fine_exposure_groups=len({r['exposure_id'] for r in complete if r['exposure_id']}),
        sector_level1_count=len({r['sector_level1'] for r in verified if r['sector_level1']}),
        sector_level2_count=len({r['sector_level2'] for r in verified if r['sector_level2']}),
        fully_classified_current=len(complete), needs_review=len(reviews),
        economically_classified_count=sum(r['economic_classification_verified'] for r in records),
        unresolved_classification_count=sum(not r['economic_classification_verified'] for r in records),
        verified_excluded_strategy_count=sum(r['classification_status']=='VERIFIED_EXCLUDED_STRATEGY' for r in records),
        execution_verified_count=sum(r['execution_attributes_verified'] for r in records),
        legal_mandates_verified_count=sum(r.get('legal_mandate_verified',False) for r in records),
        legal_non_passive_mandates_count=sum(r.get('tracking_mode')=='ACTIVE_QDII_FOF' for r in records),
        no_verified_tracking_identity=sum(not r['exact_index_verified'] for r in records),
        historical_classifications_before_capture=0,
        review_reasons=dict(Counter(x for r in reviews for x in r['reasons'])),
        legacy_current_count=len(current), legacy_coverage={
            field:sum(bool(r.get(field)) for r in current.values()) for field in ['underlying_key','risk_bucket','style_sector']},
        legacy_review=sum(r['needs_review'] for r in current.values()),
        legacy_historical_safe_flags=sum(r['historical_safe'] for r in current.values()),
        dedup_comparison=dict(raw_archive_symbols=len(coverage),
            verified_archive_symbols=sum(r['symbol'] in coverage for r in verified),
            approved_archive_symbols=sum(r['symbol'] in coverage for r in complete),
            exact_index_groups=len({r['exact_index_key'] for r in complete if r['symbol'] in coverage}),
            fine_exposure_groups=len({r['exposure_id'] for r in complete if r['symbol'] in coverage and r['exposure_id']}),
            broad_sector_groups=len({(r['region_primary'],r['exposure_type'],r['sector_level1']) for r in complete
                                     if r['symbol'] in coverage and r['sector_level1']}),
            warning='Partial verified subsets; unknowns are exclusions, never deduplication savings'))
    dump(out/'summary.json', summary)
    # Full input digests plus deterministic output manifest; no wall-clock build
    # timestamp so repeated identical frozen inputs produce identical artifacts.
    files = [args.metadata, args.bars, Path(__file__).with_name('index_aliases.json'), Path(__file__).with_name('fund_contract_evidence_v31.json'), Path(__file__).with_name('index_history_events_v32.json')] + sorted(Path(__file__).parent.glob('*.py')) + sorted(args.profiles.glob('*.json')) + sorted(args.official.glob('*.json')) + sorted(Path(__file__).with_name('snapshot').joinpath('supplement_v32').glob('*'))
    output_names = ['classifications.json','classifications.csv','classifications.parquet','review_queue.json',
        'review_queue.csv','identity_review.json','quality_audit.json','profiles.json','calendar_observed.json',
        'prelisting_history_review.json','strategy_history_review.json','index_history_review.json','summary.json']
    dump(out/'manifest.json', dict(version='V3.2.0', inputs=[dict(name=p.name, sha256=hashlib.sha256(p.read_bytes()).hexdigest()) for p in files],
        outputs={name:hashlib.sha256((out/name).read_bytes()).hexdigest() for name in output_names}))
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
