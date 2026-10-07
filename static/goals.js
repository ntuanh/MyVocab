// File: static/goals.js
// Weekly goals: fills in a goal panel (templates/_goal_panel.html) with one
// skill's points this week against its goal, and lets the learner change it.
// Used by the Practice page (Vocab) and the Tracking page (every band).

(function () {
    // Weeks start on the learner's Monday, so the server is told this clock's offset.
    function utcOffset() {
        return -new Date().getTimezoneOffset();
    }

    function localDate(iso) {
        return new Date(`${iso}T12:00:00`);
    }

    // "5 Oct"
    function shortDate(iso) {
        return localDate(iso).toLocaleDateString('en-GB', { day: 'numeric', month: 'short' });
    }

    // "5–11 Oct", or "28 Sep – 4 Oct" across two months.
    function weekRange(mondayIso) {
        const start = localDate(mondayIso);
        const end = new Date(start);
        end.setDate(start.getDate() + 6);
        const day = d => d.getDate();
        const month = d => d.toLocaleDateString('en-GB', { month: 'short' });
        return start.getMonth() === end.getMonth()
            ? `${day(start)}–${day(end)} ${month(end)}`
            : `${day(start)} ${month(start)} – ${day(end)} ${month(end)}`;
    }

    function show(el, visible) {
        el.classList.toggle('hidden', !visible);
    }

    function setText(el, text) {
        el.textContent = text || '';
        show(el, Boolean(text));
    }

    async function requestJSON(url, body) {
        const response = await fetch(url, body === undefined ? {} : {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(body),
        });
        const data = await response.json().catch(() => ({}));
        if (!response.ok) {
            const error = new Error(data.error || `The server answered ${response.status}.`);
            error.data = data;
            throw error;
        }
        return data;
    }

    // Binds one goal panel. onRender(progress) runs after every render, so a
    // page can keep its own pieces (Tracking's band tiles) in step.
    function panel(root, { onRender } = {}) {
        const skill = root.dataset.skill;
        const pastWeeks = Number(root.dataset.pastWeeks) || 0;
        const part = name => root.querySelector(`[data-goal="${name}"]`);
        const el = {
            dates: part('dates'), points: part('points'), due: part('due'), carried: part('carried'),
            bar: part('bar'), barFill: part('bar-fill'), status: part('status'), streak: part('streak'),
            edit: part('edit'), form: part('form'), input: part('input'), week: part('week'),
            past: part('past'), pastList: part('past-list'),
        };
        let now = null;
        let wasReached = null;  // unknown until the first render, so loading a page never celebrates

        function renderWeek(days, due, todayIso) {
            const share = Math.ceil(due / 7);  // an even day's share of the target
            const top = Math.max(share, ...days.map(day => day.points));
            el.week.style.setProperty('--target-at', `${(share / top) * 100}%`);
            el.week.replaceChildren(...days.map(day => {
                const name = localDate(day.date).toLocaleDateString('en-GB', { weekday: 'short' });
                const li = document.createElement('li');
                li.classList.toggle('met', day.points >= share);
                li.classList.toggle('today', day.date === todayIso);
                li.classList.toggle('future', day.date > todayIso);
                li.title = `${name}: ${day.points} points`;
                const track = document.createElement('span');
                track.className = 'bar-track';
                const bar = document.createElement('span');
                bar.className = 'bar';
                bar.style.height = `${(Math.max(0, day.points) / top) * 100}%`;
                track.append(bar);
                const label = document.createElement('span');
                label.textContent = name;
                const points = document.createElement('span');
                points.className = 'points-text';
                points.textContent = `: ${day.points} points`;
                li.append(track, label, points);
                return li;
            }));
        }

        function renderPastWeeks(weeks) {
            if (!el.pastList) return;
            el.pastList.replaceChildren(...weeks.map(week => {
                const due = week.target + week.carried;
                const li = document.createElement('li');
                li.className = week.met ? 'met' : 'missed';
                const dates = document.createElement('span');
                dates.textContent = weekRange(week.week_start);
                const score = document.createElement('span');
                score.className = 'past-score';
                score.textContent = `${week.points} / ${due}`;
                const mark = document.createElement('span');
                mark.className = 'past-mark';
                mark.textContent = week.met ? '✓ met' : `${due - week.points} short`;
                li.append(dates, score, mark);
                return li;
            }));
            show(el.past, weeks.length > 0);
        }

        function render(progress) {
            if (!progress) return;
            now = progress;
            const { points, target, carried, due, remaining, streak } = progress;
            el.dates.textContent = `This week · ${weekRange(progress.week_start)}`;
            const fx = window.MyVocabFx;
            if (fx) fx.countTo(el.points, points); else el.points.textContent = points;
            el.due.textContent = due;
            setText(el.carried, carried > 0 ? `Target ${target} + ${carried} carried over from earlier weeks` : '');
            el.barFill.style.width = `${Math.max(0, Math.min(100, (points / due) * 100))}%`;
            el.bar.setAttribute('aria-valuemax', due);
            el.bar.setAttribute('aria-valuenow', Math.max(0, Math.min(points, due)));

            // A skill nobody has practised yet keeps its target but counts nothing.
            const reached = progress.started && remaining === 0;
            root.classList.toggle('reached', reached);
            const days = progress.days_left === 1 ? 'today, the last day' : `the ${progress.days_left} days left`;
            el.status.textContent = !progress.started
                ? `Not started: tracking begins with your first ${skill} points.`
                : reached
                    ? "This week's target is reached. Well done!"
                    : `${remaining} to go: about ${progress.per_day_needed} a day for ${days}.`;

            const flame = document.createElement('i');
            flame.className = 'fas fa-fire';
            flame.setAttribute('aria-hidden', 'true');
            el.streak.replaceChildren(flame, ` ${streak}-week streak`);
            show(el.streak, streak > 0);

            if (fx && wasReached === false && reached) {
                fx.cannons();
                fx.celebrate('Weekly target reached!',
                    `${skill[0].toUpperCase()}${skill.slice(1)}: ${points} of ${due} points`, 'fa-bullseye');
            }
            wasReached = reached;

            const todayIso = progress.days[7 - progress.days_left].date;
            renderWeek(progress.days, due, todayIso);
            renderPastWeeks(progress.past_weeks);
            if (onRender) onRender(progress);
        }

        async function load() {
            try {
                render(await requestJSON(`/api/progress?skill=${skill}&past_weeks=${pastWeeks}&utc_offset=${utcOffset()}`));
            } catch (error) {
                el.status.textContent = 'Could not load your progress.';
            }
        }

        function setFormOpen(open) {
            show(el.form, open);
            el.edit.setAttribute('aria-expanded', String(open));
            if (open) {
                el.input.value = now ? now.target : '';
                el.input.focus();
                el.input.select();
            }
        }

        el.edit.addEventListener('click', () => setFormOpen(el.form.classList.contains('hidden')));

        el.form.addEventListener('submit', async (e) => {
            e.preventDefault();
            try {
                render(await requestJSON('/api/progress/target',
                    { skill, target: Number(el.input.value), past_weeks: pastWeeks, utc_offset: utcOffset() }));
                setFormOpen(false);
            } catch (error) {
                el.status.textContent = error.message;
            }
        });

        return { skill, render, load, showError: message => { el.status.textContent = message; } };
    }

    window.MyVocabGoals = { utcOffset, localDate, shortDate, weekRange, requestJSON, panel };
})();
