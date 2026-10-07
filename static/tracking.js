// File: static/tracking.js
// The Tracking page: one band per skill. A tile for each shows this week at a
// glance; the open band shows its target (goals.js) and its last 8 weeks as
// columns, with the same numbers in a table. "Set targets" sets every band's
// weekly target at once.

document.addEventListener('DOMContentLoaded', () => {
    const goals = window.MyVocabGoals;
    const tabs = Array.from(document.querySelectorAll('.band-tab'));
    const tooltip = document.getElementById('viz-tooltip');
    const targetsBtn = document.getElementById('targets-btn');
    const targetsForm = document.getElementById('targets-form');
    const targetsError = document.getElementById('targets-error');
    const targetsSaved = document.getElementById('targets-saved');
    const targetsCancel = document.getElementById('targets-cancel');
    const latest = new Map();  // skill -> the progress last shown

    // --- 1. HELPERS ---

    function el(tag, className, text) {
        const node = document.createElement(tag);
        if (className) node.className = className;
        if (text !== undefined) node.textContent = text;
        return node;
    }

    function plural(n, word) {
        return `${n} ${word}${n === 1 ? '' : 's'}`;
    }

    const WEEKS_SHOWN = 8;

    // A clean top for the scale, at or above the value: 300 stays 300, 360 becomes 400.
    function niceTop(value) {
        const power = 10 ** Math.floor(Math.log10(Math.max(1, value)));
        return [1, 1.5, 2, 2.5, 3, 4, 5, 6, 8, 10].map(step => step * power).find(top => top >= value);
    }

    function addWeeks(iso, n) {
        const date = goals.localDate(iso);
        date.setDate(date.getDate() + 7 * n);
        return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}-${String(date.getDate()).padStart(2, '0')}`;
    }

    // The last 8 weeks oldest first, ending with this one; due is the goal plus
    // carry-over. Weeks from before the goal began are kept as empty slots, so
    // the chart keeps its shape from the first week on.
    function weeksOf(progress) {
        const done = new Map(progress.past_weeks.map(week => [week.week_start, week]));
        const weeks = [];
        for (let n = WEEKS_SHOWN - 1; n > 0; n--) {
            const start = addWeeks(progress.week_start, -n);
            const week = done.get(start);
            weeks.push(week ? { ...week, due: week.target + week.carried, current: false }
                : { week_start: start, empty: true });
        }
        weeks.push({
            week_start: progress.week_start, target: progress.target, carried: progress.carried,
            due: progress.due, points: progress.points, met: progress.points >= progress.due, current: true,
        });
        return weeks;
    }

    function result(week) {
        if (week.current) return week.met ? 'Target met so far' : 'In progress';
        return week.met ? 'Target met' : `${week.due - week.points} short`;
    }

    // --- 2. HOVER / FOCUS READOUT ---
    // Enhances only: every number is also in the table, and each column's
    // aria-label says the same for screen readers.

    function showTip(target, valueText, nameText) {
        tooltip.replaceChildren(el('div', 'tip-value', valueText), el('div', 'tip-name', nameText));
        tooltip.hidden = false;
        const mark = target.getBoundingClientRect();
        const tip = tooltip.getBoundingClientRect();
        const left = Math.min(Math.max(8, mark.left + mark.width / 2 - tip.width / 2), window.innerWidth - tip.width - 8);
        const above = mark.top - tip.height - 8;
        tooltip.style.left = `${left}px`;
        tooltip.style.top = `${above < 8 ? mark.bottom + 8 : above}px`;
    }

    function hideTip() {
        tooltip.hidden = true;
    }

    // --- 3. THE LAST 8 WEEKS ---

    function renderHistory(progress) {
        const box = document.querySelector(`.band-history[data-skill="${progress.skill}"]`);
        const chart = box.querySelector('[data-history="chart"]');
        const table = box.querySelector('[data-history="table"]');
        const note = box.querySelector('[data-history="note"]');
        const weeks = weeksOf(progress);
        const tracked = weeks.filter(week => !week.empty);
        const top = niceTop(Math.max(...tracked.map(week => Math.max(week.due, week.points))));
        const at = value => `${(Math.max(0, value) / top) * 100}%`;

        // Recessive gridlines at clean values, labelled on the left.
        const grid = el('div', 'history-grid');
        grid.setAttribute('aria-hidden', 'true');
        [0, top / 2, top].forEach(value => {
            const line = el('span');
            line.style.bottom = at(value);
            line.dataset.value = value.toLocaleString('en-GB');
            grid.append(line);
        });

        const cols = el('ol', 'history-cols');
        cols.style.setProperty('--weeks', weeks.length);
        weeks.forEach((week, i) => {
            const name = week.current ? `This week, ${goals.weekRange(week.week_start)}` : goals.weekRange(week.week_start);
            const state = week.empty ? 'empty' : week.current ? 'current' : week.met ? 'met' : 'short';
            const col = el('li', `history-col ${state}`);
            col.style.setProperty('--i', i);  // columns grow in one after another
            const plot = el('span', 'col-plot');
            const label = el('span', 'col-label');
            label.setAttribute('aria-hidden', 'true');
            const [day, month] = goals.shortDate(week.week_start).split(' ');
            if (week.empty) {
                // Before tracking began: a dated slot with nothing in it.
                label.append(el('span', '', day), el('span', '', month));
                col.setAttribute('aria-label', `${name}: before tracking began.`);
                col.append(plot, label);
                cols.append(col);
                return;
            }
            col.tabIndex = 0;
            col.style.setProperty('--bar', at(week.points));
            col.style.setProperty('--goal', at(week.due));
            col.setAttribute('aria-label', `${name}: ${week.points} of ${week.due} points. ${result(week)}.`);
            plot.append(el('span', 'col-bar'), el('span', 'col-goal'));
            // Only this week's value rides its column; the rest are in the tooltip and table.
            if (week.current) plot.append(el('span', 'col-value', week.points));

            if (week.current) {
                label.append(el('span', '', 'This'), el('span', '', 'week'));
            } else {
                label.append(el('span', '', day), el('span', '', month));
            }
            col.append(plot, label);

            const value = `${week.points} of ${week.due} points`;
            const detail = `${name} · ${result(week)}`;
            col.addEventListener('pointerenter', () => showTip(col, value, detail));
            col.addEventListener('focus', () => showTip(col, value, detail));
            col.addEventListener('pointerleave', hideTip);
            col.addEventListener('blur', hideTip);
            cols.append(col);
        });
        chart.replaceChildren(grid, cols);

        // The table view, newest first.
        table.replaceChildren(...[...tracked].reverse().map(week => {
            const row = el('tr');
            const goal = week.carried > 0 ? `${week.due} (${week.target} + ${week.carried} carried)` : `${week.due}`;
            row.append(
                el('th', '', week.current ? `This week, ${goals.weekRange(week.week_start)}` : goals.weekRange(week.week_start)),
                el('td', 'num', week.points), el('td', 'num', goal), el('td', '', result(week)),
            );
            row.firstChild.scope = 'row';
            return row;
        }));

        note.textContent = !progress.started
            ? `Not started yet: tracking begins with your first ${progress.skill} points.`
            : progress.weeks_done === 0
            ? 'Your history starts this week. Each week joins the chart when it ends.'
            : `Target met in ${progress.weeks_met} of ${plural(progress.weeks_done, 'finished week')}.`;
    }

    // --- 4. TILES ---

    function renderTile(progress) {
        const tab = tabs.find(t => t.dataset.skill === progress.skill);
        const part = name => tab.querySelector(`[data-tile="${name}"]`);
        const reached = progress.started && progress.remaining === 0;
        const fx = window.MyVocabFx;
        if (fx) fx.countTo(part('points'), progress.points); else part('points').textContent = progress.points;
        part('due').textContent = progress.due;
        part('fill').style.width = `${Math.max(0, Math.min(100, (progress.points / progress.due) * 100))}%`;
        part('status').textContent = !progress.started ? 'Not started yet'
            : reached ? '✓ Target met'
            : `${progress.remaining} to go · ${plural(progress.days_left, 'day')} left`;
        tab.classList.toggle('reached', reached);
    }

    // --- 4a. SET TARGETS (every band at once) ---

    function setTargetsOpen(open) {
        targetsForm.hidden = !open;
        targetsBtn.setAttribute('aria-expanded', String(open));
        targetsError.hidden = true;
        if (!open) return;
        targetsSaved.hidden = true;
        targetsForm.querySelectorAll('input').forEach(input => {
            const progress = latest.get(input.name);
            input.value = progress ? progress.target : '';
            input.removeAttribute('aria-invalid');
        });
        targetsForm.querySelector('input').focus();
    }

    function targetsProblem(message, skill) {
        targetsError.textContent = message;
        targetsError.hidden = false;
        const input = skill && targetsForm.querySelector(`input[name="${skill}"]`);
        if (input) {
            input.setAttribute('aria-invalid', 'true');
            input.focus();
            input.select();
        }
    }

    targetsBtn.addEventListener('click', () => setTargetsOpen(targetsForm.hidden));
    targetsCancel.addEventListener('click', () => { setTargetsOpen(false); targetsBtn.focus(); });
    targetsForm.addEventListener('keydown', (e) => {
        if (e.key === 'Escape') { setTargetsOpen(false); targetsBtn.focus(); }
    });

    targetsForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        targetsForm.querySelectorAll('input').forEach(input => input.removeAttribute('aria-invalid'));
        const targets = Object.fromEntries(
            Array.from(targetsForm.querySelectorAll('input'), input => [input.name, input.value.trim()]));
        const save = targetsForm.querySelector('.targets-save');
        save.disabled = true;
        try {
            const { bands } = await goals.requestJSON('/api/progress/targets',
                { targets, utc_offset: goals.utcOffset() });
            bands.forEach(band => panels.get(band.skill).render(band.progress));
            setTargetsOpen(false);
            targetsSaved.textContent = 'Targets saved. They count from this week on.';
            targetsSaved.hidden = false;
            targetsBtn.focus();
        } catch (error) {
            targetsProblem(error.message, error.data && error.data.skill);
        } finally {
            save.disabled = false;
        }
    });

    // --- 5. BANDS AS TABS ---

    function select(skill, focus) {
        const chosen = tabs.find(t => t.dataset.skill === skill) || tabs[0];
        tabs.forEach(tab => {
            const on = tab === chosen;
            tab.setAttribute('aria-selected', String(on));
            tab.tabIndex = on ? 0 : -1;
            document.getElementById(tab.getAttribute('aria-controls')).hidden = !on;
        });
        if (focus) chosen.focus();
        hideTip();
        try {
            history.replaceState(null, '', `#${chosen.dataset.skill}`);
        } catch (error) { /* the address just keeps its old band */ }
    }

    tabs.forEach((tab, i) => {
        tab.addEventListener('click', () => select(tab.dataset.skill));
        // Arrow keys move between bands, as in any row of tabs.
        tab.addEventListener('keydown', (e) => {
            const next = { ArrowRight: i + 1, ArrowLeft: i - 1, Home: 0, End: tabs.length - 1 }[e.key];
            if (next === undefined) return;
            e.preventDefault();
            select(tabs[(next + tabs.length) % tabs.length].dataset.skill, true);
        });
    });

    // --- 6. LOADING ---

    const panels = new Map();
    document.querySelectorAll('.band-panel .goal-panel').forEach(root => {
        panels.set(root.dataset.skill, goals.panel(root, {
            onRender: progress => { latest.set(progress.skill, progress); renderTile(progress); renderHistory(progress); },
        }));
    });

    async function load() {
        try {
            const { bands } = await goals.requestJSON(`/api/progress/all?utc_offset=${goals.utcOffset()}`);
            bands.forEach(band => panels.get(band.skill).render(band.progress));
        } catch (error) {
            panels.forEach(panel => panel.showError('Could not load your scores.'));
            tabs.forEach(tab => {
                tab.querySelector('[data-tile="status"]').textContent = 'Could not load';
            });
        }
    }

    // The address names the open band (/tracking#listening), also when it is
    // changed by hand or by the Back button on this page.
    const bandInAddress = () => decodeURIComponent(location.hash.slice(1));
    window.addEventListener('hashchange', () => select(bandInAddress()));
    select(bandInAddress());
    load();
});
