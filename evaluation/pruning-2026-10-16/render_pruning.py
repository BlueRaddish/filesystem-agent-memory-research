"""Six descriptive scientific figures from retained aggregate tables."""
import argparse
import hashlib
import json
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

POLICIES = ('all', 'ttl8', 'lru96', 'lfu96', 'latest', 'latest_dependencies', 'random96')
LABELS = ('All originals', 'TTL 8', 'LRU 96', 'LFU 96', 'Latest', 'Latest + refs', 'Random 96')
ARCHIVES = ('off', 'unresolved_only', 'scheduled_cold')
ARCHIVE_LABELS = ('Archive unavailable', 'Cold on unresolved', 'Scheduled cold')
METHODS = ('global', 'project', 'linked')
COLORS = ('#222222', '#bd4f30', '#197b91', '#7251a3', '#a17b12', '#24733c', '#b34c87')


def render(table_path, output):
    assert not output.exists(), 'output directory exists'
    output.mkdir()
    table = json.loads(table_path.read_text(encoding='utf-8'))
    arm = {r['arm']: r for r in table['arm']}
    ep = {(r['arm'], r['epoch']): r for r in table['epoch']}
    store = {(r['arm'], r['epoch']): r for r in table['epoch_storage']}
    scenario = {(r['arm'], r['scenario']): r for r in table['scenario']}
    epochs = list(range(4, 33, 4))
    plt.rcParams.update({'font.size': 10, 'axes.spines.top': False, 'axes.spines.right': False,
                         'savefig.facecolor': 'white', 'svg.hashsalt': 'longitudinal-pruning-2026-10-16'})
    manifest = {'tables_sha256': hashlib.sha256(table_path.read_bytes()).hexdigest(), 'figures': []}
    def save(fig, name, caption):
        for ext in ('png', 'svg'):
            path = output / (name + '.' + ext)
            kwargs = {'dpi': 170} if ext == 'png' else {'metadata': {'Date': None}}
            fig.savefig(path, bbox_inches='tight', **kwargs)
            manifest['figures'].append({'path': path.name, 'sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
                                        'caption': caption})
        plt.close(fig)

    fig, axes = plt.subplots(1, 3, figsize=(15, 4.5), sharey=True)
    for ax, archive, label in zip(axes, ARCHIVES, ARCHIVE_LABELS):
        for policy, policy_label, color in zip(POLICIES, LABELS, COLORS):
            values = [ep[f'{policy}|{archive}|global', e]['support_complete'] / 128 * 100 for e in epochs]
            ax.plot(epochs, values, '-o', color=color, markersize=3, label=policy_label)
        ax.set(title=label, xlabel='Arrival epoch', ylim=(-3, 103), xticks=epochs)
        ax.grid(alpha=.2)
    axes[0].set_ylabel('Support-complete deterministic tasks (%)')
    axes[-1].legend(loc='upper left', bbox_to_anchor=(1.02, 1), frameon=False)
    fig.suptitle('1. Growing collections: pruning, fallback and evidence loss\nGlobal BM25; 32 worlds × 4 tasks = 128 repeated queries per epoch', y=1.06)
    fig.tight_layout()
    save(fig, '01-longitudinal-success', 'Epoch support-complete success, global retrieval; repeated queries within shared-backbone worlds.')

    fig, ax = plt.subplots(figsize=(12, 5))
    cells = [(a, m) for a in ARCHIVES for m in METHODS]
    values = np.array([[ep[f'{p}|{a}|{m}', 32]['support_complete'] for a, m in cells] for p in POLICIES])
    image = ax.imshow(values, vmin=0, vmax=128, cmap='YlGnBu', aspect='auto')
    for i in range(7):
        for j in range(9):
            ax.text(j, i, f'{int(values[i,j])}/128', ha='center', va='center', fontsize=9,
                    color='white' if values[i,j] > 85 else '#222222')
    ax.set_yticks(range(7), LABELS)
    archive_short = {'off': 'No archive', 'unresolved_only': 'Unresolved', 'scheduled_cold': 'Scheduled'}
    ax.set_xticks(range(9), [f'{archive_short[a]}\n{m}' for a, m in cells])
    ax.set_title('2. Final checkpoint: all 63 cells\nCorrect value plus every required original; 32 worlds × 4 tasks per cell', pad=18)
    fig.colorbar(image, ax=ax, label='Support-complete tasks / 128', shrink=.8)
    fig.tight_layout()
    save(fig, '02-final-factorial', 'Final checkpoint counts for every policy × archive mode × retrieval method.')

    fig, axes = plt.subplots(1, 2, figsize=(13, 5))
    markers = ('o', 's', '^')
    for policy, label, color in zip(POLICIES, LABELS, COLORS):
        for archive, marker in zip(ARCHIVES, markers):
            ident = f'{policy}|{archive}|global'
            storage = store[ident, 32]
            active = storage['active_bytes'] / storage['n'] / 1024
            retained = storage['retained_bytes'] / storage['n'] / 1024
            success = ep[ident, 32]['support_complete'] / 128 * 100
            axes[0].scatter(active, success, color=color, marker=marker, s=55)
            axes[1].scatter(retained, success, color=color, marker=marker, s=55)
    for ax, title in zip(axes, ('Active searchable originals', 'All retained originals, including archive')):
        ax.set(title=title, xlabel='Mean original UTF-8 KiB at epoch 32', ylabel='Support-complete tasks (%)', ylim=(-3, 103))
        ax.grid(alpha=.2)
    handles = [plt.Line2D([], [], marker='o', color=c, linestyle='', label=l) for l, c in zip(LABELS, COLORS)]
    handles += [plt.Line2D([], [], marker=m, color='#555555', linestyle='', label=l) for m, l in zip(markers, ARCHIVE_LABELS)]
    axes[-1].legend(handles=handles, bbox_to_anchor=(1.02, 1), loc='upper left', frameon=False)
    fig.suptitle('3. Active-set reduction and retained-storage reduction are different\nGlobal retrieval; exact byte accounting excludes index and archive metadata', y=1.04)
    fig.tight_layout()
    save(fig, '03-storage-utility', 'Final active versus retained original bytes; archive tiers preserve total originals.')

    families = sorted({r['scenario'] for r in table['scenario']})
    fig, ax = plt.subplots(figsize=(13, 5))
    values = np.array([[scenario[f'{p}|off|global', f]['support_complete'] for f in families] for p in POLICIES])
    image = ax.imshow(values, cmap='YlGnBu', vmin=0, vmax=128, aspect='auto')
    for i in range(7):
        for j in range(8):
            ax.text(j, i, str(int(values[i,j])), ha='center', va='center', color='white' if values[i,j] > 85 else '#222222')
    ax.set_yticks(range(7), LABELS)
    ax.set_xticks(range(8), [f.replace('_', '\n') for f in families])
    ax.set_title('4. Workload-specific failure patterns\nArchive unavailable, global BM25; 128 repeated queries per authored overlay', pad=18)
    fig.colorbar(image, ax=ax, label='Support-complete tasks / 128', shrink=.8)
    fig.tight_layout()
    save(fig, '04-scenario-outcomes', 'Scenario counts; eight overlays share an authored backbone and are not independent mechanisms.')

    fig, axes = plt.subplots(1, 2, figsize=(13, 5), sharey=True)
    max_abs = 1
    matrices = []
    for archive in ARCHIVES[1:]:
        values = np.array([[arm[f'{p}|{archive}|{m}']['support_complete'] - arm[f'{p}|off|{m}']['support_complete']
                            for m in METHODS] for p in POLICIES])
        matrices.append(values)
        max_abs = max(max_abs, int(abs(values).max()))
    for ax, archive, values in zip(axes, ARCHIVES[1:], matrices):
        image = ax.imshow(values, cmap='RdBu', vmin=-max_abs, vmax=max_abs, aspect='auto')
        for i in range(7):
            for j in range(3):
                ax.text(j, i, f'{int(values[i,j]):+d}', ha='center', va='center', color='white' if abs(values[i,j]) > max_abs * .65 else '#222222')
        ax.set_yticks(range(7), LABELS)
        ax.set_xticks(range(3), METHODS)
        ax.set_title(archive.replace('_', ' '))
    fig.suptitle('5. Cold-store fallback can recover or displace evidence\nPaired descriptive difference from archive unavailable; same total 4 calls / 8,192 bytes', y=1.04)
    fig.subplots_adjust(left=.15, right=.82, wspace=.2, bottom=.12, top=.83)
    color_axis = fig.add_axes([.86, .16, .018, .64])
    fig.colorbar(image, cax=color_axis, label='Net additional support-complete tasks / 1,024')
    save(fig, '05-archive-effects', 'Paired archive-mode success differences; scheduled cold also tests confident stale-answer blind spots.')

    fig, axes = plt.subplots(1, 2, figsize=(13, 4.7))
    for policy, label, color in zip(POLICIES, LABELS, COLORS):
        ident = f'{policy}|off|global'
        axes[0].plot(epochs, [ep[ident,e]['candidate_work'] / ep[ident,e]['n'] for e in epochs], '-o', color=color, markersize=3, label=label)
        axes[1].plot(epochs, [store[ident,e]['active_bytes'] / store[ident,e]['n'] / 1024 for e in epochs], '-o', color=color, markersize=3)
    axes[0].set(title='Candidates examined across four calls', ylabel='Mean candidate work per query')
    axes[1].set(title='Searchable original bytes', ylabel='Mean active UTF-8 KiB per world')
    for ax in axes:
        ax.set(xlabel='Arrival epoch', xticks=epochs)
        ax.grid(alpha=.2)
    axes[-1].legend(*axes[0].get_legend_handles_labels(), bbox_to_anchor=(1.02,1), loc='upper left', frameon=False)
    fig.suptitle('6. Growing work and active-source volume\nArchive unavailable, global retrieval; scoped work counters are not wall-clock speed', y=1.05)
    fig.tight_layout()
    save(fig, '06-work-and-growth', 'Candidate examinations and active original bytes over epochs; indexing, sorting and parsing costs excluded.')
    (output / 'manifest.json').write_text(json.dumps(manifest, indent=2, sort_keys=True) + '\n', encoding='utf-8')
    return {'exports': len(manifest['figures']), 'manifest_sha256': hashlib.sha256((output / 'manifest.json').read_bytes()).hexdigest()}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('tables', type=Path)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    print(json.dumps(render(args.tables, args.output), indent=2))
