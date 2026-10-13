"""Render external/development scientific figures from safe completed aggregates.

Optionally stream development cell receipts for preplanned paired packing stats.
No corpus, main outcomes, model, private path or source text is published.
"""
import argparse
from collections import defaultdict
import hashlib
import json
from pathlib import Path
import textwrap

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

HERE = Path(__file__).resolve().parent
OUT = HERE/'supplement-figures'
COLORS = ('#2d6aaf', '#39815c', '#80579b', '#d56c35')
EXT = ('body_bm25','entity_rrf','dense_windows','dense_window_rrf')
DEV = ('body_bm25','entity_rrf','graph_diffusion')
ENAMES = ('BM25','Word/char RRF','Dense windows','Dense + BM25 RRF')
DNAMES = ('BM25','Entity RRF','Graph diffusion')
CNAMES = {'baseline':'Original','iteration_shuffle':'Insertion order','opaque_ids':'Opaque IDs',
          'path_permutation':'Paths/layout','padding_before':'Noise before','padding_after':'Noise after',
          'padding_balanced':'Noise balanced','near_alias_cues':'Near-ID aliases',
          'near_identifier_records':'Near-ID markers','combined_shuffle_opaque_paths':'Combined'}


def sha(value):
    data=json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False).encode('utf-8')
    return hashlib.sha256(data).hexdigest()


def fdigest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def find(data, **criteria):
    return next(c for c in data['cells'] if all(c[k]==v for k,v in criteria.items()))


def style():
    plt.rcParams.update({'font.family':'DejaVu Sans','font.size':10,'axes.titlesize':11,
                        'axes.labelsize':10,'axes.spines.top':False,'axes.spines.right':False,
                        'svg.hashsalt':'oct13-supplement-v1','savefig.facecolor':'white'})


def tidy(ax, label):
    ax.set_ylabel(label);ax.set_ylim(0,100);ax.set_yticks([0,25,50,75,100])
    ax.grid(axis='y',color='#e1e5e9',linewidth=.7);ax.set_axisbelow(True)


def finish(fig, name, title, caption, table, registry):
    width,height=fig.get_size_inches()
    title_lines='\n'.join(textwrap.wrap(title,width=int(width*10)))
    caption_lines=[line for original in caption.split('\n') for line in textwrap.wrap(original,width=int(width*13))]
    fig.suptitle(title_lines,x=.06,ha='left',fontsize=14,fontweight='bold',y=.985)
    fig.text(.06,.02,'\n'.join(caption_lines),ha='left',va='bottom',fontsize=8.5,color='#48515b')
    bottom=max(.12,(.18+.16*len(caption_lines))/height)
    fig.tight_layout(rect=[.03,bottom,.99,.90])
    png,svg=OUT/(name+'.png'),OUT/(name+'.svg')
    fig.savefig(png,dpi=170,metadata={'Software':'Matplotlib scientific supplement'})
    fig.savefig(svg,metadata={'Date':None,'Creator':'Matplotlib scientific supplement'})
    plt.close(fig)
    registry.append({'id':name,'title':title,'caption':caption,'input_table_sha256':sha(table),
                     'input_table':table,'png':{'path':'supplement-figures/'+png.name,'sha256':fdigest(png),'bytes':png.stat().st_size},
                     'svg':{'path':'supplement-figures/'+svg.name,'sha256':fdigest(svg),'bytes':svg.stat().st_size}})


def stream_paired(path):
    # Streaming is needed only for paired endpoint counts absent from aggregate
    # cells; keep two booleans/key, not 26MB of per-cell/source interval records.
    paired=defaultdict(dict);rank_hashes={};count=0
    with path.open(encoding='utf-8') as stream:
        for line in stream:
            r=json.loads(line);count+=1
            if r['packer'] in ('whole_record','nested_whole'):
                key=(r['condition'],r['qid'],r['ranker'],r['budget'])
                paired[key][r['packer']]=(r['span_bundle'],r['fault'],r['template_group'])
            if r['condition'] in ('padding_before','padding_after','padding_balanced') and r['packer']=='whole_record' and r['budget']==4096:
                rank_hashes[(r['condition'],r['qid'],r['ranker'])]=(r.get('ranking_sha256'),r['fault'])
    assert count==19440 and all(set(v)=={'whole_record','nested_whole'} for v in paired.values())
    buckets=defaultdict(list)
    for (condition,qid,method,budget),v in paired.items():
        nested,greedy=v['nested_whole'],v['whole_record']
        buckets[(condition,method,budget)].append((int(nested[0])-int(greedy[0]),nested[1] or greedy[1]))
    table=[]
    for (condition,method,budget),values in sorted(buckets.items()):
        differences=[v for v,f in values]
        table.append({'condition':condition,'ranker':method,'budget':budget,'scheduled_pairs':len(values),
                      'gains':differences.count(1),'ties':differences.count(0),'regressions':differences.count(-1),
                      'fault_pairs':sum(f for v,f in values)})
    position=[]
    for alternate in ('padding_after','padding_balanced'):
        for method in DEV:
            keys=[(q,m) for c,q,m in rank_hashes if c=='padding_before' and m==method]
            assessed=matches=0
            for q,m in keys:
                a,b=rank_hashes[('padding_before',q,m)],rank_hashes[(alternate,q,m)]
                if not a[1] and not b[1]: assessed+=1;matches+=a[0]==b[0]
            position.append({'compared_to':'padding_before','condition':alternate,'ranker':method,
                             'assessed_queries':assessed,'equal_rank_digests':matches,'unassessed_queries':len(keys)-assessed})
    return {'source_receipt_sha256':fdigest(path),'rows_streamed':count,'nested_vs_greedy':table,'padding_rank_equivalence':position}


def render(external,dev):
    registry=[]
    # 1: Every external budget cell, with necessary byte-feasibility bounds.
    fig,axs=plt.subplots(1,2,figsize=(10.3,4.9),sharey=True)
    table=[]
    for ax,packer,label in zip(axs,('whole_record','sentence_neighbors'),('Whole messages','Sentence neighbors')):
        for method,color,name,marker in zip(EXT,COLORS,ENAMES,('o','s','^','D')):
            cells=[find(external,ranker=method,packer=packer,budget=b) for b in (4096,8192,16384)]
            table.extend(cells);ax.plot([4,8,16],[c['whole_bundle']*100 for c in cells],marker=marker,color=color,label=name,linewidth=1.8)
        bound=[find(external,ranker='body_bm25',packer=packer,budget=b)['whole_feasible']*100 for b in (4096,8192,16384)]
        ax.plot([4,8,16],bound,'--',color='#7b828b',linewidth=1,label='Byte bound')
        ax.set_title(label);ax.set_xticks([4,8,16]);ax.set_xlabel('UTF-8 packet budget (KiB)');tidy(ax,'Complete declared-ID union (%)')
    handles,labels=axs[0].get_legend_handles_labels()
    fig.legend(handles,labels,fontsize=8,loc='upper center',bbox_to_anchor=(.53,.90),ncol=5,frameon=False)
    finish(fig,'01-external-budget','BEAM adaptation: complete original-message recovery',
           '90 labeled questions; five synthetic histories; no QA/official score. Dashed bound is necessary only.\nSentence bound uses optimistic lean wrappers. All 2,160 scheduled packets completed; zero observed faults.',table,registry)
    # 2: Candidate presence, partial ID selection and original-body exposure.
    cells=[find(external,ranker=m,packer='sentence_neighbors',budget=8192) for m in EXT]
    fig,ax=plt.subplots(figsize=(8.1,4.9));positions=np.arange(4);width=.24
    for off,metric,label,color in [(-width,'candidate_all_32','All IDs in top 32','#b2bac5'),(0,'selected_bundle','All IDs selected (partials count)','#65a8a1'),(width,'whole_bundle','All original bodies exposed','#285b86')]:
        values=[c[metric]*100 for c in cells];bars=ax.bar(positions+off,values,width,color=color,label=label)
        for bar,c in zip(bars,cells):ax.text(bar.get_x()+bar.get_width()/2,bar.get_height()+1.4,str(round(c[metric]*90)),ha='center',fontsize=8.5)
    ax.set_xticks(positions,ENAMES,fontsize=9);tidy(ax,'Queries (%)');ax.legend(fontsize=8,loc='upper right')
    finish(fig,'02-external-exposure-gap','BEAM at 8 KiB: finding an ID is a weaker endpoint',
           'Sentence-neighbor packets; bar labels are counts out of 90, within five histories.\nPartial selection and complete-message exposure do not certify semantic sufficiency; no source span labels exist.',cells,registry)
    # 3: Five history clusters, rather than an independent-90 interpretation.
    histories=external['freeze']['histories'];matrix=[];table=[]
    for h in histories:
        row=[]
        for method in EXT:
            c=next(c for c in external['history_cells'] if c['history']==h['history'] and c['ranker']==method and c['packer']=='sentence_neighbors' and c['budget']==8192)
            table.append(c);row.append(round(c['whole_bundle']*18))
        matrix.append(row)
    fig,ax=plt.subplots(figsize=(8.3,4.7));im=ax.imshow(matrix,vmin=0,vmax=18,cmap='Blues',aspect='auto')
    ax.set_xticks(range(4),ENAMES,fontsize=9);ax.set_yticks(range(5),[h['history']+' (chat '+h['upstream_path'].split('/')[-2]+')' for h in histories])
    for i,row in enumerate(matrix):
        for j,value in enumerate(row):ax.text(j,i,f'{value}/18',ha='center',va='center',color='white' if value>10 else '#17252d')
    fig.colorbar(im,ax=ax,label='Queries with complete original-message bundle')
    finish(fig,'03-external-histories','BEAM at 8 KiB: five history clusters',
           'Sentence neighbors; 18 labeled queries per history. These are synthetic, externally authored histories.\nNo query-level confidence interval or population claim. Colors show counts, not answer accuracy.',table,registry)
    # 4: Publisher category labels are task strata, not successful task actions.
    categories=sorted({c['category'] for c in external['category_cells']});matrix=[];table=[]
    for category in categories:
        row=[]
        for method in EXT:
            c=next(c for c in external['category_cells'] if c['category']==category and c['ranker']==method and c['packer']=='sentence_neighbors' and c['budget']==8192)
            table.append(c);row.append(round(c['whole_bundle']*10))
        matrix.append(row)
    fig,ax=plt.subplots(figsize=(8.3,6.7));im=ax.imshow(matrix,vmin=0,vmax=10,cmap='Blues',aspect='auto')
    ax.set_xticks(range(4),ENAMES,fontsize=9);ax.set_yticks(range(9),[c.replace('_',' ').capitalize() for c in categories],fontsize=9)
    for i,row in enumerate(matrix):
        for j,v in enumerate(row):ax.text(j,i,f'{v}/10',ha='center',va='center',color='white' if v>6 else '#17252d')
    fig.colorbar(im,ax=ax,label='Complete declared-message bundles')
    finish(fig,'04-external-categories','BEAM source categories: label recovery at 8 KiB',
           '10 labeled questions per category across five histories; sentence neighbors.\nCategory names do not mean instruction/preference/order correctness was evaluated. No QA, action or official score.',table,registry)
    # 5: Paired gains and regressions, without treating repeats as independent.
    paired=[next(c for c in external['paired_vs_matched_body_bm25'] if c['ranker']==m and c['packer']=='sentence_neighbors' and c['budget']==8192) for m in EXT[1:]]
    fig,ax=plt.subplots(figsize=(8.0,4.5));y=np.arange(3)
    ax.barh(y,[-c['regressions'] for c in paired],color='#b85551',label='Lost complete bundles')
    ax.barh(y,[c['gains'] for c in paired],color='#3f8668',label='Gained complete bundles')
    for i,c in enumerate(paired):
        if c['regressions']:ax.text(-c['regressions']-.3,i,str(c['regressions']),ha='right',va='center')
        ax.text(c['gains']+.3,i,f"{c['gains']}  |  {c['ties']} ties",ha='left',va='center')
    ax.axvline(0,color='#707984',linewidth=.8);ax.set_yticks(y,ENAMES[1:]);ax.set_xlabel('Paired query counts versus BM25');ax.set_xlim(-17,22)
    handles,labels=ax.get_legend_handles_labels();fig.legend(handles,labels,fontsize=8,loc='upper center',bbox_to_anchor=(.56,.85),ncol=2,frameon=False)
    finish(fig,'05-external-paired','BEAM at 8 KiB: paired bundle gains and regressions',
           '90 paired queries in five history clusters; sentence neighbors; complete publisher-ID bundle exposure.\nDescriptive counts only. A positive net change is not a population winner or answer-accuracy result.',paired,registry)
    # 6: All development perturbations under one explicit packet policy.
    conditions=dev['freeze']['conditions'];matrix=[];table=[]
    for condition in conditions:
        row=[]
        for method in DEV:
            c=find(dev,condition=condition,ranker=method,packer='whole_record',budget=8192);table.append(c);row.append(c['span_bundle_count'])
        matrix.append(row)
    fig,ax=plt.subplots(figsize=(8.0,6.6));im=ax.imshow(matrix,vmin=0,vmax=72,cmap='YlGnBu',aspect='auto')
    ax.set_xticks(range(3),DNAMES);ax.set_yticks(range(10),[CNAMES[c] for c in conditions])
    for i,row in enumerate(matrix):
        for j,v in enumerate(row):ax.text(j,i,f'{v}/72',ha='center',va='center',color='white' if v>42 else '#17252d')
    fig.colorbar(im,ax=ax,label='Complete declared original-span alternatives')
    finish(fig,'06-dev-conditions','Development: source-span response to controlled perturbations',
           'Whole-record packets at 8 KiB; 72 development queries / four authored template groups; zero observed faults.\nOrder/layout each match all 1,944 paired packet checks because IDs are sorted and paths are not features; no navigation claim.',table,registry)
    # 7: Packing bytes and span exposure are separate measurable quantities.
    conditions=('baseline','padding_before','padding_after','padding_balanced');table=[];fig,axs=plt.subplots(2,1,figsize=(8.0,6.4),sharex=True)
    x=np.arange(4);width=.34
    for off,packer,name,color in [(-width/2,'whole_record','Whole records','#2d6aaf'),(width/2,'sentence_neighbors','Sentence neighbors','#39815c')]:
        cells=[find(dev,condition=c,ranker='entity_rrf',packer=packer,budget=8192) for c in conditions];table.extend(cells)
        axs[0].bar(x+off,[c['span_bundle']*100 for c in cells],width,color=color,label=name)
        axs[1].bar(x+off,[c['bytes_used']/1024 for c in cells],width,color=color)
    tidy(axs[0],'Complete source-span alternatives (%)');axs[0].legend(fontsize=9,loc='upper right')
    axs[1].set_ylabel('Mean used UTF-8 bytes (KiB)');axs[1].set_ylim(0,8.5);axs[1].axhline(8,color='#707984',linestyle='--',linewidth=.8);axs[1].grid(axis='y',color='#e1e5e9');axs[1].set_axisbelow(True)
    axs[1].set_xticks(x,[CNAMES[c] for c in conditions])
    finish(fig,'07-dev-placement-bytes','Development: padding placement, span exposure and bytes',
           'Fixed entity-RRF illustration at 8 KiB; 72 development queries / four groups; observed byte cells = 72 per bar.\nEach padded body adds 4,096 ASCII noise bytes + two newlines. Body length/normalization/feasibility also change; no isolated causal placement claim.',table,registry)
    # 8: Nested growth preserves prior observations but can reduce recovery.
    fig,axs=plt.subplots(1,3,figsize=(10.7,4.9),sharey=True);table=[]
    for ax,method,name in zip(axs,DEV,DNAMES):
        values_by_packer={}
        for packer,color,label,marker in [('whole_record','#2d6aaf','Greedy whole','o'),('nested_whole','#d56c35','Nested whole','s')]:
            cells=[find(dev,condition='baseline',ranker=method,packer=packer,budget=b) for b in (4096,8192,16384)];table.extend(cells)
            values_by_packer[packer]=[c['span_bundle_count'] for c in cells]
            ax.plot([4,8,16],values_by_packer[packer],marker=marker,color=color,label=label)
        for n,b in enumerate((4,8,16)):
            greedy,nested=values_by_packer['whole_record'][n],values_by_packer['nested_whole'][n]
            if greedy==nested:
                ax.annotate(str(greedy),(b,greedy),xytext=(0,8),textcoords='offset points',ha='center',fontsize=8,color='#30383f')
            else:
                for value,color in ((greedy,'#2d6aaf'),(nested,'#d56c35')):
                    ax.annotate(str(value),(b,value),xytext=(0,8 if value==max(greedy,nested) else -17),textcoords='offset points',ha='center',fontsize=8,color=color)
        loss=next(t['span_success_losses'] for t in dev['budget_transitions'] if t['condition']=='baseline' and t['ranker']==method and t['packer']=='whole_record' and t['from_budget']==4096)
        ax.set_title(name+f'\nGreedy 4→8 KiB losses: {loss}');ax.set_xticks([4,8,16]);ax.set_xlabel('Budget (KiB)');ax.set_ylim(0,78);ax.grid(axis='y',color='#e1e5e9');ax.set_axisbelow(True)
    axs[0].set_ylabel('Complete original-span bundles (out of 72)');axs[0].legend(fontsize=8,loc='lower right')
    finish(fig,'08-dev-nested-growth','Development: nested-budget retention and retrieval tradeoff',
           'Baseline only; 72 matched development queries / four groups. All transition pairs assessed, zero faults.\nNested packets retain byte prefixes/source intervals; early irrelevant originals can consume later budget. No optimality or main-policy replacement.',table,registry)
    # 9: Identifier probes disclose the corpus/statistics confound and empty subgroup.
    conditions=('opaque_ids','near_alias_cues','near_identifier_records');fig,ax=plt.subplots(figsize=(8.6,4.8));x=np.arange(3);width=.24;table=[]
    for n,condition in enumerate(conditions):
        selected=[next(c for c in dev['paired_vs_baseline'] if c['condition']==condition and c['ranker']==m and c['packer']=='whole_record' and c['budget']==8192) for m in DEV]
        table.extend(selected);values=[c['gains']-c['regressions'] for c in selected]
        bars=ax.bar(x+(n-1)*width,values,width,color=COLORS[n],label=CNAMES[condition])
        for bar,value in zip(bars,values):ax.text(bar.get_x()+bar.get_width()/2,value+(.15 if value>=0 else -.2),f'{value:+}',ha='center',va='bottom' if value>=0 else 'top',fontsize=9)
    ax.set_xticks(x,DNAMES);ax.set_ylim(-6,5);ax.set_ylabel('Net span-recovery change (queries out of 72)');ax.axhline(0,color='#707984',linewidth=.8);ax.grid(axis='y',color='#e1e5e9');ax.set_axisbelow(True)
    handles,labels=ax.get_legend_handles_labels();fig.legend(handles,labels,fontsize=9,loc='upper center',bbox_to_anchor=(.57,.88),ncol=3,frameon=False)
    finish(fig,'09-dev-identifier-cues','Development: identifier cue perturbations at 8 KiB',
           'Whole-source packets. Opaque IDs: 99 body references, no literal record-ID queries (0/72); that query subgroup is unavailable.\nNear cues: 25 observable identifiers / 30 queries, deliberately query-aware. Marker records double corpus size (276→552), confounding IDF/length effects.',table,registry)
    return registry


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--private-cell-receipts',type=Path)
    args=parser.parse_args();OUT.mkdir(exist_ok=True);style()
    ep,dp=HERE/'external-results.json',HERE/'development-results.json'
    external,dev=json.loads(ep.read_bytes()),json.loads(dp.read_bytes())
    assert external['executed_packets']==2160 and dev['executed_packets']==19440
    assert dev['failed_cells']==0, 'Failure-bearing plots require an explicit visual amendment'
    extra=stream_paired(args.private_cell_receipts) if args.private_cell_receipts else None
    if extra: assert extra['source_receipt_sha256']==dev['completion']['rows_sha256']
    figures=render(external,dev)
    registry={'schema_version':1,'scope':'Completed external BEAM adaptation and development-only diagnostics; no main outcomes.',
              'renderer_sha256':fdigest(Path(__file__)),'source_tables':[
                  {'file':'external-results.json','sha256':fdigest(ep),'bytes':ep.stat().st_size},
                  {'file':'development-results.json','sha256':fdigest(dp),'bytes':dp.stat().st_size}],
              'matplotlib_version':matplotlib.__version__,'numpy_version':np.__version__,
              'svg_date_metadata':False,'host_paths_private_corpus_or_question_text_in_figures':False,
              'confidence_intervals_drawn':False,'extra_preplanned_safe_aggregates':extra,'figures':figures}
    path=HERE/'supplement-figure-registry.json';path.write_text(json.dumps(registry,ensure_ascii=False,sort_keys=True,indent=2,allow_nan=False)+'\n',encoding='utf-8',newline='\n')
    print(json.dumps({'figures':len(figures),'png_svg_pairs':len(figures),'registry_sha256':fdigest(path)},sort_keys=True))
