"""Render the separate fixed reader follow-up; refuses existing figure exports."""
import argparse
import hashlib
import json
from pathlib import Path


def render(results, destination):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    report = json.loads(results.read_bytes())
    assert report['planned_cases'] == 48 and report['counts']['valid'] == 48
    arms = ('all|off|global', 'ttl8|off|global', 'ttl8|scheduled_cold|global',
            'latest_dependencies|off|linked')
    values = [report['by_arm'][arm] for arm in arms]
    assert all(v['planned'] == v['valid'] == 12 and
               v['value_agreement'] + v['abstention'] <= 12 for v in values)
    destination.mkdir(exist_ok=True)
    paths = [destination/('01-reader-packets.' + ext) for ext in ('png', 'svg')]
    manifest = destination/'manifest.json'
    assert not any(p.exists() for p in paths+[manifest]), 'Refusing to overwrite exports'
    figure, axis = plt.subplots(figsize=(11, 6.3))
    x = range(4)
    correct = [v['value_agreement'] for v in values]
    abstain = [v['abstention'] for v in values]
    other = [12-c-a for c,a in zip(correct,abstain)]
    axis.bar(x, correct, color='#247F70', label='Value agrees with full history')
    axis.bar(x, other, bottom=correct, color='#D98B35', label='Other returned value')
    axis.bar(x, abstain, bottom=[c+o for c,o in zip(correct,other)], color='#A8AFB7', label='Abstention')
    axis.scatter(x, [v['gold_support_in_packet'] for v in values], marker='D',
                 facecolor='white', edgecolor='#202020', s=75, zorder=5,
                 label='Complete gold source support in packet')
    for i,c in enumerate(correct):
        axis.text(i, c/2, f'{c}/12', ha='center', va='center', color='white', weight='bold')
    axis.set_xticks(list(x), ['Retain all\nglobal / no archive', 'TTL 8\nglobal / no archive',
                             'TTL 8\nglobal / scheduled cold', 'Latest + refs\nlinked / no archive'])
    axis.set_ylim(0,12.6)
    axis.set_yticks(range(0,13,2))
    axis.set_ylabel('Fixed probe answers / 12 per cell')
    axis.grid(axis='y',alpha=.16)
    axis.set_axisbelow(True)
    axis.spines[['top','right']].set_visible(False)
    figure.suptitle('7. Fresh source-only readers: packet evidence and returned answers\n'
                    '48 answers; twelve fixed probes in four cells; eight shared contexts',fontsize=13)
    figure.legend(loc='lower center',bbox_to_anchor=(.5,.045),ncol=2,frameon=False,fontsize=9)
    figure.text(.5,.012,'Structured assertions and a shared synthetic backbone; descriptive counts, without population inference.',
                ha='center',fontsize=8.5)
    figure.subplots_adjust(top=.82,bottom=.28,left=.09,right=.98)
    figure.savefig(paths[0],dpi=180)
    figure.savefig(paths[1])
    plt.close(figure)
    receipt = {'results_sha256':hashlib.sha256(results.read_bytes()).hexdigest(),
               'renderer_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
               'exports':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}}
    manifest.write_text(json.dumps(receipt,indent=2)+'\n',encoding='utf8',newline='\n')
    print(json.dumps(receipt,indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('results',type=Path)
    parser.add_argument('new_exports',type=Path)
    args = parser.parse_args()
    render(args.results,args.new_exports)
