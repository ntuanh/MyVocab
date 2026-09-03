document.addEventListener('DOMContentLoaded', () => {
    const tableBody = document.getElementById('data-table-body');
    const statsBtn = document.getElementById('stats-btn');
    const statsBtnLabel = document.getElementById('stats-btn-label');
    const statsPanel = document.getElementById('stats-panel');
    const statsBar = document.getElementById('stats-bar');
    const meter = document.getElementById('meter');
    const meterFill = document.getElementById('meter-fill');
    const tooltip = document.getElementById('viz-tooltip');

    // priority_score is the exam's weighting: it starts at 5, a correct answer
    // lowers it (floor 1) and a wrong answer raises it. So a word is LEARNED once
    // its score drops below 5, and at 5 or above it is still on the to-do list.
    // Score 5 keeps its own bucket -- folding the untested in with either side
    // would misstate both, and the three buckets have to add back up to the total.
    const NEUTRAL_SCORE = 5;

    // Ordered best-known -> least-known, which is also the fill ramp's dark -> light
    // direction and the left -> right order of the stacked bar.
    const BUCKETS = [
        { key: 'learned',  cls: 'swatch-learned',  name: 'Learned',        detail: 'score 1-4' },
        { key: 'untested', cls: 'swatch-untested', name: 'Not tested yet', detail: 'score 5' },
        { key: 'practice', cls: 'swatch-practice', name: 'Needs practice', detail: 'score 6+' }
    ];

    // Rendered from the same payload that fills the table, so opening the panel
    // costs no extra request.
    let savedWords = [];

    function bucketOf(word) {
        const score = Number(word.priority_score);
        if (!Number.isFinite(score)) return null;
        if (score < NEUTRAL_SCORE) return 'learned';
        if (score > NEUTRAL_SCORE) return 'practice';
        return 'untested';
    }

    function pct(value, total) {
        return total ? Math.round((value / total) * 100) : 0;
    }

    // --- Hover / focus readout -------------------------------------------------
    // Enhances only: every number here is also printed in the tiles and the table,
    // so nothing is reachable by hover alone. Focus shows the same as hover.
    function showTip(target, valueText, nameText) {
        tooltip.replaceChildren();
        const value = document.createElement('div');
        value.className = 'tip-value';
        value.textContent = valueText;
        const name = document.createElement('div');
        name.className = 'tip-name';
        name.textContent = nameText;
        tooltip.append(value, name);
        tooltip.hidden = false;

        const mark = target.getBoundingClientRect();
        const tip = tooltip.getBoundingClientRect();
        // Centre over the mark, then keep it inside the viewport.
        const left = Math.min(
            Math.max(8, mark.left + mark.width / 2 - tip.width / 2),
            window.innerWidth - tip.width - 8
        );
        const above = mark.top - tip.height - 8;
        tooltip.style.left = left + 'px';
        tooltip.style.top = (above < 8 ? mark.bottom + 8 : above) + 'px';
    }

    function hideTip() {
        tooltip.hidden = true;
    }

    function attachTip(el, valueText, nameText) {
        el.addEventListener('pointerenter', () => showTip(el, valueText, nameText));
        el.addEventListener('focus', () => showTip(el, valueText, nameText));
        el.addEventListener('pointerleave', hideTip);
        el.addEventListener('blur', hideTip);
    }

    // --- The progress panel ----------------------------------------------------
    function renderStats() {
        hideTip();

        const counts = { learned: 0, untested: 0, practice: 0 };
        savedWords.forEach(word => {
            const bucket = bucketOf(word);
            if (bucket) counts[bucket] += 1;
        });

        const total = counts.learned + counts.untested + counts.practice;
        const notLearned = counts.untested + counts.practice;

        document.getElementById('stat-total').textContent = total;
        BUCKETS.forEach(b => {
            document.getElementById('stat-' + b.key).textContent = counts[b.key];
        });

        // Meter: learned against everything saved -- one value against a limit.
        const learnedPct = pct(counts.learned, total);
        meterFill.style.width = learnedPct + '%';
        document.getElementById('meter-readout').textContent = total
            ? counts.learned + ' of ' + total + ' · ' + learnedPct + '%'
            : 'No words saved yet';
        document.getElementById('meter-learned-label').textContent =
            counts.learned + ' learned';
        document.getElementById('meter-remaining-label').textContent =
            notLearned + ' not learned yet';
        meter.setAttribute('aria-label', total
            ? 'Learned ' + counts.learned + ' of ' + total + ' saved words, ' +
              learnedPct + ' percent. ' + notLearned + ' not learned yet.'
            : 'No saved words yet.');
        attachTip(meter,
            counts.learned + ' of ' + total + ' learned (' + learnedPct + '%)',
            notLearned + ' still to go');

        // Stacked bar: the same total split three ways.
        const segments = BUCKETS
            .map(b => Object.assign({ value: counts[b.key] }, b))
            .filter(segment => segment.value > 0);

        statsBar.replaceChildren();
        statsBar.hidden = total === 0;
        if (total === 0) {
            statsBar.setAttribute('aria-label', 'No saved words to chart yet.');
            return;
        }

        segments.forEach(segment => {
            const bar = document.createElement('div');
            bar.className = 'stats-bar-segment ' + segment.cls;
            bar.style.flexGrow = String(segment.value / total);
            bar.tabIndex = 0;
            attachTip(bar,
                segment.value + ' of ' + total + ' (' + pct(segment.value, total) + '%)',
                segment.name + ' · ' + segment.detail);
            statsBar.appendChild(bar);
            segment.el = bar;
        });

        // Label only a segment that can hold its number with padding on both sides.
        // Measuring the laid-out width beats guessing at a share threshold: three
        // digits in a narrow segment would be clipped, and a cropped number is
        // worse than none. Either way the value stays in the tiles and the table.
        segments.forEach(segment => {
            const text = String(segment.value);
            if (segment.el.offsetWidth >= text.length * 9 + 16) {
                segment.el.textContent = text;
            }
        });

        statsBar.setAttribute('aria-label', 'Words by how well you know them: ' +
            segments.map(s => s.name + ', ' + s.value + ' of ' + total).join('; '));
    }

    statsBtn.addEventListener('click', () => {
        const willShow = statsPanel.hidden;
        statsPanel.hidden = !willShow;
        statsBtn.setAttribute('aria-expanded', String(willShow));
        statsBtnLabel.textContent = willShow ? 'Hide Progress' : 'Show Progress';
        if (willShow) renderStats();
        else hideTip();
    });

    // Function to fetch and display saved words
    async function loadSavedWords() {
        try {
            const response = await fetch('/api/all_data');
            if (!response.ok) {
                // If unauthorized (password not entered), redirect to home
                if (response.status === 401) {
                    window.location.href = '/';
                }
                throw new Error('Failed to fetch data');
            }
            const words = await response.json();
            savedWords = words;
            if (!statsPanel.hidden) renderStats();

            tableBody.innerHTML = ''; // Clear the "Loading..." message

            if (words.length === 0) {
                tableBody.innerHTML = '<tr><td colspan="5" style="text-align:center;">You have not saved any words yet.</td></tr>';
                return;
            }

            words.forEach(word => {
                const bucket = BUCKETS.find(b => b.key === bucketOf(word));
                // Table-view twin of the chart: the same buckets in words, so the
                // split is readable without colour and without hovering.
                const status = bucket
                    ? '<span class="stat-swatch ' + bucket.cls + '"></span>' + bucket.name
                    : '&mdash;';
                const row = document.createElement('tr');
                row.setAttribute('data-word-id', word.id);
                row.innerHTML = `
                    <td>${word.word}</td>
                    <td>${word.english_definition || 'N/A'}</td>
                    <td>${word.priority_score}</td>
                    <td class="status-cell">${status}</td>
                    <td><button class="delete-btn" data-id="${word.id}">Delete</button></td>
                `;
                tableBody.appendChild(row);
            });
        } catch (error) {
            console.error('Error loading words:', error);
            tableBody.innerHTML = '<tr><td colspan="5" style="text-align:center;">Could not load data. Please try again.</td></tr>';
        }
    }

    // Event listener for delete buttons (using event delegation)
    tableBody.addEventListener('click', async (event) => {
        if (event.target.classList.contains('delete-btn')) {
            const button = event.target;
            const wordId = button.dataset.id;

            const confirmed = confirm('Are you sure you want to delete this word?');

            if (confirmed) {
                try {
                    const response = await fetch(`/api/delete_word/${wordId}`, {
                        method: 'DELETE'
                    });
                    const result = await response.json();

                    if (result.status === 'success') {
                        // Keep the counts honest -- a deleted word must leave the
                        // progress panel too, not just the table.
                        savedWords = savedWords.filter(w => String(w.id) !== String(wordId));
                        if (!statsPanel.hidden) renderStats();

                        // Remove the row from the table smoothly
                        const rowToDelete = document.querySelector(`tr[data-word-id='${wordId}']`);
                        if (rowToDelete) {
                            rowToDelete.style.opacity = '0';
                            setTimeout(() => rowToDelete.remove(), 300);
                        }
                    } else {
                        alert('Failed to delete the word.');
                    }
                } catch (error) {
                    console.error('Error deleting word:', error);
                    alert('An error occurred while deleting the word.');
                }
            }
        }
    });

    // Initial load of data when the page opens
    loadSavedWords();
});
