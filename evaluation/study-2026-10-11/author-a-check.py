"""Manually authored fictional corpus; run to regenerate and validate author-a.json.

The scenario prose, queries, gold fields and evidence requirements below are manual.
Shared code only assigns IDs/dates, preserves schema, and adds a common archival
provenance paragraph to short records. It does not call a model or read other files.
"""
import json
from pathlib import Path
from collections import Counter

DEST = Path(__file__).with_name('author-a.json')
FAMILIES = []
PROVENANCE = (' This is an immutable fictional archive entry. Later summaries may quote it, '
              'but a summary date does not change its authority or extend its named scope. '
              'Readers must combine applicable decisions, exceptions and recorded receipts; '
              'silence in this entry is not proof that another requirement was completed.')

def family(fid, name, domain, aliases, stratum, sources, views, tasks, overrides=None):
    overrides = overrides or {}
    records = []
    for n, source in enumerate(sources, 1):
        title, scope, body = source[:3]
        options = source[3] if len(source) > 3 else {}
        rid = f'{fid}R{n:02d}'
        text = body + PROVENANCE
        records.append(dict(id=rid, kind='source', revision=1,
            authored_at=options.get('authored_at', f'2026-09-{[1,4,8,12,24,25,26,27][n-1]:02d}T09:00:00Z'),
            title=title, scope=scope, body=text,
            links=[f'{fid}R{x:02d}' for x in options.get('links', [])],
            supersedes=[f'{fid}R{x:02d}' for x in options.get('supersedes', [])],
            incorporates=[]))
    for n, view in enumerate(views, 9):
        title, scope, body, ledger = view[:4]
        options = view[4] if len(view) > 4 else {}
        records.append(dict(id=f'{fid}R{n:02d}', kind='derived',
            revision=options.get('revision', 2),
            authored_at=f'2026-10-{n-1:02d}T15:00:00Z', title=title, scope=scope,
            body=body + PROVENANCE,
            links=[f'{fid}R{x:02d}' for x in options.get('links', ledger)],
            supersedes=[], incorporates=[{'id': f'{fid}R{x:02d}', 'revision': 1}
            for x in ledger]))
        for entry in records[-1]['incorporates']:
            entry['revision'] = options.get('ledger_revisions', {}).get(entry['id'], 1)
    converted = []
    for n, (query, status, answer, evidence) in enumerate(tasks, 1):
        converted.append(dict(id=f'{fid}Q{n}', query=query,
            answer_keys=list(answer), expected={'status':status,'answer':answer},
            critical_keys=list(answer), evidence_sets=[[f'{fid}R{x:02d}' for x in group]
            for group in evidence]))
    FAMILIES.append(dict(id=fid, name=name, domain=domain, aliases=aliases,
        stratum=stratum, records=records, tasks=converted))

family('A01', 'Hushglass Mineral Room', 'museum light conservation',
 ['Hushglass gallery','the quiet mineral room'], 'late_correction', [
 ('Exhibition stewardship charter','exhibition',
  'The conservation desk alone approves light exposure for the Hushglass Mineral Room. Exhibition operations may choose hours within approved limits, but sponsor cards have no conservation authority. This charter covers the permanent west-room specimens. A separate travelling mineral kit uses synthetic replicas and its own lighting instructions.'),
 ('Initial amber lamp instruction','exhibition',
  'For the opening arrangement, the conservation desk approved amber lamps at 80 lux for six hours per day. That instruction assumed the cases contained only quartz and feldspar. Staff were told to keep a cumulative daily exposure log; resetting a timer during lunch does not begin a new allowance.'),
 ('Installed case inventory','exhibition',
  'The signed installation inventory identifies case W3 as containing real fluorite as well as quartz. Every other west-room case contains quartz or feldspar. W3 has an independently dimmable lamp and an opaque cover. Its inventory is final for this exhibition, and the travelling kit inventory cannot substitute for it.'),
 ('Cover inspection receipt','exhibition',
  'The case technician tested the opaque W3 cover and recorded a pass: it blocks the lamp completely and does not touch the fluorite. The receipt authorizes use of that cover in the west room. It does not authorize brighter lamps, and the unused cloth from the travelling kit was not tested.'),
 ('Fluorite exposure correction','exhibition',
  'The conservation desk corrects the earlier all-case instruction after reviewing the installed inventory. Real fluorite must receive no more than 30 lux for two hours daily; then its passed opaque cover must close. Quartz and feldspar keep the 80-lux, six-hour allowance. This correction applies immediately to W3 and replaces the initial instruction only for fluorite.', {'supersedes':[2], 'links':[3,4]}),
 ('Replica demonstration clearance','travelling-kit',
  'The travelling Hushglass kit contains painted resin replicas, including a replica labelled fluorite. Its school demonstration may use 120 lux for eight hours and needs no opaque cover. The education desk issued this clearance only for that kit. The word fluorite on a replica label is not a record that W3 became synthetic.'),
 ('Sponsor opening-night card','exhibition',
  'The sponsor printed an opening-night card promising eight hours of bright mineral viewing. Its copy was prepared before the fluorite inventory arrived. The card describes audience expectations and contains no conservation signature. The event manager retained it as a historical marketing record, with the west-room lighting left to the conservation desk.'),
 ('Storage cupboard lamp trial','storage',
  'A technician tried a 30-lux amber lamp in a storage cupboard for two hours and liked the color. No displayed minerals were present and no exposure approval resulted. The trial reused Hushglass equipment names to match purchasing records. It is evidence of a lamp test, not a west-room installation inventory or a conservation decision.')], [
 ('West room quick card, rewritten','exhibition',
  'This quick card was typeset again in October from the opening packet. It says every case may run at 80 lux for six hours and mentions the daily log. It incorporates the initial instruction and installation inventory, but its author did not ingest the fluorite correction. Its polished rewrite date describes layout work, not a conservation reconsideration.', [1,2,3]),
 ('Travelling kit handout','travelling-kit',
  'The school handout describes painted resin specimens, a 120-lux lamp setting and an eight-hour demonstration. It cites the education clearance and reminds staff that the permanent west room has real minerals. This summary is useful for the travelling kit, but it deliberately leaves permanent exhibition exposure values outside its scope.', [6,1])], [
 ('For the permanent Hushglass gallery, give today’s lamp limit, exposure hours and after-limit action for case W3, and the authority that governs it.', 'ready', {'lux':30,'hours_per_day':2,'after_limit':'close opaque cover','authority':'conservation desk'}, [[1,3,4,5]]),
 ('Prepare the school travelling Hushglass kit and explain whether its fluorite-labelled object needs W3’s cover rule. Give material, lux, daily hours and cover requirement.', 'ready', {'material':'painted resin','lux':120,'hours_per_day':8,'cover_required':False}, [[1,3,6]])])

family('A02', 'Larkwheel Orchard', 'seed distribution and viability',
 ['Larkwheel seed bank','the spiral orchard'], 'late_correction', [
 ('Distribution authority and lots','public-release',
  'The Larkwheel seed steward signs public releases. Volunteers may pack a signed lot but may not substitute viability estimates. Lot P7 is the autumn pear batch; lot P7-S is a teaching batch of wooden seed models. Similar lot labels are intentional so handling drills can use realistic paperwork without distributing biological material.'),
 ('Provisional pear release','public-release',
  'The steward provisionally planned to offer twenty pear seeds per envelope with a germination claim of 85 percent. That plan depended on a second viability test of lot P7. It was a planning quantity, not a release receipt. The first test used freshly collected seeds and therefore could not measure the effect of later storage.'),
 ('Cold-room interruption log','public-release',
  'The storekeeper recorded that P7 warmed overnight when its cold-room fan stopped. P7-S wooden models were on a separate shelf and could not lose viability. The interruption ended before dawn, but the log gives no permission to distribute P7. The steward requested a test of seeds taken from the warmed batch.'),
 ('Retest sampling receipt','public-release',
  'The independent tester received a sealed sample drawn after the warming event and measured P7 viability at 62 percent. The sample seal and lot label passed inspection. The result covers the biological pear batch, not the wooden models, and replaces the first test as the release label’s measured percentage.'),
 ('Final autumn release correction','public-release',
  'Using the valid retest, the steward approves P7 distribution at twelve seeds per envelope with a 62-percent germination label. No envelope may carry the provisional 85-percent claim. Release is authorized only after the packer signs a count-and-label receipt; the test receipt alone is insufficient. The provisional twenty-seed plan is superseded.', {'links':[4], 'supersedes':[2]}),
 ('Packing receipt for autumn batch','public-release',
  'The packer signed the P7 count-and-label receipt: twelve biological pear seeds in each envelope, germination label 62 percent, with no old labels remaining. This is the receipt requested by the final release decision. It was checked against the sealed retest lot and applies to the full public batch prepared that afternoon.'),
 ('Teaching drill release','teaching',
  'P7-S wooden seed models may be handed out twenty per envelope with a clearly printed “model, not viable seed” label. A teaching coordinator signed this drill release. No viability percentage should appear. The drill borrows the orchard’s packing vocabulary, but its permission cannot release actual P7 pear seeds.'),
 ('Pear jam fundraising note','fundraising',
  'The orchard’s jam team estimates that twelve pears fill a demonstration basket and that eighty-five jars may sell at the fair. This note mentions autumn distribution and the Larkwheel stand but concerns food samples. It has no seed lot, no germination test and no steward signature; its numbers should not be copied onto seed envelopes.')], [
 ('Autumn distribution desk summary','public-release',
  'The desk summary was rewritten after the fair schedule changed, but retained the provisional twenty-seed envelope and 85-percent germination statement. Its ledger includes the distribution charter and provisional release only. It explicitly describes a plan awaiting a second viability test, despite using an upbeat “ready for fair” heading.', [1,2,3]),
 ('Teaching packing summary','teaching',
  'The teaching summary says wooden models are supplied twenty per envelope and must be labelled as models. It avoids any germination claim and points to the drill coordinator’s release. Biological P7 envelopes need their own final decision and packing receipt, which this teaching packet neither summarizes nor incorporates.', [1,7])], [
 ('Can the Larkwheel seed bank release biological pear lot P7 now? Give envelope count, germination label and the two completed receipt types supporting release.', 'ready', {'seeds_per_envelope':12,'germination_percent':62,'receipts':['valid retest','count-and-label']}, [[1,4,5,6]]),
 ('Set up the spiral orchard’s P7-S teaching handout: give objects per envelope, object material and exact label text, and whether a germination percentage is allowed.', 'ready', {'objects_per_envelope':20,'material':'wood','label':'model, not viable seed','germination_percent_allowed':False}, [[1,3,7]])])

family('A03', 'Morrowfin Ferry', 'tidal navigation and passenger scheduling',
 ['Morrowfin night boat','the estuary shuttle'], 'late_correction', [
 ('Captain and harbor responsibilities','night-service',
  'The harbor pilot sets the safe channel for Morrowfin night service. The ferry captain sets departure time within that clearance and confirms the passenger ramp inspection. Tourism posters cannot choose a channel. The daytime freight skiff shares the estuary shuttle nickname but does not carry passengers and has a separate channel clearance.'),
 ('Early north-channel plan','night-service',
  'The pilot initially cleared the north channel for a 20:30 passenger departure, provided the tide reached 1.4 metres at the gauge. The captain pencilled that time onto a draft roster. This was the early plan before a shoal survey; the roster itself could not establish the channel’s safe depth.'),
 ('Shoal survey and gauge rule','night-service',
  'The signed shoal survey found the north channel’s narrow bend unsafe for the passenger ferry at every tide expected this month. The south channel remains usable once the tide gauge reaches 1.8 metres. Gauge observations must be made within fifteen minutes of departure; an afternoon estimate cannot serve as the departure reading.'),
 ('Ramp inspection certificate','night-service',
  'The landing mechanic certified the passenger ramp for tonight’s Morrowfin sailing. Its latch, lighting and non-slip surface passed. This certificate covers either channel because both return to the same landing. It does not clear water depth or certify the freight skiff’s loading plank, which was not part of the inspection.'),
 ('Revised pilot clearance','night-service',
  'The pilot replaces the north-channel plan with south-channel passage at a minimum gauge reading of 1.8 metres, taken within fifteen minutes of departure. The captain then moves the passenger departure to 21:10. The revised clearance preserves the separate ramp certificate requirement. No tourism commitment can restore the north channel.', {'supersedes':[2], 'links':[3,4]}),
 ('Departure gauge observation','night-service',
  'At 21:00 the gauge observer measured 1.9 metres and signed the reading for the 21:10 passenger departure. That observation is within the required fifteen-minute interval. The observer did not inspect the ramp or choose the channel. The signed value is a measurement receipt, not a promise that future sailings will have the same tide.'),
 ('Freight skiff clearance','day-freight',
  'The lightweight daytime freight skiff may use the north channel above 1.2 metres because it has a shallower draft and passes outside passenger hours. The pilot signed this separate clearance. It does not contradict the passenger survey: the vessels have different draft limits, loads and turns at the narrow bend.'),
 ('Tourism moonrise flyer','night-service',
  'A moonrise flyer advertises a 20:30 north-channel ride for Morrowfin visitors. It was printed from the early roster and remained on a noticeboard after the pilot’s revision. Its moonrise description is still useful, but it is neither a navigation clearance nor a current departure instruction; refunds are handled independently of sailing safety.')], [
 ('Moonrise operator card','night-service',
  'The operator card was redrawn in October to use a larger moon icon. It repeats the 20:30 north-channel plan and the 1.4-metre tide threshold. Its incorporation ledger stops before the shoal survey and revised pilot clearance. The redraw therefore adds readability while retaining an obsolete passenger route.', [1,2]),
 ('Freight skiff route summary','day-freight',
  'This summary preserves the freight skiff’s north-channel threshold of 1.2 metres and explains its shallow draft. It distinguishes the daytime freight vessel from Morrowfin passenger service. It includes no passenger gauge receipt, since a freight clearance cannot establish that a particular night departure has met its measured tide prerequisite.', [1,7])], [
 ('For tonight’s Morrowfin night boat, may the 21:10 passenger sailing proceed? Give channel, minimum tide, observed tide, reading time and departure time.', 'ready', {'channel':'south','minimum_tide_m':1.8,'observed_tide_m':1.9,'reading_time':'21:00','departure_time':'21:10'}, [[3,4,5,6]]),
 ('Plan a daytime freight run of the estuary shuttle at a 1.3-metre tide: give permitted channel, minimum tide and the vessel distinction that makes the old passenger north-channel ban inapplicable.', 'ready', {'channel':'north','minimum_tide_m':1.2,'vessel':'shallow-draft freight skiff'}, [[1,3,7]])])
family('A04', 'Velvet Reed Theatre', 'accessible audience entry',
 ['Velvet Reed playhouse','the reed stage'], 'scope_exception', [
 ('Audience access authority','performances',
  'The access coordinator controls audience entry routes. The stage manager controls rehearsal movement only. Velvet Reed has a main stair entrance and a level garden entrance; a route being convenient for performers is not sufficient permission for audience use.'),
 ('Ordinary ticket entry rule','performances',
  'Ordinary evening ticket holders enter by the main stairs thirty minutes before curtain. The garden entrance stays shut to reduce sound spill. This rule explicitly defers to signed access exceptions and does not prescribe a route for mobility-aid users.'),
 ('Mobility access exception','performances',
  'The access coordinator permits mobility-aid users and one accompanying person to use the garden entrance forty-five minutes before curtain. The exception requires a passed garden-path inspection for the same performance date. Other ticket holders keep the ordinary entry route.', {'links':[2]}),
 ('Garden path inspection','performances',
  'For tonight’s performance the garden path passed: the surface is level, the door opens fully and the call button works. The inspector signed the dated receipt. It covers audience entry, including the approved companion, but does not certify backstage passages.'),
 ('Quiet mat decision','performances',
  'The access coordinator requires the felt sound mat to remain across the garden door threshold during the access entry period. The mat has a bevel safe for wheels and walking frames. Sound spill is managed by that mat, not by withdrawing the access exception.'),
 ('Rehearsal performer circulation','rehearsal',
  'During rehearsal, all performers use the garden door ten minutes before their call. The stage manager issued that rule while the main stairs were being cleaned. It is rehearsal circulation, not an expansion of audience eligibility at public performances.'),
 ('Garden picnic invitation','garden-event',
  'A summer garden picnic invitation asked every visitor to enter through the garden at noon. That event had no curtain, tickets or felt mat. The invitation survives in the theatre publicity folder but cannot determine tonight’s performance entry route.'),
 ('Companion ticket clarification','performances',
  'The box office confirms that the one accompanying person uses the same entry window as the mobility-aid user and needs no separate access appointment. A paid ticket is still required for their seat. The box office cannot expand the exception to a larger accompanying group.')], [
 ('General audience entry card','performances',
  'This general card highlights main stairs and thirty-minute admission. It leaves access exceptions out because it was written for the ordinary ticket queue. Its ledger includes the ordinary rule only; its October date does not show that the coordinator revoked the garden exception.', [1,2]),
 ('Rehearsal arrival summary','rehearsal',
  'The rehearsal summary directs performers to the garden door ten minutes before call. It acknowledges that public audiences follow a different authority and access plan. It includes neither a performance-date path inspection nor a companion eligibility decision, and cannot replace those audience records.', [1,6])], [
 ('For tonight at the Velvet Reed playhouse, give the entrance and admission window for a walking-frame user and one companion, the required path receipt, and the threshold treatment.', 'ready', {'entrance':'garden','minutes_before_curtain':45,'companion_count':1,'path_inspection':'passed tonight','threshold_treatment':'bevelled felt mat'}, [[3,4,5,8]]),
 ('Set arrival instructions for the reed stage’s rehearsal performers and ordinary evening ticket queue. Give each route, timing and responsible authority.', 'ready', {'rehearsal_route':'garden','rehearsal_minutes_before_call':10,'rehearsal_authority':'stage manager','ordinary_route':'main stairs','ordinary_minutes_before_curtain':30,'ordinary_authority':'access coordinator'}, [[1,2,6]])])

family('A05', 'Mica Spring Cisterns', 'water sanitation and potable supply',
 ['Mica Spring tanks','the hill cisterns'], 'scope_exception', [
 ('Two water systems charter','all',
  'Mica Spring has a potable kitchen cistern K and a roof-water irrigation cistern R. The water steward signs sanitation rules for K; the gardener controls R. Hoses and labels are kept separate. Similar tank shapes do not make their water interchangeable.'),
 ('Routine potable flushing','potable',
  'After ordinary maintenance, K must be flushed with 200 litres, tested for clarity and reopened by the water steward. This routine addresses settled sediment only. The instruction explicitly excludes any event involving animal entry into the tank.'),
 ('Animal-entry sanitation exception','potable',
  'Animal entry into K requires draining, a 24-hour disinfectant contact period, a clean-water rinse and a negative microbial sample before reopening. The water steward issued this exception. A clear-looking sample or the routine 200-litre flush cannot satisfy the microbial prerequisite.'),
 ('Incident scope inspection','potable',
  'The inspection found a small bird inside kitchen cistern K after a loose lid was discovered. Irrigation cistern R remained covered. The bird was removed, but removal alone did not restore potable status. The inspector classified K under the animal-entry sanitation exception.'),
 ('Drain and disinfect receipt','potable',
  'The sanitation crew completed draining, a full 24-hour disinfectant contact period and a clean-water rinse for K. The steward accepted the sequence receipt. This receipt records process completion; it is not a microbial laboratory result or permission to reopen drinking-water taps.'),
 ('Negative sample and reopening','potable',
  'The laboratory reported K’s post-rinse microbial sample negative. The water steward then signed reopening of kitchen drinking-water taps. The lab sample identifies K, not R, and was taken after the accepted rinse. Reopening is restricted to the potable kitchen system.', {'links':[3,5]}),
 ('Garden cistern maintenance','irrigation',
  'R supplies plants only and is marked non-potable. The gardener’s ordinary leaf-screen cleaning uses a 20-litre rinse and no microbial reopening test. That procedure is valid for irrigation but cannot authorize kitchen drinking water, even if both cisterns appear clear.'),
 ('Clear-water photograph note','potable',
  'A visitor photographed K after bird removal and described the water as crystal clear. The photograph may document appearance, but no sample was collected and no sanitation time was measured. The visitor has no water-steward authority and did not observe the later rinse.')], [
 ('Hill cistern maintenance card','all',
  'This card places routine K flushing and R leaf-screen cleaning on the same page. It shows 200 litres for K and 20 litres for R. It omits the animal-entry exception, so its clean design and later rewrite cannot establish a response to the recorded bird incident.', [1,2,7]),
 ('Potable reopening abstract','potable',
  'The abstract identifies the bird incident as an exception and records accepted disinfecting followed by a negative post-rinse sample and steward reopening. It preserves process order and keeps irrigation water outside the potable permission. Its claims can be checked against the incorporated original receipts.', [3,4,5,6])], [
 ('May Mica Spring’s kitchen taps reopen after the bird incident? Give the governing treatment, contact hours, final sample result and reopening authority.', 'ready', {'treatment':['drain','disinfect','clean-water rinse'],'contact_hours':24,'sample':'negative','authority':'water steward'}, [[3,4,5,6]]),
 ('Prepare routine cleaning of the hill cisterns’ roof-water tank R. Give use category, rinse litres, responsible role and whether its procedure can reopen K’s drinking taps.', 'ready', {'use':'irrigation','rinse_litres':20,'authority':'gardener','can_reopen_K':False}, [[1,3,7]])])

family('A06', 'Nacre Lantern Archive', 'microfilm digitization and embargo',
 ['Nacre film archive','the lantern reels'], 'scope_exception', [
 ('Archive release charter','digitization',
  'The archive curator controls release of digitized Nacre Lantern reels. Technicians may create preservation copies without publishing them. A classroom set of fabricated reels is managed separately by education staff; it imitates catalogue language but contains no historical correspondence.'),
 ('Routine reel publication rule','digitization',
  'Routine unrestricted reels may be scanned at 600 dpi and published with their catalogue captions. The curator’s rule requires a caption check before release. It applies to reels carrying the unrestricted flag and does not override donor embargoes recorded on restricted reels.'),
 ('Reel L9 donor embargo','restricted-L9',
  'The accepted donor agreement for reel L9 withholds public text and images until 2027-01-01. A public catalogue stub containing title and year is allowed now. Preservation scans may be made at 600 dpi, but the files must remain in the closed preservation store.'),
 ('L9 catalogue classification','restricted-L9',
  'The accession receipt identifies L9 as the donor’s original correspondence reel and marks it restricted under the accepted agreement. Its title is Lantern Council Letters and its year is 1941. A duplicate number on the fabricated classroom reel has an E prefix and is a different object.'),
 ('Stub caption approval','restricted-L9',
  'The curator approved L9’s public stub with exactly its title and year. No transcription, thumbnail or letter excerpt was approved. The caption check is complete for the stub only; the approval expressly preserves the donor embargo on public scans.', {'links':[3,4]}),
 ('Preservation scan receipt','restricted-L9',
  'A technician completed L9’s 600-dpi preservation scan and placed it in the closed preservation store. The receipt reports verified image checksums and access restricted to conservation staff. Completion of scanning does not move the embargo date or authorize public downloads.'),
 ('Education reel E-L9 permission','classroom',
  'Education staff permit public download of fabricated E-L9 at 300 dpi with a teaching-fiction label. It contains invented letters, not donor material. The permission belongs to the classroom set and cannot be transferred by dropping the E prefix from a catalogue search.'),
 ('Unrestricted reel L8 caption check','unrestricted-L8',
  'The caption check for L8, Lantern Equipment Receipts, is complete. L8 carries the unrestricted flag and may be published at 600 dpi under the routine rule. Sharing a lantern title word and adjacent reel number gives it no power to remove L9’s donor restriction.')], [
 ('Digitization production queue','all',
  'The queue summary lists 600-dpi scanning and caption checks as the normal release workflow. It includes L8’s completed check but lacks L9’s donor agreement. L9 appearing beside L8 in the queue means it can be scanned, not that every resulting scan can be published.', [1,2,8]),
 ('Restricted reel preservation summary','restricted-L9',
  'The preservation summary records L9’s restricted classification, completed 600-dpi scan and closed storage. It keeps the donor’s 2027-01-01 public embargo separate from technical completion. It omits the stub caption decision, so it should not be treated as a complete public catalogue instruction.', [3,4,6])], [
 ('Publish what is allowed now for Nacre film archive reel L9. Give public fields, their values, scan visibility and the date public text/images become eligible.', 'ready', {'public_fields':['title','year'],'title':'Lantern Council Letters','year':1941,'scan_visibility':'closed preservation store','public_text_images_date':'2027-01-01'}, [[3,4,5,6]]),
 ('Prepare downloads for the lantern reels L8 and fabricated E-L9. Give each resolution and any teaching label; explain whether either permission authorizes L9 publication.', 'ready', {'L8_dpi':600,'E_L9_dpi':300,'E_L9_label':'teaching fiction','authorizes_L9':False}, [[2,3,7,8]])])
family('A07', 'Vélune Kiln Collection', 'art provenance and exhibition labels',
 ['Vélune bowls','the moon kiln collection'], 'unresolved_conflict', [
 ('Attribution publication charter','original-bowls',
  'Original Vélune bowls may carry a named maker only after both accepted provenance chains agree or the provenance panel signs an adjudication. The curator cannot break a tie by choosing the newer document. Replica labels instead follow the commissioned replica maker’s receipt.'),
 ('Bowl V4 identity inspection','original-bowls',
  'The inspected V4 is the original blue bowl with a crescent footmark, not the contemporary shop replica V4-R. Its accession seal is intact. The identity inspection links V4 to both accepted estate chains but does not decide who shaped the clay.'),
 ('Western estate attribution','original-bowls',
  'The accepted western estate chain attributes the crescent-foot blue bowl to ceramicist Mera Vale. Its inventory describes the inspected V4 dimensions and seal. The chain remains admissible and has not been withdrawn, although it conflicts with the eastern estate’s maker claim.'),
 ('Eastern estate attribution','original-bowls',
  'The accepted eastern estate chain attributes the same V4 bowl to ceramicist Tovin Ash. The provenance panel authenticated the inventory paper without accepting its maker claim over the western chain. Paper authentication does not adjudicate competing attributions, and the entry deliberately preserves that distinction.'),
 ('Panel docket status','original-bowls',
  'The provenance panel records that V4’s maker dispute is still open. No adjudication has been signed and neither estate chain has been withdrawn. Public exhibition may proceed with the neutral label “maker unresolved”; a named maker must remain unset until the charter’s agreement or adjudication condition is met.'),
 ('Replica commission receipt','replica-shop',
  'The commissioned V4-R replica was made by potter Nalo Reed and delivered with a signed receipt. Its underside bears the word replica rather than the original crescent footmark. The shop may credit Nalo Reed when that replica distinction is printed beside the name.'),
 ('Kiln fuel invoice','kiln-maintenance',
  'A fuel invoice names Tovin Ash as the person who paid for one firing week. It does not list bowl V4 or identify a clay shaper. Payment and making are separate roles. The invoice is retained for kiln history, not accepted as a third provenance chain.'),
 ('Neutral exhibition label approval','original-bowls',
  'The curator approved the neutral V4 display label with “maker unresolved” and “original bowl.” This label is consistent with the open panel docket. Approval permits display without named attribution; it neither appoints the curator as adjudicator nor settles either estate’s claim.')], [
 ('Collection guide attribution table','original-bowls',
  'This guide table credits Tovin Ash after copying the eastern estate inventory into a column labelled maker. It also lists the western chain in its ledger but does not explain their disagreement. Its later rewrite date gives no panel adjudication, so the table’s apparent certainty exceeds the incorporated evidence.', [2,3,4]),
 ('Replica shop card','replica-shop',
  'The shop card credits Nalo Reed for V4-R and prints the required replica distinction. It cites the commission receipt and charter’s separate rule for replicas. The original bowl’s open attribution remains outside the shop card’s authority, even though both objects share a blue crescent design.', [1,2,6])], [
 ('Choose the public named-maker field for the original Vélune V4 bowl. Report the maker, permissible interim label and unresolved issue under the publication rule.', 'hold', {'maker':None,'interim_label':'maker unresolved','unresolved':['maker attribution']}, [[1,2,3,4,5]]),
 ('Prepare sale credit for the moon kiln collection’s V4-R replica. Give maker, required object distinction and whether that credit settles original V4’s attribution.', 'ready', {'maker':'Nalo Reed','distinction':'replica','settles_original':False}, [[1,2,6]])])

family('A08', 'Sølvi Marsh Refuge', 'overlapping habitat permits',
 ['Sølvi boardwalk','the silver marsh path'], 'unresolved_conflict', [
 ('Dual permit requirement','public-boardwalk',
  'The Sølvi public boardwalk needs both the refuge council’s seasonal permission and the wetland trust’s nesting clearance. Either authority may withhold its own permission. Neither permit has precedence over the other, and a tourism office cannot reconcile different boundary descriptions.'),
 ('Council opening permit','public-boardwalk',
  'The refuge council permits public boardwalk use from 10:00 to 16:00 in September, classifying the outer bend as outside the nesting strip. Its permit covers ordinary visitors but expressly remains subject to a valid trust nesting clearance. It does not authorize research boats.'),
 ('Trust closure notice','public-boardwalk',
  'The wetland trust withholds nesting clearance for the outer boardwalk bend until its boundary survey is reconciled. Its current map includes that bend within the nesting strip. This signed closure notice remains active and is not a draft, even though the council classifies the same bend differently.'),
 ('Boundary reconciliation status','public-boardwalk',
  'The joint boundary meeting ended without an agreed map or revised permit. Both parties confirmed that their existing notices remain in force. There is no majority-vote shortcut and no permission to infer a common boundary from the tourism map. Another joint survey is scheduled but has not occurred.'),
 ('Research boat clearance','research-boat',
  'The trust and council jointly approve a silent research boat on the south water lane between 06:00 and 08:00. The clearance covers tagged survey staff only and bypasses the disputed boardwalk bend. It is a separate activity with an agreed route, not a partial public-boardwalk opening.'),
 ('Staff tag receipt','research-boat',
  'The survey coordinator issued current staff tags to the entire research crew and recorded each tag as checked. The receipt meets the joint research clearance’s eligibility condition. A public visitor ticket is not a survey tag and cannot be used to board that research boat.'),
 ('Tourism path illustration','visitor-publicity',
  'The tourism office drew a silver marsh path running around the outer bend and labelled it open in daylight. The artist used the council’s public hours and omitted the trust’s nesting layer. This illustration has no wetland-trust signature and is not a third permit authority.'),
 ('Equipment dock maintenance','maintenance',
  'Maintenance workers may reach the equipment dock from the inland service road at any hour after checking the gate log. That route touches neither the public boardwalk bend nor the research water lane. Its broad hours concern repair access and cannot supply a missing visitor permit.')], [
 ('Visitor boardwalk overview','public-boardwalk',
  'The overview says the silver marsh path opens from 10:00 to 16:00 and reproduces the council map. It omits the trust’s active closure and dual-permit charter from its ledger. This makes it a one-authority visitor overview, despite an October redesign after the unsuccessful boundary meeting.', [2,7]),
 ('Research launch brief','research-boat',
  'The launch brief records a silent south-lane boat from 06:00 to 08:00 for tagged staff. It cites the joint research clearance and completed tag receipt. The brief preserves activity boundaries and does not describe a public opening of the disputed outer boardwalk bend.', [1,5,6])], [
 ('Can ordinary visitors use the Sølvi boardwalk’s outer bend now? Give an authorized public opening window if one exists, the authorities needed and the unresolved boundary issue.', 'hold', {'opening_window':None,'required_authorities':['refuge council','wetland trust'],'unresolved':['outer-bend nesting boundary']}, [[1,2,3,4]]),
 ('Prepare the silver marsh path team’s authorized research launch. Give route, hours, vessel condition and eligibility receipt; keep the public-boardwalk dispute in its own scope.', 'ready', {'route':'south water lane','hours':'06:00-08:00','vessel_condition':'silent boat','eligibility':'checked current staff tags'}, [[1,5,6]])])

family('A09', 'Ōrra Lunar Relay', 'clock reconciliation and timed transmission',
 ['Ōrra beacon','the far-side relay'], 'unresolved_conflict', [
 ('Clock consistency transmission rule','science-link',
  'Ōrra science transmission requires two independent clock solutions to agree within 2 milliseconds. If they differ more, the synchronization engineer must issue a reconciled phase receipt before transmission. Neither a newer calibration timestamp nor a preferred vendor may automatically select the science phase.'),
 ('Clock C solution','science-link',
  'Clock C’s signed solution places the next science phase at 04:12:00.006. Its calibration passed internal checks and its uncertainty is below one millisecond. This qualifies the solution for comparison; it does not establish agreement with the independent clock or authorize transmission by itself.'),
 ('Clock D solution','science-link',
  'Clock D’s signed solution places the same science phase at 04:12:00.011. Its own calibration also passed and its uncertainty is below one millisecond. It references the same packet epoch as clock C, so the five-millisecond discrepancy cannot be dismissed as different scheduled packets.'),
 ('Synchronization docket','science-link',
  'The synchronization engineer records the five-millisecond disagreement as unresolved. No reconciled science phase receipt exists. A test operator may exercise the antenna but must not transmit the science packet at either disputed phase. The next calibration review has been requested rather than completed.'),
 ('Packet epoch mapping','science-link',
  'The packet coordinator maps science packet S2 to the phase used by both C and D. Packet S1 has already been retired. The mapping confirms this is one shared target epoch and rules out treating the two clock solutions as permissions for different science packets.'),
 ('Engineering beacon exemption','engineering-test',
  'The unmodulated engineering beacon needs no science-phase agreement. The test engineer permits a continuous low-power beacon at 2 watts for ten minutes, provided the antenna isolator passes. This exemption cannot carry science packet bits and does not reconcile clock C or D.'),
 ('Antenna isolator receipt','engineering-test',
  'The antenna isolator passed the engineering beacon leakage test and the test engineer accepted the signed receipt. The acceptance covers a continuous 2-watt test for ten minutes. It reports no clock measurement and cannot act as the missing reconciled science phase receipt.'),
 ('Vendor clock advertisement','procurement',
  'A vendor advertisement calls clock D the most accurate far-side relay clock and highlights a newer enclosure. Procurement retained it beside the signed calibration files. Marketing praise and enclosure age are neither synchronization evidence nor an engineer’s authorization to choose D’s phase.')], [
 ('Science timing dashboard export','science-link',
  'The export displays clock D’s 04:12:00.011 phase as the next launch time. Its ledger includes both clock solutions but lacks the consistency rule and unresolved docket. The display chooses the later solution without documenting agreement, so its singular time field is an unsupported selection.', [2,3,5]),
 ('Engineering beacon checklist','engineering-test',
  'The checklist describes a continuous ten-minute 2-watt beacon and records the passed antenna isolator receipt. It forbids embedding science packet bits. Its incorporated exemption concerns hardware exercise only; it does not create a valid science-phase choice from the disagreeing clock solutions.', [1,6,7])], [
 ('Set the Ōrra science packet S2 launch phase now. Report the chosen phase, observed clock difference, allowed agreement threshold and unresolved requirement.', 'hold', {'phase':None,'difference_ms':5,'agreement_threshold_ms':2,'unresolved':['reconciled science phase receipt']}, [[1,2,3,4,5]]),
 ('Run the far-side relay’s engineering beacon after its isolator test. Give power, duration, modulation and whether science bits are permitted.', 'ready', {'power_watts':2,'duration_minutes':10,'modulation':'unmodulated continuous','science_bits_allowed':False}, [[1,6,7]])])
family('A10', 'Frostvine Seed Vault', 'cold-chain custody transfer',
 ['Frostvine cryobank','the blue seed vault'], 'missing_prerequisite', [
 ('External transfer gate','external-shipment',
  'Frostvine’s vault custodian may release living seed boxes externally only after a destination capacity acceptance, sealed-container inspection and uninterrupted cold-chain recorder receipt are all present. An internal shelf move is not an external release and follows a separate two-person custody rule.'),
 ('Shipment FV6 destination acceptance','external-shipment',
  'The destination vault accepted shipment FV6 and reserved freezer space at minus 20 Celsius. Its signed acceptance names six living-seed boxes. This proves available receiving capacity, not the temperature history during packing or transit preparation; those remain independent release conditions.'),
 ('FV6 seal inspection','external-shipment',
  'The container inspector passed FV6’s tamper seal and insulation closure. The six living-seed boxes match the destination acceptance. No temperature recorder file was opened during this inspection. A passed seal must not be represented as proof of an uninterrupted cold chain.'),
 ('Recorder upload status','external-shipment',
  'The FV6 temperature recorder’s upload failed before its file was saved. The device screen currently shows minus 20 Celsius, but the custodian records that no uninterrupted-history receipt exists. The screen cannot establish the packing interval. An original recorder export and review must precede any external release.'),
 ('Custodian release docket','external-shipment',
  'FV6 remains in the origin freezer with no external release signature. Destination capacity and container seals are complete; recorder history is the outstanding gate. The custodian ordered staff to retry the original export and review it rather than manufacture a temperature history from spot readings.'),
 ('Internal shelf-move procedure','internal-storage',
  'An internal move between Frostvine freezer shelves requires two staff to witness box IDs and complete a shelf-location receipt. It does not require destination acceptance or an external cold-chain file because the boxes never leave the monitored freezer. Both staff must remain present throughout the move.'),
 ('Internal move receipt','internal-storage',
  'Two staff jointly moved box FV2 from shelf B to shelf D within the monitored freezer and signed matching ID and location entries. The receipt is complete for FV2’s internal move. It contains no FV6 temperature history and cannot satisfy FV6’s external transfer gate.'),
 ('Dry demonstration parcel','training',
  'A dry training parcel marked FV6-D contains plastic seed replicas and a simulated recorder display. Trainers may carry it outside without cold-chain evidence if its demonstration label remains visible. The suffix D is part of its identity and never denotes the living shipment FV6.')], [
 ('FV6 dispatch readiness board','external-shipment',
  'The board marks destination capacity and seals green, then labels FV6 ready. It was rewritten from those two completed receipts and lacks the external transfer gate and recorder status. Its readiness label collapses three independent prerequisites into two, so the visual state is not a custodian release.', [2,3]),
 ('Internal shelf log summary','internal-storage',
  'The shelf summary places FV2 on shelf D and records two matching witness signatures. It cites the internal movement rule and receipt. It distinguishes that completed custody move from shipping FV6, whose cold-chain recorder evidence is not part of this internal shelf log.', [1,6,7])], [
 ('Release living shipment FV6 from the Frostvine cryobank if all gates are met. Give release authorization, receiving temperature and the unresolved prerequisite.', 'hold', {'release_authorization':None,'receiving_temperature_c':-20,'unresolved':['uninterrupted cold-chain recorder receipt']}, [[1,2,3,4,5]]),
 ('Audit the blue seed vault’s completed FV2 shelf move. Give current shelf, witness count and the procedure type; say whether that receipt can replace FV6 recorder history.', 'ready', {'current_shelf':'D','witness_count':2,'procedure':'internal shelf move','replaces_FV6_history':False}, [[1,6,7]])])

family('A11', 'Copper Finch Bindery', 'adhesive cure and handling windows',
 ['Copper Finch books','the finch binding bench'], 'missing_prerequisite', [
 ('Load-bearing cure rule','cloth-binding',
  'Copper Finch cloth bindings may be clamped shut for two hours but cannot undergo page-pull testing or customer shipment until adhesive cures for eighteen uninterrupted hours above 18 Celsius. The bench supervisor signs the elapsed-condition check. The two-hour clamp stage is not the full cure.'),
 ('Book B12 adhesive start','cloth-binding',
  'The bench log records adhesive application to cloth book B12 at 08:00 today. The room remained above 18 Celsius through the observation interval. B12 is a load-bearing stitched-and-glued customer binding, unlike removable dust jackets. The log provides a start time, not a completed eighteen-hour cure.'),
 ('B12 clamp removal receipt','cloth-binding',
  'At 10:00 the supervisor removed B12’s clamps after two hours and passed its alignment check. This permits careful placement on the cure rack. It explicitly does not permit pulling pages or shipping to the customer because the load-bearing adhesive has not yet completed its cure interval.'),
 ('Midday cure observation','cloth-binding',
  'At 14:00 today B12 had cured six uninterrupted hours above 18 Celsius. The supervisor recorded no completed cure check and left the customer shipping slot blank. If temperature stays above threshold, the earliest eighteen-hour completion is 02:00 tomorrow; this forecast is not a future receipt.'),
 ('Shipment gate confirmation','cloth-binding',
  'The dispatch lead confirms that B12 needs the supervisor’s completed elapsed-condition check before page-pull testing, then a passed page-pull receipt before shipment. Neither exists at 14:00. A customer’s request for same-day delivery changes urgency but cannot shorten the adhesive’s required cure.'),
 ('Dust jacket packaging rule','dust-jacket',
  'Unattached removable dust jackets use no load-bearing adhesive and may be packaged after an alignment check. They must remain separate from uncured customer books. The bench supervisor approves jacket alignment; dispatch may ship the separate jacket order without a page-pull test.'),
 ('Jacket J5 alignment receipt','dust-jacket',
  'The supervisor passed alignment for unattached jacket J5, and dispatch confirmed its separate order and packaging. The receipt identifies J5 alone, not a jacket already fitted onto B12. It therefore meets the jacket rule without implying that B12 is ready for handling.'),
 ('Metallic foil drying experiment','prototype',
  'A foil prototype dried on a hot plate in six hours and survived a decorative rub test. Its adhesive and substrate differ from B12’s cloth binding. The experiment was never approved as a customer-binding cure method, and decorative rub strength does not replace a page-pull test.')], [
 ('Bench progress quick view','cloth-binding',
  'The quick view shows B12’s clamps removed and alignment passed, then prints a ship icon. Its ledger incorporates the start and clamp receipt without the full cure rule or dispatch gate. The icon represents a mistaken inference from an intermediate handling stage, not a completed cure.', [2,3]),
 ('Separate jacket dispatch summary','dust-jacket',
  'The jacket summary lists J5 aligned and separately packaged, with no adhesive cure or page-pull test required. It incorporates the jacket rule and receipt. Its separate-order note matters: packing J5 onto uncured B12 would change the task and lose this limited dispatch permission.', [1,6,7])], [
 ('At 14:00 today, ship Copper Finch customer book B12 if ready. Give shipment authorization, earliest possible cure completion and outstanding gates.', 'hold', {'shipment_authorization':None,'earliest_cure_completion':'02:00 tomorrow','unresolved':['completed eighteen-hour cure check','passed page-pull receipt']}, [[1,2,3,4,5]]),
 ('Pack the finch binding bench’s separate J5 dust-jacket order now. Give handling permission, required completed check and whether a page-pull test is needed.', 'ready', {'handling_permission':'package and ship separately','completed_check':'alignment','page_pull_required':False}, [[1,6,7]])])

family('A12', 'Brindle Creek Gauges', 'sensor units and hydrologic conversion',
 ['Brindle gauge network','the creek level sensors'], 'missing_prerequisite', [
 ('Flood estimate validation rule','live-flood',
  'Brindle live flood estimates require a signed sensor-to-datum conversion for the installed probe and a valid zero-offset receipt. Raw voltage cannot be interpreted directly as water depth. The hydrologist signs conversion coefficients; the field technician may certify installation and zero readings only.'),
 ('Installed probe identity','live-flood',
  'Probe G8, serial Copper-6, replaced G8’s older serial Copper-4. The technician recorded the installed serial and a secure mounting inspection. Both probes emit voltage, but their depth conversion slopes differ. A station name match cannot transfer Copper-4 coefficients onto Copper-6.'),
 ('Copper-6 raw sample','live-flood',
  'The live sampler reports 1.6 volts from installed G8 serial Copper-6 at the current observation time. This is a valid raw sample. The sampler leaves the centimetre field empty because it does not contain a signed conversion for that serial; it does not estimate depth from the display scale.'),
 ('Zero-offset receipt','live-flood',
  'The field technician measured and signed Copper-6’s zero offset as 0.2 volts using the dry reference position. The hydrologist accepts this offset receipt as valid. The receipt supplies an intercept reference but no depth-per-volt slope, which must come from a signed conversion.'),
 ('Conversion registry status','live-flood',
  'The registry contains no signed depth-per-volt slope for Copper-6. Copper-4’s old slope remains archived and explicitly cannot be reused for the replacement. The hydrologist ordered a new span calibration. Until it is signed, G8 live depth and derived flood estimates must remain unset.'),
 ('Retired Copper-4 calibration','retired-probe',
  'Retired Copper-4 used a signed slope of 50 centimetres per volt and a 0.1-volt offset. That calibration was valid while Copper-4 was installed. Its retirement limits future use but does not invalidate historical calculations for correctly identified old samples.'),
 ('Historical Copper-4 sample','retired-probe',
  'A preserved pre-replacement sample identifies Copper-4 and reads 1.1 volts. The hydrologist allows historical depth to be recalculated using its archived slope and offset: subtract the offset, then multiply by the slope. The sample must not be relabelled as Copper-6 live data.'),
 ('Visitor level ruler','visitor-display',
  'A painted creek ruler beside G8 marks scenic water heights but its footing settled after a storm. It is intended for visitors and has no datum survey. Its apparent match to 1.6 on the sampler display cannot establish a signed probe conversion or a live flood estimate.')], [
 ('G8 flood dashboard summary','live-flood',
  'The summary reuses Copper-4’s archived coefficients and displays a live depth for G8. It incorporates the retired calibration and current raw voltage but omits the installed serial identity and conversion registry status. The shared station label hides a physically different probe, so the displayed depth lacks a valid conversion.', [3,6]),
 ('Historical sample worksheet','retired-probe',
  'The worksheet calculates 50 centimetres for the preserved Copper-4 sample by subtracting its 0.1-volt offset from 1.1 volts and multiplying by 50. It identifies the retired serial explicitly. The calculation is historical and provides no current Copper-6 depth or flood prediction.', [1,6,7])], [
 ('Produce the current Brindle G8 depth in centimetres for a live flood estimate. Give depth, installed serial, raw voltage, valid offset and unresolved conversion item.', 'hold', {'depth_cm':None,'installed_serial':'Copper-6','raw_voltage':1.6,'zero_offset_volts':0.2,'unresolved':['signed Copper-6 depth-per-volt slope']}, [[1,2,3,4,5]]),
 ('Recalculate the creek level sensors’ preserved Copper-4 sample. Give historical depth, serial and arithmetic inputs, and whether this result supplies G8’s live depth.', 'ready', {'depth_cm':50,'serial':'Copper-4','sample_volts':1.1,'offset_volts':0.1,'slope_cm_per_volt':50,'supplies_live_depth':False}, [[1,6,7]])])
family('A13', 'Élan Café', 'fictional beverage labelling and preparation',
 ['Élan tasting bar','E\u0301lan coffee room'], 'unicode_alias', [
 ('Name and venue identity register','tasting-bar',
  'Élan Café, Élan tasting bar and the decomposed spelling E\u0301lan coffee room identify one venue. Elan Canteen is a separate workplace kitchen. The café beverage lead controls recipes and labels; matching an unaccented word in a search does not transfer canteen permissions.'),
 ('Evening cup recipe','tasting-bar',
  'The café’s evening cup uses oat drink, cocoa and orange peel, with no nut ingredient. The recipe still requires a dedicated nut-free preparation station and a nut-free ingredient receipt before the label may say “prepared without nuts.” Ordinary shared-station preparation cannot earn that label.'),
 ('Dedicated station readiness','tasting-bar',
  'The evening-cup station was cleaned, its utensils isolated from the praline station and its nut-free preparation check passed. The beverage lead accepted this readiness receipt for tonight. This records station separation, not ingredient origin, so the ingredient receipt remains an independent requirement.'),
 ('Evening ingredients receipt','tasting-bar',
  'The supplier receipt identifies tonight’s oat drink, cocoa and orange peel as the café’s specified nut-free lots. The beverage lead checked the delivered lot seals and accepted them. The receipt excludes the praline topping, which was delivered separately for a different recipe.'),
 ('Label approval for tonight','tasting-bar',
  'With both preparation and ingredient receipts accepted, the beverage lead approves “prepared without nuts” on tonight’s evening cup. The lead does not approve “allergen free,” because oat is still declared. The approval is limited to this recipe and the checked station and lots.', {'links':[2,3,4]}),
 ('Canteen evening drink','canteen',
  'Elan Canteen’s evening drink uses almond drink and cocoa on a shared station. Its kitchen supervisor requires “contains almond” on the label. This is a different venue and recipe from Élan Café despite similar evening-drink wording; the canteen supervisor has no café label authority.'),
 ('Praline cup menu record','tasting-bar',
  'The café’s praline cup contains hazelnut topping and must say “contains hazelnut.” It is prepared at the praline station with its own utensils. Its supplier delivery arrived beside the evening-cup ingredients but is excluded from the evening recipe and nut-free station receipt.'),
 ('Cup substitution policy','tasting-bar',
  'A customer asking to substitute almond drink into an evening cup must receive a separately prepared cup labelled “contains almond.” The beverage lead forbids retaining the nut-free claim after that substitution. No new blanket label approval is created by a customer preference or an unchanged menu name.')], [
 ('Unaccented venue search card','all',
  'The search card merges Elan Canteen’s almond evening drink into a row headed Elan evening cups. It has only the canteen recipe in its incorporation ledger. The absence of accents in its heading is a display choice that erases a real venue distinction, not evidence that the registered names are equivalent.', [6]),
 ('Evening cup label brief','tasting-bar',
  'The label brief records the café evening recipe, dedicated station, checked ingredient lots and limited “prepared without nuts” approval. It declares oat and avoids an allergen-free claim. It uses the registered Élan name and does not import the separate canteen’s almond recipe.', [1,2,3,4,5])], [
 ('At E\u0301lan coffee room tonight, label the standard evening cup. Give base drink, permitted nut statement, remaining declared ingredient and approving role.', 'ready', {'base':'oat drink','nut_statement':'prepared without nuts','declared_ingredient':'oat','authority':'beverage lead'}, [[1,2,3,4,5]]),
 ('At the Élan tasting bar, a guest substitutes almond drink in an evening cup. Give the required nut label, whether the standard nut-free statement survives and whether the canteen recipe is the café’s authority.', 'ready', {'required_label':'contains almond','standard_nut_statement_allowed':False,'canteen_is_authority':False}, [[1,2,8]])])

family('A14', 'Bjørn Quay', 'cargo handling and lifting authority',
 ['Bjoern quay','the northern bear wharf'], 'unicode_alias', [
 ('Quay identity and lifting charter','cargo-quay',
  'Bjørn Quay, Bjoern quay and the northern bear wharf are one cargo facility. Bjorn Recreational Pier is elsewhere and has no freight crane. At the cargo quay, the lift engineer certifies crane loads while the harbor marshal assigns unloading zones.'),
 ('Crate C3 verified mass','cargo-quay',
  'The cargo scale receipt gives crate C3 a gross mass of 740 kilograms, including its lifting frame. An earlier consignee estimate excluded the frame. The receipt identifies the crate seal and is accepted by the lift engineer; packing-list net mass cannot replace verified gross load.'),
 ('Crane L capacity certificate','cargo-quay',
  'Crane L is certified for 800 kilograms only with the short boom and outrigger pads set. With the long boom it is limited to 600 kilograms. The lift engineer signed both conditions. Capacity must be compared against gross load, and boom choice cannot be assumed from equipment availability.'),
 ('Unloading zone instruction','cargo-quay',
  'The harbor marshal assigns C3 to paved zone West-2. Zone East-2 is closed for a fuel spill and no load may be placed there. West-2 has marked outrigger pad positions. This routing instruction chooses the unloading location but does not certify crane L’s operating capacity.'),
 ('Crane setup inspection','cargo-quay',
  'The lift engineer inspected crane L with its short boom and all outrigger pads set at West-2. The setup passed for today’s C3 lift. The inspection does not change the certificate’s load limits; it confirms that the required certified configuration is actually installed.', {'links':[3,4]}),
 ('Recreational pier cart notice','recreational-pier',
  'Bjorn Recreational Pier permits hand carts up to 90 kilograms on its boardwalk. Its recreation manager cannot authorize cargo cranes and the pier has no West-2 zone. The plain spelling Bjorn on tourist notices refers to this separate facility, not the registered Bjoern cargo alias.'),
 ('Long boom demonstration','training',
  'A training demonstration at the cargo quay lifted a 500-kilogram dummy with crane L’s long boom. It proved that particular training load fit the 600-kilogram long-boom limit. It did not approve a 740-kilogram C3 lift or reopen the spilled-fuel zone.'),
 ('Post-lift custody rule','cargo-quay',
  'After C3 is lowered at West-2, custody transfers only when the receiving clerk checks the crate seal against the scale receipt and signs the delivery entry. Crane setup permission is not a custody signature. If the seal differs, the clerk holds the crate for the cargo inspector.')], [
 ('Bear wharf unloading dashboard','cargo-quay',
  'The dashboard places C3 on East-2 and offers the long-boom training configuration as a suggested setup. Its ledger includes the mass receipt and training demonstration without the zone closure or setup inspection. The northern bear nickname makes it searchable but does not repair these omitted conditions.', [1,2,7]),
 ('Crane L verified lift brief','cargo-quay',
  'The lift brief records C3 at 740 kilograms, West-2 placement and a passed short-boom setup with pads set. It cites the separate capacity and routing authorities. Delivery custody remains a later seal-check and signature step, outside the lift brief’s completion claim.', [2,3,4,5])], [
 ('Unload C3 at Bjoern quay today. Give gross mass, crane configuration, certified capacity and placement zone, using the inspected configuration.', 'ready', {'gross_mass_kg':740,'boom':'short','outrigger_pads':'set','capacity_kg':800,'zone':'West-2'}, [[1,2,3,4,5]]),
 ('At the northern bear wharf, describe what must happen after the C3 lift before custody transfers and what a seal mismatch requires. Give responsible role and comparison record.', 'ready', {'responsible_role':'receiving clerk','comparison':'crate seal against scale receipt','required_action':'sign delivery entry','mismatch_action':'hold for cargo inspector'}, [[1,2,8]])])

family('A15', 'Kōra Loomhouse', 'textile quality and replacement guarantees',
 ['Kora weave hall','the long-vowel loom guild'], 'unicode_alias', [
 ('Guild names and warranty authority','woven-cloth',
  'Kōra Loomhouse, Kora weave hall and the long-vowel loom guild are registered aliases for the weaving cooperative. Kora Chemical Works is unrelated. The guild assessor signs cloth grades and warranty eligibility; shop staff may process replacements within those signed terms but cannot change grades.'),
 ('Grade S acceptance rule','woven-cloth',
  'Grade S shawls need at least 18 warp threads per centimetre and no more than 3 percent shrinkage after the prescribed wash test. Both measured conditions must pass for a Grade S label. A soft feel alone is not a grade measurement, and unwashed density does not establish shrinkage.'),
 ('Shawl H2 density receipt','woven-cloth',
  'The assessor measured H2 at 20 warp threads per centimetre before the wash test. The receipt identifies the sewn guild tag and records a valid density pass. It does not report shrinkage, so it cannot independently assign Grade S even though its count exceeds the minimum.'),
 ('H2 wash test receipt','woven-cloth',
  'H2 shrank 2 percent under the prescribed wash test and retained its sewn guild tag. The assessor signed that result and accepted both H2 measurement receipts. The wash result must be paired with the density receipt; neither test is a substitute for the other.'),
 ('Grade and guarantee decision','woven-cloth',
  'The assessor assigns H2 Grade S after both tests pass. Its guarantee permits one replacement within 90 days for an unravelled edge if the original sewn guild tag remains attached. Stains and deliberate cuts are excluded. A Grade S sale receipt proves purchase, not the cause of damage.', {'links':[2,3,4]}),
 ('H2 replacement inspection','warranty',
  'On day 40 after sale, the shop inspector found H2’s edge unravelled during ordinary use and its original sewn tag attached. No stain or deliberate cut was present. The assessor accepted this cause inspection, so the shop may issue the single replacement allowed by the signed guarantee.'),
 ('Chemical Works coated cloth flyer','industrial-cloth',
  'Kora Chemical Works advertises coated fabric with 8 percent allowable shrinkage and a one-year industrial warranty. Its flyer borrows the word Kora but refers to a different producer and product. Industrial coating terms cannot classify a handwoven loomhouse shawl or enlarge its guarantee.'),
 ('Grade T blanket rule','woven-blankets',
  'The guild’s Grade T blankets require 12 warp threads per centimetre and allow 5 percent shrinkage. Blanket guarantees cover manufacturing seams for 30 days. These are signed guild terms for a different product category, not an alternate way to grade or replace H2’s shawl.')], [
 ('Kora cloth comparison sheet','all',
  'The comparison sheet assigns the chemical works’ one-year warranty to a row labelled Kora shawls. Its ledger includes only the industrial flyer and Grade T blanket rule. The flattened alias and product categories discard the registered loomhouse identity and Grade S guarantee decision.', [7,8]),
 ('H2 quality card','woven-cloth',
  'The quality card records 20 warp threads per centimetre, 2 percent wash shrinkage and the assessor’s Grade S decision. It includes the guarantee’s 90-day, one-replacement limit. It does not incorporate H2’s later damage inspection, so eligibility for a particular claim needs that original too.', [1,2,3,4,5])], [
 ('At Kora weave hall, determine H2’s cloth grade from its measured tests. Give grade, measured density and shrinkage, both acceptance limits and authority.', 'ready', {'grade':'S','density_threads_per_cm':20,'shrinkage_percent':2,'minimum_density':18,'maximum_shrinkage_percent':3,'authority':'guild assessor'}, [[1,2,3,4,5]]),
 ('Process H2’s day-40 unravelled-edge claim at the long-vowel loom guild. Give replacement count, warranty limit and the attached identity item that makes this inspected claim eligible.', 'ready', {'replacement_count':1,'warranty_days':90,'required_identity':'original sewn guild tag','claim_eligible':True}, [[1,5,6]])])
family('A16', 'Tessera Reef Studio', 'underwater art installation permits',
 ['Tessera reef workshop','the tiled reef studio'], 'late_import', [
 ('Permit appendix filing rule','reef-installation',
  'Tessera reef permit appendices become binding when the reef registrar authenticates and files their signed originals. An appendix’s original date is preserved when imported. A newer studio summary cannot override a filed permit condition. Dry-land workshops are outside the reef registrar’s installation jurisdiction.'),
 ('Original reef installation permit','reef-installation',
  'The January permit allowed anchor drilling to a depth of 12 centimetres for ordinary bare-rock sites. It reserved protected sponge beds to a later habitat appendix. The permit signer did not promise that every bare-looking site was ordinary rock; the habitat survey determines site class.', {'authored_at':'2026-01-02T09:00:00Z'}),
 ('Site T2 habitat survey','reef-installation',
  'The accepted survey identifies installation site T2 as a protected sponge bed beneath a thin gravel layer. T3 is ordinary bare rock. Both sites belong to the same tiled art project. Visual gravel appearance does not let the studio treat T2 as T3 or escape a habitat appendix.'),
 ('T2 weighted-frame receipt','reef-installation',
  'The marine engineer passed T2’s removable weighted frame for stability without any drilling. Its ballast is enclosed and can be removed intact. This receipt certifies the nonpenetrating design, not permission to use anchors. The tested frame is available for the installation decision.'),
 ('Signed habitat appendix original','reef-installation',
  'The February habitat appendix forbids all drilling in protected sponge beds, requires removable weighted frames and permits ordinary bare-rock anchors to retain their 12-centimetre limit. It supersedes the January permit wherever a site is a protected bed. The signed original was kept offsite until the registrar’s later import.', {'authored_at':'2026-02-04T09:00:00Z','supersedes':[2], 'links':[2]}),
 ('Registrar import and authentication receipt','reef-installation',
  'The registrar authenticated the February habitat appendix’s seal and filed its original into the active Tessera permit register today. Filing is complete and the appendix is binding now. The import date is later than the studio’s survey, but the original’s February authorship date remains unchanged.', {'links':[5]}),
 ('Dry-land tile workshop rule','dry-workshop',
  'Dry workshop tile demonstrations may screw practice frames into reusable timber blocks to a depth of 4 centimetres. The workshop manager signed this instruction. No seabed, sponge or reef permit is involved. The practice rule cannot authorize either T2 drilling or T3 anchors.'),
 ('T3 ordinary-rock setup request','reef-installation',
  'The studio requests 10-centimetre anchors at ordinary bare-rock site T3. The accepted habitat survey identifies T3 as ordinary rock. This request is within the original 12-centimetre limit if the filed appendix leaves ordinary rock unchanged; it creates no exception for protected T2.')], [
 ('Reef studio installation digest','reef-installation',
  'The digest was rewritten in October from the January permit and September site survey. It applies a blanket 12-centimetre drilling limit to T2 and T3. Its ledger lacks the old-authored but newly filed habitat appendix and filing receipt, so rewrite recency does not supply the missing protected-bed condition.', [1,2,3]),
 ('Dry workshop practice sheet','dry-workshop',
  'The practice sheet allows 4-centimetre screws into reusable timber demonstration blocks. It explains that dry exercises do not install art in the reef. This derived view is useful for classroom setup but has no reef site classification, registrar filing receipt or habitat appendix in its ledger.', [1,7])], [
 ('Choose a permitted installation method for Tessera reef workshop site T2 now that the archive import is complete. Give site class, drilling permission, approved method and binding authority event.', 'ready', {'site_class':'protected sponge bed','drilling_allowed':False,'method':'removable weighted frame','authority_event':'registrar authenticated and filed habitat appendix'}, [[1,3,4,5,6]]),
 ('Decide the tiled reef studio’s 10-centimetre anchor request at T3 under the current permit. Give site class, maximum anchor depth and whether the request fits.', 'ready', {'site_class':'ordinary bare rock','maximum_anchor_depth_cm':12,'request_permitted':True}, [[2,3,5,8]])])

family('A17', 'Peregrine Map Press', 'cartographic editions and coordinate correction',
 ['Peregrine atlas shop','the wandering map press'], 'late_import', [
 ('Errata adoption charter','edition-4',
  'Peregrine edition 4 uses survey-board errata once the editor authenticates their originals and enters them in the edition register. Source authorship dates survive imports. Printer layout revisions do not choose coordinate signs. Edition 3 remains a separate historical reference with its own north-axis convention.'),
 ('Edition 4 first coordinate table','edition-4',
  'The first edition-4 table printed the dune beacon’s northing as plus 320 metres, measured from the harbour origin with north positive. Its easting was plus 80 metres. The table was provisional while the survey board checked a transcribed sign; users were warned not to infer sign from artwork.', {'authored_at':'2026-01-05T09:00:00Z'}),
 ('Edition 4 origin and axes','edition-4',
  'The accepted edition-4 axis sheet defines harbour origin zero, east positive and north positive. The dune beacon’s corrected position must use that sheet. A south-up illustration rotates paper presentation only; it does not invert coordinate signs or move the harbour origin.'),
 ('Dune route endpoint request','edition-4',
  'The route editor wants the edition-4 vector from harbour origin to the dune beacon. No intermediate waypoint is required. Components must retain the edition’s east-positive and north-positive signs. A compass bearing copied from an old edition is not an acceptable substitute for the corrected vector.'),
 ('Survey-board signed sign erratum','edition-4',
  'The survey board’s February erratum corrects the dune beacon northing to minus 320 metres while retaining easting plus 80 metres. The earlier plus northing was a transcription error. The signed original supersedes the first edition-4 coordinate table’s northing only; edition 3 and illustration orientation are unaffected.', {'authored_at':'2026-02-11T09:00:00Z','supersedes':[2]}),
 ('Editor authentication and import receipt','edition-4',
  'The editor authenticated the February sign erratum and entered it into the active edition-4 register today. The entry retains the original February authorship date and marks adoption complete. The current layout proof was prepared without that original, so its later file date cannot displace the registered correction.', {'links':[5]}),
 ('Edition 3 historical convention','edition-3',
  'Edition 3 measured from its old inland origin with south positive. Its historical dune beacon entry was 270 metres south and 110 metres east. The press permits quoting those figures only when edition 3 and its origin are stated. They do not translate directly into edition 4.'),
 ('South-up art director note','illustration',
  'The artist rotates the harbour illustration so south appears at the top of the page. The art director confirms all edition-4 numeric coordinates still use the accepted north-positive axis sheet. Rotation improves composition but is not a numerical erratum, nor a return to edition 3’s origin.')], [
 ('Edition 4 layout proof digest','edition-4',
  'The October proof digest prints the dune beacon at easting plus 80 and northing plus 320. Its ledger ends with the provisional table, axis sheet and art note. The older-authored signed erratum was imported later and is absent, so the proof’s production date does not make its sign authoritative.', [2,3,8]),
 ('Historical edition comparison','edition-3',
  'The comparison preserves edition 3’s inland origin and south-positive dune coordinates of 270 south and 110 east. It distinguishes numerical conventions from south-up page art. It contains no adopted edition-4 correction and cannot produce a harbour-origin route vector for the current edition.', [1,7,8])], [
 ('Update Peregrine atlas shop edition 4’s dune beacon coordinate entry after the import. Give easting, northing, origin and sign convention.', 'ready', {'easting_m':80,'northing_m':-320,'origin':'harbour','positive_axes':['east','north']}, [[1,3,5,6]]),
 ('For the wandering map press edition 4, compute the harbour-to-dune route components for a south-up illustration. Give signed east/north components and whether paper rotation changes them.', 'ready', {'east_component_m':80,'north_component_m':-320,'paper_rotation_changes_components':False}, [[1,3,5,6,8]])])

family('A18', 'Saffron Comet Dance', 'performance license and recording limits',
 ['Saffron Comet troupe','the amber-tail dancers'], 'late_import', [
 ('Contract rider activation','public-performance',
  'A Saffron Comet rights rider becomes operative when the producer verifies its signature and records it in the production contract register. Original signing dates remain intact after import. Public live performance, ticket promotion and recorded distribution are separate permissions; rehearsal notes cannot enlarge a rights grant.'),
 ('Base choreography license','public-performance',
  'The January base license allows the troupe to perform choreography Lantern Drift live during its autumn run. It leaves public recording permission to a later rider. Ticket promotion may use the dance title and a posed still photograph. The base grant does not authorize uploading performance video.', {'authored_at':'2026-01-09T09:00:00Z'}),
 ('Production identity sheet','public-performance',
  'Tonight’s Saffron Comet program uses Lantern Drift in the paid public autumn run. The rehearsal exercise called Lantern Draft is a different unticketed movement study. Similar titles are not alternative spellings. The producer accepted this identity sheet for the contract and recording plan.'),
 ('Promotion asset request','ticket-promotion',
  'The publicity coordinator requests a posed still photograph and a 45-second performance clip for ticket promotion. Both assets would be publicly posted. The requested clip contains Lantern Drift choreography from tonight’s paid run; calling it a preview does not turn it into an unticketed rehearsal study.'),
 ('Original signed recording rider','public-recording',
  'The February rider permits public performance clips of Lantern Drift only up to 20 seconds, without downloadable full-resolution files. It allows the posed still already covered by the base license. Longer clips and full-show recordings need a new written grant. The signed original was held by the rights representative until import.', {'authored_at':'2026-02-17T09:00:00Z','links':[2]}),
 ('Producer rider verification receipt','public-recording',
  'The producer verified the February rider’s rights signature and entered it into the production contract register today. Activation is complete. No new grant for a 45-second clip or full-show recording was received. The later import date does not change the rider’s original 20-second condition.', {'links':[5]}),
 ('Private rehearsal recording rule','rehearsal',
  'The movement coach allows internal recording of unticketed Lantern Draft rehearsals for ten days of private study. The files must remain on the private rehearsal drive and be removed after the study interval. The coach controls that exercise, not public Lantern Drift recording rights.'),
 ('Ticket promotion slogan draft','ticket-promotion',
  'A slogan draft promises viewers an extended amber-tail dance preview. It contains no clip length, rights signature or download restriction. The publicity coordinator retained it as copywriting material. Describing a video as promotional cannot supply the new grant required for a longer performance clip.')], [
 ('Autumn troupe promotion packet','ticket-promotion',
  'The packet combines the base live license with the coordinator’s 45-second clip request and labels both assets cleared. Its ledger lacks the recording rider and activation receipt. The request is recorded faithfully, but the packet incorrectly promotes a requested permission into a granted recording right.', [2,3,4]),
 ('Rehearsal study summary','rehearsal',
  'The study summary allows ten days of private Lantern Draft rehearsal viewing and later file removal. It distinguishes the movement exercise from paid Lantern Drift performances. Its internal permission cannot be cited for public promotion, even if a rehearsal camera uses the same costume colors as the public program.', [1,3,7])], [
 ('Clear the Saffron Comet troupe’s public ticket-promotion assets after the rider import. Give still permission, maximum performance clip length, download restriction and whether the requested 45-second clip is allowed.', 'ready', {'posed_still_allowed':True,'maximum_clip_seconds':20,'full_resolution_download_allowed':False,'requested_45_second_clip_allowed':False}, [[1,3,4,5,6]]),
 ('Set the amber-tail dancers’ private Lantern Draft rehearsal recording retention. Give audience, retention days, required end action and whether this permission covers Lantern Drift promotion.', 'ready', {'audience':'private study','retention_days':10,'end_action':'remove files','covers_public_promotion':False}, [[1,3,7]])])
family('A19', 'Glass Fern Conservatory', 'pollinator containment and ventilation routes',
 ['Glass Fern house','the fern dome'], 'missing_edge', [
 ('Containment decision authority','pollination-room',
  'The conservatory ecologist controls live pollinator containment. Facilities staff may inspect doors and ventilation hardware, but cannot choose release conditions. Room P contains live moths for orchid pollination; room D has mechanical moth models and follows a separate visitor demonstration plan.'),
 ('Early cross-ventilation plan','pollination-room',
  'The early room-P plan opened both north and south doors for cross-ventilation during pollination. It was written before the live moth shipment was confirmed. The ecologist marked it provisional and instructed facilities to retain a record of the configuration for later comparison.'),
 ('Live shipment identification','pollination-room',
  'The accepted shipment receipt identifies room P’s pollinators as live, free-flying moths. Their crates carry no model suffix. Room D’s mechanical demonstrations are unrelated. The ecologist confirms that an open exterior door would let the live shipment escape, regardless of the similar wing patterns in the models.'),
 ('Filtered vent inspection','pollination-room',
  'Facilities passed the north filtered vent and both exterior door latches in room P. The filter mesh is intact and stops the shipment’s moth size. The receipt reports a usable closed-door ventilation route. It does not set the ecological release configuration by itself.'),
 ('Ecologist containment correction','pollination-room',
  'The ecologist replaces the early cross-ventilation plan for room P: keep both exterior doors latched and ventilate only through the passed north filtered vent while live moths are loose. Release may occur after the live shipment and hardware receipts are accepted. The registrar’s export lost the predecessor and dependency edges; the signed body preserves the decision.'),
 ('Room D model demonstration','model-demo',
  'Room D’s mechanical moth demonstration may use open doors because the models are tethered and contain no living pollinators. The visitor coordinator permits fifteen-minute shows. Its open-door practice does not override room P’s ecological containment correction or prove that the live shipment is tethered.'),
 ('Night reset procedure','pollination-room',
  'After room-P live moths return to their closed crates and the ecologist signs a crate-count receipt, facilities may open exterior doors for a ten-minute nightly purge. During the purge the north filter stays closed. The crate-count receipt is a prerequisite; an empty-looking room is insufficient.'),
 ('Tonight crate-count receipt','pollination-room',
  'The ecologist counted all room-P moths back into their closed crates tonight and signed the matching shipment count. Facilities may now follow the nightly reset procedure. The receipt ends tonight’s free-flight interval; it does not authorize open-door ventilation during the next pollination release.')], [
 ('Fern dome ventilation overview','pollination-room',
  'The overview recommends both doors open during pollination based on the early cross-ventilation plan. It includes the live shipment in its ledger yet does not reconsider containment. The ecologist’s body-only correction was missed because this overview’s author followed dependency edges rather than reading later governing originals.', [1,2,3]),
 ('Mechanical moth visitor card','model-demo',
  'The visitor card describes fifteen-minute tethered model shows with open doors in room D. It cites the demonstration permission and identity distinction. These instructions remain useful for mechanical exhibits, but the shared moth vocabulary cannot move their open-door conditions into room P.', [1,3,6])], [
 ('Configure the Glass Fern house room P for live moth release now. Give door state, ventilation route, approving role and whether the required shipment/hardware receipts are present.', 'ready', {'doors':'both latched','ventilation':'north filtered vent','authority':'conservatory ecologist','required_receipts_present':True}, [[1,3,4,5]]),
 ('After tonight’s crate count in the fern dome room P, run the nightly purge. Give duration, exterior door state, north-filter state and the prerequisite that has now been completed.', 'ready', {'duration_minutes':10,'doors':'open','north_filter':'closed','completed_prerequisite':'ecologist signed matching crate-count receipt'}, [[3,7,8]])])

family('A20', 'Pelagic Bronze Hall', 'mechanical exhibit energy isolation',
 ['Pelagic ballast exhibit','the bronze submarine hall'], 'missing_edge', [
 ('Motion exhibit control charter','moving-exhibit',
  'The mechanical safety engineer controls visitor operation of the Pelagic moving ballast exhibit. The interpretation team controls narration. The exhibit has a live spring-driven ballast lever and a separate fixed display cutaway. A safe narration script cannot certify mechanical isolation or motion limits.'),
 ('Initial lever operating card','moving-exhibit',
  'The initial card allowed visitors to pull the ballast lever through its full 60-degree arc after a guard check. That card assumed a low-force demonstration spring. The safety engineer marked the force assumption pending delivery inspection, so the printed full-arc instruction was not unconditional.'),
 ('Installed spring inspection','moving-exhibit',
  'The delivered spring is the high-force model, installed because the low-force unit was unavailable. Its verified stored energy is 90 joules. The inspector matched its serial to the moving exhibit and recorded that the fixed cutaway contains no spring. No operating permission was issued in this inspection.'),
 ('Hard stop installation receipt','moving-exhibit',
  'The technician installed and tested a rigid 15-degree stop on the live ballast lever. The stop passed repeated pulls without deformation. The receipt verifies the travel-limiting hardware but does not disconnect spring energy or replace the engineer’s decision about visitor operation.'),
 ('High-force operating correction','moving-exhibit',
  'The safety engineer withdraws the initial full-arc operating card for the installed high-force spring. Visitor pulls are permitted only with the tested 15-degree hard stop and the original guard passed. The machine-readable links and supersedes fields were lost during cataloguing; this preserved signed body explicitly replaces the 60-degree instruction.'),
 ('Guard inspection receipt','moving-exhibit',
  'The original finger guard passed inspection after the 15-degree stop was installed. The engineer accepted the guard and stop receipts together for today’s visitor demonstration. The guard covers the live lever pinch point, not the adjacent fixed cutaway or any dismantled maintenance configuration.'),
 ('Maintenance energy isolation rule','maintenance',
  'Before technicians remove the moving exhibit’s spring, they must discharge it to zero stored energy and lock the lever. The safety engineer requires an isolation receipt before dismantling. A 15-degree visitor stop restricts travel but does not dissipate 90 joules or make spring removal safe.'),
 ('Maintenance isolation receipt','maintenance',
  'For tonight’s maintenance, the technician discharged the spring to zero stored energy, locked the lever and signed the isolation receipt. The safety engineer accepted it for spring removal. This isolated maintenance state must end with reinspection before the moving exhibit is offered to visitors again.')], [
 ('Ballast visitor script and controls','moving-exhibit',
  'The visitor guide repeats a 60-degree pull and discusses submarine ballast narration. It incorporates the initial card and installed spring inspection but lacks the body-only high-force correction. Interpretation text cannot cure that omission; the new spring’s energy is recorded without the updated travel restriction.', [1,2,3]),
 ('Maintenance isolation abstract','maintenance',
  'The maintenance abstract records zero stored energy, a locked lever and an accepted isolation receipt before spring removal. It cites the mechanical maintenance rule, not the visitor operating card. Its completed isolation belongs to tonight’s dismantling state and does not authorize next-day demonstrations without reinspection.', [3,7,8])], [
 ('Operate the Pelagic ballast exhibit for today’s visitors. Give maximum lever travel, installed spring energy, required protective hardware and the decision authority.', 'ready', {'maximum_travel_degrees':15,'spring_energy_joules':90,'hardware':['tested hard stop','passed finger guard'],'authority':'mechanical safety engineer'}, [[1,3,4,5,6]]),
 ('Remove the spring tonight at the bronze submarine hall. Give required energy state, lever state and completed authorization receipt, and whether the visitor stop alone would suffice.', 'ready', {'stored_energy_joules':0,'lever_state':'locked','receipt':'accepted isolation receipt','visitor_stop_alone_sufficient':False}, [[3,7,8]])])

family('A21', 'Cairn Halo Observatory', 'instrument drift and exposure scheduling',
 ['Cairn Halo telescope','the ridge halo dome'], 'missing_edge', [
 ('Instrument exposure authority','camera-C',
  'The observatory instrument scientist signs camera-C exposure corrections. Night operators apply them to the scheduled target; public clock tours use a separate simulator. Instrument ticks are not civil-time seconds until the currently signed tick calibration is applied, even when a display labels both values as time.'),
 ('Initial tick calibration','camera-C',
  'The initial camera-C calibration treated one instrument tick as one second and planned 120 ticks for the star Sable exposure. That calibration used the previous oscillator. It remained on the operator card pending inspection of the replacement oscillator; it was not a claim about every camera.'),
 ('Replacement oscillator measurement','camera-C',
  'The replacement oscillator measurement shows one camera-C tick lasts 1.25 seconds. The instrument scientist accepted the bench timing result. The target Sable still requires 120 real seconds of integration. A longer tick therefore changes tick count rather than the scientific exposure duration.'),
 ('Shutter timing receipt','camera-C',
  'The shutter controller passed a 96-tick opening and closing test with the replacement oscillator. The measured integration was 120 seconds. The accepted receipt identifies camera C and the current oscillator. A test on the public clock simulator would not verify this physical shutter.'),
 ('Signed exposure tick correction','camera-C',
  'The instrument scientist replaces the initial one-second tick calibration for camera C with 1.25 seconds per tick. Sable’s 120-second integration must use 96 ticks, after the matching shutter test passes. This original’s predecessor and dependency links were omitted in export, but its signed body explicitly corrects the earlier 120-tick instruction.'),
 ('Public simulator timing plan','clock-tour',
  'The public clock-tour simulator intentionally uses one tick per second and runs a 120-tick demonstration. It contains no telescope camera and no real star exposure. The education leader approves simulator timing; that permission does not calibrate camera C’s replacement oscillator.'),
 ('Dark-frame acquisition rule','camera-C',
  'Camera C’s matching dark frame must use the same real integration time and tick count as Sable’s corrected exposure, with its shutter covered. The instrument scientist requires a completed dark-frame receipt before reduction of the science frame. Matching brightness by eye is not sufficient.'),
 ('Dark-frame receipt','camera-C',
  'The operator recorded camera C’s covered-shutter dark frame at 96 ticks and 120 real seconds using the replacement oscillator. The instrument scientist accepted it for reduction of the matching Sable frame. It is a real instrument receipt, not the clock-tour simulator’s demonstration log.')], [
 ('Night operator timing quick card','camera-C',
  'The quick card retains 120 ticks for Sable and pairs it with the replacement oscillator measurement. It does not incorporate the signed tick correction, whose omitted dependency edges hid it from the export walk. The card’s later layout timestamp cannot reconcile its count with the recorded 1.25-second ticks.', [1,2,3]),
 ('Public clock tour guide','clock-tour',
  'The guide explains the simulator’s one-second ticks and 120-tick demonstration. It distinguishes simulation from the observatory’s camera clock. It has no physical shutter or dark-frame receipts in its ledger and therefore cannot establish that a real Sable integration is ready for reduction.', [1,6])], [
 ('Set the Cairn Halo telescope camera C exposure for Sable with the replacement oscillator. Give real duration, tick duration, tick count and whether the matching shutter test passed.', 'ready', {'integration_seconds':120,'seconds_per_tick':1.25,'ticks':96,'shutter_test_passed':True}, [[1,3,4,5]]),
 ('Prepare reduction of the ridge halo dome’s Sable science frame. Give required matching dark-frame duration, ticks, shutter condition and whether its receipt is complete.', 'ready', {'dark_integration_seconds':120,'dark_ticks':96,'dark_shutter':'covered','dark_receipt_complete':True}, [[3,5,7,8]])])
family('A22', 'Juniper Moon Cellar', 'batch composition and product identity',
 ['Juniper Moon cheeses','the crescent cheese cellar'], 'wrong_ledger', [
 ('Composition label authority','sale-batches',
  'The cellar batch assessor controls Juniper Moon product composition labels. Sales staff may quote signed labels but cannot infer milk type from a familiar cheese name. Goat-only and mixed-milk batches use different labels even when the aging recipe and crescent rind stamp are identical.'),
 ('Initial G4 ingredient plan','sale-batches',
  'The initial G4 plan specified only goat milk and proposed the name “goat crescent.” The plan was written before delivered ingredient reconciliation. Its milk identity remained provisional. The cellar’s crescent rind stamp indicates the aging style, not a guarantee that all ingredients are goat milk.'),
 ('Delivered milk reconciliation','sale-batches',
  'The signed G4 reconciliation shows 70 litres of goat milk and 30 litres of sheep milk were actually used. The sheep lot entered during a goat-supply shortage. Both lots are traced to G4, not the separate G5 batch. The report corrects the delivered composition without assigning a sale label.'),
 ('G4 aging completion receipt','sale-batches',
  'The assessor accepted G4’s required 40-day aging completion and its crescent rind check. That receipt establishes aging status only; it does not verify a goat-only composition. A batch can meet the familiar aging recipe while requiring a different truthful composition label.'),
 ('Mixed-milk label correction','sale-batches',
  'The assessor withdraws G4’s proposed goat-only name after ingredient reconciliation. The approved sale label is “mixed goat and sheep crescent,” with goat 70 percent and sheep 30 percent by milk volume. The 40-day aging requirement remains. No goat-only label may be used for G4.', {'supersedes':[2], 'links':[3,4]}),
 ('Label replacement receipt','sale-batches',
  'The packer replaced every G4 goat-only sticker with the approved mixed goat and sheep label and the 70/30 milk-volume composition. The assessor checked the replacement receipt. G4 may now be offered using that identity; the receipt is not evidence about the separate G5 batch.'),
 ('G5 goat-only reconciliation','sale-batches',
  'G5’s signed reconciliation confirms 100 percent goat milk. Its 40-day aging receipt is also accepted, and the assessor approves the “goat crescent” label for G5. Batch identity matters: G5’s unchanged label cannot be copied onto G4 merely because both have crescent rinds.'),
 ('Rind stamp purchasing invoice','packaging',
  'The packaging supplier delivered crescent rind stamps and sticker sheets bearing a goat icon. The invoice records ordered packaging, not actual milk composition. Unused stickers may be retained for goat-only batches; their presence beside G4 does not establish assessor approval for that batch.')], [
 ('G4 sale readiness summary','sale-batches',
  'The summary declares G4 a goat-only crescent with aging complete and stickers checked. Its incorporation ledger claims the mixed-milk correction and label replacement receipt were consumed, yet the text still preserves the withdrawn goat-only identity. The ledger is a defective coverage claim, not a factual override of those originals.', [1,2,3,5,6]),
 ('G5 composition card','sale-batches',
  'The G5 card identifies a goat-only batch with accepted 40-day aging and the approved goat crescent label. It distinguishes G5 from G4’s mixed composition. This derived record’s correct batch-scoped summary demonstrates why a matching product style cannot substitute for the original reconciliation of another batch.', [1,7])], [
 ('Set the sale identity for Juniper Moon cheeses batch G4 now. Give label, milk-volume percentages, aging days and whether the replacement label receipt is complete.', 'ready', {'label':'mixed goat and sheep crescent','goat_percent':70,'sheep_percent':30,'aging_days':40,'label_replacement_complete':True}, [[3,4,5,6]]),
 ('Compare sale labels for the crescent cheese cellar’s G4 and G5. Give each label and whether identical rind stamps authorize copying G5’s label to G4.', 'ready', {'G4_label':'mixed goat and sheep crescent','G5_label':'goat crescent','copy_by_rind_stamp_allowed':False}, [[1,5,7]])])

family('A23', 'River Bell Soundbank', 'recording channel provenance and archival masters',
 ['River Bell audio archive','the bell river tapes'], 'wrong_ledger', [
 ('Master channel provenance rule','archive-release',
  'River Bell archival masters must preserve recorded channel identity, using the sound curator’s signed channel map. Restoration staff may remove noise but cannot relabel channels by listening impressions. Exhibition mono mixes are separate derivatives and may not replace the two-channel archival master.'),
 ('Initial RB8 channel notebook','archive-release',
  'The initial notebook described RB8 channel 1 as upstream and channel 2 as downstream. The recorder’s cabling had not yet been checked. The curator marked these names provisional pending the equipment trace; they were not fixed properties of every bell-river recording.'),
 ('RB8 cable trace receipt','archive-release',
  'The equipment trace found recorder input 1 connected to the downstream microphone and input 2 to upstream. The technician identified the original RB8 connector tags and accepted file checksum. The trace concerns the two-channel source, not a later mono exhibition mix.'),
 ('Restored master checksum receipt','archive-release',
  'Restoration staff removed the approved hum from RB8 without swapping channel order and recorded the restored file’s checksum. The curator accepted preservation of the source input order. The receipt validates order and restoration, but channel location names still require the signed map.'),
 ('Curator channel map correction','archive-release',
  'The curator replaces the provisional notebook labels: RB8 channel 1 is downstream and channel 2 is upstream. The archival master must retain that order and corrected location metadata. This signed original is revision 1; no revision 2 exists. The mono exhibition mix remains a separately labelled derivative.', {'supersedes':[2], 'links':[3,4]}),
 ('Archive metadata acceptance','archive-release',
  'The curator checked the restored RB8 master’s metadata against the corrected channel map and accepted downstream on channel 1, upstream on channel 2. The master is ready for archive release with its restored checksum. A coverage ledger that names an unavailable revision cannot substitute for this original acceptance.'),
 ('Mono exhibition mix decision','exhibition-mix',
  'The exhibition designer may combine RB8’s channels equally into a mono loop labelled “exhibition mix, not archival master.” The curator approved a 30-second loop. A mono loop has no separate upstream and downstream output channels, so channel-map names should not be invented for it.'),
 ('Different recording RB9 notebook','archive-release',
  'RB9 used channel 1 upstream and channel 2 downstream, and the curator accepted those labels after its own cable check. RB9’s setup was not identical to RB8’s. Their shared river and bell titles do not permit transferring channel provenance between recording sessions.')], [
 ('RB8 archive export manifest','archive-release',
  'The manifest keeps channel 1 upstream and channel 2 downstream from the provisional notebook. Its ledger claims revision 2 of the curator correction, although the archive contains only revision 1. The nonexistent-revision coverage claim and obsolete labels make the manifest insufficient even with an October rewrite timestamp.', [2,3,5], {'ledger_revisions':{'A23R05':2}}),
 ('Exhibition loop handout','exhibition-mix',
  'The handout describes an equal-channel 30-second mono loop and requires the exhibition-mix distinction. It cites the separate mix decision and corrected source map. It preserves source provenance while acknowledging that the displayed mono output is a derivative, not a release of the two-channel master.', [1,5,7])], [
 ('Release the River Bell audio archive RB8 restored master with correct location metadata. Give channel 1, channel 2, order action and whether curator metadata acceptance is complete.', 'ready', {'channel_1':'downstream','channel_2':'upstream','order_action':'retain source input order','metadata_acceptance_complete':True}, [[1,3,4,5,6]]),
 ('Prepare the bell river tapes’ RB8 exhibition loop. Give channel combination, output type, duration and required distinction from the archival master.', 'ready', {'channel_combination':'equal','output':'mono','duration_seconds':30,'label':'exhibition mix, not archival master'}, [[1,5,7]])])

family('A24', 'Aurora Kite Range', 'autonomous flight safeguards and manual control',
 ['Aurora kite trials','the dawn sail test range'], 'wrong_ledger', [
 ('Autonomous launch gate','autonomous-flight',
  'The Aurora range controller permits autonomous kite launches only after a current geofence test and an accepted radio-loss landing test. Wind must also be below 12 knots. Manual tether demonstrations follow a separate ground rule. A simulation receipt cannot replace a physical safeguard test.'),
 ('Initial launch checklist','autonomous-flight',
  'The draft checklist treated a successful geofence simulation as sufficient and scheduled kite K2 for launch. The controller marked that shortcut provisional until physical boundary response was tested. The scheduled launch time is a booking, not flight authorization or a completed safeguard receipt.'),
 ('Current wind observation','autonomous-flight',
  'The range weather reader measured 8 knots for today’s K2 launch slot and the controller accepted the observation. This satisfies the wind limit. It does not establish geofence or radio-loss behavior; a calm launch can still violate containment if the safeguards are not tested.'),
 ('Radio-loss landing test','autonomous-flight',
  'K2 passed the physical radio-loss test and landed within the marked recovery strip when its control signal stopped. The controller accepted the receipt for today. The test intentionally did not approach the geofence boundary and therefore cannot demonstrate the required boundary response.'),
 ('Physical geofence requirement correction','autonomous-flight',
  'The controller withdraws the simulation shortcut. K2 requires a current physical geofence boundary-response receipt in addition to its radio-loss test and wind observation. The simulation still helps plan a test but cannot authorize flight. The autonomous release field must remain unset until the physical receipt is accepted.', {'supersedes':[2], 'links':[1,4]}),
 ('Physical test status docket','autonomous-flight',
  'The physical K2 geofence test has not been run. The docket contains a completed simulation and no physical boundary-response receipt. The controller keeps autonomous release unsigned. Staff should perform and obtain acceptance of that physical test; copying the simulation success into a physical field is forbidden.'),
 ('Manual tether demonstration rule','manual-ground',
  'A manually held kite may demonstrate on a 5-metre ground tether below 10 knots, with a spotter present and no autonomous controller engaged. The range controller approved this ground activity. The operator’s tether supplies containment, so this distinct manual demonstration requires no autonomous geofence receipt.'),
 ('Manual setup inspection','manual-ground',
  'Today’s manual demonstration setup passed: the tether is 5 metres, a spotter is present and the autonomous controller is disengaged. The same accepted weather observation is 8 knots. The range controller signed manual-ground permission only, leaving K2’s autonomous release unsigned.')], [
 ('K2 launch completion dashboard','autonomous-flight',
  'The dashboard says physical geofence passed and autonomous launch cleared. Its ledger actually incorporates the draft checklist, wind, radio-loss receipt and manual setup inspection; it does not contain a physical geofence result. This wrong-evidence ledger merges a completed manual setup into a missing autonomous safeguard.', [2,3,4,8]),
 ('Manual ground demo card','manual-ground',
  'The ground card records the 5-metre tether, spotter, disengaged autonomous controller and 8-knot wind. It cites the signed manual rule and inspection, with manual-only permission. It correctly avoids claiming an autonomous release or physical geofence acceptance from this ground demonstration.', [3,7,8])], [
 ('Authorize today’s Aurora kite trials autonomous K2 launch if all gates are met. Give authorization, observed wind, completed safeguard and unresolved safeguard.', 'hold', {'authorization':None,'wind_knots':8,'completed_safeguard':'radio-loss landing test','unresolved':['accepted current physical geofence boundary-response receipt']}, [[1,3,4,5,6]]),
 ('Run the dawn sail test range’s manually held ground demonstration today. Give tether length, wind, spotter condition, controller state and permission scope.', 'ready', {'tether_metres':5,'wind_knots':8,'spotter':'present','autonomous_controller':'disengaged','permission_scope':'manual-ground only'}, [[3,7,8]])])

def validate(payload):
    families = payload['families']
    assert len(families) == 24
    assert Counter(f['stratum'] for f in families) == {
        'late_correction':3, 'scope_exception':3, 'unresolved_conflict':3,
        'missing_prerequisite':3, 'unicode_alias':3, 'late_import':3,
        'missing_edge':3, 'wrong_ledger':3}
    all_ids = []
    nonexistent_revisions = []
    for f in families:
        assert len(f['records']) == 10 and len(f['tasks']) == 2
        sources = {r['id']:r for r in f['records'] if r['kind'] == 'source'}
        all_records = {r['id']:r for r in f['records']}
        assert len(sources) == 8
        assert len(f['aliases']) == 2
        for r in f['records']:
            all_ids.append(r['id'])
            assert r['revision'] >= 1
            assert 70 <= len(r['body'].split()) <= 130, (r['id'], len(r['body'].split()))
            assert r['authored_at'].startswith('2026-') and r['authored_at'].endswith('Z')
            assert all(x in all_records for x in r['links'] + r['supersedes'])
            assert all(x in sources for x in r['supersedes'])
            if r['kind'] == 'source':
                assert r['incorporates'] == []
            else:
                for entry in r['incorporates']:
                    assert entry['id'] in sources and entry['revision'] >= 1
                    if entry['revision'] != sources[entry['id']]['revision']:
                        nonexistent_revisions.append((r['id'], entry['id'], entry['revision']))
        for task in f['tasks']:
            all_ids.append(task['id'])
            answer = task['expected']['answer']
            assert task['expected']['status'] in ('ready','hold')
            assert set(task['answer_keys']) == set(answer) == set(task['critical_keys'])
            assert all(v is None or isinstance(v, (str,int,float,bool,list)) for v in answer.values())
            if task['expected']['status'] == 'hold':
                assert any(v is None for v in answer.values())
                assert isinstance(answer.get('unresolved'), list) and answer['unresolved']
            assert task['evidence_sets']
            for group in task['evidence_sets']:
                assert 3 <= len(group) <= 5
                assert len(group) == len(set(group))
                assert all(x in sources for x in group)
            assert not any(rid in task['query'] for rid in all_records)
    assert len(all_ids) == len(set(all_ids))
    assert nonexistent_revisions == [('A23R09','A23R05',2)]
    assert sum(any(ord(c) > 127 for c in ' '.join([f['name']] + f['aliases'])) for f in families) >= 6
    return {'families':len(families), 'records':sum(len(f['records']) for f in families),
        'originals':sum(r['kind']=='source' for f in families for r in f['records']),
        'tasks':sum(len(f['tasks']) for f in families),
        'hold_tasks':sum(t['expected']['status']=='hold' for f in families for t in f['tasks']),
        'intentional_wrong_revision':nonexistent_revisions}

if __name__ == '__main__':
    corpus = {'schema_version':1, 'author':'author-a', 'families':FAMILIES}
    checks = validate(corpus)
    DEST.write_text(json.dumps(corpus, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    saved = json.loads(DEST.read_text(encoding='utf-8'))
    assert validate(saved) == checks
    print(json.dumps(checks, ensure_ascii=False))
